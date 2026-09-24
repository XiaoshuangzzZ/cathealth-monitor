import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

# 數據庫路徑：Render 使用 /data，本地使用當前目錄
DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'cathealth.db'))

class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """初始化數據庫表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 用戶表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 貓咪表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                breed TEXT,
                age TEXT,
                weight TEXT,
                gender TEXT,
                photo TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # 健康記錄表（用於存儲分析歷史）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER,
                user_id INTEGER NOT NULL,
                record_type TEXT NOT NULL,  -- 'stool_analysis', 'health_survey', etc.
                result_data TEXT,  -- JSON 格式的結果
                risk_level INTEGER,
                confidence REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cat_id) REFERENCES cats(id) ON DELETE SET NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        conn.close()
        print("[DB] Database initialized")

    # ========== 用戶相關操作 ==========

    def create_user(self, email, password, name):
        """創建新用戶"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            password_hash = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (email, password_hash, name)
                VALUES (?, ?, ?)
            ''', (email, password_hash, name))
            conn.commit()
            user_id = cursor.lastrowid
            return self.get_user_by_id(user_id)
        except sqlite3.IntegrityError:
            return None  # 郵箱已存在
        finally:
            conn.close()

    def get_user_by_email(self, email):
        """通過郵箱獲取用戶"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_id(self, user_id):
        """通過 ID 獲取用戶"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def verify_password(self, user, password):
        """驗證密碼"""
        return check_password_hash(user['password_hash'], password)

    def update_user(self, user_id, name=None, email=None):
        """更新用戶信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if name:
                cursor.execute(
                    'UPDATE users SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (name, user_id)
                )
            if email:
                cursor.execute(
                    'UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (email, user_id)
                )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    # ========== 貓咪相關操作 ==========

    def create_cat(self, user_id, name, breed=None, age=None, weight=None,
                   gender=None, photo=None, notes=None):
        """創建新貓咪"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cats (user_id, name, breed, age, weight, gender, photo, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, breed, age, weight, gender, photo, notes))
        conn.commit()
        cat_id = cursor.lastrowid
        conn.close()
        return self.get_cat_by_id(cat_id)

    def get_cat_by_id(self, cat_id):
        """通過 ID 獲取貓咪"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM cats WHERE id = ?', (cat_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_cats(self, user_id):
        """獲取用戶的所有貓咪"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM cats WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_cat(self, cat_id, user_id, **kwargs):
        """更新貓咪信息（帶用戶驗證）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 先驗證貓咪是否屬於該用戶
        cursor.execute('SELECT user_id FROM cats WHERE id = ?', (cat_id,))
        row = cursor.fetchone()
        if not row or row['user_id'] != user_id:
            conn.close()
            return None  # 無權限或不存在

        # 構建更新語句
        allowed_fields = ['name', 'breed', 'age', 'weight', 'gender', 'photo', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

        if updates:
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [cat_id]
            cursor.execute(
                f"UPDATE cats SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
            conn.commit()

        conn.close()
        return self.get_cat_by_id(cat_id)

    def delete_cat(self, cat_id, user_id):
        """刪除貓咪（帶用戶驗證）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 驗證權限
        cursor.execute('SELECT user_id FROM cats WHERE id = ?', (cat_id,))
        row = cursor.fetchone()
        if not row or row['user_id'] != user_id:
            conn.close()
            return False

        cursor.execute('DELETE FROM cats WHERE id = ?', (cat_id,))
        conn.commit()
        conn.close()
        return True

    # ========== 健康記錄相關操作 ==========

    def create_health_record(self, user_id, cat_id=None, record_type='stool_analysis',
                           result_data=None, risk_level=None, confidence=None, notes=None):
        """創建健康記錄"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO health_records
            (user_id, cat_id, record_type, result_data, risk_level, confidence, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, cat_id, record_type, result_data, risk_level, confidence, notes))
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return self.get_health_record_by_id(record_id)

    def get_health_record_by_id(self, record_id):
        """通過 ID 獲取健康記錄"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM health_records WHERE id = ?', (record_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_health_records(self, user_id, cat_id=None, limit=50):
        """獲取用戶的健康記錄"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if cat_id:
            cursor.execute('''
                SELECT * FROM health_records
                WHERE user_id = ? AND cat_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, cat_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM health_records
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def delete_health_record(self, record_id, user_id):
        """刪除健康記錄"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT user_id FROM health_records WHERE id = ?', (record_id,))
        row = cursor.fetchone()
        if not row or row['user_id'] != user_id:
            conn.close()
            return False

        cursor.execute('DELETE FROM health_records WHERE id = ?', (record_id,))
        conn.commit()
        conn.close()
        return True

    # ========== 統計數據 ==========

    def get_user_stats(self, user_id):
        """獲取用戶統計數據"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 貓咪數量
        cursor.execute('SELECT COUNT(*) as cat_count FROM cats WHERE user_id = ?', (user_id,))
        cat_count = cursor.fetchone()['cat_count']

        # 分析次數
        cursor.execute('''
            SELECT COUNT(*) as analysis_count
            FROM health_records
            WHERE user_id = ? AND record_type = 'stool_analysis'
        ''', (user_id,))
        analysis_count = cursor.fetchone()['analysis_count']

        # 最近的分析記錄
        cursor.execute('''
            SELECT * FROM health_records
            WHERE user_id = ? AND record_type = 'stool_analysis'
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_id,))
        latest_analysis = cursor.fetchone()

        conn.close()

        return {
            'cat_count': cat_count,
            'analysis_count': analysis_count,
            'latest_analysis': dict(latest_analysis) if latest_analysis else None
        }
