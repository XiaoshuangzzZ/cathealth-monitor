import os
import sys
import jwt
import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from database import Database
import paths

app = Flask(__name__)
# 允許所有來源（開發階段）
CORS(app, resources={
    r"/api/*": {
        "origins": ["*", "https://xiaoshuang425.github.io", "http://localhost", "http://127.0.0.1"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# 配置
# 安全修复：不允许可预测的默认密钥。未设置 SECRET_KEY 时直接拒绝启动，
# 避免攻击者用已知密钥伪造 JWT。
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise RuntimeError("SECRET_KEY environment variable is required. Refusing to start with a predictable default.")
app.config['TOKEN_EXPIRY'] = 30  # 天

# 初始化數據庫
# 路徑完全由 Database.__init__ 依 DATABASE_URL（Postgres）或 DATABASE_PATH
# （SQLite）決定。原本這裡會設定 DATABASE_PATH 環境變數，但 database.py 在
# 本行之前的 import 就已經求值完畢，該設定毫無效果——這個 bug 讓資料庫被寫進
# 臨時目錄，每次重新部署就清空。
db = Database()

# YOLO狀態
yolo_available = False
yolo_detector = None

# 低於此大小視為下載不完整／檔案損毀
MIN_MODEL_BYTES = 1_000_000

def get_model_path():
    """取得模型儲存路徑。

    以實際可寫性探測決定目錄，不再假設 /data 存在——Render 免費方案不支援
    掛載持久化磁碟，硬編 /data 會拋 PermissionError；該異常被上層的
    except Exception 吞掉後，YOLO 從未載入成功，每次分析都靜默退回隨機的
    模擬結果，使用者只看到「結果每次都不一樣」而沒有任何錯誤訊息。
    """
    model_dir = paths.model_dir()
    if model_dir is None:
        print("[INIT] ERROR: no writable directory found for the model file")
        return None
    return os.path.join(model_dir, "best.onnx")

def _is_valid_model_file(path):
    """模型檔是否存在、大小合理，且真的是 ONNX（而不是被誤命的 PyTorch 檔）。

    只檢查 os.path.exists 不夠：舊版直接 urlretrieve 到最終路徑，下載中斷會
    留下截斷的檔案，而 exists() 為真，導致之後每次載入都失敗且無法自癒。

    大小檢查也不夠：Render 上的 MODEL_URL 曾指向舊的 best.pt，於是 40MB 的
    PyTorch zip 被存成 best.onnx，大小過關但 onnxruntime 載不起來。
    PyTorch 的 .pt 是 zip 容器（開頭 PK\\x03\\x04），ONNX 是 protobuf，不會是。
    """
    try:
        if not path or not os.path.exists(path):
            return False
        if os.path.getsize(path) < MIN_MODEL_BYTES:
            return False
        with open(path, "rb") as f:
            return not f.read(4).startswith(b"PK\x03\x04")
    except OSError:
        return False

def download_model():
    """確保模型檔存在，必要時下載。下載到 .part 後原子改名，不會留下半個檔案。"""
    import shutil
    import urllib.request

    model_url = os.environ.get('MODEL_URL', 'https://huggingface.co/lingshuang/cathealth-yolov11/resolve/main/best_dynamic.onnx')
    model_path = get_model_path()
    if model_path is None:
        print("[DOWNLOAD] ERROR: no writable directory available for the model file")
        return None

    if _is_valid_model_file(model_path):
        print(f"[DOWNLOAD] Model already exists: {model_path} ({os.path.getsize(model_path)} bytes)")
        return model_path

    if os.path.exists(model_path):
        # 清掉舊版留下的損毀檔案，否則會永久卡住
        print(f"[DOWNLOAD] Removing incomplete/corrupt model file: {model_path}")
        try:
            os.remove(model_path)
        except OSError as e:
            print(f"[DOWNLOAD] Could not remove corrupt file: {e}")

    # repo 內若已帶模型就複製過去。注意 *.onnx 在 .gitignore 中，所以這條
    # 分支在 Render 上永遠不成立，雲端一律走下方的下載路徑。
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    local_fallback = os.path.join(backend_dir, "models", "best.onnx")
    if _is_valid_model_file(local_fallback) and os.path.abspath(local_fallback) != os.path.abspath(model_path):
        print(f"[DOWNLOAD] Copying model from {local_fallback} to {model_path}")
        try:
            shutil.copy2(local_fallback, model_path)
            print(f"[DOWNLOAD] Success! File size: {os.path.getsize(model_path)} bytes")
            return model_path
        except OSError as e:
            print(f"[DOWNLOAD] Copy failed: {e}, will try download")

    print(f"[DOWNLOAD] Downloading model from: {model_url}")
    print(f"[DOWNLOAD] Saving to: {model_path}")
    part_path = model_path + ".part"
    try:
        with urllib.request.urlopen(model_url, timeout=300) as response, open(part_path, 'wb') as out:
            shutil.copyfileobj(response, out)
        size = os.path.getsize(part_path)
        if size < MIN_MODEL_BYTES:
            raise IOError(f"downloaded file is too small ({size} bytes)")
        os.replace(part_path, model_path)  # 原子替換
        print(f"[DOWNLOAD] Success! File size: {size} bytes")
        return model_path
    except Exception as e:
        print(f"[DOWNLOAD] Error: {e}")
        try:
            if os.path.exists(part_path):
                os.remove(part_path)
        except OSError:
            pass
        return None

def init_yolo():
    """初始化YOLO模型，回傳 (success, error_message)"""
    global yolo_available, yolo_detector
    if yolo_available:
        return True, None
    try:
        # 清除可能的緩存
        import importlib
        if 'yolo.detector' in sys.modules:
            del sys.modules['yolo.detector']
        if 'yolo' in sys.modules:
            del sys.modules['yolo']

        backend_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, backend_dir)

        from yolo.detector import YOLODetector
        import yolo.detector as detector_module
        print(f"[INIT] Loaded detector from: {detector_module.__file__}")

        # 確認載入的是 ONNX Runtime 版本。先前用 PyTorch 時，推論一次峰值要吃
        # 576MB，在 Render 的 512MB 容器上會被 OOM kill。
        with open(detector_module.__file__, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'onnxruntime' in content:
                print("[INIT] Detector backend: ONNX Runtime")
            else:
                print("[INIT] Detector backend: UNKNOWN (預期是 ONNX Runtime)")

        model_path = get_model_path()
        if model_path is None:
            return False, "No writable directory available for the model file"
        print(f"[INIT] Model path: {model_path}")
        print(f"[INIT] Model exists: {os.path.exists(model_path)}")

        # 如果模型不存在，嘗試下載
        if not os.path.exists(model_path):
            print("[INIT] Model not found, trying to download...")
            model_path = download_model()
            if not model_path:
                return False, "Model download failed"

        if model_path and os.path.exists(model_path):
            file_size = os.path.getsize(model_path)
            print(f"[INIT] Model file size: {file_size} bytes")

            yolo_detector = YOLODetector(model_path)
            yolo_available = yolo_detector.model is not None
            print(f"[INIT] YOLO loaded: {yolo_available}")
            if yolo_available:
                print(f"[INIT] Conf threshold: {yolo_detector.conf_threshold}")
                return True, None
            else:
                return False, "YOLODetector model is None after loading"
        else:
            return False, f"Model file not found at {model_path}"
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"[INIT] Error: {error_msg}")
        traceback.print_exc()
        return False, error_msg
    return False, "Unknown init error"

# ========== 認證裝飾器 ==========

def token_required(f):
    """驗證 JWT Token 的裝飾器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'success': False, 'error': 'Token format invalid'}), 401

        if not token:
            return jsonify({'success': False, 'error': 'Token is missing'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = db.get_user_by_id(data['user_id'])
            if not current_user:
                return jsonify({'success': False, 'error': 'User not found'}), 401
            g.current_user = current_user
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Token is invalid'}), 401

        return f(*args, **kwargs)
    return decorated

# ========== 前端路由 ==========

@app.route('/')
def home():
    return jsonify({
        "service": "CatHealth API",
        "status": "running",
        "version": "1.0",
        "endpoints": ["/api/health", "/api/auth/login", "/api/auth/register", "/api/ai/analyze"]
    })

@app.route('/<path:filename>')
def serve_file(filename):
    if filename in ['index.html', 'dashboard.html', 'manifest.json', 'service-worker.js']:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return send_from_directory(repo_root, filename)
    return jsonify({"error": "Not found"}), 404

# ========== 認證 API ==========

@app.route('/api/auth/register', methods=['POST'])
def register():
    """用戶註冊"""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    name = data.get('name', '').strip()

    if not email or not password or not name:
        return jsonify({'success': False, 'error': 'Email, password and name are required'}), 400

    # 安全修复：密码策略加强（至少 8 位）
    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400

    user = db.create_user(email, password, name)
    if not user:
        return jsonify({'success': False, 'error': 'Email already exists'}), 409

    # 生成 token
    token = jwt.encode({
        'user_id': user['id'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=app.config['TOKEN_EXPIRY'])
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'name': user['name']
        }
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    """用戶登錄"""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    # 安全修复：不记录密码相关信息

    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password are required'}), 400

    user = db.get_user_by_email(email)

    if not user:
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401

    password_valid = db.verify_password(user, password)

    if not password_valid:
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401

    # 生成 token
    token = jwt.encode({
        'user_id': user['id'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=app.config['TOKEN_EXPIRY'])
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'name': user['name']
        }
    })

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user():
    """獲取當前用戶信息"""
    user = g.current_user
    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'name': user['name']
        }
    })

@app.route('/api/auth/update', methods=['PUT'])
@token_required
def update_user():
    """更新用戶信息"""
    data = request.get_json()
    user = g.current_user

    name = data.get('name')
    email = data.get('email')

    success = db.update_user(user['id'], name=name, email=email)
    if not success:
        return jsonify({'success': False, 'error': 'Email already exists'}), 409

    updated_user = db.get_user_by_id(user['id'])
    return jsonify({
        'success': True,
        'user': {
            'id': updated_user['id'],
            'email': updated_user['email'],
            'name': updated_user['name']
        }
    })

# ========== 貓咪管理 API ==========

@app.route('/api/cats', methods=['GET'])
@token_required
def get_cats():
    """獲取用戶的所有貓咪"""
    user = g.current_user
    cats = db.get_user_cats(user['id'])
    return jsonify({
        'success': True,
        'cats': cats
    })

@app.route('/api/cats', methods=['POST'])
@token_required
def create_cat():
    """創建新貓咪"""
    user = g.current_user
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({'success': False, 'error': 'Cat name is required'}), 400

    cat = db.create_cat(
        user_id=user['id'],
        name=data.get('name'),
        breed=data.get('breed'),
        age=data.get('age'),
        weight=data.get('weight'),
        gender=data.get('gender'),
        photo=data.get('photo'),
        notes=data.get('notes')
    )

    return jsonify({
        'success': True,
        'cat': cat
    })

@app.route('/api/cats/<int:cat_id>', methods=['GET'])
@token_required
def get_cat(cat_id):
    """獲取單個貓咪信息"""
    user = g.current_user
    cat = db.get_cat_by_id(cat_id)

    if not cat or cat['user_id'] != user['id']:
        return jsonify({'success': False, 'error': 'Cat not found'}), 404

    return jsonify({
        'success': True,
        'cat': cat
    })

@app.route('/api/cats/<int:cat_id>', methods=['PUT'])
@token_required
def update_cat(cat_id):
    """更新貓咪信息"""
    user = g.current_user
    data = request.get_json()

    cat = db.update_cat(
        cat_id=cat_id,
        user_id=user['id'],
        name=data.get('name'),
        breed=data.get('breed'),
        age=data.get('age'),
        weight=data.get('weight'),
        gender=data.get('gender'),
        photo=data.get('photo'),
        notes=data.get('notes')
    )

    if not cat:
        return jsonify({'success': False, 'error': 'Cat not found or no permission'}), 404

    return jsonify({
        'success': True,
        'cat': cat
    })

@app.route('/api/cats/<int:cat_id>', methods=['DELETE'])
@token_required
def delete_cat(cat_id):
    """刪除貓咪"""
    user = g.current_user
    success = db.delete_cat(cat_id, user['id'])

    if not success:
        return jsonify({'success': False, 'error': 'Cat not found or no permission'}), 404

    return jsonify({
        'success': True,
        'message': 'Cat deleted successfully'
    })

# ========== 工具函数 ==========

def check_cat_ownership(cat_id, user_id):
    """校验猫咪是否属于当前用户，返回 (cat, error_response)"""
    if cat_id is None:
        return None, None
    cat = db.get_cat_by_id(cat_id)
    if not cat or cat['user_id'] != user_id:
        return None, (jsonify({'success': False, 'error': 'Cat not found or no permission'}), 403)
    return cat, None

# ========== 健康記錄 API ==========

@app.route('/api/health-records', methods=['GET'])
@token_required
def get_health_records():
    """獲取健康記錄"""
    user = g.current_user
    cat_id = request.args.get('cat_id', type=int)
    # 安全修复：限制 limit 上限，防止超大数据量响应
    limit = min(request.args.get('limit', 50, type=int) or 50, 100)

    records = db.get_user_health_records(user['id'], cat_id=cat_id, limit=limit)
    return jsonify({
        'success': True,
        'records': records
    })

@app.route('/api/health-records', methods=['POST'])
@token_required
def create_health_record():
    """創建健康記錄"""
    user = g.current_user
    data = request.get_json()

    # 安全修复：校验 cat_id 归属，防止越权关联他人/不存在的猫
    cat_id = data.get('cat_id') if data else None
    _, ownership_error = check_cat_ownership(cat_id, user['id'])
    if ownership_error:
        return ownership_error

    import json
    record = db.create_health_record(
        user_id=user['id'],
        cat_id=cat_id,
        record_type=data.get('record_type', 'stool_analysis'),
        result_data=json.dumps(data.get('result_data')) if data.get('result_data') else None,
        risk_level=data.get('risk_level'),
        confidence=data.get('confidence'),
        notes=data.get('notes')
    )

    return jsonify({
        'success': True,
        'record': record
    })

@app.route('/api/health-records/<int:record_id>', methods=['DELETE'])
@token_required
def delete_health_record(record_id):
    """刪除健康記錄"""
    user = g.current_user
    success = db.delete_health_record(record_id, user['id'])

    if not success:
        return jsonify({'success': False, 'error': 'Record not found or no permission'}), 404

    return jsonify({
        'success': True,
        'message': 'Record deleted successfully'
    })

# ========== 統計 API ==========

@app.route('/api/stats', methods=['GET'])
@token_required
def get_stats():
    """獲取用戶統計數據"""
    user = g.current_user
    stats = db.get_user_stats(user['id'])
    return jsonify({
        'success': True,
        'stats': stats
    })

# ========== 原有 API ==========

def _memory_info():
    """讀取 /proc/meminfo（僅 Linux）。Render 免費方案只有 512MB，載入
    PyTorch + 40MB 模型有 OOM 風險，留下這個數字以便日後判斷是否為記憶體問題。"""
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                key, _, rest = line.partition(':')
                if key in ('MemTotal', 'MemAvailable'):
                    info[key] = rest.strip()
        return info or None
    except OSError:
        return None

@app.route('/api/health')
def health():
    """健康檢查端點"""
    db_ok, db_error = db.ping()
    if db_error:
        # 內部錯誤只寫進伺服器日誌，不對外暴露
        print(f"[HEALTH] database ping failed: {db_error}")
    return jsonify({
        "status": "healthy" if db_ok else "degraded",
        # dashboard.html 讀取此欄位顯示「模型加载: 是/否」，後端原本從未回傳
        "model_loaded": yolo_available,
        "yolo_available": yolo_available,
        "database": "connected" if db_ok else "error",
        "database_dialect": "postgres" if db.is_postgres else "sqlite"
    })

@app.route('/api/yolo-status', methods=['GET'])
def yolo_status():
    """診斷端點：模型與資料庫狀態。

    讓正式環境能直接用瀏覽器確認狀況，不必翻 Render 日誌——這正是先前
    排查困難的原因。
    """
    try:
        model_path = get_model_path()
        try:
            size = os.path.getsize(model_path) if model_path and os.path.exists(model_path) else 0
        except OSError:
            size = 0
        table_counts, counts_error = db.table_counts()
        return jsonify({
            "yolo_available": yolo_available,
            "model_path": model_path,
            "model_exists": _is_valid_model_file(model_path),
            "model_size_bytes": size,
            "model_size_mb": round(size / 1024 / 1024, 2),
            "min_valid_size_bytes": MIN_MODEL_BYTES,
            "database_dialect": "postgres" if db.is_postgres else "sqlite",
            "database_location": db.describe(),   # 不含帳密
            "database_table_counts": table_counts,
            "database_error": counts_error,
            "runs_on_render": bool(os.environ.get('RENDER')),
            "memory": _memory_info(),
            "cwd": os.getcwd(),
            "backend_dir": os.path.dirname(os.path.abspath(__file__))
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        # 只回型別，細節留在日誌
        return jsonify({"error": type(e).__name__}), 500

@app.route('/api/init', methods=['POST'])
def api_init():
    """初始化 YOLO"""
    success, error = init_yolo()
    return jsonify({"success": success, "yolo_available": yolo_available, "error": error})

@app.route('/api/ai/analyze', methods=['POST'])
@token_required
def analyze():
    """分析端點（現在需要登錄）"""
    user = g.current_user
    print(f"\n[API] ====== New Request from User {user['id']} ======")

    try:
        # 獲取數據
        data = request.get_json()
        cat_id = data.get('cat_id') if data else None

        # 安全修复：校验 cat_id 归属，防止越权写入记录
        _, ownership_error = check_cat_ownership(cat_id, user['id'])
        if ownership_error:
            return ownership_error

        # 確保YOLO已加載
        if not yolo_available:
            print("[API] Initializing YOLO...")
            init_success, init_error = init_yolo()
            print(f"[API] init_yolo result: {init_success}, error: {init_error}")

        if not yolo_available:
            # 不再退回隨機模擬。
            #
            # 原本這裡會呼叫 analyze_with_backup_ai()，在模型不可用時隨機挑一個
            # 症狀回傳。對健康類應用這是錯的：使用者拿到的是一個憑空捏造、卻
            # 長得跟真實分析一模一樣的醫療建議（「檢測到便秘，建議…」）。
            # 寧可誠實說分析不了，也不要編一個結果出來。
            #
            # 回 200 + success:false（而非 5xx）是因為前端 App 對非 2xx 只會顯示
            # 「HTTP错误: 503」，讀不到這裡的 error 訊息。改成這樣使用者才會看到
            # 真正的原因。
            print("[API] YOLO unavailable — refusing to fabricate a result")
            return jsonify({
                "success": False,
                "error": "AI 分析服务暂时无法使用，请稍后重试。若持续发生，请联系管理员检查模型状态。",
                "model_error": init_error,
            })

        print(f"[API] Request data type: {type(data)}")

        if not data or 'image' not in data:
            print("[API] No image data")
            return jsonify({"success": False, "error": "No image data"}), 400

        img_data = data['image']

        print(f"[API] Image data length: {len(str(img_data))}")

        # 解碼圖片
        image = yolo_detector.base64_to_image(img_data)
        if image is None:
            print("[API] Decode failed")
            return jsonify({"success": False, "error": "Decode failed"}), 400

        print(f"[API] Decoded image: {image.size}, mode: {image.mode}")

        # 運行檢測
        result = yolo_detector.detect_stool_features(image)
        print(f"[API] Result: {result['detection']['class_name']}")

        # 保存健康記錄
        import json
        db.create_health_record(
            user_id=user['id'],
            cat_id=cat_id,
            record_type='stool_analysis',
            result_data=json.dumps(result),
            risk_level=result['risk_metrics']['risk_level'],
            confidence=result['detection']['confidence'],
            notes=result['health_analysis']['message']
        )

        result["success"] = True
        result["disclaimer"] = "本结果由 AI 模型自动生成，仅供参考，不构成医疗诊断，如有异常请咨询专业兽医"
        return jsonify(result)

    except Exception as e:
        import traceback
        print(f"[API] ERROR: {e}")
        traceback.print_exc()
        # 安全修复：不向客户端暴露内部错误细节
        return jsonify({"success": False, "error": "Internal server error, please try again later"}), 500

if __name__ == '__main__':
    # 不在啟動時預載模型：Render free tier 啟動時間有限，
    # 模型改在第一次 /api/ai/analyze 請求時按需載入
    print("[SERVER] YOLO model will be loaded on first request")
    # 啟動時就把解析結果印出來，讓日誌能直接回答「模型路徑到底在哪」
    print(f"[SERVER] Model path: {get_model_path()}")
    print(f"[SERVER] Database: {db.describe()} ({'postgres' if db.is_postgres else 'sqlite'})")

    memory = _memory_info()
    if memory:
        print(f"[SERVER] Memory: {memory.get('MemTotal')} total, {memory.get('MemAvailable')} available")

    port = int(os.environ.get('PORT', 10002))
    print(f"[SERVER] Starting on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
