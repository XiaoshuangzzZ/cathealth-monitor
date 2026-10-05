#!/usr/bin/env python3
"""
從根目錄的 IMAGE.jpg 產生全站應用圖示。

用法：python generate-icons.py

產生：
  - android/app/src/main/res/mipmap-*/  (ic_launcher / ic_launcher_round / ic_launcher_foreground)
  - images/icons/*.png                  (PWA manifest 用)
  - images/icons/android/*.png
  - images/icons/ios/*.png
  - images/icons/windows11/*.png

需要：pillow, numpy, scipy
"""

import pathlib
import sys

import numpy as np

# Windows 主控台預設為 cp950，避免中文/符號輸出時炸掉
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "IMAGE.jpg"

# 原圖中插畫內容的邊界（去掉外圍白邊）
CONTENT_BBOX = (16, 19, 696, 733)

# 非方形目標（例如 Windows 寬磚、啟動畫面）的背景色，取自 manifest.json
PAD_COLOR = (253, 248, 240)


def load_master() -> Image.Image:
    """載入原圖，裁掉白邊並置中裁成正方形。"""
    im = Image.open(SRC).convert("RGB")
    im = im.crop(CONTENT_BBOX)
    w, h = im.size
    s = min(w, h)
    left, top = (w - s) // 2, (h - s) // 2
    return im.crop((left, top, left + s, top + s))


def cut_out_background(im: Image.Image) -> Image.Image:
    """
    把插畫圓角以外的白底變成透明（連通區域洪水填充，保留原本的圓角形狀）。
    只處理「接到影像邊界」的純白區域，避免誤刪插畫內部的白色內容。
    """
    a = np.asarray(im).astype(np.int16)
    is_white = (a.min(axis=2) >= 240) & ((a.max(axis=2) - a.min(axis=2)) <= 12)

    labels, _ = ndimage.label(is_white)
    border = np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    border_labels = np.unique(border[border > 0])
    outside = np.isin(labels, border_labels)

    ratio = outside.mean()
    if not 0.005 < ratio < 0.25:
        raise SystemExit(
            f"背景去背結果不合理（{ratio:.1%} 的像素被判為背景），請調整門檻值。"
        )
    print(f"   去背：{ratio:.1%} 的像素為透明背景")

    alpha = np.where(outside, 0, 255).astype(np.uint8)
    alpha_img = Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(1.0))

    out = im.convert("RGBA")
    out.putalpha(alpha_img)
    return out


def square_icon(master: Image.Image, size: int) -> Image.Image:
    """圓角透明底的正方形圖示。"""
    return master.resize((size, size), Image.LANCZOS)


def round_icon(master: Image.Image, size: int) -> Image.Image:
    """圓形圖示（4 倍超取樣，邊緣平順）。"""
    ss = 4
    big = master.resize((size * ss, size * ss), Image.LANCZOS)
    mask = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * ss - 1, size * ss - 1), fill=255)
    big.putalpha(Image.composite(big.getchannel("A"), Image.new("L", big.size, 0), mask))
    return big.resize((size, size), Image.LANCZOS)


def foreground_icon(master: Image.Image, size: int) -> Image.Image:
    """自適應圖示前景：插畫縮到中央安全區（約 66%），其餘透明。"""
    inner = max(1, round(size * 0.66))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    art = master.resize((inner, inner), Image.LANCZOS)
    off = (size - inner) // 2
    canvas.paste(art, (off, off), art)
    return canvas


def cover_fit(master: Image.Image, w: int, h: int) -> Image.Image:
    """把方形插畫裁切成任意長寬比（非方形磚使用）。"""
    if abs(w - h) < 2:
        return master.resize((w, h), Image.LANCZOS)
    box = Image.new("RGBA", (w, h), PAD_COLOR + (255,))
    inner = max(1, round(min(w, h) * 0.8))
    art = master.resize((inner, inner), Image.LANCZOS)
    box.paste(art, ((w - inner) // 2, (h - inner) // 2), art)
    return box


def save(im: Image.Image, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "PNG")
    print(f"   {path.relative_to(ROOT)}  ({im.size[0]}x{im.size[1]})")


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"找不到來源圖檔：{SRC}")

    print(f"讀取 {SRC.name} ...")
    master = cut_out_background(load_master())

    # 1. Android launcher icons
    print("\n[1/4] Android mipmap")
    densities = {
        "mdpi": 48,
        "hdpi": 72,
        "xhdpi": 96,
        "xxhdpi": 144,
        "xxxhdpi": 192,
    }
    res = ROOT / "android" / "app" / "src" / "main" / "res"
    for dpi, size in densities.items():
        d = res / f"mipmap-{dpi}"
        save(square_icon(master, size), d / "ic_launcher.png")
        save(round_icon(master, size), d / "ic_launcher_round.png")
        save(foreground_icon(master, size), d / "ic_launcher_foreground.png")

    icons = ROOT / "images" / "icons"

    # 2. PWA / web manifest icons
    print("\n[2/4] PWA icons")
    for size in (72, 96, 128, 144, 152, 192, 384, 512):
        save(square_icon(master, size), icons / f"icon-{size}x{size}.png")

    # 3. Android + iOS 圖示組
    print("\n[3/4] android/ 與 ios/")
    for size in (48, 72, 96, 144, 192, 512):
        save(
            square_icon(master, size),
            icons / "android" / f"android-launchericon-{size}-{size}.png",
        )
    for f in sorted((icons / "ios").glob("*.png")):
        size = int(f.stem)
        # iOS 圖示不可有透明通道，改用白底方形
        bg = Image.new("RGBA", master.size, (255, 255, 255, 255))
        bg.alpha_composite(master)
        save(bg.resize((size, size), Image.LANCZOS).convert("RGB"), f)

    # 4. Windows 11 磚（沿用原本每個檔案的尺寸）
    print("\n[4/4] windows11/")
    for f in sorted((icons / "windows11").glob("*.png")):
        w, h = Image.open(f).size
        save(cover_fit(master, w, h), f)

    print("\n✅ 圖示產生完成")


if __name__ == "__main__":
    main()
