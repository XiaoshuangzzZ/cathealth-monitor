# WSGI 入口文件 for Render
import sys
import os

# 註：原本這裡會在 RENDER 時設定 DATABASE_PATH=/data/cathealth.db。該設定
# 既無效（database.py 於 import 期就求值完畢）也不正確（免費方案無持久化
# 磁碟）。資料庫路徑現由 Database.__init__ 決定。

# 添加 backend/flask 到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'flask'))

# 導入 Flask 應用
from app import app as application

# Render 使用 'application' 變量
app = application

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10002))
    print(f"[SERVER] Starting on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
