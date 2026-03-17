"""
note.com 完全自動投稿 - メインスクリプト
========================================
AI記事生成 → SEOチェック → サムネイル生成 → note.com投稿 → 通知
複数アカウントへの同時投稿にも対応。

使い方:
    python main.py              # 通常実行（公開）
    python main.py --draft      # 下書き保存
    python main.py --theme "AI" # テーマ指定
    python main.py --stats      # 投稿統計を表示
    python main.py --headless   # ヘッドレスモード
    python main.py --no-thumbnail  # サムネイル生成スキップ
    python main.py --no-notify     # 通知スキップ
"""

import asyncio
import argparse
import os
import sys
import traceback
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def _get_accounts() -> list[dict]:
    """
    環境変数から投稿アカウントの一覧を取得する。

    単一アカウント: NOTE_EMAIL / NOTE_PASSWORD
    複数アカウント: NOTE_EMAIL_1/NOTE_PASSWORD_1, NOTE_EMAIL_2/NOTE_PASSWORD_2, ...
    """
    accounts = []

    # 複数アカウント（NOTE_EMAIL_1, NOTE_EMAIL_2, ...）
    idx = 1
    while True:
        email = os.getenv(f"NOTE_EMAIL_{idx}")
        password = os.getenv(f"NOTE_PASSWORD_{idx}")
        if not email or not password:
            break
        accounts.append({"email": email, "password": password, "index": idx})
        idx += 1

    # 単一アカウント（従来互換）
    if not accounts:
        email = os.getenv("NOTE_EMAIL")
        password = os.getenv("NOTE_PASSWORD")
        if email and password:
            accounts.append({"email": email, "password": password, "index": 0})

    return accounts


