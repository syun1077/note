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
            error_msg = str(e)
            if "intercepts pointer events" in error_msg:
                print(f"   ⚠️ モーダルがポインタをブロック → クロップ解除を試みます")
                await _dismiss_crop_dialog(page)
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1500)
                # モーダル解除直後に即リトライ（attemptカウントとは独立）
                try:
                    await locator.click(timeout=10000)
                    print(f"   ✅ {description}をクリック（モーダル解除後）")
                    return True
                except Exception:
                    pass
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


async def _dismiss_crop_dialog(page: Page) -> bool:
    """
    CropModal を全フレームで探して閉じる。
    note.com は ReactModalPortal を iframe 内に表示する可能性があるため
    page.frames で全フレームを検索する（メインフレームのみでは見つからない場合がある）。
    """
    all_frames = page.frames

    # デバッグ: フレーム数をログ
    if len(all_frames) > 1:
        urls = ", ".join(f.url[:40] for f in all_frames if f.url)
        print(f"   🔍 フレーム数: {len(all_frames)} ({urls})")

    for frame in all_frames:
        # --- Strategy A: JS（そのフレームのコンテキストで実行） ---
        try:
            clicked = await frame.evaluate("""
                () => {
                    const modal = document.querySelector('.CropModal__overlay')
                                 || document.querySelector('.ReactModal__Overlay--after-open');
                    if (!modal) return null;
                    const btns = Array.from(modal.querySelectorAll('button'));
                    const target = btns.find(b => /完了|保存|OK|適用|確定/.test(b.textContent || ''))
                                 || (btns.length ? btns[btns.length - 1] : null);
                    if (target) { target.click(); return target.textContent.trim(); }
                    return null;
                }
            """)
            if clicked:
                label = (frame.url or "main")[:40]
                print(f"   ✅ クロップ確認（frame: {label}, JS: {clicked}）")
                await page.wait_for_timeout(2000)
                return True
        except Exception:
            pass

        # --- Strategy B: Playwright locator（そのフレームにスコープ） ---
        for modal_sel in ['.CropModal__overlay', '.ReactModal__Overlay--after-open']:
            try:
                modal = frame.locator(modal_sel)
                if await modal.count() > 0:
                    label = (frame.url or "main")[:40]
                    print(f"   🔧 モーダル検出（frame: {label}, {modal_sel}）")
                    await take_screenshot(page, "crop_modal_detected")
                    # button と [role="button"] 両方を対象にテキストで探す
                    btn_sel_base = 'button, [role="button"]'
                    for text in ["保存", "完了", "OK", "適用", "確定", "そのまま", "使用"]:
                        btn = modal.locator(f'{btn_sel_base}').filter(has_text=text).first
                        if await btn.count() > 0:
                            await btn.click(force=True)
                            print(f"   ✅ クロップ確認（locator: {text}）")
                            await page.wait_for_timeout(2000)
                            return True
                    # テキストマッチなし → 最後のボタンをクリック
                    all_btns = modal.locator(btn_sel_base)
                    n = await all_btns.count()
                    print(f"   🔍 モーダル内ボタン数: {n}")
                    if n > 0:
                        # ボタンテキストをログ
                        for bi in range(n):
                            t = (await all_btns.nth(bi).text_content() or "").strip()
                            print(f"      [{bi}] '{t}'")
                        await all_btns.nth(n - 1).click(force=True)
                        print(f"   ✅ クロップ確認（last button）")
                        await page.wait_for_timeout(2000)
                        return True
            except Exception as ex:
                print(f"   ⚠️ Strategy B 例外: {ex}")

    return False


