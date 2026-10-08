#!/usr/bin/env python3
"""
數據庫初始化腳本
運行此腳本來創建和初始化 SQLite 數據庫
"""

import os
import sys

def init_database():
    """初始化數據庫"""
    print("🚀 開始初始化數據庫...")

    # Postgres 模式下 schema 由 Database() 自動建立。這裡必須在刪除檔案之前
    # 就返回，否則在雲端情境下可能誤刪資料；而且本腳本有互動式 input()，
    # 本來就不適合在非互動環境執行。
    if os.environ.get('DATABASE_URL'):
        print("ℹ️  偵測到 DATABASE_URL，使用 Postgres 模式")
        print("ℹ️  schema 由 Database() 自動建立，略過刪檔流程")
        from database import Database
        db = Database()
        print(f"📁 資料庫位置: {db.describe()}")
        counts, error = db.table_counts()
        if error:
            print(f"❌ 無法連線或讀取資料表: {error}")
            return False
        print("\n📊 資料表筆數:")
        for table, count in counts.items():
            print(f"  - {table}: {count}")
        print("\n🎉 數據庫準備就緒！")
        return True

    # 刪除舊數據庫（如果存在）
    db_path = os.path.join(os.path.dirname(__file__), 'cathealth.db')
    if os.path.exists(db_path):
        print(f"⚠️  發現舊數據庫: {db_path}")
        response = input("是否刪除舊數據庫並重新創建? (y/N): ")
        if response.lower() == 'y':
            os.remove(db_path)
            print("✅ 舊數據庫已刪除")
        else:
            print("📝 保留舊數據庫，繼續初始化...")

    # 導入並初始化數據庫
    try:
        from database import Database
        db = Database()
        print(f"✅ 數據庫初始化完成!")
        print(f"📁 數據庫位置: {db.db_path}")

        # 測試數據庫連接
        conn = db.get_connection()
        cursor = conn.cursor()

        # 檢查表是否創建成功
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\n📊 已創建的表:")
        for table in tables:
            print(f"  - {table['name']}")

        conn.close()

        print("\n🎉 數據庫準備就緒！")
        print("\n💡 提示:")
        print("  - 運行 'python app.py' 啟動服務器")
        print("  - API 端點: http://127.0.0.1:10002")
        print("  - 前端頁面: http://127.0.0.1:10002")

        return True

    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    init_database()