def main():
    parser = argparse.ArgumentParser(description="note.com 完全自動投稿ツール")
    parser.add_argument("--draft", action="store_true", help="下書き保存モード")
    parser.add_argument("--theme", type=str, default=None, help="記事のテーマを指定")
    parser.add_argument("--headless", action="store_true", help="ヘッドレスモードで実行")
    parser.add_argument("--stats", action="store_true", help="投稿統計を表示して終了")
    parser.add_argument("--no-thumbnail", action="store_true", help="サムネイル生成をスキップ")
    parser.add_argument("--no-notify", action="store_true", help="通知を送信しない")
    args = parser.parse_args()

    # 統計表示モード
    if args.stats:
        from post_history import print_stats
        print_stats()
        sys.exit(0)

    print("=" * 60)
    print("🚀 note.com 完全自動投稿ツール")
    print(f"📅 実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📝 モード: {'下書き保存' if args.draft else '公開'}")
    print("=" * 60)

    # 環境変数チェック
    if not os.getenv("GROQ_API_KEY"):
        print("\n❌ エラー: GROQ_API_KEY が設定されていません")
        print("   .env ファイルを作成して設定してください")
        sys.exit(1)

    accounts = _get_accounts()
    if not accounts:
        print("\n❌ エラー: NOTE_EMAIL / NOTE_PASSWORD が設定されていません")
        print("   .env ファイルを作成して設定してください")
        sys.exit(1)

    print(f"\n👥 投稿アカウント数: {len(accounts)}")
    for acc in accounts:
        prefix = f"[{acc['index']}] " if acc["index"] else ""
        print(f"   {prefix}{acc['email'][:4]}***")

    # ヘッドレスモード設定
    if args.headless:
        import config
        config.HEADLESS = True
        config.SLOW_MO = 0  # ヘッドレスでは遅延不要

    # 投稿履歴の確認
    from post_history import get_used_themes, add_record, print_stats
    used_themes = get_used_themes()
    if used_themes:
        print(f"\n📚 これまでに {len(used_themes)} 個のテーマで投稿済み")

    # ────────────────────────────────────────────────
    # Step 1: AI記事生成
    # ────────────────────────────────────────────────
    print("\n" + "-" * 40)
    print("📖 Step 1: AI記事生成")
    print("-" * 40)

    from article_generator import generate_article
    selected_theme = args.theme

    try:
        article = generate_article(theme=selected_theme, used_themes=used_themes)
    except Exception as e:
        print(f"❌ 記事生成に失敗しました: {e}")
        traceback.print_exc()
        add_record(
            theme=selected_theme or "ランダム",
            title="(生成失敗)",
            success=False,
            error=str(e),
        )
        sys.exit(1)

    print(f"\n📋 生成された記事:")
    print(f"   タイトル: {article['title']}")
    print(f"   文字数:   {len(article['body'])}文字")
    print(f"   タグ:     {', '.join(article['hashtags'])}")

    # ────────────────────────────────────────────────
    # Step 2: SEOスコアチェック
    # ────────────────────────────────────────────────
    print("\n" + "-" * 40)
    print("🔍 Step 2: SEOスコアチェック")
    print("-" * 40)

    from seo_checker import check_seo, print_seo_report
    seo = check_seo(article["title"], article["body"], article["hashtags"])
    print_seo_report(seo)

    if seo["score"] < 40:
        print("   ⚠️  SEOスコアが低めです。記事テーマを見直すことを推奨します。")

    # ────────────────────────────────────────────────
    # Step 3: サムネイル生成
    # ────────────────────────────────────────────────
    from config import ENABLE_THUMBNAIL
    thumbnail_path = None

    if ENABLE_THUMBNAIL and not args.no_thumbnail:
        print("\n" + "-" * 40)
        print("🖼️  Step 3: サムネイル生成")
        print("-" * 40)
        from thumbnail_generator import generate_thumbnail
        thumbnail_path = generate_thumbnail(
            title=article["title"],
            theme=article.get("theme", ""),
        )
        if not thumbnail_path:
            print("   ⚠️  サムネイルなしで続行します")
    else:
        print("\n⏭️  Step 3: サムネイル生成 (スキップ)")

    # ────────────────────────────────────────────────
    # Step 4: note.comへ投稿（複数アカウント対応）
    # ────────────────────────────────────────────────
    print("\n" + "-" * 40)
    print(f"📤 Step 4: note.comに投稿 ({len(accounts)}アカウント)")
    print("-" * 40)

    from note_poster import run_post
    import note_poster as _np
    from pathlib import Path

    as_draft = args.draft or os.getenv("POST_AS_DRAFT", "false").lower() == "true"

    all_success = True
    results = []

    for acc in accounts:
        label = f"[{acc['index']}] " if acc["index"] else ""
        print(f"\n{label}📤 {acc['email'][:4]}*** に投稿中...")

        # 環境変数を一時的にこのアカウントのものに差し替える
        orig_email = os.environ.get("NOTE_EMAIL")
        orig_pass = os.environ.get("NOTE_PASSWORD")
        os.environ["NOTE_EMAIL"] = acc["email"]
        os.environ["NOTE_PASSWORD"] = acc["password"]

        # 複数アカウントの場合は認証状態ファイルを分ける
        orig_auth_file = _np.AUTH_STATE_FILE
        if acc["index"]:
            _np.AUTH_STATE_FILE = Path(f"auth_state_{acc['index']}.json")

        try:
            success = asyncio.run(
                run_post(
                    title=article["title"],
                    body=article["body"],
                    hashtags=article["hashtags"],
                    as_draft=as_draft,
                    thumbnail_path=thumbnail_path,
                )
            )
        except Exception as e:
            print(f"❌ 投稿に失敗しました: {e}")
            traceback.print_exc()
            success = False
            add_record(
                theme=article.get("theme", selected_theme or "ランダム"),
                title=article["title"],
                success=False,
                as_draft=as_draft,
                error=str(e),
            )
        finally:
            # 環境変数・認証ファイルを元に戻す
            if orig_email is not None:
                os.environ["NOTE_EMAIL"] = orig_email
            elif "NOTE_EMAIL" in os.environ:
                del os.environ["NOTE_EMAIL"]
            if orig_pass is not None:
                os.environ["NOTE_PASSWORD"] = orig_pass
            elif "NOTE_PASSWORD" in os.environ:
                del os.environ["NOTE_PASSWORD"]
            _np.AUTH_STATE_FILE = orig_auth_file

        add_record(
            theme=article.get("theme", selected_theme or "ランダム"),
            title=article["title"],
            success=success,
            as_draft=as_draft,
            seo_score=seo.get("score"),
            persona=article.get("persona"),
        )
        results.append((acc["email"], success))
        if not success:
            all_success = False

    # ────────────────────────────────────────────────
    # Step 5: 通知を送信
    # ────────────────────────────────────────────────
    if not args.no_notify:
        from notifier import send_notification
        send_notification(
            title=article["title"],
            success=all_success,
            error=None if all_success else "一部アカウントで投稿失敗",
        )

    # ────────────────────────────────────────────────
    # 結果表示
    # ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("📊 投稿結果:")
    for email, ok in results:
        status = "✅ 成功" if ok else "❌ 失敗"
        print(f"   {status}  {email[:4]}***")

    if all_success:
        print("\n🎉 全アカウントへの投稿が完了しました!")
    else:
        print("\n⚠️  一部の投稿に失敗しました。screenshots/ フォルダを確認してください。")
    print("=" * 60)

    print_stats()

    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
