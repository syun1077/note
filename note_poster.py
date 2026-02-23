"""
note.com 自動投稿 - Playwright自動化モジュール
===============================================
ブラウザ自動化でnote.comにログインし、記事を投稿します。
UI変更への耐性を強化した堅牢版。
"""

import os
import asyncio
import time
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser
from dotenv import load_dotenv
from config import (
    NOTE_LOGIN_URL,
    NOTE_NEW_POST_URL,
    PAGE_TIMEOUT,
    ACTION_TIMEOUT,
    HEADLESS,
    SLOW_MO,
    ENABLE_PAID_ARTICLE,
    ARTICLE_PRICE,
    FREE_PREVIEW_RATIO,
    ENABLE_THUMBNAIL,
)

load_dotenv()

# スクリーンショット保存先
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

# 認証状態保存先
AUTH_STATE_FILE = Path("auth_state.json")


async def take_screenshot(page: Page, name: str):
    """デバッグ用スクリーンショット"""
    try:
        path = SCREENSHOT_DIR / f"{name}.png"
        await page.screenshot(path=str(path), full_page=False)
        print(f"📸 スクリーンショット保存: {path}")
    except Exception as e:
        print(f"⚠️ スクリーンショット保存失敗: {e}")


async def _find_element(page: Page, selectors: list[str], description: str = "要素"):
    """
    複数のセレクターを試して最初に見つかった要素を返す。
    見つからない場合は None を返す。
    """
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                # 要素が可視かチェック
                first = locator.first
                if await first.is_visible():
                    print(f"   🎯 {description}検出: {selector}")
                    return first
        except Exception:
            continue
    return None


async def _safe_click(page: Page, locator, description: str = "ボタン"):
    """安全にクリックする（リトライ付き）"""
    for attempt in range(3):
        try:
            await locator.click(timeout=10000)
            print(f"   ✅ {description}をクリック")
            return True
        except Exception as e:
            if attempt < 2:
                print(f"   ⚠️ {description}クリックリトライ... ({attempt + 1}/3)")
                await page.wait_for_timeout(2000)
            else:
                print(f"   ❌ {description}クリック失敗: {e}")
                return False


async def login(page: Page) -> bool:
    """
    note.comにログインする
    
    Returns:
        bool: ログイン成功した場合True
    """
    email = os.getenv("NOTE_EMAIL")
    password = os.getenv("NOTE_PASSWORD")
    
    if not email or not password:
        raise ValueError("NOTE_EMAIL と NOTE_PASSWORD を .env ファイルに設定してください")
    
    print(f"🔑 note.com にログイン中...")
    print(f"   メール: {email[:3]}***")
    
    # ログインページへ移動
    await page.goto(NOTE_LOGIN_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT)
    await page.wait_for_timeout(3000)
    await take_screenshot(page, "01_login_page")
    
    # メールアドレス入力
    email_selectors = [
        'input[name="login"]',
        'input[placeholder*="メールアドレス"]',
        'input[placeholder*="note ID"]',
        'input[placeholder*="email"]',
        'input[type="email"]',
        'input[type="text"]',
    ]
    
    email_input = await _find_element(page, email_selectors, "メールアドレス入力欄")
    if email_input is None:
        print("   ❌ メールアドレス入力欄が見つかりませんでした")
        await take_screenshot(page, "error_no_email_input")
        return False
    
    await email_input.fill(email)
    print("   ✅ メールアドレス入力完了")
    
    # パスワード入力
    password_input = await _find_element(page, ['input[type="password"]'], "パスワード入力欄")
    if password_input is None:
        print("   ❌ パスワード入力欄が見つかりませんでした")
        await take_screenshot(page, "error_no_password_input")
        return False
    
    await password_input.fill(password)
    print("   ✅ パスワード入力完了")
    
    await take_screenshot(page, "02_login_filled")
    
    # ログインボタンクリック
    login_selectors = [
        'button:has-text("ログイン")',
        'button[type="submit"]',
        'input[type="submit"]',
    ]
    
    login_button = await _find_element(page, login_selectors, "ログインボタン")
    if login_button is None:
        print("   ❌ ログインボタンが見つかりませんでした")
        await take_screenshot(page, "error_no_login_button")
        return False
    
    await _safe_click(page, login_button, "ログインボタン")
    print("   ⏳ ログイン処理中...")
    
    # ログイン完了を待機
    try:
        await page.wait_for_url("**/", timeout=PAGE_TIMEOUT)
        await page.wait_for_timeout(3000)
    except Exception:
        await page.wait_for_timeout(5000)
    
    await take_screenshot(page, "03_after_login")
    
    # ログイン成功確認
    current_url = page.url
    if "login" in current_url.lower():
        try:
            error_el = page.locator('.o-login__error, [class*="error"], [class*="alert"]')
            if await error_el.count() > 0:
                error_text = await error_el.first.text_content()
                print(f"   ❌ ログイン失敗: {error_text}")
            else:
                print(f"   ❌ ログイン失敗: 不明なエラー")
        except Exception:
            print(f"   ❌ ログイン失敗: エラー情報の取得に失敗")
        return False
    
    print(f"   ✅ ログイン成功! (URL: {current_url})")
    
    # 認証状態を保存
    await page.context.storage_state(path=str(AUTH_STATE_FILE))
    print(f"   💾 認証状態を保存しました: {AUTH_STATE_FILE}")
    
    return True


