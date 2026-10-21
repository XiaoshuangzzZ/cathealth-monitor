import os
import sys
import json
import jwt
import datetime
import urllib.error
import urllib.request
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
        "endpoints": ["/api/health", "/api/auth/login", "/api/auth/register", "/api/ai/analyze", "/api/ai/chat"]
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


# ========== AI 健康助手 ==========
#
# 原本微信小程序用雲函數呼叫 DeepSeek。搬到 Flask 後改由後端代理，
# 避免把 API Key 暴露在前端；沒有設定 DEEPSEEK_API_KEY 時，改用內建的
# 貓咪健康知識庫回覆，功能不會因為缺少金鑰而整個不能用。

DEEPSEEK_API_URL = os.environ.get(
    "DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"
).strip()
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()

_CHAT_LANGUAGE_NAMES = {
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "en": "English",
    "pt": "Portuguese",
}

_CHAT_SYSTEM_PROMPT = """You are "CatHealth Assistant", a warm, knowledgeable cat health assistant inside the CatHealth Monitor app.

Your scope:
- Cat nutrition, hydration, litter box habits (stool and urine), weight, behaviour, grooming and preventive care.
- Helping users understand the app's AI waste-analysis results and when to see a vet.

How to answer:
- Be friendly, concise and practical. Use plain language and avoid unnecessary jargon.
- Use at most one or two emojis per reply.
- Ask a short follow-up question when important details are missing (cat's age, symptoms, duration, appetite, water intake).
- Never diagnose, prescribe medication or give drug dosages.
- For severe, sudden or persistent symptoms (difficulty breathing, seizures, inability to urinate, blood in urine or stool, repeated vomiting, extreme lethargy), tell the user to seek veterinary care immediately.
- Make clear that your advice does not replace a veterinarian, but do not repeat a long disclaimer in every sentence.
- Do not use markdown headings or tables. Short paragraphs and simple bullet points are fine.
- Reply in {language}. If the user writes in a different language, reply in the user's language.

Title: CatHealth Assistant."""

