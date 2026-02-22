"""
note.com 自動投稿 - SEOスコアチェックモジュール
================================================
生成された記事のSEO品質を自動チェックします。
"""

import re


def check_seo(title: str, body: str, hashtags: list[str]) -> dict:
    """
    記事のSEOスコアを算出する（100点満点）

    採点基準:
      - タイトル文字数    20点
      - 本文文字数        20点
      - 見出し構造        20点
      - ハッシュタグ      20点
      - キーワード密度    20点
    """
    score = 0
    issues = []
    suggestions = []

    # ── タイトル文字数 ──────────────────────────────────────────────
    tlen = len(title)
    if 25 <= tlen <= 60:
        score += 20
    elif tlen < 25:
        score += 10
        issues.append(f"タイトルが短い ({tlen}文字 / 推奨 25〜60文字)")
    else:
        score += 10
        issues.append(f"タイトルが長すぎる ({tlen}文字 / 推奨 25〜60文字)")

    # ── 本文文字数 ──────────────────────────────────────────────────
    blen = len(body)
    if blen >= 3000:
        score += 20
    elif blen >= 1500:
        score += 13
        suggestions.append("本文を 3,000 文字以上にするとSEO的に有利です")
    elif blen >= 800:
        score += 7
        suggestions.append("本文が短めです。1,500 文字以上を目指しましょう")
    else:
        issues.append(f"本文が短すぎます ({blen}文字 / 推奨 3,000文字以上)")

    # ── 見出し構造 ──────────────────────────────────────────────────
    headings = re.findall(r"^#{1,3}\s+.+", body, re.MULTILINE)
    h_count = len(headings)
    if h_count >= 4:
        score += 20
    elif h_count >= 2:
        score += 13
        suggestions.append("見出し(##)を 4 つ以上入れると構造がわかりやすくなります")
    elif h_count == 1:
        score += 5
        suggestions.append("見出し(##)が 1 つだけです。複数の章に分けましょう")
    else:
        issues.append("見出し(##)がありません。記事を章立てしてください")

    # ── ハッシュタグ数 ──────────────────────────────────────────────
    htag_count = len([h for h in hashtags if h.strip()])
    if htag_count >= 4:
        score += 20
    elif htag_count >= 2:
        score += 13
        suggestions.append("ハッシュタグを 4〜5 個設定することを推奨します")
    elif htag_count == 1:
        score += 5
        issues.append("ハッシュタグが 1 個しかありません")
    else:
        issues.append("ハッシュタグが設定されていません")

    # ── キーワード密度（タイトルの主要語が本文に含まれるか） ────────
    # 日本語・英語の2文字以上の語を抽出
    title_words = set(re.findall(r"[一-龯ぁ-ん゛゜ァ-ンヴーａ-ｚＡ-Ｚa-zA-Z0-9]{2,}", title))
    if title_words:
        matched = sum(1 for w in title_words if w in body)
        ratio = matched / len(title_words)
        if ratio >= 0.6:
            score += 20
        elif ratio >= 0.3:
            score += 10
            suggestions.append("タイトルのキーワードを本文中でもっと使いましょう")
        else:
            score += 0
            suggestions.append("タイトルと本文のキーワードが一致していません")
    else:
        score += 10

    grade = (
        "S" if score >= 90
        else "A" if score >= 80
        else "B" if score >= 60
        else "C" if score >= 40
        else "D"
    )

    return {
        "score": score,
        "max_score": 100,
        "grade": grade,
        "issues": issues,
        "suggestions": suggestions,
        "details": {
            "title_length": tlen,
            "body_length": blen,
            "heading_count": h_count,
            "hashtag_count": htag_count,
        },
    }


def print_seo_report(seo: dict):
    """SEOレポートを標準出力に表示"""
    grade = seo["grade"]
    score = seo["score"]
    bar_filled = int(score / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    print(f"\n🔍 SEOスコア: {score}/100  [{bar}]  グレード: {grade}")

    d = seo["details"]
    print(
        f"   タイトル {d['title_length']}文字 | "
        f"本文 {d['body_length']:,}文字 | "
        f"見出し {d['heading_count']}個 | "
        f"タグ {d['hashtag_count']}個"
    )

    if seo["issues"]:
        print("   ⚠️  問題:")
        for issue in seo["issues"]:
            print(f"      · {issue}")

    if seo["suggestions"]:
        print("   💡 改善提案:")
        for s in seo["suggestions"]:
            print(f"      · {s}")
