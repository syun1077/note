"""
note.com 自動投稿 - サムネイル自動生成モジュール
================================================
Gemini Imagen API でサムネイル画像を自動生成します。
生成できない場合は Pillow でテキストベースの画像を作成します。
"""

import os
import re
import textwrap
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

THUMBNAIL_DIR = Path("thumbnails")
THUMBNAIL_DIR.mkdir(exist_ok=True)


def _safe_filename(title: str) -> str:
    """タイトルから安全なファイル名を生成"""
    cleaned = re.sub(r"[^\w\s\-]", "", title)
    cleaned = cleaned.strip()[:40].strip()
    return cleaned or "thumbnail"


def generate_thumbnail_imagen(title: str, theme: str) -> Path | None:
    """
    Gemini Imagen API でサムネイル画像を生成する。

    Returns:
        Path: 保存した画像ファイルのパス、失敗時は None
    """
    try:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)

        prompt = (
            f"A clean, modern blog cover image for a Japanese note.com article. "
            f"Theme: {theme}. No text. Flat illustration style. "
            f"Bright and professional color palette. 16:9 aspect ratio."
        )

        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config={"number_of_images": 1, "aspect_ratio": "16:9"},
        )

        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            fname = _safe_filename(title) + ".png"
            out_path = THUMBNAIL_DIR / fname
            out_path.write_bytes(image_bytes)
            print(f"   🖼️  Imagen サムネイル生成完了: {out_path}")
            return out_path

    except Exception as e:
        print(f"   ⚠️  Imagen 生成失敗: {e}")

    return None


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _draw_gradient(img: "Image.Image", color1: tuple, color2: tuple, direction: str = "diagonal") -> "Image.Image":
    """ピクセル単位でグラデーション背景を描画する"""
    from PIL import Image as PILImage
    W, H = img.size
    pixels = img.load()
    for y in range(H):
        for x in range(W):
            if direction == "diagonal":
                t = (x / W * 0.6 + y / H * 0.4)
            else:
                t = y / H
            r = int(color1[0] + (color2[0] - color1[0]) * t)
            g = int(color1[1] + (color2[1] - color1[1]) * t)
            b = int(color1[2] + (color2[2] - color1[2]) * t)
            pixels[x, y] = (r, g, b)
    return img


