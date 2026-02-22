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


def send_notification(
    title: str,
    success: bool,
    article_url: str = None,
    error: str = None,
):
    """
    全通知チャンネル（Discord / LINE）に投稿結果を送信する。
    環境変数が未設定のチャンネルはスキップされる。
    """
    has_discord = bool(os.getenv("DISCORD_WEBHOOK_URL"))
    has_line = bool(os.getenv("LINE_NOTIFY_TOKEN"))

    if not has_discord and not has_line:
        return  # 通知設定なし

    print("\n📢 通知を送信中...")
    _notify_discord(title, success, article_url, error)

    if success:
        line_msg = f"\n✅ note投稿完了\n記事: {title}"
        if article_url:
            line_msg += f"\n{article_url}"
    else:
        line_msg = f"\n❌ note投稿失敗\n記事: {title}"
        if error:
            line_msg += f"\nエラー: {error[:200]}"

    _notify_line(line_msg)