async def _insert_image(page: Page, image_path: Path) -> bool:
    """
    エディタのカーソル位置に画像をインライン挿入する。
    複数の方法を試みて、成功したら True を返す。
    """
    print(f"   🖼️  画像挿入中: {image_path.name}")

    # 前の画像のクロップダイアログが残っていれば先に閉じる
    await _dismiss_crop_dialog(page)

    # カーソルを新しい行へ移動
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(800)

    # Strategy 1: note.com の floating + ボタン → 画像メニュー
    # クラス名 sc-ebe7c9bf（浮動追加ボタン）or sc-fd3d5259（インラインツールバー）
    note_plus_selectors = [
        'button[class*="sc-ebe7c9bf"]',  # 浮動 + ボタン（w≈48）
        'button[class*="sc-fd3d5259"]',  # インラインツールバー + ボタン
    ]
    for sel in note_plus_selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                async with page.expect_file_chooser(timeout=8000) as fc_info:
                    await el.click(force=True)
                    await page.wait_for_timeout(600)
                    # + メニューから「画像」を選択
                    img_menu = page.locator('button:has-text("画像")').first
                    if await img_menu.is_visible(timeout=3000):
                        await img_menu.click()
                fc = await fc_info.value
                await fc.set_files(str(image_path))
                # ファイル設定直後のスクリーンショット（タイミング確認用）
                await page.wait_for_timeout(1500)
                await take_screenshot(page, f"crop_check_{image_path.stem}")
                # クロップダイアログをポーリングで検出（2秒ごと、最大16秒）
                dismissed = False
                for _attempt in range(8):
                    if await _dismiss_crop_dialog(page):
                        dismissed = True
                        print(f"   ✅ クロップを{(_attempt+1)*2}秒後に閉じました")
                        break
                    if _attempt < 7:
                        print(f"   ⌛ クロップ待機... {(_attempt+1)*2}s/16s")
                        await page.wait_for_timeout(2000)
                if not dismissed:
                    print("   ℹ️ クロップダイアログなし（続行）")
                await take_screenshot(page, f"img_{image_path.stem}")
                print(f"   ✅ 画像挿入完了（+ボタン経由）")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)
                return True
        except Exception:
            pass

    # Strategy 2: hidden な file input に直接セット
    for selector in [
        'input[type="file"][accept*="image"]',
        'input[type="file"]',
    ]:
        locator = page.locator(selector)
        if await locator.count() > 0:
            try:
                await locator.first.set_input_files(str(image_path))
                await page.wait_for_timeout(4000)
                await take_screenshot(page, f"img_{image_path.stem}")
                print(f"   ✅ 画像挿入完了（hidden input）")
                await page.keyboard.press("Enter")
                return True
            except Exception:
                pass

    # Strategy 3: ツールバーの画像ボタン
    toolbar_img_selectors = [
        'button[aria-label="画像"]',
        'button[title="画像"]',
        '[class*="toolbar"] button[class*="image"]',
        '[class*="toolbar"] button[class*="Image"]',
    ]
    for sel in toolbar_img_selectors:
        el = page.locator(sel).first
        try:
            if await el.is_visible(timeout=2000):
                async with page.expect_file_chooser(timeout=5000) as fc_info:
                    await el.click()
                fc = await fc_info.value
                await fc.set_files(str(image_path))
                await page.wait_for_timeout(4000)
                await take_screenshot(page, f"img_{image_path.stem}")
                print(f"   ✅ 画像挿入完了（ツールバー経由）")
                await page.keyboard.press("Enter")
                return True
        except Exception:
            pass

    await take_screenshot(page, f"img_failed_{image_path.stem}")
    print(f"   ⚠️ 画像挿入をスキップしました（UIが見つかりませんでした）")
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

    # 画像マーカーを事前にダウンロード
    from image_fetcher import fetch_images_for_article, IMAGE_MARKER_PATTERN
    article_images = fetch_images_for_article(body)

    # デバッグ: article_images のキー確認
    print(f"   🔍 画像キー: {list(article_images.keys())}")

    async def _type_paragraphs(text: str):
        """段落を入力し、[IMAGE:keyword] マーカーで画像を挿入する"""
        paragraphs = text.split("\n")
        for i, paragraph in enumerate(paragraphs):
            stripped = paragraph.strip()
            # 画像マーカーを search() で行内のどこでも検出
            img_match = IMAGE_MARKER_PATTERN.search(stripped)
            if img_match:
                keyword = img_match.group(1).strip()
                img_path = article_images.get(keyword)
                print(f"   🔍 マーカー検出: '{keyword}' → {img_path}")
                if img_path:
                    await _insert_image(page, img_path)
                continue  # マーカー行は Enter しない
            if stripped:
                await page.keyboard.type(paragraph, delay=10)
            await page.keyboard.press("Enter")
            if i > 0 and i % 50 == 0:
                print(f"   📝 本文入力中... {i}/{len(paragraphs)} 行")

    # 有料記事モードの場合: 無料パート → 有料パートに分けて入力
    # 無料記事モードの場合: 全体を入力（---ここから有料---マーカーは除去）
    if ENABLE_PAID_ARTICLE and "---ここから有料---" in body:
        body_parts = body.split("---ここから有料---")
        free_body = body_parts[0]
        paid_body = body_parts[1]
        await _type_paragraphs(free_body)
        print("   💰 有料パート入力中...")
        await _type_paragraphs(paid_body)
        total_lines = len(free_body.split("\n")) + len(paid_body.split("\n"))
    else:
        # 有料マーカーを取り除いて全文を投稿
        full_body = body.replace("---ここから有料---", "")
        await _type_paragraphs(full_body)
        total_lines = len(full_body.split("\n"))

    print(f"   ✅ 本文入力完了 ({total_lines} 行)")
    # 残っているクロップダイアログを全て閉じる
    await _dismiss_crop_dialog(page)
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

    # ネットワーク監視（最初から全て1つのリスナーで管理）
    api_errors: list[str] = []
    published_via_api: list[str] = []   # draft=false API 成功 → 公開確定
    all_publish_requests: list[str] = []

    async def _on_response(response):
        url = response.url
        status = response.status
        if "note.com" not in url:
            return
        if status >= 400 and "publish" in url:
            api_errors.append(f"HTTP {status}: {url}")
        if status in (200, 201):
            if any(k in url for k in ("publish", "notes/n", "create")):
                all_publish_requests.append(f"HTTP {status}: {url}")
            # draft=false → 記事が公開されたことを意味する
            if "draft=false" in url:
                published_via_api.append(url)
                print(f"   ✅ 公開API検出 (draft=false → 200)")

    page.on("response", _on_response)

    try:
        # 公開前にクロップダイアログが残っていれば閉じる
        await _dismiss_crop_dialog(page)
        await page.wait_for_timeout(500)

        # 「公開」ボタンをクリック（/publish/ ページへ遷移 or モーダル表示）
        # note.com UI バリエーション: 「公開設定」「公開に進む」「公開」
        publish_button_selectors = [
            'button:has-text("公開設定")',
            'button:has-text("公開に進む")',
            'button:has-text("公開")',
            '[class*="publish"] button',
            '[class*="Publish"] button',
        ]

        publish_button = await _find_element(page, publish_button_selectors, "公開設定ボタン")
        if publish_button:
            await _safe_click(page, publish_button, "公開設定ボタン")
            # URL 遷移 or モーダル表示を待つ
            try:
                await page.wait_for_url("**/publish/**", timeout=5000)
            except Exception:
                pass
            # モーダルが開いた場合も考慮して待機
            await page.wait_for_timeout(2000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            await take_screenshot(page, "08_publish_dialog")

        # ページ上のボタンを全て確認（デバッグ）
        try:
            btn_texts = []
            for b in await page.locator("button").all():
                t = (await b.text_content() or "").strip()
                if t:
                    btn_texts.append(t)
            if btn_texts:
                print(f"   📋 /publish/ ページのボタン: {btn_texts[:15]}")
        except Exception:
            pass

        # 公開設定ページでハッシュタグを入力
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
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)
                print("   ✅ タグ入力完了")
            else:
                print("   ⚠️ タグ入力欄が見つかりませんでした（スキップ）")

        # 有料記事の価格設定（有効な場合）
        if ENABLE_PAID_ARTICLE:
            await _set_paid_article(page)

        # 本人確認モーダルを閉じる
        await _close_identification_modal(page)

        # 有料設定後のボタン一覧をデバッグ
        try:
            btn_texts_after = []
            for b in await page.locator("button").all():
                t = (await b.text_content() or "").strip()
                if t:
                    btn_texts_after.append(t)
            print(f"   📋 有料設定後のボタン: {btn_texts_after[:20]}")
        except Exception:
            pass
        await take_screenshot(page, "08c_before_final_click")

        # 最終「投稿する」ボタン（拡張セレクタ）
        # note.com の UI バリエーション: 「投稿する」「公開する」「公開に進む」等
        final_publish_selectors = [
            'button:has-text("投稿する")',
            'button:has-text("公開する")',
            'button:has-text("今すぐ公開する")',
            'button:has-text("今すぐ公開")',
            'button:has-text("公開に進む")',
            'button:has-text("確定する")',
            'button[class*="submit"]',
            'button[class*="Submit"]',
            'button[type="submit"]',
        ]

        # 有料設定時「有料エリア設定」ボタンが出る場合
        # → エディタに戻って有料エリアを確定 → 再度「公開に進む」→「投稿する」
        if ENABLE_PAID_ARTICLE:
            paid_area_btn = page.locator('button:has-text("有料エリア設定")').first
            if await paid_area_btn.count() > 0:
                print("   💰 有料エリア設定ボタンをクリック（エディタへ戻る）...")
                await paid_area_btn.click(force=True)
                await page.wait_for_timeout(4000)
                await take_screenshot(page, "08d_paid_area_editor")

                # エディタ上で有料エリア確定ボタンを探す
                confirm_selectors = [
                    'button:has-text("確認")',
                    'button:has-text("設定する")',
                    'button:has-text("ここを有料にする")',
                    'button:has-text("有料エリアを設定")',
                    'button:has-text("決定")',
                ]
                confirm_btn = await _find_element(page, confirm_selectors, "有料エリア確認ボタン")
                if confirm_btn:
                    await _safe_click(page, confirm_btn, "有料エリア確認")
                    await page.wait_for_timeout(2000)

                # エディタから再度「公開に進む」をクリック
                publish_again_selectors = [
                    'button:has-text("公開設定")',
                    'button:has-text("公開に進む")',
                    'button:has-text("公開")',
                ]
                publish_again = await _find_element(page, publish_again_selectors, "公開設定ボタン(再)")
                if publish_again:
                    print("   🔄 公開設定を再クリック...")
                    await _safe_click(page, publish_again, "公開設定ボタン(再)")
                    try:
                        await page.wait_for_url("**/publish/**", timeout=8000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(2000)

                    # 有料設定を再適用（価格が消えている場合のみ）
                    price_check = page.locator('input[type="number"]')
                    if await price_check.count() == 0:
                        await _set_paid_article(page)
                    await take_screenshot(page, "08e_republish_page")

        # ページ先頭にスクロールしてボタンを表示させる
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

        # 最終「投稿する」ボタンをクリック
        final_button = await _find_element(page, final_publish_selectors, "最終公開ボタン")
        if final_button:
            await _safe_click(page, final_button, "最終公開ボタン")
            await page.wait_for_timeout(500)
        else:
            # JavaScriptで直接クリック
            print("   ⚠️ 最終公開ボタンが見つかりませんでした（JS クリック試行）")
            clicked = await page.evaluate("""
                () => {
                    const texts = ['投稿する', '公開する', '今すぐ公開する', '今すぐ公開', '確定する'];
                    const btns = Array.from(document.querySelectorAll('button'));
                    const btn = btns.find(b => texts.includes((b.textContent || '').trim()));
                    if (btn) { btn.click(); return btn.textContent.trim(); }
                    return null;
                }
            """)
            if clicked:
                print(f"   ✅ JS クリック成功: {clicked}")
            else:
                print("   ❌ 投稿ボタンが見つかりませんでした")

        # ネットワーク処理完了を待つ
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # APIベースで再確認
        if published_via_api:
            print(f"   ✅ 記事が公開されました（API確認）")
            await take_screenshot(page, "09_published")
            return True

        # URL変化で確認
        try:
            await page.wait_for_url(
                lambda url: "/publish/" not in url and "/notes/new" not in url,
                timeout=20000,
            )
            print("   ✅ ページ遷移を確認")
        except Exception:
            print("   ⚠️ 20秒以内にページ遷移が確認できませんでした")

        if all_publish_requests:
            for req in all_publish_requests[:5]:
                print(f"   📡 {req}")
        if api_errors:
            for err in api_errors:
                print(f"   ⚠️ APIエラー: {err}")

        await take_screenshot(page, "09_published")

        current_url = page.url
        if "/publish/" in current_url or "/notes/new" in current_url or "/edit" in current_url:
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

        # 価格入力欄を探す（有料ラジオ選択後に表示される）
        # wait_for_selector で確実に待つ
        price_input = None
        try:
            await page.wait_for_selector(
                'input[type="number"], input[placeholder*="価格"], input[placeholder*="円"]',
                timeout=5000
            )
        except Exception:
            pass

        price_selectors = [
            'input[type="number"]',
            'input[placeholder*="価格"]',
            'input[placeholder*="円"]',
            'input[name*="price"]',
        ]
        price_input = await _find_element(page, price_selectors, "価格入力欄")
        if price_input:
            await price_input.click()
            await page.keyboard.press("Control+a")
            await price_input.fill(str(ARTICLE_PRICE))
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(500)
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
            "bypass_csp": True,  # note.com の CSP による eval ブロックを回避
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
