"""
note.com 自動投稿 - AI記事生成モジュール
========================================
Groq API（無料）を使って記事を自動生成します。
テーマの重複を自動防止します。
"""

import os
import json
import random
import time
from groq import Groq
from dotenv import load_dotenv
from config import ARTICLE_THEMES, ARTICLE_STYLE, DEFAULT_HASHTAGS, GROQ_MODEL

load_dotenv()

# リトライ設定
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 65  # レート制限は通常60秒でリセット


def setup_groq():
    """Groq APIクライアントを初期化"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY が .env ファイルまたは環境変数に設定されていません")
    return Groq(api_key=api_key)


def generate_article(theme: str = None, used_themes: set = None) -> dict:
    """
    AIを使って記事を生成する

    Args:
        theme: 記事のテーマ（指定しない場合はランダム選択）
        used_themes: 使用済みテーマのセット（重複防止）

    Returns:
        dict: {"title": str, "body": str, "hashtags": list[str], "theme": str}
    """
    client = setup_groq()

    if theme is None:
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

    system_prompt = (
        "あなたはnote.comで人気のブロガーです。"
        "ユーザーの指示に従い、必ず有効なJSONのみを返してください。"
        "JSONのキーは title, body, hashtags の3つです。"
        "余分なテキスト、コードブロック記号、説明文は一切含めないでください。"
    )

    user_prompt = f"""以下のテーマでnote.com記事を書き、JSON形式で返してください。

テーマ: {theme}

スタイル要件:
{ARTICLE_STYLE}

出力形式（このJSONのみを返す）:
{{
  "title": "記事タイトル（キャッチーで30〜50文字）",
  "body": "記事本文（Markdown形式、3000文字以上）",
  "hashtags": ["タグ1", "タグ2", "タグ3", "タグ4", "タグ5"]
}}"""

    # リトライ付きでAPI呼び出し
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=4096,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            break
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                if attempt < MAX_RETRIES:
                    print(f"   ⏳ レート制限。{RETRY_WAIT_SECONDS}秒待ってリトライ... ({attempt}/{MAX_RETRIES})")
                    time.sleep(RETRY_WAIT_SECONDS)
                else:
                    raise Exception(f"レート制限により{MAX_RETRIES}回リトライしましたが失敗: {e}")
            elif "json_object" in error_msg.lower() or "response_format" in error_msg.lower():
                # response_format 非対応モデルの場合はフォールバック
                print(f"   ⚠️ JSON mode 非対応。テキストモードで再試行...")
                return _generate_article_text_mode(client, theme, user_prompt)
            else:
                raise
    else:
        raise Exception(f"記事生成に失敗しました: {last_error}")

    # JSONパース
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # JSON部分を抽出して再試行
        print(f"   ⚠️ JSONパース失敗。テキストから抽出を試みます...")
        data = _extract_json_from_text(raw)

    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    hashtags = data.get("hashtags") or []

    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split(",") if h.strip()]
    hashtags = [str(h).strip().lstrip("#") for h in hashtags if h][:5]

    if not hashtags:
        hashtags = DEFAULT_HASHTAGS[:5]

    if not title or not body:
        print(f"   ⚠️ レスポンス内容（先頭200文字）: {raw[:200]}")
        raise ValueError(f"記事の生成に失敗しました。title={bool(title)}, body={bool(body)}")

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


def _generate_article_text_mode(client: Groq, theme: str, user_prompt: str) -> dict:
    """response_format非対応の場合のフォールバック（マーカー方式）"""
    fallback_prompt = f"""テーマ「{theme}」でnote.com記事を書いてください。
必ず以下のマーカーを使って出力してください：

---TITLE_START---
タイトルをここに
---TITLE_END---

---BODY_START---
本文をここに（3000文字以上）
---BODY_END---

---HASHTAGS_START---
タグ1, タグ2, タグ3, タグ4, タグ5
---HASHTAGS_END---"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": fallback_prompt}],
        max_tokens=4096,
        temperature=0.7,
    )
    text = response.choices[0].message.content

    title = _extract_between(text, "---TITLE_START---", "---TITLE_END---").strip()
    body = _extract_between(text, "---BODY_START---", "---BODY_END---").strip()
    hashtags_raw = _extract_between(text, "---HASHTAGS_START---", "---HASHTAGS_END---").strip()
    hashtags = [h.strip().lstrip("#") for h in hashtags_raw.split(",") if h.strip()][:5]

    if not hashtags:
        hashtags = DEFAULT_HASHTAGS[:5]
    if not title or not body:
        print(f"   ⚠️ フォールバックレスポンス（先頭200文字）: {text[:200]}")
        raise ValueError("フォールバックでも記事生成に失敗しました")

    return {"title": title, "body": body, "hashtags": hashtags, "theme": theme}


def _extract_json_from_text(text: str) -> dict:
    """テキストからJSON部分を抽出してパースする"""
    # ```json ... ``` ブロックを探す
    import re
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # { ... } を直接探す
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("レスポンスからJSONが抽出できませんでした")


def _extract_between(text: str, start_marker: str, end_marker: str) -> str:
    """テキストからマーカー間の文字列を抽出"""
    try:
        start_idx = text.index(start_marker) + len(start_marker)
        end_idx = text.index(end_marker, start_idx)
        return text[start_idx:end_idx]
    except ValueError:
        return ""


if __name__ == "__main__":
    article = generate_article()
    print("\n" + "=" * 60)
    print(f"タイトル: {article['title']}")
    print(f"ハッシュタグ: {article['hashtags']}")
    print("=" * 60)
    print(article["body"][:500] + "...")
