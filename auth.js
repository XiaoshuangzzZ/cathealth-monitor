/**
 * API 認證模塊 - 處理後端 API 調用
 * 注意：登錄/註冊 UI 在 index.html 中處理
 */

/**
 * 根據運行環境選擇後端 API 地址
 * - Capacitor 原生 App：固定使用 Render 生產後端
 * - 瀏覽器本地開發：使用 http://127.0.0.1:10002
 * - 其他線上託管：使用 Render 生產後端
 */
function getApiBaseUrl() {
    if (window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform()) {
        return 'https://cathealth-monitor-fn41.onrender.com';
    }
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://127.0.0.1:10002';
    }
    return 'https://cathealth-monitor-fn41.onrender.com';
}

const AUTH_API_URL = getApiBaseUrl();

// Token 存儲鍵名
const TOKEN_KEY = 'cathealth_token';
const USER_KEY = 'currentUser';  // 與 index.html 保持一致

/**
 * 獲取存儲的 Token
 */
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

/**
 * 設置 Token
 */
function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

/**
 * 清除 Token
 */
function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
}

/**
 * 獲取當前用戶信息
 */
function getCurrentUser() {
    const userStr = localStorage.getItem(USER_KEY);
    return userStr ? JSON.parse(userStr) : null;
}

/**
 * 設置當前用戶
 */
function setCurrentUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/**
 * 發送帶認證的請求
 */
async function authenticatedFetch(url, options = {}) {
    const token = getToken();

    // 如果沒有 token，重定向到登錄頁
    if (!token) {
        window.location.href = 'index.html';
        throw new Error('請先登錄');
    }

    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    };

    // 合併選項
    const finalOptions = {
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };

    const response = await fetch(url, finalOptions);

    // 處理 401 未授權
    if (response.status === 401) {
        clearToken();
        window.location.href = 'index.html';
        throw new Error('登錄已過期，請重新登錄');
    }

    return response;
}

/**
 * ========== 貓咪 API ==========
 */

/**
 * 獲取所有貓咪
 */
async function getCats() {
    const response = await authenticatedFetch(`${AUTH_API_URL}/api/cats`);
    return await response.json();
}

/**
 * 創建貓咪
 */
async function createCat(catData) {
    const response = await authenticatedFetch(`${AUTH_API_URL}/api/cats`, {
        method: 'POST',
        body: JSON.stringify(catData)
    });
    return await response.json();
}

/**
 * 更新貓咪
 */
async function updateCatAPI(catId, catData) {
    const response = await authenticatedFetch(`${AUTH_API_URL}/api/cats/${catId}`, {
        method: 'PUT',
        body: JSON.stringify(catData)
    });
    return await response.json();
}

/**
 * 刪除貓咪
 */
async function deleteCatAPI(catId) {
    const response = await authenticatedFetch(`${AUTH_API_URL}/api/cats/${catId}`, {
        method: 'DELETE'
    });
    return await response.json();
}

/**
 * ========== 健康記錄 API ==========
 */

/**
 * 獲取健康記錄
 */
async function getHealthRecords(catId = null) {
    let url = `${AUTH_API_URL}/api/health-records`;
    if (catId) {
        url += `?cat_id=${catId}`;
    }
    const response = await authenticatedFetch(url);
    return await response.json();
}

/**
 * 創建健康記錄
 */
async function createHealthRecord(recordData) {
    const response = await authenticatedFetch(`${AUTH_API_URL}/api/health-records`, {
        method: 'POST',
        body: JSON.stringify(recordData)
    });
    return await response.json();
}

/**
 * 刪除健康記錄
 */
async function deleteHealthRecord(recordId) {
    const response = await authenticatedFetch(`${AUTH_API_URL}/api/health-records/${recordId}`, {
        method: 'DELETE'
    });
    return await response.json();
}

/**
 * ========== 統計 API ==========
 */

/**
 * 獲取統計數據
 */
async function getStats() {
    const response = await authenticatedFetch(`${AUTH_API_URL}/api/stats`);
    return await response.json();
}

/**
 * 更新用戶信息
 */
async function updateUserInfo(name, email) {
    const response = await authenticatedFetch(`${AUTH_API_URL}/api/auth/update`, {
        method: 'PUT',
        body: JSON.stringify({ name, email })
    });
    return await response.json();
}

/**
 * 獲取用戶信息
 */
async function fetchUserInfo() {
    const response = await authenticatedFetch(`${AUTH_API_URL}/api/auth/me`);
    return await response.json();
}

/**
 * ========== 記住登入信息 ==========
 * 用於登入頁「記住我」功能。
 * 注意：在手機 App WebView 中 localStorage 與 App 綁定，但仍建議謹慎保存密碼。
 */

const REMEMBER_KEY = 'cathealth_remember_login';
const REMEMBER_EMAIL_KEY = 'cathealth_saved_email';
const REMEMBER_PASSWORD_KEY = 'cathealth_saved_password';

// 簡單的 base64 編解碼，避免明文存儲密碼（僅輕度混淆，非加密）
function encodeCredential(value) {
    if (!value) return '';
    try {
        return btoa(unescape(encodeURIComponent(value)));
    } catch (e) {
        return value;
    }
}

function decodeCredential(value) {
    if (!value) return '';
    try {
        return decodeURIComponent(escape(atob(value)));
    } catch (e) {
        return value;
    }
}

/**
 * 保存登入信息
 * @param {string} email - 電郵地址
 * @param {string} password - 密碼
 * @param {boolean} rememberAccount - 是否記住帳號
 * @param {boolean} rememberPassword - 是否記住密碼
 */
function saveLoginCredentials(email, password, rememberAccount, rememberPassword) {
    if (rememberAccount) {
        localStorage.setItem(REMEMBER_KEY, 'true');
        localStorage.setItem(REMEMBER_EMAIL_KEY, encodeCredential(email));
        if (rememberPassword) {
            localStorage.setItem(REMEMBER_PASSWORD_KEY, encodeCredential(password));
        } else {
            localStorage.removeItem(REMEMBER_PASSWORD_KEY);
        }
    } else {
        clearSavedLoginCredentials();
    }
}

/**
 * 讀取已保存的登入信息
 * @returns {{remember: boolean, email: string, password: string}}
 */
function loadSavedLoginCredentials() {
    const remember = localStorage.getItem(REMEMBER_KEY) === 'true';
    const email = remember ? decodeCredential(localStorage.getItem(REMEMBER_EMAIL_KEY) || '') : '';
    const password = remember ? decodeCredential(localStorage.getItem(REMEMBER_PASSWORD_KEY) || '') : '';
    return { remember, email, password };
}

/**
 * 清除已保存的登入信息
 */
function clearSavedLoginCredentials() {
    localStorage.removeItem(REMEMBER_KEY);
    localStorage.removeItem(REMEMBER_EMAIL_KEY);
    localStorage.removeItem(REMEMBER_PASSWORD_KEY);
}

/**
 * 登出：清除 token、用戶信息與記住的登入信息
 */
function logoutUser() {
    clearToken();
    clearSavedLoginCredentials();
    window.location.href = 'index.html';
}
