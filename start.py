#!/usr/bin/env python3
import sys
import os

# 设置工作目录
os.chdir(os.path.join(os.path.dirname(__file__), 'backend', 'flask'))

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'flask'))

# 导入并运行 Flask
from app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10002))
    app.run(host='0.0.0.0', port=port, debug=False)