async def _upload_thumbnail(page: Page, image_path: Path) -> bool:
    """
    サムネイル画像をアップロードする。
    note.com のエディタ上部にあるヘッダー画像エリアを操作する。

    Returns:
        bool: アップロード成功時 True
    """
    if not image_path or not image_path.exists():
        return False

    print(f"   🖼️  サムネイルをアップロード中: {image_path.name}")

    # hidden な file input に直接セット（最速・最確実）
    hidden_input_selectors = [
        'input[type="file"][accept*="image"]',
        'input[type="file"]',
    ]
    for selector in hidden_input_selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                await locator.first.set_input_files(str(image_path))
                await page.wait_for_timeout(3000)
                print("   ✅ サムネイルアップロード完了（直接セット）")
                await take_screenshot(page, "thumbnail_uploaded")
                return True
        except Exception:
            continue

    # クリックして file picker を開かせてからセット
    header_selectors = [
        '[class*="thumbnail"]',
        '[class*="cover"]',
        '[class*="headerImage"]',
        '[class*="eyecatch"]',
        'label:has-text("画像")',
        'button:has-text("画像")',
    ]
    for selector in header_selectors:
        try:
            el = page.locator(selector).first
            if await el.is_visible():
                async with page.expect_file_chooser(timeout=5000) as fc_info:
                    await el.click()
                fc = await fc_info.value
                await fc.set_files(str(image_path))
                await page.wait_for_timeout(3000)
                print("   ✅ サムネイルアップロード完了（ファイルチューザー）")
                await take_screenshot(page, "thumbnail_uploaded")
                return True
        except Exception:
            continue

    print("   ⚠️  サムネイルアップロード欄が見つかりませんでした（スキップ）")
    return False


