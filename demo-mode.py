#!/usr/bin/env python3
"""
展示影片模式的切換開關。

    python demo-mode.py demo      # 進入展示模式（固定便秘 + 延遲 10 秒 + 隱藏模擬警告）
    python demo-mode.py real      # 還原成真實行為
    python demo-mode.py status    # 看目前是哪一邊

兩份快照都存在 _demo_backup/ 底下，所以可以來回切換、重複錄影。

    _demo_backup/demo/   <- 展示模式版本
    _demo_backup/real/   <- 真實版本（含 detection.features 的渲染修正）

切換後要生效：
    前端 -> node build-apk.js      （打包新的 APK）
    後端 -> git push               （Render 會自動重新部署）

注意：後端一定要重新部署才會生效。只還原原始碼而不 push，線上的
Render 服務仍會回傳固定的便秘結果。
"""

import hashlib
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
BACKUP = ROOT / "_demo_backup"

# (快照目錄, 專案內路徑)
FILES = [
    ("app.py", ROOT / "backend" / "flask" / "app.py"),
    ("dashboard.html", ROOT / "dashboard.html"),
]


def digest(path: pathlib.Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def apply(mode: str) -> None:
    src_dir = BACKUP / mode
    if not src_dir.is_dir():
        raise SystemExit(f"❌ 找不到快照目錄：{src_dir}")

    for name, dest in FILES:
        src = src_dir / name
        if not src.exists():
            raise SystemExit(f"❌ 快照缺少檔案：{src}")
        shutil.copy2(src, dest)
        if digest(src) != digest(dest):
            raise SystemExit(f"❌ 複製後雜湊不符：{dest}")
        print(f"  {mode:4s} -> {dest.relative_to(ROOT)}")

    label = "展示模式（固定便秘、延遲 10 秒）" if mode == "demo" else "真實行為"
    print(f"\n✅ 已切換為：{label}")
    print("\n接下來：")
    print("  前端  node build-apk.js")
    print("  後端  git push   （Render 自動部署，未 push 則線上仍是舊行為）")


def status() -> None:
    print("目前檔案狀態：")
    for name, dest in FILES:
        cur = digest(dest)
        if cur == digest(BACKUP / "demo" / name):
            state = "展示模式"
        elif cur == digest(BACKUP / "real" / name):
            state = "真實版本"
        else:
            state = "自上次快照後有改動（兩邊都不符）"
        print(f"  {str(dest.relative_to(ROOT)):32s} {state}")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("demo", "real", "status"):
        raise SystemExit(__doc__)

    mode = sys.argv[1]
    if mode == "status":
        status()
        return

    print(f"切換為 {mode} 模式 ...\n")
    apply(mode)

    if mode == "demo" and "--rebuild" in sys.argv:
        subprocess.run(["node", "build-apk.js"], cwd=ROOT, check=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
