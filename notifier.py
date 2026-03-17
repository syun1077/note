"""
note.com 自動投稿 - 通知モジュール
====================================
投稿結果を Discord / LINE Notify に通知します。
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()


def _notify_discord(title: str, success: bool, article_url: str = None, error: str = None):
    """Discord Webhook に通知"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return

    if success:
        color = 0x00C896  # 緑
        header = "✅ note記事を投稿しました"
        description = f"**{title}**"
        if article_url:
            description += f"\n[記事を見る]({article_url})"
    else:
        color = 0xFF4444  # 赤
        header = "❌ note投稿に失敗しました"
        description = f"**{title}**"
        if error:
            description += f"\n```{error[:800]}```"

    payload = {
        "embeds": [
            {
                "title": header,
                "description": description,
                "color": color,
            }
        ]
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            print("   📢 Discord通知: 送信完了")
        else:
            print(f"   ⚠️ Discord通知: HTTPエラー {resp.status_code}")
    except Exception as e:
        print(f"   ⚠️ Discord通知失敗: {e}")


def _notify_line(message: str):
    """LINE Notify に通知"""
    token = os.getenv("LINE_NOTIFY_TOKEN")
    if not token:
        return

    try:
        resp = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": message},
            timeout=10,
        )
        if resp.status_code == 200:
            print("   📢 LINE通知: 送信完了")
        else:
            print(f"   ⚠️ LINE通知: HTTPエラー {resp.status_code}")
    except Exception as e:
        print(f"   ⚠️ LINE通知失敗: {e}")


def _notify_x(title: str, article_url: str = None):
    """X (Twitter) に投稿告知をポストする（X API v2 / OAuth 1.0a）"""
    import hmac
    import hashlib
    import time
    import uuid
    import urllib.parse

    api_key = os.getenv("X_API_KEY")
    api_secret = os.getenv("X_API_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_secret = os.getenv("X_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        return

    try:
        text = f"📝 新しい記事を投稿しました！\n\n「{title}」\n"
        if article_url:
            text += f"\n{article_url}\n"
        text += "\n#note #有料記事"
        text = text[:280]

        url = "https://api.twitter.com/2/tweets"
        method = "POST"

        oauth_params = {
            "oauth_consumer_key": api_key,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": access_token,
            "oauth_version": "1.0",
        }

        param_str = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
            for k, v in sorted(oauth_params.items())
        )
        base_str = "&".join([
            method,
            urllib.parse.quote(url, safe=""),
            urllib.parse.quote(param_str, safe=""),
        ])
        signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_secret, safe='')}"
        sig = hmac.new(signing_key.encode(), base_str.encode(), hashlib.sha1).digest()
        import base64
        oauth_params["oauth_signature"] = base64.b64encode(sig).decode()

        auth_header = "OAuth " + ", ".join(
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        )

        resp = requests.post(
            url,
            headers={"Authorization": auth_header, "Content-Type": "application/json"},
            json={"text": text},
            timeout=15,
        )
        if resp.status_code in (200, 201):
            print("   🐦 X投稿: 完了")
        else:
            print(f"   ⚠️ X投稿失敗: HTTP {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"   ⚠️ X投稿失敗: {e}")


def send_notification(
    title: str,
    success: bool,
    article_url: str = None,
    error: str = None,
):
    """
    全通知チャンネル（Discord / LINE / X）に投稿結果を送信する。
    環境変数が未設定のチャンネルはスキップされる。
    """
    has_discord = bool(os.getenv("DISCORD_WEBHOOK_URL"))
    has_line = bool(os.getenv("LINE_NOTIFY_TOKEN"))
    has_x = all([
        os.getenv("X_API_KEY"), os.getenv("X_API_SECRET"),
        os.getenv("X_ACCESS_TOKEN"), os.getenv("X_ACCESS_SECRET"),
    ])

    if not has_discord and not has_line and not has_x:
        return  # 通知設定なし

    print("\n📢 通知を送信中...")
    _notify_discord(title, success, article_url, error)

    if success:
        line_msg = f"\n✅ note投稿完了\n記事: {title}"
        if article_url:
            line_msg += f"\n{article_url}"
        _notify_line(line_msg)
        _notify_x(title, article_url)
    else:
        line_msg = f"\n❌ note投稿失敗\n記事: {title}"
        if error:
            line_msg += f"\nエラー: {error[:200]}"
        _notify_line(line_msg)
