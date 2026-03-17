"""
note.com 自動投稿 - 投稿履歴管理モジュール
==========================================
過去の投稿を記録し、テーマの重複を防止します。
"""

import json
from datetime import datetime
from pathlib import Path

HISTORY_FILE = Path("post_history.json")


def load_history() -> list[dict]:
    """投稿履歴を読み込む"""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_history(history: list[dict]):
    """投稿履歴を保存する"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def add_record(
    theme: str,
    title: str,
    success: bool,
    as_draft: bool = False,
    error: str = None,
    seo_score: int = None,
    persona: str = None,
):
    """投稿記録を追加する"""
    history = load_history()
    record = {
        "timestamp": datetime.now().isoformat(),
        "theme": theme,
        "title": title,
        "success": success,
        "as_draft": as_draft,
        "error": error,
        "seo_score": seo_score,
        "persona": persona,
    }
    history.append(record)
    save_history(history)
    return record


def get_used_themes() -> set[str]:
    """使用済みテーマのセットを返す（成功した投稿のみ）"""
    history = load_history()
    return {
        record["theme"]
        for record in history
        if record.get("success") and not record.get("as_draft")
    }


def get_stats() -> dict:
    """投稿統計を返す"""
    history = load_history()
    total = len(history)
    success = sum(1 for r in history if r.get("success"))
    failed = sum(1 for r in history if not r.get("success"))
    drafts = sum(1 for r in history if r.get("as_draft"))

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "drafts": drafts,
        "success_rate": f"{(success / total * 100):.1f}%" if total > 0 else "N/A",
    }


def print_stats():
    """投稿統計を表示する"""
    stats = get_stats()
    print(f"\n📊 投稿統計:")
    print(f"   総投稿数:   {stats['total']}")
    print(f"   成功:       {stats['success']}")
    print(f"   失敗:       {stats['failed']}")
    print(f"   下書き:     {stats['drafts']}")
    print(f"   成功率:     {stats['success_rate']}")


if __name__ == "__main__":
    print_stats()