_LOCAL_CHAT = {
    "zh-CN": {
        "emergency": "这可能是急症：呼吸困难、抽搐、无法排尿、尿血/便血、持续呕吐或精神极度萎靡都需要立即就医，请不要等待或自行用药。",
        "vomit": "偶尔呕吐可能是毛球或吃太快。请记录呕吐次数和内容，并确保有清水。如果反复呕吐、呕吐物带血、精神差、超过24小时不吃东西，请尽快看兽医。",
        "diarrhea": "请先注意补水和记录排便次数。若腹泻超过24–48小时、带血，或幼猫同时呕吐、精神差，请就医。",
        "constipation": "可以先增加饮水和湿粮。若超过2–3天没有排便、频繁蹲猫砂盆或痛苦叫唤，请就医。",
        "water": "猫咪天生不爱喝水。可以多放几个水碗、使用流动饮水机、喂湿粮，并留意每天尿量和排尿次数。",
        "diet": "换粮建议用7–10天逐步过渡；定时定量，避免人类食物，并确保新鲜饮水。若猫咪超过24小时完全不吃东西，请咨询兽医。",
        "weight": "定期称重并观察体态。若短期明显变胖或变瘦，建议让兽医评估。",
        "urine": "如果猫咪频繁蹲猫砂盆却尿不出来、叫唤或尿中带血，尤其是公猫，请立即就医。",
        "prevention": "定期疫苗、驱虫、体检和口腔护理都很重要；具体计划请按兽医建议。",
        "behavior": "突然的行为改变可能与压力、环境或身体不适有关。先排除疾病，再考虑环境丰富化。",
        "analysis": "你可以上传猫咪排泄物照片使用 AI 分析。照片越清晰、光线越充足，结果越可靠；分析结果仅供参考，不能替代兽医诊断。",
        "default": "我是 CatHealth 健康小助手。你可以问我猫咪的饮食、饮水、排泄、体重、行为或 AI 分析结果。请告诉我猫咪的年龄、症状和持续时间，我会给出更有针对性的建议。",
        "disclaimer": "以上是一般健康资讯，不能替代兽医诊断。",
    },
    "zh-TW": {
        "emergency": "這可能是急症：呼吸困難、抽搐、無法排尿、尿血／便血、持續嘔吐或精神極度萎靡都需要立即就醫，請不要等待或自行用藥。",
        "vomit": "偶爾嘔吐可能是毛球或吃太快。請記錄嘔吐次數和內容，並確保有清水。如果反覆嘔吐、嘔吐物帶血、精神差、超過24小時不吃東西，請盡快看獸醫。",
        "diarrhea": "請先注意補水和記錄排便次數。若腹瀉超過24–48小時、帶血，或幼貓同時嘔吐、精神差，請就醫。",
        "constipation": "可以先增加飲水和濕糧。若超過2–3天沒有排便、頻繁蹲貓砂盆或痛苦叫喚，請就醫。",
        "water": "貓咪天生不愛喝水。可以多放幾個水碗、使用流動飲水機、餵濕糧，並留意每天尿量和排尿次數。",
        "diet": "換糧建議用7–10天逐步過渡；定時定量，避免人類食物，並確保新鮮飲水。若貓咪超過24小時完全不吃東西，請諮詢獸醫。",
        "weight": "定期稱重並觀察體態。若短期明顯變胖或變瘦，建議讓獸醫評估。",
        "urine": "如果貓咪頻繁蹲貓砂盆卻尿不出來、叫喚或尿中帶血，尤其是公貓，請立即就醫。",
        "prevention": "定期疫苗、驅蟲、體檢和口腔護理都很重要；具體計劃請按獸醫建議。",
        "behavior": "突然的行為改變可能與壓力、環境或身體不適有關。先排除疾病，再考慮環境豐富化。",
        "analysis": "你可以上傳貓咪排泄物照片使用 AI 分析。照片越清晰、光線越充足，結果越可靠；分析結果僅供參考，不能替代獸醫診斷。",
        "default": "我是 CatHealth 健康小助手。你可以問我貓咪的飲食、飲水、排泄、體重、行為或 AI 分析結果。請告訴我貓咪的年齡、症狀和持續時間，我會給出更有針對性的建議。",
        "disclaimer": "以上是一般健康資訊，不能替代獸醫診斷。",
    },
    "en": {
        "emergency": "This may be an emergency. Difficulty breathing, seizures, inability to urinate, blood in urine or stool, repeated vomiting, or extreme lethargy all need immediate veterinary care. Do not wait or self-medicate.",
        "vomit": "Occasional vomiting can be caused by hairballs or eating too fast. Note how often it happens and what is vomited, and keep fresh water available. See a vet promptly if vomiting repeats, contains blood, is accompanied by lethargy, or your cat has not eaten for 24 hours.",
        "diarrhea": "Keep your cat hydrated and note how often it passes stool. See a vet if diarrhoea lasts more than 24–48 hours, contains blood, or a kitten also vomits or is lethargic.",
        "constipation": "Try increasing water intake and wet food. See a vet if there has been no stool for 2–3 days, your cat keeps straining in the litter box, or seems to be in pain.",
        "water": "Cats are naturally poor drinkers. Use several water bowls, a pet fountain, and wet food, and keep an eye on daily urine output and how often your cat urinates.",
        "diet": "Transition food gradually over 7–10 days, feed measured meals at set times, avoid human food, and always provide fresh water. If your cat has not eaten at all for 24 hours, consult a vet.",
        "weight": "Weigh your cat regularly and check its body condition. Ask a vet to assess any sudden weight gain or loss.",
        "urine": "If your cat frequently visits the litter box but cannot urinate, cries out, or has blood in its urine — especially a male cat — seek veterinary care immediately.",
        "prevention": "Regular vaccination, deworming, check-ups and dental care are important. Follow your vet's recommended schedule.",
        "behavior": "A sudden change in behaviour can be caused by stress, the environment, or illness. Rule out medical causes first, then consider enrichment.",
        "analysis": "You can upload a photo of your cat's waste to the AI analysis feature. Clearer photos in good light give more reliable results. The result is for reference only and cannot replace a vet's diagnosis.",
        "default": "I am the CatHealth Assistant. Ask me about your cat's diet, water intake, litter box, weight, behaviour, or the AI analysis results. Tell me your cat's age, symptoms and how long they have lasted for more specific guidance.",
        "disclaimer": "This is general information and does not replace veterinary advice.",
    },
    "pt": {
        "emergency": "Isto pode ser uma emergência. Dificuldade em respirar, convulsões, incapacidade de urinar, sangue na urina ou nas fezes, vómitos repetidos ou apatia extrema exigem cuidados veterinários imediatos. Não espere nem se automedique.",
        "vomit": "Vómitos ocasionais podem dever-se a bolas de pelo ou a comer demasiado depressa. Registe a frequência e o conteúdo e mantenha água fresca disponível. Consulte um veterinário se os vómitos se repetirem, tiverem sangue, houver apatia ou o gato não comer há 24 horas.",
        "diarrhea": "Mantenha o gato hidratado e registe a frequência das fezes. Consulte um veterinário se a diarreia durar mais de 24–48 horas, tiver sangue, ou se for um gatinho com vómitos ou apatia.",
        "constipation": "Aumente a ingestão de água e a comida húmida. Consulte um veterinário se não houver fezes durante 2–3 dias, se o gato fizer força na areia com frequência ou parecer ter dor.",
        "water": "Os gatos bebem naturalmente pouca água. Use várias tigelas, uma fonte de água e comida húmida, e vigie o volume e a frequência da urina.",
        "diet": "Faça a transição de comida ao longo de 7–10 dias, dê refeições medidas a horas fixas, evite comida humana e garanta água fresca. Se o gato não comer nada durante 24 horas, consulte um veterinário.",
        "weight": "Pese o gato regularmente e avalie a condição corporal. Peça a um veterinário para avaliar aumentos ou perdas de peso súbitos.",
        "urine": "Se o gato vai muitas vezes à areia mas não consegue urinar, mia, ou tem sangue na urina — especialmente um macho — procure ajuda veterinária imediatamente.",
        "prevention": "A vacinação regular, a desparasitação, as consultas e os cuidados dentários são importantes. Siga o plano recomendado pelo veterinário.",
        "behavior": "Uma mudança súbita de comportamento pode dever-se a stress, ao ambiente ou a doença. Primeiro exclua causas médicas e depois considere enriquecimento ambiental.",
        "analysis": "Pode carregar uma foto dos dejetos do gato na análise com IA. Fotos mais nítidas e bem iluminadas dão resultados mais fiáveis. O resultado é apenas indicativo e não substitui o diagnóstico veterinário.",
        "default": "Sou o Assistente CatHealth. Pergunte-me sobre a alimentação, hidratação, areia, peso, comportamento do seu gato ou sobre os resultados da análise com IA. Diga-me a idade, os sintomas e há quanto tempo duram para obter orientações mais específicas.",
        "disclaimer": "Esta é informação geral e não substitui a consulta veterinária.",
    },
}

