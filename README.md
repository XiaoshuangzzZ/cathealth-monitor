# CatHealth Monitor - 貓咪健康監測系統

基於 YOLOv8 的貓咪排泄物智能分析系統，幫助貓主人通過排泄物圖片快速了解貓咪健康狀況。

## 功能特點

- **AI 智能分析**：上傳排泄物圖片，自動分析顏色、質地、形狀與健康風險
- **健康檔案**：為每隻貓咪建立獨立檔案，保存分析歷史
- **醫院地圖**：顯示附近寵物醫院位置（需自行設置騰訊地圖 API Key）
- **PWA 支援**：可安裝為桌面/手機 Web App，並提供離線頁面緩存
- **Android APK**：使用 Capacitor 包裝成原生 Android 應用

## 技術架構

- **前端**：HTML5 + CSS3 + JavaScript（PWA / Capacitor）
- **後端**：Flask（`backend/flask/app.py`）
- **資料庫**：SQLite（`backend/flask/database.py`）
- **AI 模型**：YOLOv8（`backend/flask/models/best.pt`）
- **部署**：Render（`render.yaml` + `main.py`）

## 環境要求

- Python 3.11+
- Node.js 18+（用於 Capacitor / APK 構建）
- Android Studio + JDK 11+（用於 APK 構建）

## 快速開始

### 1. 安裝 Python 依賴

```bash
pip install -r requirements.txt
```

### 2. 設置環境變量

```bash
# Linux / macOS
export SECRET_KEY="your-secret-key-here"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="your-admin-password"

# Windows (CMD)
set SECRET_KEY=your-secret-key-here
set ADMIN_EMAIL=admin@example.com
set ADMIN_PASSWORD=your-admin-password
```

> `SECRET_KEY` 用於 JWT 簽名，**必須設置**，否則後端拒絕啟動。

### 3. 啟動後端

```bash
python main.py
```

後端將運行在 `http://127.0.0.1:10002`。

### 4. 訪問前端

直接打開 `index.html` 或使用任意靜態伺服器：

```bash
python -m http.server 8080
```

然後訪問 `http://localhost:8080/index.html`。

> 本地開發時，前端會自動連接到 `http://127.0.0.1:10002`；在 Capacitor APK 或線上託管時，會自動連接到 Render 後端。

## 資料庫說明

本專案使用 **SQLite**，由 `backend/flask/database.py` 自動管理：

### 資料表

- `users`：用戶帳號（`id, email, password_hash, name, created_at, updated_at`）
- `cats`：貓咪資料（`id, user_id, name, breed, age, weight, gender, photo, notes, created_at, updated_at`）
- `health_records`：健康分析記錄（`id, user_id, cat_id, record_type, result_data, risk_level, confidence, notes, created_at`）

### 資料庫位置

- **本地開發**：`backend/flask/cathealth.db`
- **Render 生產環境**：`/data/cathealth.db`（透過 `render.yaml` 掛載持久化磁碟）

資料表會在後端啟動時自動建立（`CREATE TABLE IF NOT EXISTS`），無需手動執行初始化腳本。

## 清空資料庫

體驗階段若需要清空所有資料：

### 本地開發

```bash
# 直接刪除 SQLite 檔案，下次啟動會自動重建空表
rm backend/flask/cathealth.db
```

### Render 生產環境

登入 Render Shell，執行：

```bash
rm /data/cathealth.db
```

然後重新部署。

## API 接口

| 接口 | 方法 | 說明 |
|---|---|---|
| `/api/health` | GET | 健康檢查 |
| `/api/auth/register` | POST | 用戶註冊 |
| `/api/auth/login` | POST | 用戶登入 |
| `/api/auth/me` | GET | 獲取當前用戶 |
| `/api/auth/update` | PUT | 更新用戶資料 |
| `/api/cats` | GET/POST | 獲取/新增貓咪 |
| `/api/cats/<id>` | GET/PUT/DELETE | 單隻貓咪操作 |
| `/api/health-records` | GET/POST | 獲取/新增健康記錄 |
| `/api/health-records/<id>` | DELETE | 刪除健康記錄 |
| `/api/stats` | GET | 獲取用戶統計 |
| `/api/ai/analyze` | POST | 上傳圖片進行 AI 分析 |

## 構建 Android APK

### 1. 構建 www 目錄

Capacitor 會從 `www/` 目錄讀取前端資源。我們已經提供 `build-www.js` 自動複製最新檔案：

```bash
npm run build:www
```

### 2. 同步到 Android 專案

```bash
npm run sync:android
```

### 3. 構建 APK（Windows）

```bash
npm run build:apk
```

APK 輸出位置：`android/app/build/outputs/apk/debug/app-debug.apk`

### 自動化說明

- **不會自動同步**：修改 `index.html`、`dashboard.html`、`auth.js` 等頂層檔案後，必須重新執行 `npm run build:www` && `npm run sync:android`，APK 才會更新。
- `npm run build:apk` 會依序執行：複製 www → 同步 Android → 編譯 debug APK。
- 第一次構建前，請確認已安裝 Android Studio、JDK 11+ 並設置 `ANDROID_SDK_ROOT`。

## Render 部署

1. 將專案推送到 GitHub。
2. 在 Render 建立新的 Web Service，選擇本倉庫。
3. Render 會讀取 `render.yaml`：
   - Runtime：Python
   - 啟動命令：`python main.py`
   - 掛載 `/data` 持久化磁碟存放 SQLite
4. 在 Render Dashboard 設置環境變量：
   - `SECRET_KEY`：任意隨機字串
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD`：管理員帳號（可選）

## 配置說明

### 騰訊地圖 API Key

應用已內置免費騰訊地圖 API Key，用戶無需手動輸入即可使用醫院地圖功能。

如需更換為自己的 Key，可在瀏覽器控制台執行：

```javascript
localStorage.setItem('tencent_map_key', '你的騰訊地圖 API Key');
```

申請地址：https://lbs.qq.com/dev/console/application/mine

### 後端地址

前端會根據環境自動選擇：

- **Capacitor 原生 App**：`https://cathealth-monitor-fn41.onrender.com`
- **瀏覽器 localhost / 127.0.0.1**：`http://127.0.0.1:10002`
- **其他線上託管**：`https://cathealth-monitor-fn41.onrender.com`

如需更換 Render 域名，請修改 `auth.js` 中的 `getApiBaseUrl()` 函數。

## 注意事項

- 本應用提供的是**初步健康評估**，不能替代專業獸醫診斷。如有嚴重症狀，請及時就醫。
- Render free tier 記憶體有限，YOLO 模型可能無法成功載入，後端會自動降級為備用 AI 分析。
- 請勿將 `SECRET_KEY`、資料庫檔案或簽名密鑰提交到公開倉庫。

## 致謝
鹽津蝦許圈圈
爾多隆小潘潘
丁不咚呱77
成呂控小呂呂
漂漂亮亮可可愛愛溫柔大方刀槍不入的指導老師
感謝所有參與測試與提供建議的朋友。

---

*最後更新：2026-09-15*  
*版本：v1.0.0*
