"""
note.com 自動投稿 - AI記事生成モジュール
========================================
Gemini APIを使って記事を自動生成します。
テーマの重複を自動防止します。
"""

import os
import random
import time
from google import genai
from dotenv import load_dotenv
from config import ARTICLE_THEMES, ARTICLE_STYLE, DEFAULT_HASHTAGS

load_dotenv()

# リトライ設定
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 65  # レート制限は通常60秒でリセット


def setup_gemini():
    """Gemini APIクライアントを初期化"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が .env ファイルに設定されていません")
    client = genai.Client(api_key=api_key)
    return client


def generate_article(theme: str = None, used_themes: set = None) -> dict:
    """
    AIを使って記事を生成する
    
    Args:
        theme: 記事のテーマ（指定しない場合はランダム選択）
        used_themes: 使用済みテーマのセット（重複防止）
    
    Returns:
        dict: {"title": str, "body": str, "hashtags": list[str], "theme": str}
    """
    client = setup_gemini()
    
    if theme is None:
        # 使用済みテーマを除外してランダム選択
        if used_themes:
            available_themes = [t for t in ARTICLE_THEMES if t not in used_themes]
            if not available_themes:
                print("   ⚠️ すべてのテーマが使用済みです。リストから再度選択します。")
                available_themes = ARTICLE_THEMES
            else:
                print(f"   📋 未使用テーマ: {len(available_themes)}/{len(ARTICLE_THEMES)} 件")
        else:
            available_themes = ARTICLE_THEMES
        
        theme = random.choice(available_themes)
    
    print(f"📝 テーマ: {theme}")
    print(f"🤖 AIが記事を生成中...")
    
    prompt = f"""
あなたはnote.comで人気のブロガーです。
以下のテーマについて、note.comに投稿する記事を書いてください。

## テーマ
{theme}

## 記事のスタイル・要件
{ARTICLE_STYLE}

## 出力フォーマット
以下の形式で出力してください（マーカーは必ず含めてください）：

---TITLE_START---
（ここに記事タイトルを1行で書く。キャッチーで読みたくなるタイトルにしてください）
---TITLE_END---

---BODY_START---
（ここに記事本文を書く。Markdown形式で。）
---BODY_END---

---HASHTAGS_START---
（ここにカンマ区切りでハッシュタグを5個書く。#は不要）
---HASHTAGS_END---
"""
    
    # リトライ付きでAPI呼び出し
    text = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = response.text
            break
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                if attempt < MAX_RETRIES:
                    print(f"   ⏳ レート制限に達しました。{RETRY_WAIT_SECONDS}秒待ってリトライします... ({attempt}/{MAX_RETRIES})")
                    time.sleep(RETRY_WAIT_SECONDS)
                else:
                    raise Exception(f"レート制限により{MAX_RETRIES}回リトライしましたが失敗しました: {e}")
            else:
                raise
    
    if text is None:
        raise Exception("記事生成に失敗しました")
    
    # パース
    title = _extract_between(text, "---TITLE_START---", "---TITLE_END---").strip()
    body = _extract_between(text, "---BODY_START---", "---BODY_END---").strip()
    hashtags_raw = _extract_between(text, "---HASHTAGS_START---", "---HASHTAGS_END---").strip()
    
    hashtags = [tag.strip() for tag in hashtags_raw.split(",") if tag.strip()]
    if not hashtags:
        hashtags = DEFAULT_HASHTAGS[:5]
    
    if not title or not body:
        raise ValueError("記事の生成に失敗しました。出力フォーマットが正しくありません。")
    
    print(f"✅ 記事生成完了!")
    print(f"   タイトル: {title}")
    print(f"   本文文字数: {len(body)}文字")
    print(f"   ハッシュタグ: {', '.join(hashtags)}")
    
    return {
        "title": title,
        "body": body,
        "hashtags": hashtags,
        "theme": theme,
    }


def _extract_between(text: str, start_marker: str, end_marker: str) -> str:
    """テキストからマーカー間の文字列を抽出"""
    try:
        start_idx = text.index(start_marker) + len(start_marker)
        end_idx = text.index(end_marker)
        return text[start_idx:end_idx]
    except ValueError:
        return ""


if __name__ == "__main__":
    # テスト実行
    article = generate_article()
    print("\n" + "=" * 60)
    print(f"タイトル: {article['title']}")
    print(f"ハッシュタグ: {article['hashtags']}")
    print("=" * 60)
    print(article["body"][:500] + "...")