_EMERGENCY_WORDS = [
    "呼吸困难", "呼吸困難", "抽搐", "无法排尿", "無法排尿", "尿不出来", "尿不出來",
    "尿血", "血尿", "便血", "吐血", "中毒", "昏迷",
    "difficulty breathing", "can't breathe", "cannot breathe", "seizure", "convulsion",
    "inability to urinate", "cannot urinate", "can't urinate", "blood in urine",
    "blood in stool", "poison", "unconscious",
    "dificuldade em respirar", "convuls", "sangue na urina", "sangue nas fezes",
    "veneno", "inconsciente",
]

_CHAT_TOPIC_WORDS = [
    ("urine", ["尿", "urina", "urin"]),
    ("vomit", ["呕吐", "嘔吐", "吐了", "反胃", "吐", "vomit", "throw up", "vomiting", "ómito", "omito", "vómito", "nausea", "enjoo"]),
    ("diarrhea", ["腹泻", "腹瀉", "拉稀", "拉肚子", "软便", "軟便", "diarrh", "diarreia", "diarrhea", "fezes moles"]),
    ("constipation", ["便秘", "没拉", "沒拉", "不拉", "排便", "拉不出", "拉屎", "大便干", "大便硬", "屎", "constipa", "prisão de ventre", "prisao de ventre", "straining", "no stool", "no poop", "litter box", "fezes duras"]),
    ("water", ["喝水", "饮水", "飲水", "喝", "water", "drink", "beber", "bebe", "água", "agua"]),
    ("diet", ["吃", "饮食", "飲食", "食欲", "食慾", "猫粮", "貓糧", "food", "diet", "appetite", "comida", "alimenta", "apetite"]),
    ("weight", ["体重", "體重", "weight", "peso", "肥", "瘦", "fat", "thin", "gordo", "magro"]),
    ("prevention", ["疫苗", "驱虫", "驅蟲", "打针", "打針", "vaccin", "vacina", "vermifug", "check-up", "checkup"]),
    ("behavior", ["行为", "行為", "抓", "咬", "哈气", "躲", "behavior", "behaviour", "scratch", "bite", "hide", "comportamento", "arranha", "morde", "esconde"]),
    ("analysis", ["分析", "照片", "结果", "結果", "analysis", "analyse", "análise", "foto", "report", "relatório", "relatorio"]),
]


