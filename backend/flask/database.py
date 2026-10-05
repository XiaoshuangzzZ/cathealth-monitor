import sqlite3
import os
import time
import contextlib
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

# psycopg2 只在真的要連 Postgres 時才需要。以 try/except 包住，讓本機純 SQLite
# 開發者不必安裝它也能跑。
try:
    import psycopg2
    import psycopg2.extras
    _PG_AVAILABLE = True
except ImportError:
    _PG_AVAILABLE = False

# 唯一鍵衝突在兩種方言下要能一致處理（例如重複 email 要回 409 而非 500）。
# psycopg2.errors.UniqueViolation 是 psycopg2.IntegrityError 的子類。
INTEGRITY_ERRORS = (sqlite3.IntegrityError,)
if _PG_AVAILABLE:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg2.IntegrityError)


class Database:
    """資料庫存取層，支援 SQLite（本機開發）與 Postgres（正式環境）。

    方言由 DATABASE_URL 環境變數決定：有值走 Postgres，沒有則走 SQLite。

    重要：方言偵測必須在 __init__ 進行，不能在 module 層求值。原本的程式碼
    在 module 層讀取環境變數，而 app.py 是在 import 之後才設定它，導致設定
    完全無效、資料庫被寫進臨時目錄並在每次重新部署時清空。
    """

    def __init__(self):
        url = (os.environ.get('DATABASE_URL') or '').strip()
        if url.startswith('postgres://'):
            # 部分供應商給的是 postgres://，正規化為 postgresql://
            url = url.replace('postgres://', 'postgresql://', 1)
        self.is_postgres = bool(url)
        self.database_url = url or None
        self._schema_ready = False

        if self.is_postgres and not _PG_AVAILABLE:
            raise RuntimeError(
                "DATABASE_URL is set but psycopg2 is not installed. "
                "Install it with: pip install psycopg2-binary"
            )

        if self.is_postgres:
            self.db_path = None
        else:
            self.db_path = os.environ.get('DATABASE_PATH') or os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 'cathealth.db')
            if os.environ.get('RENDER'):
                # 大聲警告：否則漏設 Dashboard 變數會原封不動重現「資料每次
                # 重新部署就消失」這個問題，而且沒有任何錯誤訊息。
                print("[DB] " + "!" * 60)
                print("[DB] WARNING: RENDER is set but DATABASE_URL is missing.")
                print("[DB] WARNING: falling back to EPHEMERAL SQLite — all data will be lost on restart.")
                print("[DB] WARNING: set DATABASE_URL in the Render dashboard to fix this.")
                print("[DB] " + "!" * 60)

        self.init_database()

    # ========== 方言適配層 ==========

    def _pk(self):
        """主鍵片段。這是 DDL 唯一需要分方言的地方，其餘型別兩邊通用。"""
        return 'SERIAL PRIMARY KEY' if self.is_postgres else 'INTEGER PRIMARY KEY AUTOINCREMENT'

    def _sql(self, query):
        """把 SQLite 的 ? 佔位符轉成 Postgres 的 %s。

        前提：本檔案所有 SQL 字面值中都不含 ? 或 %。目前成立（24 個 ? 全是
        佔位符），但若日後加入 LIKE 查詢，Postgres 需要把 % 寫成 %% 並避開 ?。
        """
        return query.replace('?', '%s') if self.is_postgres else query

    def _to_dict(self, row):
        """把查詢結果轉成 dict，並統一時間欄位的型別。

        SQLite 回傳時間欄位為字串，psycopg2 回傳 datetime 物件。兩者 jsonify
        都不會報錯，但輸出的格式會不同（後者變成 RFC-822 風格），前端日期
        顯示會悄悄壞掉。因此所有讀取路徑都必須經過這裡正規化。
        """
        if row is None:
            return None
        result = dict(row)
        if self.is_postgres:
            for key, value in list(result.items()):
                if isinstance(value, datetime):
                    result[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(value, date):
                    result[key] = value.isoformat()
        return result

    def _insert_get_id(self, cursor, query, params):
        """執行 INSERT 並取得新資料列的 id。

        Postgres 用 RETURNING id（必須在 commit 之前取，否則游標已失效），
        SQLite 用 lastrowid。
        """
        if self.is_postgres:
            cursor.execute(self._sql(query) + ' RETURNING id', params)
            return cursor.fetchone()['id']
        cursor.execute(self._sql(query), params)
        return cursor.lastrowid

    # ========== 連線管理 ==========

    def get_connection(self):
        if self.is_postgres:
            dsn = self.database_url
            extra = []
            if 'sslmode=' not in dsn:
                extra.append('sslmode=require')
            if 'connect_timeout=' not in dsn:
                extra.append('connect_timeout=10')
            if extra:
                dsn += ('&' if '?' in dsn else '?') + '&'.join(extra)

            # 免費方案的 Postgres 會在閒置後暫停，喚醒時首次連線可能失敗或很慢。
            last_error = None
            for attempt in range(3):
                try:
                    return psycopg2.connect(
                        dsn, cursor_factory=psycopg2.extras.RealDictCursor)
                except psycopg2.OperationalError as e:
                    last_error = e
                    if attempt < 2:
                        time.sleep(0.5 * (2 ** attempt))
            raise last_error

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 原本的 DDL 宣告了 ON DELETE CASCADE/SET NULL，但 SQLite 預設不強制
        # 外鍵，導致級聯實際上是失效的。開啟後才會與 Postgres 行為一致。
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    @contextlib.contextmanager
    def _conn(self):
        """連線 context manager：正常結束時 commit，異常時 rollback，一律關閉。

        原本多數方法用裸的 conn.close()、部分方法完全沒有 try/finally，
        一旦查詢拋錯就會洩漏連線。在 SQLite 上只是漏檔案描述元，但在
        Postgres 連線池上會累積成 too many clients，看起來像網路故障。
        """
        if not self._schema_ready:
            self._ensure_schema()
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()

    # ========== 建表 ==========

    def _ddl_statements(self):
        pk = self._pk()
        return [
            f'''
            CREATE TABLE IF NOT EXISTS users (
                id {pk},
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            f'''
            CREATE TABLE IF NOT EXISTS cats (
                id {pk},
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
            ''',
            f'''
            CREATE TABLE IF NOT EXISTS health_records (
                id {pk},
                cat_id INTEGER,
                user_id INTEGER NOT NULL,
                record_type TEXT NOT NULL,
                result_data TEXT,
                risk_level INTEGER,
                confidence REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cat_id) REFERENCES cats(id) ON DELETE SET NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            ''',
        ]

    def _create_tables(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            for ddl in self._ddl_statements():
                cursor.execute(ddl)
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self):
        try:
            self._create_tables()
            self._schema_ready = True
        except Exception as e:
            self._schema_ready = False
            print(f"[DB] WARNING: schema initialization failed: {type(e).__name__}: {e}")

    def init_database(self):
        """建立資料表。

        必須非致命：本方法在 app.py 的 import 期執行，若因 Postgres 冷啟動
        而拋錯，行程會直接結束、Render 判定部署失敗。改為記錄警告並允許
        啟動，之後第一個請求會自動重試。
        """
        self._ensure_schema()
        if self._schema_ready:
            backend = 'Postgres' if self.is_postgres else f'SQLite ({self.db_path})'
            print(f"[DB] Database initialized [{backend}]")
        else:
            print("[DB] WARNING: starting without a verified schema; will retry on first request")

    # ========== 診斷 ==========

    def ping(self):
        """實際確認資料庫可用，回傳 (ok, error_message)。

        原本 /api/health 是把 "connected" 寫死的，無論資料庫是否真的可用
        都回報正常。這裡做真正的查詢。
        """
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                cursor.fetchone()
            return True, None
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def describe(self):
        """回傳資料庫位置描述（不含帳密），供診斷端點顯示。"""
        if not self.is_postgres:
            return self.db_path
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.database_url)
            port = parsed.port or 5432
            return f"{parsed.hostname}:{port}{parsed.path or ''}"
        except Exception:
            return 'unknown'

    def table_counts(self):
        """回傳三張表的筆數，用於確認資料是否真的寫進持久化儲存。"""
        counts = {}
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                for table in ('users', 'cats', 'health_records'):
                    cursor.execute(f'SELECT COUNT(*) as c FROM {table}')
                    counts[table] = int(cursor.fetchone()['c'])
            return counts, None
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"

    # ========== 用戶相關操作 ==========

    def create_user(self, email, password, name):
        """創建新用戶"""
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                password_hash = generate_password_hash(password)
                user_id = self._insert_get_id(cursor, '''
                    INSERT INTO users (email, password_hash, name)
                    VALUES (?, ?, ?)
                ''', (email, password_hash, name))
            return self.get_user_by_id(user_id)
        except INTEGRITY_ERRORS:
            return None  # 郵箱已存在

    def get_user_by_email(self, email):
        """通過郵箱獲取用戶"""
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(self._sql('SELECT * FROM users WHERE email = ?'), (email,))
            return self._to_dict(cursor.fetchone())

    def get_user_by_id(self, user_id):
        """通過 ID 獲取用戶"""
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(self._sql('SELECT * FROM users WHERE id = ?'), (user_id,))
            return self._to_dict(cursor.fetchone())

    def verify_password(self, user, password):
        """驗證密碼"""
        return check_password_hash(user['password_hash'], password)

    def update_user(self, user_id, name=None, email=None):
        """更新用戶信息"""
        try:
            with self._conn() as conn:
                cursor = conn.cursor()
                if name:
                    cursor.execute(
                        self._sql('UPDATE users SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'),
                        (name, user_id)
                    )
                if email:
                    cursor.execute(
                        self._sql('UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'),
                        (email, user_id)
                    )
            return True
        except INTEGRITY_ERRORS:
            return False

    # ========== 貓咪相關操作 ==========

    def create_cat(self, user_id, name, breed=None, age=None, weight=None,
                   gender=None, photo=None, notes=None):
        """創建新貓咪"""
        with self._conn() as conn:
            cursor = conn.cursor()
            cat_id = self._insert_get_id(cursor, '''
                INSERT INTO cats (user_id, name, breed, age, weight, gender, photo, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, name, breed, age, weight, gender, photo, notes))
        return self.get_cat_by_id(cat_id)

    def get_cat_by_id(self, cat_id):
        """通過 ID 獲取貓咪"""
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(self._sql('SELECT * FROM cats WHERE id = ?'), (cat_id,))
            return self._to_dict(cursor.fetchone())

    def get_user_cats(self, user_id):
        """獲取用戶的所有貓咪"""
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(self._sql('''
                SELECT * FROM cats WHERE user_id = ? ORDER BY created_at DESC, id DESC
            '''), (user_id,))
            return [self._to_dict(row) for row in cursor.fetchall()]

    def update_cat(self, cat_id, user_id, **kwargs):
        """更新貓咪信息（帶用戶驗證）"""
        with self._conn() as conn:
            cursor = conn.cursor()

            # 先驗證貓咪是否屬於該用戶
            cursor.execute(self._sql('SELECT user_id FROM cats WHERE id = ?'), (cat_id,))
            row = cursor.fetchone()
            if not row or row['user_id'] != user_id:
                return None  # 無權限或不存在

            # 構建更新語句
            allowed_fields = ['name', 'breed', 'age', 'weight', 'gender', 'photo', 'notes']
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

            if updates:
                set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
                values = list(updates.values()) + [cat_id]
                cursor.execute(
                    self._sql(f"UPDATE cats SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"),
                    values
                )

        return self.get_cat_by_id(cat_id)

    def delete_cat(self, cat_id, user_id):
        """刪除貓咪（帶用戶驗證）"""
        with self._conn() as conn:
            cursor = conn.cursor()

            # 驗證權限
            cursor.execute(self._sql('SELECT user_id FROM cats WHERE id = ?'), (cat_id,))
            row = cursor.fetchone()
            if not row or row['user_id'] != user_id:
                return False

            cursor.execute(self._sql('DELETE FROM cats WHERE id = ?'), (cat_id,))
        return True

    # ========== 健康記錄相關操作 ==========

    def create_health_record(self, user_id, cat_id=None, record_type='stool_analysis',
                           result_data=None, risk_level=None, confidence=None, notes=None):
        """創建健康記錄"""
        with self._conn() as conn:
            cursor = conn.cursor()
            record_id = self._insert_get_id(cursor, '''
                INSERT INTO health_records
                (user_id, cat_id, record_type, result_data, risk_level, confidence, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, cat_id, record_type, result_data, risk_level, confidence, notes))
        return self.get_health_record_by_id(record_id)

    def get_health_record_by_id(self, record_id):
        """通過 ID 獲取健康記錄"""
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(self._sql('SELECT * FROM health_records WHERE id = ?'), (record_id,))
            return self._to_dict(cursor.fetchone())

    def get_user_health_records(self, user_id, cat_id=None, limit=50):
        """獲取用戶的健康記錄"""
        with self._conn() as conn:
            cursor = conn.cursor()

            if cat_id:
                cursor.execute(self._sql('''
                    SELECT * FROM health_records
                    WHERE user_id = ? AND cat_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                '''), (user_id, cat_id, limit))
            else:
                cursor.execute(self._sql('''
                    SELECT * FROM health_records
                    WHERE user_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                '''), (user_id, limit))

            return [self._to_dict(row) for row in cursor.fetchall()]

    def delete_health_record(self, record_id, user_id):
        """刪除健康記錄"""
        with self._conn() as conn:
            cursor = conn.cursor()

            cursor.execute(self._sql('SELECT user_id FROM health_records WHERE id = ?'), (record_id,))
            row = cursor.fetchone()
            if not row or row['user_id'] != user_id:
                return False

            cursor.execute(self._sql('DELETE FROM health_records WHERE id = ?'), (record_id,))
        return True

    # ========== 統計數據 ==========

    def get_user_stats(self, user_id):
        """獲取用戶統計數據"""
        with self._conn() as conn:
            cursor = conn.cursor()

            # 貓咪數量
            cursor.execute(self._sql('SELECT COUNT(*) as cat_count FROM cats WHERE user_id = ?'), (user_id,))
            cat_count = cursor.fetchone()['cat_count']

            # 分析次數
            cursor.execute(self._sql('''
                SELECT COUNT(*) as analysis_count
                FROM health_records
                WHERE user_id = ? AND record_type = 'stool_analysis'
            '''), (user_id,))
            analysis_count = cursor.fetchone()['analysis_count']

            # 最近的分析記錄
            cursor.execute(self._sql('''
                SELECT * FROM health_records
                WHERE user_id = ? AND record_type = 'stool_analysis'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            '''), (user_id,))
            latest_analysis = cursor.fetchone()

        return {
            # 明確轉 int：避免任何方言回傳 Decimal 之類 jsonify 無法序列化的型別
            'cat_count': int(cat_count),
            'analysis_count': int(analysis_count),
            'latest_analysis': self._to_dict(latest_analysis)
        }
