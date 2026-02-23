"""
note.com 自動投稿 - 記事画像取得モジュール
==========================================
記事本文中の [IMAGE:キーワード] マーカーを検出して画像をダウンロードします。

優先順位:
  1. Unsplash API (UNSPLASH_ACCESS_KEY が設定されている場合・キーワード一致)
  2. Lorem Picsum フォールバック (APIキー不要)
"""

import os
import re
import time
import requests
from pathlib import Path

IMAGES_DIR = Path("images")
IMAGES_DIR.mkdir(exist_ok=True)

# 本文中の画像マーカー: [IMAGE:keyword]
IMAGE_MARKER_PATTERN = re.compile(r"\[IMAGE:([^\]]+)\]")


def fetch_image(keyword: str, filename: str) -> Path | None:
    """
    キーワードに合った画像をダウンロードして保存し、Pathを返す。
    失敗した場合は None を返す。
    """
    save_path = IMAGES_DIR / filename
    if save_path.exists():
        return save_path  # キャッシュ済み

    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if access_key:
        try:
            return _fetch_unsplash(keyword, save_path, access_key)
        except Exception as e:
            print(f"   ⚠️ Unsplash取得失敗: {e} → Picsumにフォールバック")

    return _fetch_picsum(save_path)


def _fetch_unsplash(keyword: str, save_path: Path, access_key: str) -> Path | None:
    """Unsplash API でキーワード検索して画像をダウンロード"""
    url = "https://api.unsplash.com/photos/random"
    params = {
        "query": keyword,
        "orientation": "landscape",
        "client_id": access_key,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    img_url = data["urls"]["regular"]  # 約1080px幅

    img_resp = requests.get(img_url, timeout=30)
    img_resp.raise_for_status()
    save_path.write_bytes(img_resp.content)
    print(f"   🖼️  Unsplash画像取得: 「{keyword}」→ {save_path.name}")
    return save_path


def _fetch_picsum(save_path: Path) -> Path | None:
    """Lorem Picsum からランダム画像をダウンロード（APIキー不要）"""
    # seed を使って毎回異なる画像にする
    seed = int(time.time() * 1000) % 1000
    url = f"https://picsum.photos/seed/{seed}/800/450.jpg"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    save_path.write_bytes(resp.content)
    print(f"   🖼️  Picsum画像取得 → {save_path.name}")
    return save_path


def fetch_images_for_article(body: str) -> dict[str, Path]:
    """
    記事本文中の全 [IMAGE:keyword] マーカーを検出し、
    画像をダウンロードして {keyword: Path} の辞書を返す。
    """
    keywords = IMAGE_MARKER_PATTERN.findall(body)
    if not keywords:
        return {}

    print(f"   🖼️  画像マーカー検出: {len(keywords)} 件")
    images: dict[str, Path] = {}
    for i, keyword in enumerate(keywords):
        kw = keyword.strip()
        filename = f"article_image_{i}.jpg"
        path = fetch_image(kw, filename)
        if path:
            images[kw] = path
        time.sleep(0.5)  # API レート制限を避けるため少し待つ

    return images
