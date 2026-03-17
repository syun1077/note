"""
note.com 自動投稿 - AI記事生成モジュール
========================================
Groq API（無料）を使って記事を自動生成します。
テーマの重複を自動防止します。
毎回異なるペルソナで書き、過去記事のSEOスコアから自動改善します。
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

# ライティングペルソナ（毎回ランダムで切り替える）
WRITING_PERSONAS = [
    (
        "体験談型",
        "自分が実際に経験した話として書く。「私は〜した」「実際にやってみて分かったのは〜」という"
        "一人称で書く。具体的な日付・金額・ツール名を入れて信頼感を出す。",
    ),
    (
        "数字・データ型",
        "具体的な数字・統計・比較データを多用する。「〇〇%」「〇ヶ月で〇万円」など。"
        "表や箇条書きを活用し、読者が一目でわかる構成にする。",
    ),
    (
        "専門家解説型",
        "その分野の専門家として書く。業界の内情・裏側・専門知識を教える先生のような口調。"
        "「実はこれを知っている人は少ない」「プロだけが使うテクニック」という切り口で書く。",
    ),
    (
        "ステップ解説型",
        "STEP1→STEP2→STEP3の順番で、初心者でも迷わない具体的な手順書として書く。"
        "各ステップに所要時間・注意点・チェックポイントを入れる。",
    ),
    (
        "失敗談型",
        "自分の失敗・間違い・後悔から学んだことを率直に書く。"
        "「こうすれば良かった」「やってはいけない」視点で書き、読者の共感を得る。"
        "失敗の原因分析と再発防止策を具体的に書く。",
    ),
    (
        "比較分析型",
        "A vs B の形式で複数の選択肢を徹底比較する。"
        "比較表・スコア・向き不向きを明示し、読者が意思決定しやすい構成にする。",
    ),
    (
        "Q&A型",
        "読者がよく抱く疑問をQ&A形式で10個以上答える。"
        "「よくある誤解」「気になるけど聞けない質問」に正直に回答する。",
    ),
]


def setup_groq():
    """Groq APIクライアントを初期化"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY が .env ファイルまたは環境変数に設定されていません")
    return Groq(api_key=api_key)


def _get_improvement_hints() -> str:
    """過去のSEOスコアから改善ヒントを取得する"""
    try:
        from post_history import load_history
        history = load_history()
        scored = [r for r in history if r.get("seo_score") is not None and r.get("success")]
        if not scored:
            return ""
        avg = sum(r["seo_score"] for r in scored) / len(scored)
        best = max(scored, key=lambda r: r["seo_score"])
        hint = f"\n【過去記事の平均SEOスコア: {avg:.0f}点】\n"
        hint += f"最高スコア記事（{best['seo_score']}点）のタイトル: 「{best['title']}」\n"
        hint += "このスコアを超える記事を書いてください。\n"
        return hint
    except Exception:
        return ""