async def post_article(page: Page, title: str, body: str, hashtags: list[str], as_draft: bool = False, thumbnail_path: Path = None) -> bool:
    """
    note.comに記事を投稿する
    
    Args:
        page: Playwrightのページ
        title: 記事タイトル
        body: 記事本文（Markdown）
        hashtags: ハッシュタグのリスト
        as_draft: Trueの場合下書き保存
        thumbnail_path: サムネイル画像ファイルのパス（省略可）

    Returns:
        bool: 投稿成功した場合True
    """
    print(f"\n📄 記事を投稿中...")
    print(f"   タイトル: {title}")

    # 記事作成ページへ移動
    await page.goto(NOTE_NEW_POST_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT)
    await page.wait_for_timeout(3000)
    await take_screenshot(page, "04_new_post_page")

    # === サムネイルアップロード ===
    if ENABLE_THUMBNAIL and thumbnail_path:
        await _upload_thumbnail(page, thumbnail_path)
    
    # === タイトル入力 ===
    title_selectors = [
        'textarea[placeholder*="タイトル"]',
        'textarea[placeholder*="記事タイトル"]',
        '[class*="title"] textarea',
        '[class*="Title"] textarea',
        'div[contenteditable="true"][class*="title"]',
        'div[contenteditable="true"][class*="Title"]',
        'textarea:first-of-type',
    ]
    
    title_input = await _find_element(page, title_selectors, "タイトル入力欄")
    if title_input is None:
        # 最終手段
        title_input = page.locator('textarea, div[contenteditable="true"]').first
        print("   ⚠️ タイトル入力欄をフォールバック検出")
    
    await title_input.click()
    await page.wait_for_timeout(500)
    await title_input.fill(title)
    await page.wait_for_timeout(1000)
    
    print("   ✅ タイトル入力完了")
    await take_screenshot(page, "05_title_filled")
    
    # === 本文入力 ===
    body_selectors = [
        'div[contenteditable="true"][class*="body"]',
        'div[contenteditable="true"][class*="Body"]',
        'div[contenteditable="true"][class*="editor"]',
        'div[contenteditable="true"][class*="Editor"]',
        'div[contenteditable="true"][class*="content"]',
        'div[contenteditable="true"][data-placeholder]',
        '[class*="noteBody"] div[contenteditable="true"]',
        'div[role="textbox"]',
    ]
    
    body_input = await _find_element(page, body_selectors, "本文入力欄")
    if body_input is None:
        # フォールバック
        all_editable = page.locator('div[contenteditable="true"]')
        count = await all_editable.count()
        if count >= 2:
            body_input = all_editable.nth(1)
            print("   ⚠️ 本文入力欄をフォールバック検出（2番目のcontenteditable）")
        elif count == 1:
            body_input = all_editable.first
            print("   ⚠️ 本文入力欄をフォールバック検出（唯一のcontenteditable）")
    
    if body_input is None:
        print("   ❌ 本文入力欄が見つかりませんでした")
        await take_screenshot(page, "error_no_body_input")
        return False
    
    # 本文を入力（段落ごと）
    await body_input.click()
    await page.wait_for_timeout(500)
    
    # 有料記事のマーカーを処理
    body_parts = body.split("---ここから有料---")
    free_body = body_parts[0] if len(body_parts) > 1 else body
    paid_body = body_parts[1] if len(body_parts) > 1 else None
    
    # 無料パートを入力
    paragraphs = free_body.split("\n")
    for i, paragraph in enumerate(paragraphs):
        if paragraph.strip():
            await page.keyboard.type(paragraph, delay=10)
        await page.keyboard.press("Enter")
        
        if i > 0 and i % 50 == 0:
            print(f"   📝 本文入力中... {i}/{len(paragraphs)} 行")
    
    # 有料パートがある場合
    if paid_body and ENABLE_PAID_ARTICLE:
        print("   💰 有料パート入力中...")
        paid_paragraphs = paid_body.split("\n")
        for i, paragraph in enumerate(paid_paragraphs):
            if paragraph.strip():
                await page.keyboard.type(paragraph, delay=10)
            await page.keyboard.press("Enter")
    
    total_lines = len(free_body.split("\n")) + (len(paid_body.split("\n")) if paid_body else 0)
    print(f"   ✅ 本文入力完了 ({total_lines} 行)")
    await page.wait_for_timeout(2000)
    await take_screenshot(page, "06_body_filled")
    
    # === ハッシュタグ入力 ===
    if hashtags:
        await _add_hashtags(page, hashtags)
    
    # === 公開 or 下書き保存 ===
    if as_draft:
        success = await _save_as_draft(page)
    else:
        success = await _publish(page, hashtags=hashtags)
    
    return success


async def _add_hashtags(page: Page, hashtags: list[str]):
    """ハッシュタグを追加"""
    print(f"   🏷️ ハッシュタグ追加中: {', '.join(hashtags)}")
    
    tag_selectors = [
        'input[placeholder*="タグ"]',
        'input[placeholder*="ハッシュタグ"]',
        '[class*="tag"] input',
        '[class*="Tag"] input',
        '[class*="hashtag"] input',
    ]
    
    tag_input = await _find_element(page, tag_selectors, "タグ入力欄")
    
    if tag_input is None:
        print("   ⚠️ タグ入力欄がまだ表示されていません（公開設定画面で入力します）")
        return
    
    for tag in hashtags[:5]:
        await tag_input.fill(tag)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(500)
    
    print(f"   ✅ ハッシュタグ追加完了")
    await take_screenshot(page, "07_hashtags_added")