def _draw_dot_pattern(draw: "ImageDraw.ImageDraw", W: int, H: int, color: tuple, alpha: int = 30):
    """右下にドットパターンを描画する"""
    dot_overlay = __import__("PIL").Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dot_draw = __import__("PIL").ImageDraw.Draw(dot_overlay)
    spacing = 28
    for gx in range(W // 2, W + spacing, spacing):
        for gy in range(H // 3, H + spacing, spacing):
            dot_draw.ellipse([gx - 2, gy - 2, gx + 2, gy + 2], fill=(*color, alpha))
    return dot_overlay


def generate_thumbnail_pillow(title: str, theme: str) -> Path | None:
    """
    Pillow でプロ品質サムネイルを生成する（Imagen の代替）。
    - 本格グラデーション背景
    - 幾何学ドットパターン
    - 有料バッジ
    - 2段テキストレイアウト

    Returns:
        Path: 保存した画像ファイルのパス、失敗時は None
    """
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter

        THEME_PALETTES = {
            "副業":     (("#0D0D1A", "#1A0D00"), "#F7931A", "#FF6B6B"),
            "AI":       (("#020B18", "#0A0628"), "#00D4FF", "#7C3AED"),
            "投資":     (("#011020", "#001A0E"), "#10B981", "#3B82F6"),
            "キャリア": (("#0E0520", "#1A0520"), "#A78BFA", "#EC4899"),
            "SNS":      (("#0A0010", "#100010"), "#FF6B9D", "#C084FC"),
            "ポイント": (("#011020", "#001A0E"), "#10B981", "#3B82F6"),
            "自己":     (("#1A1000", "#0D0D17"), "#FBBF24", "#F87171"),
            "睡眠":     (("#030810", "#070318"), "#818CF8", "#38BDF8"),
            "読書":     (("#130C00", "#001209"), "#D97706", "#059669"),
            "ADHD":     (("#0D1117", "#001A10"), "#34D399", "#60A5FA"),
            "HSP":      (("#130010", "#0A0020"), "#F472B6", "#A78BFA"),
            "Kindle":   (("#0D0D1A", "#1A0D00"), "#F7931A", "#FF6B6B"),
            "YouTube":  (("#1A0000", "#0D0010"), "#FF4444", "#FF9500"),
            "TikTok":   (("#000D1A", "#1A0010"), "#00F5FF", "#FF0080"),
        }

        (bg1_hex, bg2_hex), accent, sub_accent = (("#0D1117", "#1A1028"), "#00C896", "#3B82F6")
        combined = theme + title
        for keyword, palette in THEME_PALETTES.items():
            if keyword in combined:
                (bg1_hex, bg2_hex), accent, sub_accent = palette
                break

        W, H = 1280, 720
        bg1 = _hex_to_rgb(bg1_hex)
        bg2 = _hex_to_rgb(bg2_hex)
        accent_rgb = _hex_to_rgb(accent)
        sub_rgb = _hex_to_rgb(sub_accent)

        # グラデーション背景
        img = Image.new("RGB", (W, H))
        img = _draw_gradient(img, bg1, bg2, direction="diagonal")

        # ドットパターン（右下）
        dot_overlay = _draw_dot_pattern(ImageDraw.Draw(img), W, H, accent_rgb, alpha=35)
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, dot_overlay)
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)

        # 左上グロー（アクセント色の発光）
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for r in range(220, 0, -20):
            alpha = int(25 * (1 - r / 220))
            gd.ellipse([-r // 2, -r // 2, r, r], fill=(*accent_rgb, alpha))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, glow)
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)

        # 上部アクセントバー（グラデーション風）
        for bx in range(W):
            t = bx / W
            r = int(accent_rgb[0] * (1 - t * 0.4) + sub_rgb[0] * t * 0.4)
            g = int(accent_rgb[1] * (1 - t * 0.4) + sub_rgb[1] * t * 0.4)
            b = int(accent_rgb[2] * (1 - t * 0.4) + sub_rgb[2] * t * 0.4)
            draw.line([(bx, 0), (bx, 7)], fill=(r, g, b))

        # 斜めアクセントライン（右上）
        for offset in [0, 18, 36]:
            draw.line([(W - 120 + offset, 0), (W + offset, 120)], fill=(*accent_rgb, 40), width=6)

        # フォント読み込み
        def load_font(size, bold=False):
            candidates = [
                "C:/Windows/Fonts/meiryob.ttc" if bold else "C:/Windows/Fonts/meiryo.ttc",
                "C:/Windows/Fonts/msgothic.ttc",
                "C:/Windows/Fonts/arial.ttf",
            ]
            for path in candidates:
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
            return ImageFont.load_default()

        font_badge  = load_font(22, bold=True)
        font_label  = load_font(27)
        font_main   = load_font(66, bold=True)
        font_sub    = load_font(48, bold=True)
        font_footer = load_font(26)

        # 有料バッジ（右上）
        badge_text = "¥100 有料"
        badge_w, badge_x, badge_y = 160, W - 180, 20
        draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + 48], fill=accent)
        draw.text((badge_x + 14, badge_y + 10), badge_text, font=font_badge, fill="#000000")

        # カテゴリラベル（左上）
        label_text = theme[:12] if len(theme) > 12 else theme
        label_x, label_y = 56, 46
        label_w = max(len(label_text) * 19 + 36, 80)
        label_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        lo = ImageDraw.Draw(label_overlay)
        lo.rectangle([label_x, label_y, label_x + label_w, label_y + 46],
                     fill=(*accent_rgb, 220))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, label_overlay)
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.text((label_x + 18, label_y + 9), label_text, font=font_label, fill="#000000")

        # タイトル分割（｜で分ける）
        if "｜" in title:
            parts = title.split("｜", 1)
            main_title = parts[0].strip()
            sub_title  = parts[1].strip()
        else:
            main_title = title
            sub_title  = ""

        # メインタイトル
        wrapped_main = textwrap.wrap(main_title, width=17)
        y_text = 126
        for line in wrapped_main[:2]:
            # アウトライン（黒）
            for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
                draw.text((80 + dx, y_text + dy), line, font=font_main, fill=(0, 0, 0))
            draw.text((80, y_text), line, font=font_main, fill="#FFFFFF")
            y_text += 80

        # サブタイトル
        if sub_title:
            wrapped_sub = textwrap.wrap(sub_title, width=22)
            y_text += 8
            for line in wrapped_sub[:2]:
                for dx, dy in [(-1, -1), (1, 1)]:
                    draw.text((80 + dx, y_text + dy), line, font=font_sub, fill=(0, 0, 0))
                draw.text((80, y_text), line, font=font_sub, fill=sub_accent)
                y_text += 58

        # 下部フッターバー
        footer_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fo = ImageDraw.Draw(footer_overlay)
        fo.rectangle([0, H - 70, W, H], fill=(0, 0, 0, 160))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, footer_overlay)
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)

        # フッターアクセントライン
        for bx in range(W):
            t = bx / W
            r = int(accent_rgb[0] * (1 - t) + sub_rgb[0] * t)
            g = int(accent_rgb[1] * (1 - t) + sub_rgb[1] * t)
            b = int(accent_rgb[2] * (1 - t) + sub_rgb[2] * t)
            draw.line([(bx, H - 70), (bx, H - 65)], fill=(r, g, b))

        draw.text((60, H - 52), "note  ●  有料記事", font=font_footer, fill=accent)

        fname = _safe_filename(title) + ".png"
        out_path = THUMBNAIL_DIR / fname
        img.save(str(out_path), "PNG", quality=95)
        print(f"   🖼️  Pillow サムネイル生成完了: {out_path}")
        return out_path

    except ImportError:
        print("   ⚠️  Pillow がインストールされていません (pip install Pillow)")
        return None
    except Exception as e:
        print(f"   ⚠️  Pillow サムネイル生成失敗: {e}")
        return None


def generate_thumbnail(title: str, theme: str) -> Path | None:
    """
    サムネイルを生成する（Imagen → Pillow の順に試みる）

    Returns:
        Path: 生成された画像ファイルのパス、失敗時は None
    """
    print(f"🖼️  サムネイル生成中...")

    # 1. Imagen API を試みる
    result = generate_thumbnail_imagen(title, theme)
    if result:
        return result

    # 2. フォールバック: Pillow
    print("   → Pillow でフォールバック生成...")
    return generate_thumbnail_pillow(title, theme)
