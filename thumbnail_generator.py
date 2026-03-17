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


def generate_thumbnail_pillow(title: str, theme: str) -> Path | None:
    """
    Pillow でテキストベースのサムネイル画像を生成する（Imagen の代替）。

    Returns:
        Path: 保存した画像ファイルのパス、失敗時は None
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        # テーマ別カラーパレット（背景色, アクセント色, サブ色）
        THEME_PALETTES = {
            "副業":     ("#0D1117", "#F7931A", "#FF6B6B"),
            "AI":       ("#050A14", "#00D4FF", "#7C3AED"),
            "投資":     ("#0A1628", "#10B981", "#3B82F6"),
            "キャリア": ("#1A0A2E", "#A78BFA", "#EC4899"),
            "SNS":      ("#0F0F1A", "#FF6B9D", "#C084FC"),
            "ポイント": ("#0A1628", "#10B981", "#3B82F6"),
            "自己":     ("#0D1117", "#FBBF24", "#F87171"),
            "睡眠":     ("#0A0E1A", "#818CF8", "#38BDF8"),
            "読書":     ("#1A1208", "#D97706", "#059669"),
            "ADHD":     ("#0D1117", "#34D399", "#60A5FA"),
            "HSP":      ("#1A0D1A", "#F472B6", "#A78BFA"),
        }

        bg_color, accent, sub_accent = "#0D1117", "#00C896", "#3B82F6"
        combined = theme + title
        for keyword, palette in THEME_PALETTES.items():
            if keyword in combined:
                bg_color, accent, sub_accent = palette
                break

        W, H = 1280, 720
        bg_rgb = _hex_to_rgb(bg_color)

        # グラデーション背景
        img = Image.new("RGB", (W, H), bg_rgb)
        draw = ImageDraw.Draw(img)

        # 左上から右下への斜めグラデーション風オーバーレイ
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        accent_rgb = _hex_to_rgb(accent)
        for i in range(200):
            x0, y0, x1, y1 = -50 + i, -50 + i, 400 - i, 400 - i
            if x1 < x0 or y1 < y0:
                break
            alpha = int(40 * (1 - i / 200))
            ov_draw.ellipse([x0, y0, x1, y1], fill=(*accent_rgb, alpha))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)

        # 右側デコレーション（縦ライン群）
        sub_rgb = _hex_to_rgb(sub_accent)
        for xi, alpha in [(W - 20, 120), (W - 40, 80), (W - 60, 50)]:
            line_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            lo_draw = ImageDraw.Draw(line_overlay)
            lo_draw.rectangle([xi, 0, xi + 4, H], fill=(*sub_rgb, alpha))
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, line_overlay)
            img = img.convert("RGB")
            draw = ImageDraw.Draw(img)

        # 上部アクセントバー
        accent_rgb = _hex_to_rgb(accent)
        draw.rectangle([0, 0, W, 8], fill=accent)

        # カテゴリラベル（ピル形状風）
        try:
            font_label = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 26)
        except Exception:
            font_label = ImageFont.load_default()

        label_text = theme[:15] if len(theme) > 15 else theme
        label_x, label_y = 60, 50
        label_w = max(len(label_text) * 20 + 40, 80)
        draw.rectangle(
            [label_x, label_y, label_x + label_w, label_y + 44],
            fill=accent
        )
        draw.text((label_x + 20, label_y + 8), label_text, font=font_label, fill="#000000")

        # タイトルテキスト（2段階フォントサイズ）
        try:
            font_title_lg = ImageFont.truetype("C:/Windows/Fonts/meiryob.ttc", 68)
            font_title_sm = ImageFont.truetype("C:/Windows/Fonts/meiryob.ttc", 52)
        except Exception:
            try:
                font_title_lg = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 68)
                font_title_sm = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 52)
            except Exception:
                font_title_lg = font_title_sm = ImageFont.load_default()

        # タイトルをメイン部分とサブ部分に分割（｜で分ける）
        if "｜" in title:
            parts = title.split("｜", 1)
            main_title = parts[0].strip()
            sub_title = parts[1].strip()
        else:
            main_title = title
            sub_title = ""

        # メインタイトル（折り返し）
        wrapped_main = textwrap.wrap(main_title, width=18)
        y_text = 130
        for line in wrapped_main[:2]:
            # テキストシャドウ
            draw.text((82, y_text + 2), line, font=font_title_lg, fill=(0, 0, 0))
            draw.text((80, y_text), line, font=font_title_lg, fill="#FFFFFF")
            y_text += 82

        # サブタイトル
        if sub_title:
            wrapped_sub = textwrap.wrap(sub_title, width=24)
            y_text += 10
            for line in wrapped_sub[:2]:
                draw.text((82, y_text + 1), line, font=font_title_sm, fill=(0, 0, 0))
                draw.text((80, y_text), line, font=font_title_sm, fill=sub_accent)
                y_text += 62

        # 下部アクセントライン
        draw.rectangle([60, H - 60, W - 60, H - 54], fill=accent)

        # note ロゴ風テキスト
        try:
            font_note = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 28)
        except Exception:
            font_note = ImageFont.load_default()
        draw.text((66, H - 48), "note", font=font_note, fill=accent)

        fname = _safe_filename(title) + ".png"
        out_path = THUMBNAIL_DIR / fname
        img.save(str(out_path), "PNG")
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