async def _publish(page: Page, hashtags: list[str] = None) -> bool:
    """記事を公開する"""
    print("   🚀 記事を公開中...")

    # APIエラーを監視
    api_errors: list[str] = []

    async def _on_response(response):
        if "publish" in response.url and response.status >= 400:
            api_errors.append(f"HTTP {response.status}: {response.url}")

    page.on("response", _on_response)

    try:
        # 「公開」ボタンをクリック（/publish/ ページへ遷移）
        publish_button_selectors = [
            'button:has-text("公開設定")',
            'button:has-text("公開")',
            '[class*="publish"] button',
            '[class*="Publish"] button',
        ]

        publish_button = await _find_element(page, publish_button_selectors, "公開設定ボタン")
        if publish_button:
            await _safe_click(page, publish_button, "公開設定ボタン")
            # /publish/ ページへ遷移するまで待つ
            try:
                await page.wait_for_url("**/publish/**", timeout=8000)
            except Exception:
                pass
            # ページが完全に読み込まれるまで待つ
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)
            await take_screenshot(page, "08_publish_dialog")

        # 公開設定ページでハッシュタグを入力（keyboard.typeでReact状態を正しく更新）
        if hashtags:
            tag_input_dialog = page.locator(
                'input[placeholder*="タグ"], input[placeholder*="ハッシュタグ"], input[placeholder*="tag"]'
            )
            if await tag_input_dialog.count() > 0:
                print("   🏷️ 公開設定ページでタグを入力中...")
                tag_input = tag_input_dialog.first
                for tag in hashtags[:5]:
                    await tag_input.click()
                    await tag_input.fill("")
                    await page.keyboard.type(tag, delay=30)
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(500)
                # タグ入力欄からフォーカスを外す
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)
                print("   ✅ タグ入力完了")
            else:
                print("   ⚠️ タグ入力欄が見つかりませんでした（スキップ）")

        # 有料記事の価格設定（有効な場合）
        if ENABLE_PAID_ARTICLE:
            await _set_paid_article(page)

        # 本人確認モーダルなどを閉じる
        await _close_identification_modal(page)

        # クリック前スクリーンショット（デバッグ用）
        await take_screenshot(page, "08c_before_final_click")

        # 全ネットワーク活動を記録（診断用）
        all_publish_requests: list[str] = []
        async def _on_any_response(response):
            if "note.com" in response.url and response.status in (200, 201):
                if any(k in response.url for k in ("publish", "note", "create")):
                    all_publish_requests.append(f"HTTP {response.status}: {response.url}")
        page.on("response", _on_any_response)

        # 最終「投稿する」ボタン: dispatch_event で確実にクリック
        final_publish_selectors = [
            'button:has-text("投稿する")',
            'button:has-text("公開する")',
            'button[class*="submit"]',
            'button[class*="Submit"]',
        ]

        final_button = await _find_element(page, final_publish_selectors, "最終公開ボタン")
        if final_button:
            # 1. 通常クリック
            await _safe_click(page, final_button, "最終公開ボタン")
            await page.wait_for_timeout(500)
            # 2. dispatchEvent（ポインターイベントをバイパス）
            print("   → dispatchEvent クリックも実行...")
            try:
                await final_button.dispatch_event("click")
            except Exception:
                pass
        else:
            print("   ⚠️ 最終公開ボタンが見つかりませんでした")

        # ネットワーク処理の完了を待つ
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # URL が /publish/ から遷移するまで最大20秒待つ
        try:
            await page.wait_for_url(
                lambda url: "/publish/" not in url and "/notes/new" not in url,
                timeout=20000,
            )
            print("   ✅ ページ遷移を確認")
        except Exception:
            print("   ⚠️ 20秒以内にページ遷移が確認できませんでした")

            # Toast/alert 系エラーのみ検出（テキストが5文字以上のもの）
            try:
                for sel in ['[role="alert"]', '[class*="Toast"]', '[class*="toast"]']:
                    el = page.locator(sel)
                    if await el.count() > 0:
                        txt = (await el.first.text_content() or "").strip()
                        if len(txt) >= 5:
                            print(f"   ⚠️ 通知メッセージ: {txt}")
                            break
            except Exception:
                pass

        # 診断: ネットワークリクエストを表示
        page.remove_listener("response", _on_any_response)
        if all_publish_requests:
            for req in all_publish_requests[:5]:
                print(f"   📡 {req}")
        else:
            print("   📡 投稿関連のネットワークリクエストが検出されませんでした")

        # APIエラーがあれば表示
        if api_errors:
            for err in api_errors:
                print(f"   ⚠️ APIエラー: {err}")

        await take_screenshot(page, "09_published")

        # 投稿成功確認
        current_url = page.url
        if "/publish/" in current_url or "/notes/new" in current_url or current_url.endswith("/edit"):
            print(f"   ⚠️ 公開結果が不明です。URL: {current_url}")
            return False
        else:
            print(f"   ✅ 記事公開成功! URL: {current_url}")
            return True

    finally:
        page.remove_listener("response", _on_response)


async def _close_identification_modal(page: Page) -> bool:
    """本人確認モーダルが出ていれば Escape で閉じる"""
    try:
        modal = page.locator('[class*="IdentificationModal"]')
        if await modal.count() > 0:
            print("   ⚠️ 本人確認モーダルを検出。閉じます...")
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1500)
            return True
    except Exception:
        pass
    return False


