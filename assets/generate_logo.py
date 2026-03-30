"""AutoLISP管理ツールのロゴを生成するスクリプト。
AutoCAD の A 風に L をあしらったデザイン。
"""

from pathlib import Path
from PIL import Image, ImageDraw

SIZE = 512
OUT_DIR = Path(__file__).parent


def draw_logo(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    s = size / 512  # スケール係数

    # 背景：角丸四角（ダークネイビー）
    draw.rounded_rectangle(
        [int(16 * s), int(16 * s), int(496 * s), int(496 * s)],
        radius=int(64 * s),
        fill=(22, 33, 62),
    )

    # --- メインの L 字形（白〜ライトグレー） ---
    l_shape = [
        (int(148 * s), int(96 * s)),
        (int(216 * s), int(96 * s)),
        (int(216 * s), int(348 * s)),
        (int(364 * s), int(348 * s)),
        (int(364 * s), int(416 * s)),
        (int(148 * s), int(416 * s)),
    ]
    draw.polygon(l_shape, fill=(240, 240, 240))

    # --- 赤アクセント：縦の斜めカット（AutoCAD の A の折り返し風） ---
    accent_vert = [
        (int(216 * s), int(96 * s)),
        (int(280 * s), int(96 * s)),
        (int(280 * s), int(284 * s)),
        (int(216 * s), int(348 * s)),
    ]
    draw.polygon(accent_vert, fill=(200, 30, 40))

    # --- 赤アクセント：底部の水平バー ---
    accent_horiz = [
        (int(280 * s), int(348 * s)),
        (int(364 * s), int(348 * s)),
        (int(364 * s), int(416 * s)),
        (int(216 * s), int(416 * s)),
        (int(216 * s), int(348 * s)),
    ]
    # 少し透過気味の赤
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.polygon(accent_horiz, fill=(200, 30, 40, 180))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # --- 細いライン装飾（CAD グリッド線風） ---
    draw.line(
        [(int(148 * s), int(440 * s)), (int(364 * s), int(440 * s))],
        fill=(230, 57, 70, 128),
        width=max(1, int(3 * s)),
    )
    draw.line(
        [(int(148 * s), int(450 * s)), (int(320 * s), int(450 * s))],
        fill=(230, 57, 70, 76),
        width=max(1, int(2 * s)),
    )

    return img


def main():
    img = draw_logo(SIZE)

    # PNG 保存
    png_path = OUT_DIR / "logo.png"
    img.save(png_path)
    print(f"保存: {png_path}")

    # ICO 保存（複数サイズ）
    ico_path = OUT_DIR / "logo.ico"
    img.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"保存: {ico_path}")


if __name__ == "__main__":
    main()
