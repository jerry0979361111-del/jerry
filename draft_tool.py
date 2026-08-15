"""草稿預覽／發佈工具：讓 Claude 能透過 GitHub Actions 讀取 WordPress 草稿內容，
或在使用者確認後把草稿改成正式發佈。

用法：
    python draft_tool.py fetch <post_id>          # 印出草稿內容 JSON（供 workflow log 讀取）
    python draft_tool.py publish <post_id>        # 把該篇文章狀態改成 publish
    python draft_tool.py strip_sources <post_id>  # 移除文末重複的「資料來源」彙總清單
    python draft_tool.py replace_text <post_id>   # 用環境變數 OLD_TEXT/NEW_TEXT 做一次文字取代
    python draft_tool.py set_category <post_id>   # 用環境變數 CATEGORY_NAME 設定文章分類（查無則自動建立）
"""
import json
import os
import re
import sys

import wordpress

_START = "===DRAFT_JSON_START==="
_END = "===DRAFT_JSON_END==="


def _print_json(data: dict) -> None:
    print(_START)
    print(json.dumps(data, ensure_ascii=False))
    print(_END)


def fetch(post_id: int) -> None:
    post = wordpress.get_post(post_id)
    _print_json(
        {
            "id": post["id"],
            "status": post.get("status", ""),
            "title": (post.get("title") or {}).get("rendered", ""),
            "content_html": (post.get("content") or {}).get("rendered", ""),
            "excerpt": (post.get("excerpt") or {}).get("rendered", ""),
            "link": post.get("link", ""),
            "slug": post.get("slug", ""),
            "featured_image_url": wordpress.get_media_url(post.get("featured_media")),
            "focus_keyword": (post.get("meta") or {}).get("rank_math_focus_keyword", ""),
        }
    )


def publish(post_id: int) -> None:
    post = wordpress.set_post_status(post_id, "publish")
    _print_json({"id": post["id"], "status": post.get("status", ""), "link": post.get("link", "")})


def strip_sources(post_id: int) -> None:
    """移除文末重複的「資料來源」彙總清單（每段結尾已個別附上資料來源連結，文末彙總是多餘的）。"""
    post = wordpress.get_post(post_id)
    content = (post.get("content") or {}).get("rendered", "")
    new_content = re.sub(r"<h2>資料來源</h2>\s*<ul>.*?</ul>\s*", "", content, flags=re.S)
    removed = new_content != content
    if removed:
        wordpress.update_post_content(post_id, new_content)
    _print_json({"id": post_id, "removed": removed, "new_length": len(new_content)})


def replace_text(post_id: int) -> None:
    """把內文裡的 OLD_TEXT 全部換成 NEW_TEXT（用環境變數傳，避免命令列參數跳脫問題）。"""
    old = os.environ.get("OLD_TEXT", "")
    new = os.environ.get("NEW_TEXT", "")
    if not old:
        raise SystemExit("缺少 OLD_TEXT 環境變數。")
    post = wordpress.get_post(post_id)
    content = (post.get("content") or {}).get("rendered", "")
    occurrences = content.count(old)
    new_content = content.replace(old, new)
    if occurrences:
        wordpress.update_post_content(post_id, new_content)
    _print_json({"id": post_id, "occurrences_replaced": occurrences, "new_length": len(new_content)})


def set_category(post_id: int) -> None:
    """把文章加到指定分類（查無該分類則自動建立），分類名稱來自 CATEGORY_NAME 環境變數。"""
    name = os.environ.get("CATEGORY_NAME", "").strip()
    if not name:
        raise SystemExit("缺少 CATEGORY_NAME 環境變數。")
    applied = wordpress.set_post_category(post_id, name)
    _print_json({"id": post_id, "category": name, "applied": applied})


_ACTIONS = {
    "fetch": fetch,
    "publish": publish,
    "strip_sources": strip_sources,
    "replace_text": replace_text,
    "set_category": set_category,
}


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in _ACTIONS:
        raise SystemExit(
            "用法：python draft_tool.py fetch|publish|strip_sources|replace_text|set_category <post_id>"
        )
    action, post_id = sys.argv[1], int(sys.argv[2])
    _ACTIONS[action](post_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — CLI 最外層，統一顯示友善錯誤
        raise SystemExit(f"❌ 發生錯誤：{exc}")
