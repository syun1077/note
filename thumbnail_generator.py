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


def generate_thumbnail_pillow(title: str, theme: str) -> Path | None:
    """
    Pillow でテキストベースのサムネイル画像を生成する（Imagen の代替）。

    Returns:
        Path: 保存した画像ファイルのパス、失敗時は None
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        # テーマ別カラーパレット
        THEME_COLORS = {
            "副業": ("#1A1A2E", "#E94560"),
            "AI":   ("#0F3460", "#16213E"),
            "投資": ("#16213E", "#0F3460"),
            "キャリア": ("#2C3E50", "#3498DB"),
            "SNS":  ("#8E44AD", "#2980B9"),
        }

        # テーマ判定（キーワード一致）
        bg_start, bg_end = "#1E3A5F", "#0D1B2A"
        for keyword, colors in THEME_COLORS.items():
            if keyword in theme or keyword in title:
                bg_start, bg_end = colors
                break

        W, H = 1280, 720
        img = Image.new("RGB", (W, H), bg_start)
        draw = ImageDraw.Draw(img)

        # グラデーション風の背景（単純な矩形重ね）
        from PIL import ImageFilter
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for i in range(H):
            alpha = int(160 * i / H)
            overlay_draw.line([(0, i), (W, i)], fill=(0, 0, 0, alpha))
        img.paste(overlay, (0, 0), overlay)
        draw = ImageDraw.Draw(img)

        # アクセントライン
        accent = "#00C896"
        draw.rectangle([60, H - 80, W - 60, H - 76], fill=accent)

        # テーマラベル
        draw.rectangle([60, 60, 60 + len(theme) * 18 + 40, 110], fill=accent)
        try:
            font_label = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 28)
        except Exception:
            font_label = ImageFont.load_default()
        draw.text((80, 68), theme, font=font_label, fill="#FFFFFF")

        # タイトルテキスト（折り返し）
        try:
            font_title = ImageFont.truetype("C:/Windows/Fonts/meiryob.ttc", 64)
        except Exception:
            try:
                font_title = ImageFont.truetype("C:/Windows/Fonts/meiryo.ttc", 64)
            except Exception:
                font_title = ImageFont.load_default()

        wrapped = textwrap.wrap(title, width=20)
        y_text = 160
        for line in wrapped[:3]:
            draw.text((80, y_text), line, font=font_title, fill="#FFFFFF")
            y_text += 80

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
