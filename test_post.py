"""
note.com 投稿テスト - Gemini APIを使わずに投稿部分だけテスト
============================================================
使い方: python test_post.py
"""

import asyncio
from note_poster import run_post


# テスト用の記事データ
TEST_ARTICLE = {
    "title": "【テスト】自動投稿のテスト記事",
    "body": """こんにちは！

これはnote.com自動投稿ツールのテスト記事です。

## この記事について

このツールはPythonとPlaywrightを使って、note.comに自動的に記事を投稿します。

## 主な機能

- AIによる記事の自動生成（Gemini API）
- note.comへの自動ログイン
- 記事の自動投稿（公開/下書き）
- GitHub Actionsによるスケジュール実行

## まとめ

自動投稿ツールが正しく動作することを確認するためのテスト記事です。
""",
    "hashtags": ["テスト", "自動投稿", "Python"],
}


async def main():
    print("🧪 投稿テスト開始（下書きモード）")
    print(f"   タイトル: {TEST_ARTICLE['title']}")
    print(f"   本文: {len(TEST_ARTICLE['body'])}文字")

    success = await run_post(
        title=TEST_ARTICLE["title"],
        body=TEST_ARTICLE["body"],
        hashtags=TEST_ARTICLE["hashtags"],
        as_draft=True,  # 安全のため下書き
    )

    if success:
        print("\n🎉 テスト成功！下書きに保存されました。")
    else:
        print("\n⚠️ テスト結果不明。screenshots/ を確認してください。")


if __name__ == "__main__":
    asyncio.run(main())