def _get_recent_titles(n: int = 5) -> list[str]:
    """直近n件の成功タイトルを返す（重複回避用）"""
    try:
        from post_history import load_history
        history = load_history()
        recent = [r["title"] for r in history if r.get("success")][-n:]
        return recent
    except Exception:
        return []


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

    # ペルソナをランダム選択
    persona_name, persona_desc = random.choice(WRITING_PERSONAS)
    print(f"📝 テーマ: {theme}")
    print(f"✍️  ペルソナ: {persona_name}")
    print(f"🤖 AIが記事を生成中...")

    # 自己改善ヒントと重複回避
    improvement_hint = _get_improvement_hints()
    recent_titles = _get_recent_titles()
    avoid_block = ""
    if recent_titles:
        avoid_block = "\n【直近の投稿タイトル（これらと同じ内容・構成は避けること）】\n"
        avoid_block += "\n".join(f"- {t}" for t in recent_titles) + "\n"

    system_prompt = (
        "あなたはnote.comで月100万円以上を稼ぐトップクリエイターです。"
        "有料noteで読者に『買ってよかった』と思わせる記事を書きます。"
        "ユーザーの指示に従い、必ず有効なJSONのみを返してください。"
        "JSONのキーは title, body, hashtags の3つです。"
        "余分なテキスト、コードブロック記号、説明文は一切含めないでください。"
    )

    user_prompt = f"""以下のテーマでnote.com有料記事を書き、JSON形式で返してください。

テーマ: {theme}

【今回のライティングスタイル: {persona_name}】
{persona_desc}
{improvement_hint}{avoid_block}
【品質チェックリスト（全て満たすこと）】
✅ 冒頭3行で読者を引き込む「刺さる問いかけ」がある
✅ 「他のブログには書いていない」一次情報・数字・実例がある
✅ 無料パートで「続きが気になる」状態を作れている
✅ 有料パートに「すぐ使えるテンプレ・表・チェックリスト」がある
✅ 見出しだけ読んでも記事の価値が伝わる構成になっている
✅ 最後に読者が行動できる「次のステップ」がある

スタイル要件:
{ARTICLE_STYLE}

出力形式（このJSONのみを返す）:
{{
  "title": "記事タイトル（キャッチーで30〜50文字、数字を入れる）",
  "body": "記事本文（Markdown形式、6000文字以上、具体的な数字・ツール名・手順を必ず入れる）",
  "hashtags": ["タグ1", "タグ2", "タグ3", "タグ4", "タグ5"]
}}"""

    # パス1: 初稿生成
    raw = _call_groq(client, system_prompt, user_prompt, temperature=0.75)

    # JSONパース
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"   ⚠️ JSONパース失敗。テキストから抽出を試みます...")
        data = _extract_json_from_text(raw)

    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    hashtags = data.get("hashtags") or []

    if not title or not body:
        print(f"   ⚠️ レスポンス内容（先頭200文字）: {raw[:200]}")
        raise ValueError(f"記事の生成に失敗しました。title={bool(title)}, body={bool(body)}")

    print(f"   📝 初稿完成: {len(body)}文字")

    # パス2: AIによる自己批評＆改善
    body = _review_and_improve(client, title, body, theme)

    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split(",") if h.strip()]
    hashtags = [str(h).strip().lstrip("#") for h in hashtags if h][:5]
    if not hashtags:
        hashtags = DEFAULT_HASHTAGS[:5]

    print(f"✅ 記事生成完了!")
    print(f"   タイトル: {title}")
    print(f"   本文文字数: {len(body)}文字")
    print(f"   ハッシュタグ: {', '.join(hashtags)}")

    return {
        "title": title,
        "body": body,
        "hashtags": hashtags,
        "theme": theme,
        "persona": persona_name,
    }


def _call_groq(client: Groq, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """リトライ付きGroq API呼び出し。raw文字列を返す。"""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=8192,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content.strip()
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
                # JSON mode非対応 → テキストモードで再試行
                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "system", "content": system_prompt},
                               {"role": "user", "content": user_prompt}],
                    max_tokens=8192,
                    temperature=temperature,
                )
                return response.choices[0].message.content.strip()
            else:
                raise
    raise Exception(f"記事生成に失敗しました: {last_error}")


def _review_and_improve(client: Groq, title: str, body: str, theme: str) -> str:
    """
    パス2: AIが自分の記事を批評し、弱い部分を書き直す。
    改善後の本文を返す。失敗時は元の本文を返す。
    """
    print(f"   🔍 AIが自己批評・改善中...")
    try:
        review_prompt = f"""あなたは厳しい編集者です。以下のnote記事を読み、品質を向上させてください。

【記事タイトル】{title}
【テーマ】{theme}

【現在の記事本文】
{body[:4000]}{'...(以下省略)' if len(body) > 4000 else ''}

【改善タスク】
1. 具体性が低い箇所を特定し、実際の数字・ツール名・手順に置き換える
2. 「---ここから有料---」より後の有料パートに「すぐ使えるテンプレート」か「比較表」を1つ追加する
3. 冒頭の書き出しを「読者が思わず続きを読みたくなる」ものに書き直す
4. 文字数が少ない場合は各セクションを深掘りして追記する（最終的に6000文字以上）

改善後の記事本文全体をそのまま出力してください。JSONではなく、Markdownテキストのみを返してください。"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": review_prompt}],
            max_tokens=8192,
            temperature=0.6,
        )
        improved = response.choices[0].message.content.strip()
        if len(improved) > len(body) * 0.5:  # 半分以上の長さがあれば採用
            print(f"   ✅ 改善完了: {len(body)}文字 → {len(improved)}文字")
            return improved
        else:
            print(f"   ⚠️ 改善結果が短すぎるため元の本文を使用")
            return body
    except Exception as e:
        print(f"   ⚠️ 自己批評スキップ: {e}")
        return body


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