def _local_cat_health_reply(text, language):
    """沒有 DeepSeek 金鑰時的貓咪健康知識庫回覆。"""
    lang = language if language in _LOCAL_CHAT else "zh-CN"
    replies = _LOCAL_CHAT[lang]
    lowered = (text or "").lower()

    topic = "default"
    if any(word in lowered for word in _EMERGENCY_WORDS):
        topic = "emergency"
    else:
        for candidate, words in _CHAT_TOPIC_WORDS:
            if any(word in lowered for word in words):
                topic = candidate
                break

    return replies[topic] + "\n\n" + replies["disclaimer"]


def _call_deepseek(messages, timeout=45):
    """呼叫 DeepSeek 的 OpenAI 相容端點。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    payload = {
        "model": DEEPSEEK_MODEL or "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1200,
        "stream": False,
    }
    request_obj = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")[:500]
        print(f"[CHAT] DeepSeek HTTP {error.code}: {detail}")
        raise

    parsed = json.loads(raw)
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError("DeepSeek returned no choices")
    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("DeepSeek returned empty content")
    return content


@app.route('/api/ai/chat', methods=['POST'])
@token_required
def ai_chat():
    """貓咪健康 AI 助手。前端只傳對話與介面語言，系統提示詞留在後端。"""
    data = request.get_json(silent=True) or {}
    messages = data.get('messages')
    language = data.get('language') if data.get('language') in _CHAT_LANGUAGE_NAMES else 'zh-CN'

    if not isinstance(messages, list) or not messages:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    clean_messages = []
    for item in messages[-14:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        content = item.get('content')
        if role not in ('user', 'assistant') or not isinstance(content, str):
            continue
        content = content.strip()
        if content:
            clean_messages.append({'role': role, 'content': content[:4000]})

    if not clean_messages or clean_messages[-1]['role'] != 'user':
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    total_chars = sum(len(message['content']) for message in clean_messages)
    if total_chars > 16000:
        return jsonify({'success': False, 'error': 'Conversation is too long'}), 400

    last_user_message = clean_messages[-1]['content']
    language_name = _CHAT_LANGUAGE_NAMES[language]
    system_prompt = _CHAT_SYSTEM_PROMPT.replace('{language}', language_name)
    prompt_messages = [{'role': 'system', 'content': system_prompt}] + clean_messages

    api_key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if not api_key:
        reply = _local_cat_health_reply(last_user_message, language)
        return jsonify({'success': True, 'data': reply, 'provider': 'local'})

    try:
        reply = _call_deepseek(prompt_messages)
        return jsonify({'success': True, 'data': reply, 'provider': 'deepseek'})
    except Exception as error:
        import traceback
        print(f"[CHAT] DeepSeek call failed: {type(error).__name__}: {error}")
        traceback.print_exc()
        # 上游失敗時仍提供本地健康知識，避免整個助手不能用。
        reply = _local_cat_health_reply(last_user_message, language)
        return jsonify({'success': True, 'data': reply, 'provider': 'local_fallback'})

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