async def _set_paid_article(page: Page):
    """有料記事の価格を設定する"""
    print(f"   💰 有料記事設定中（価格: ¥{ARTICLE_PRICE}）...")

    # 有料設定のトグル/チェックボックスを探す
    paid_selectors = [
        'label:has-text("有料")',
        'button:has-text("有料")',
        '[class*="paid"] input',
        '[class*="price"] input',
        'input[name*="price"]',
    ]

    paid_toggle = await _find_element(page, paid_selectors, "有料設定")
    if paid_toggle:
        await _safe_click(page, paid_toggle, "有料設定トグル")
        await page.wait_for_timeout(1500)

        # 本人確認モーダルが出た場合は閉じてスキップ
        if await _close_identification_modal(page):
            print("   ⚠️ 本人確認が必要なため有料設定をスキップします（無料記事として投稿）")
            await take_screenshot(page, "08b_paid_settings")
            return

        # 価格入力欄を探す
        price_selectors = [
            'input[type="number"]',
            'input[placeholder*="価格"]',
            'input[placeholder*="円"]',
            'input[name*="price"]',
        ]

        price_input = await _find_element(page, price_selectors, "価格入力欄")
        if price_input:
            await price_input.fill(str(ARTICLE_PRICE))
            print(f"   ✅ 価格設定完了: ¥{ARTICLE_PRICE}")
        else:
            print("   ⚠️ 価格入力欄が見つかりませんでした")
    else:
        print("   ⚠️ 有料設定が見つかりませんでした（UIを確認してください）")

    await take_screenshot(page, "08b_paid_settings")


async def _save_as_draft(page: Page) -> bool:
    """下書き保存する"""
    print("   💾 下書き保存中...")
    
    draft_selectors = [
        'button:has-text("下書き保存")',
        'button:has-text("下書き")',
        '[class*="draft"] button',
    ]
    
    draft_button = await _find_element(page, draft_selectors, "下書き保存ボタン")
    if draft_button:
        await _safe_click(page, draft_button, "下書き保存ボタン")
    else:
        print("   ⚠️ 下書き保存ボタンが見つかりませんでした")
        await take_screenshot(page, "error_no_draft_button")
        return False
    
    await page.wait_for_timeout(3000)
    await take_screenshot(page, "09_draft_saved")
    print("   ✅ 下書き保存完了")
    return True


async def run_post(
    title: str,
    body: str,
    hashtags: list[str],
    as_draft: bool = False,
    thumbnail_path: Path = None,
) -> bool:
    """
    メイン実行関数: ブラウザを起動してログイン→投稿を行う

    Args:
        title: 記事タイトル
        body: 記事本文
        hashtags: ハッシュタグリスト
        as_draft: Trueなら下書き保存
        thumbnail_path: サムネイル画像のパス（省略可）

    Returns:
        bool: 成功した場合True
    """
    async with async_playwright() as p:
        # ブラウザ起動設定
        launch_args = {
            "headless": HEADLESS,
            "slow_mo": SLOW_MO,
        }
        
        browser = await p.chromium.launch(**launch_args)
        
        # 認証状態があれば再利用
        context_args = {
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        
        if AUTH_STATE_FILE.exists():
            print("🔄 保存された認証状態を使用してログインをスキップ...")
            context_args["storage_state"] = str(AUTH_STATE_FILE)
        
        context = await browser.new_context(**context_args)
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        
        try:
            # 認証状態がない場合、ログインを実行
            if not AUTH_STATE_FILE.exists():
                login_success = await login(page)
                if not login_success:
                    print("❌ ログイン失敗のため処理を中断します")
                    return False
            else:
                # 認証状態があっても有効か確認
                await page.goto("https://note.com/", wait_until="networkidle", timeout=PAGE_TIMEOUT)
                await page.wait_for_timeout(2000)
                
                login_link = page.locator('a[href="/login"], a:has-text("ログイン")')
                if await login_link.count() > 0:
                    print("⚠️ 認証状態が無効です。再ログインします...")
                    AUTH_STATE_FILE.unlink(missing_ok=True)
                    login_success = await login(page)
                    if not login_success:
                        print("❌ 再ログイン失敗のため処理を中断します")
                        return False
                else:
                    print("✅ 認証状態は有効です")
            
            # 記事投稿
            success = await post_article(page, title, body, hashtags, as_draft, thumbnail_path)
            return success
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            await take_screenshot(page, "error_exception")
            raise
        finally:
            await browser.close()
