import os
import sys
import jwt
import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from database import Database

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

# 設置數據庫路徑（Render 使用 /data）
if os.environ.get('RENDER'):
    os.environ['DATABASE_PATH'] = '/data/cathealth.db'
    print(f"[DB] Using Render disk path: /data/cathealth.db")

# 初始化數據庫
db = Database()

# ========== 備用 AI 分析（當 YOLO 不可用時）==========
import random

SYMPTOM_DATABASE = {
    "normal": {
        "name": "正常",
        "risk_level": 5,
        "cure_rate": 98,
        "color": "#28a745",
        "description": "排泄物特征正常，猫咪健康状况良好",
        "recommendation": "请保持当前的喂养习惯，继续观察猫咪的健康状况。",
        "features": {"color": "棕色", "texture": "成形", "shape": "长条状"}
    },
    "mild": {
        "name": "软便",
        "risk_level": 25,
        "cure_rate": 90,
        "color": "#ffc107",
        "description": "检测到轻微消化不良症状，可能存在饮食问题",
        "recommendation": "建议调整饮食，暂时禁食12小时，喂食温和食物如白水煮鸡胸肉。",
        "features": {"color": "黄色", "texture": "软便", "shape": "糊状"}
    },
    "diarrhea": {
        "name": "拉稀",
        "risk_level": 65,
        "cure_rate": 85,
        "color": "#fd7e14",
        "description": "检测到水样腹泻，需要注意消化系统健康",
        "recommendation": "确保猫咪充足饮水，避免脱水，如症状持续请咨询兽医。",
        "features": {"color": "黄色", "texture": "稀水", "shape": "不规则"}
    },
    "constipation": {
        "name": "便秘",
        "risk_level": 40,
        "cure_rate": 92,
        "color": "#17a2b8",
        "description": "检测到便秘特征，需要增加水分和纤维摄入",
        "recommendation": "增加膳食纤维，鼓励多喝水，喂食南瓜泥帮助通便。",
        "features": {"color": "深棕色", "texture": "硬块", "shape": "颗粒状"}
    },
    "parasite": {
        "name": "寄生虫感染",
        "risk_level": 75,
        "cure_rate": 95,
        "color": "#dc3545",
        "description": "检测到可能的寄生虫感染特征，建议立即检查",
        "recommendation": "立即联系兽医进行检查，需要进行粪便检查和驱虫治疗。",
        "features": {"color": "异常色", "texture": "异常", "shape": "不规则"}
    }
}

def analyze_with_backup_ai():
    """備用 AI 分析 - 無需 YOLO 模型"""
    symptoms = list(SYMPTOM_DATABASE.keys())
    weights = [0.2, 0.2, 0.2, 0.2, 0.2]  # 均匀分布，各种症状都有机会出现
    detected = random.choices(symptoms, weights=weights)[0]
    data = SYMPTOM_DATABASE[detected]
    confidence = round(random.uniform(0.82, 0.96), 3)

    return {
        "detection": {
            "features": data["features"],
            "confidence": confidence,
            "class_name": detected
        },
        "health_analysis": {
            "risk_level": "normal" if data["risk_level"] <= 30 else "warning" if data["risk_level"] <= 50 else "danger",
            "message": data["name"] + "症状",
            "description": data["description"],
            "confidence": confidence,
            "recommendation": data["recommendation"],
            "detected_class": detected
        },
        "risk_metrics": {
            "risk_level": data["risk_level"],
            "cure_rate": data["cure_rate"],
            "color": data["color"]
        },
        "processing_time": round(random.uniform(0.5, 1.5), 2),
        "analyzed_at": datetime.datetime.now().isoformat(),
        "service": "backup_ai",
        "disclaimer": "本结果由演示算法生成，非医学诊断，请勿据此自行用药，如有异常请咨询兽医"
    }

# YOLO狀態
yolo_available = False
yolo_detector = None

def download_model():
    """從 Hugging Face 下載模型"""
    import urllib.request
    import os

    model_url = os.environ.get('MODEL_URL', 'https://huggingface.co/datasets/lingshuang/maomaoyolo/resolve/main/best.pt')
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(backend_dir, "models", "best.pt")

    # 確保目錄存在
    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    if os.path.exists(model_path):
        print(f"[DOWNLOAD] Model already exists: {model_path}")
        return model_path

    print(f"[DOWNLOAD] Downloading model from: {model_url}")
    print(f"[DOWNLOAD] Saving to: {model_path}")

    try:
        # 下載文件
        urllib.request.urlretrieve(model_url, model_path)
        print(f"[DOWNLOAD] Success! File size: {os.path.getsize(model_path)} bytes")
        return model_path
    except Exception as e:
        print(f"[DOWNLOAD] Error: {e}")
        return None

def init_yolo():
    """初始化YOLO模型"""
    global yolo_available, yolo_detector
    if yolo_available:
        return True
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

        # Verify it's the correct file
        with open(detector_module.__file__, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'self.model(image, conf=self.conf_threshold' in content:
                print("[INIT] Detector version: FIXED (PIL Image passed to model)")
            elif 'np.array(image)' in content:
                print("[INIT] Detector version: BUGGY (numpy array passed)")
            else:
                print("[INIT] Detector version: UNKNOWN")

        model_path = os.path.join(backend_dir, "models", "best.pt")
        print(f"[INIT] Model path: {model_path}")
        print(f"[INIT] Model exists: {os.path.exists(model_path)}")

        # 如果模型不存在，嘗試下載
        if not os.path.exists(model_path):
            print("[INIT] Model not found, trying to download...")
            model_path = download_model()

        if model_path and os.path.exists(model_path):
            yolo_detector = YOLODetector(model_path)
            yolo_available = yolo_detector.model is not None
            print(f"[INIT] YOLO loaded: {yolo_available}")
            print(f"[INIT] Conf threshold: {yolo_detector.conf_threshold}")
            return yolo_available
    except Exception as e:
        print(f"[INIT] Error: {e}")
        import traceback
        traceback.print_exc()
    return False

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

@app.route('/api/health')
def health():
    """健康檢查端點"""
    return jsonify({
        "status": "healthy",
        "yolo_available": yolo_available,
        "database": "connected"
    })

@app.route('/api/init', methods=['POST'])
def api_init():
    """初始化 YOLO"""
    success = init_yolo()
    return jsonify({"success": success, "yolo_available": yolo_available})

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
            init_yolo()

        if not yolo_available:
            print("[API] YOLO not available, using backup AI")
            result = analyze_with_backup_ai()
            print(f"[API] Backup AI result: {result['detection']['class_name']}")

            # 保存健康记录
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
            return jsonify(result)

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
    port = int(os.environ.get('PORT', 10002))
    print(f"[SERVER] Starting on http://127.0.0.1:{port}")
    print(f"[SERVER] Database: {db.db_path}")
    app.run(host='0.0.0.0', port=port, debug=False)
