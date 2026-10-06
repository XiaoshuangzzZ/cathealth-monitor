#!/usr/bin/env python3
"""
在 Render build 階段先把 YOLO 模型抓下來。

為什麼需要這一步
----------------
`best.onnx` 在 .gitignore 裡（77MB），所以它不在 repo 中；而 Render 免費方案
沒有持久化磁碟，每次部署的容器都是全新的。原本只能等第一次
`/api/ai/analyze` 請求才觸發下載，造成兩個問題：

  1. 部署後第一次分析要多等下載時間。
  2. 如果那次下載失敗（網路、HuggingFace 暫時異常），模型就不存在，
     分析功能直接不能用。

在 build 階段下載，模型會跟著這次部署的容器一起存在，start 之後立即可用。

刻意設計成「失敗不讓 build 失敗」
--------------------------------
若這裡因故抓不到，我們仍希望服務能啟動——`app.py` 的 `download_model()`
還有執行期的按需下載後備路徑。讓 build 失敗只會把整個部署擋掉，反而更糟。
所以失敗時印出明顯的警告並回傳 0，讓問題在日誌裡看得見，但不阻擋部署。

用法（render.yaml 的 buildCommand 會自動呼叫）：
    python download_model.py
"""

import os
import shutil
import sys
import urllib.request
from pathlib import Path

MIN_MODEL_BYTES = 1_000_000
DEFAULT_MODEL_URL = "https://huggingface.co/lingshuang/cathealth-yolov11/resolve/main/best_dynamic.onnx"

# 與 app.py 的 paths.model_dir() 在 Render 上的結果一致
MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_NAME = "best.onnx"


def _is_valid(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size >= MIN_MODEL_BYTES
    except OSError:
        return False


def main() -> int:
    url = os.environ.get("MODEL_URL", DEFAULT_MODEL_URL)
    dest = MODEL_DIR / MODEL_NAME

    print(f"[BUILD-MODEL] target : {dest}")
    print(f"[BUILD-MODEL] source : {url}")

    if _is_valid(dest):
        print(f"[BUILD-MODEL] already present ({dest.stat().st_size} bytes), skipping")
        return 0

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".onnx.part")

    # 清掉先前的殘檔，否則截斷的檔案會讓後續每次載入都失敗
    for stale in (part, dest):
        if stale.exists():
            print(f"[BUILD-MODEL] removing {stale.name}")
            try:
                stale.unlink()
            except OSError as e:
                print(f"[BUILD-MODEL] could not remove {stale.name}: {e}")

    try:
        with urllib.request.urlopen(url, timeout=600) as response, open(part, "wb") as out:
            shutil.copyfileobj(response, out)

        size = part.stat().st_size
        if size < MIN_MODEL_BYTES:
            raise IOError(f"downloaded file is too small ({size} bytes)")

        os.replace(part, dest)  # 原子替換
        print(f"[BUILD-MODEL] success: {size} bytes ({size / 1024 / 1024:.1f} MB)")
        return 0

    except Exception as e:
        print("!" * 66)
        print(f"[BUILD-MODEL] WARNING: download failed: {type(e).__name__}: {e}")
        print("[BUILD-MODEL] WARNING: 容器啟動時不會有模型檔。")
        print("[BUILD-MODEL] WARNING: 第一次分析會嘗試重新下載；若仍失敗，")
        print("[BUILD-MODEL] WARNING: 分析端點會回報『分析服務暫時無法使用』（不再回傳隨機結果）。")
        print("!" * 66)
        try:
            if part.exists():
                part.unlink()
        except OSError:
            pass
        return 0  # 刻意不讓 build 失敗


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
