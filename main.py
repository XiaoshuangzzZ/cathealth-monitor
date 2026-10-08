#!/usr/bin/env python3
import sys
import os

# 切换到后端目录
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', 'flask')
os.chdir(backend_dir)

# 添加路径：backend/flask 優先，避免與頂層 app.py 衝突
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

# 导入并运行 Flask
from app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10002))
    print(f"[MAIN] Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
