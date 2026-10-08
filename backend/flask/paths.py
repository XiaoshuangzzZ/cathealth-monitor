"""可寫目錄解析。

本模組的存在源自一個具體的線上事故：原本的程式碼假設 Render 上
`/data` 一定存在且可寫，於是無條件執行 `os.makedirs("/data/models")`。
但 Render 免費方案不支援掛載持久化磁碟，`/data` 從未被建立、容器使用者也
無權在 `/` 下建目錄，於是拋出 PermissionError。該異常被上層的
`except Exception` 吞掉，導致 YOLO 模型從未載入成功，每次分析都靜默退回
隨機的模擬結果——使用者只覺得「結果每次都不一樣」，卻沒有任何錯誤訊息。

教訓：不要對檔案系統路徑做未經驗證的假設。這裡一律以「實際寫入一個探測檔」
來驗證可寫性，而非假設路徑存在或 `os.access` 的結果。
"""

import os
import tempfile

_PROBE_NAME = ".write_probe"


def is_writable_dir(path):
    """實際寫檔以確認目錄可寫。任何 OSError 都視為不可用，永不拋出異常。"""
    if not path:
        return False
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, _PROBE_NAME)
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
        return True
    except OSError:
        return False


def first_writable_dir(candidates):
    """回傳第一個可寫入的目錄；全部失敗則回傳 None。"""
    for path in candidates:
        if is_writable_dir(path):
            return path
    return None


def model_dir():
    """回傳可寫的模型目錄，永不拋出異常；全部失敗時回傳 None。

    順序：
      1. /data/models —— 僅在 Render 上嘗試。免費方案會失敗，但若日後升級
         方案並掛載磁碟，模型快取即可持久化，免去每次冷啟動重下 40MB。
      2. backend/flask/models —— repo 檢出目錄，在 Render 上可寫。
      3. 系統 temp 目錄 —— 最後防線，至少能跑。
    """
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if os.environ.get("RENDER"):
        candidates.append("/data/models")
    candidates.append(os.path.join(backend_dir, "models"))
    candidates.append(os.path.join(tempfile.gettempdir(), "cathealth-models"))
    return first_writable_dir(candidates)
