# Render 入口文件
import sys
import os

# 註：原本這裡會在 RENDER 時設定 DATABASE_PATH=/data/cathealth.db，但該路徑
# 在免費方案上不存在也不可寫，而且 database.py 是在 import 期求值環境變數，
# 這個設定實際上毫無作用。資料庫路徑現由 Database.__init__ 依 DATABASE_URL
# 或 DATABASE_PATH 決定。

# 獲取項目根目錄
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, 'backend', 'flask')

# 添加路徑
sys.path.insert(0, root_dir)
sys.path.insert(0, backend_dir)

print(f"[INIT] Root dir: {root_dir}")
print(f"[INIT] Backend dir: {backend_dir}")
print(f"[INIT] Python path: {sys.path}")

# 切換到 backend/flask 目錄（為了數據庫路徑正確）
os.chdir(backend_dir)

# 導入 Flask 應用
print("[INIT] Importing Flask app...")
try:
    from app import app
    print("[INIT] Flask app imported successfully")
except Exception as e:
    print(f"[INIT] Error importing app: {e}")
    import traceback
    traceback.print_exc()
    raise

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10002))
    print(f"[SERVER] Starting on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
