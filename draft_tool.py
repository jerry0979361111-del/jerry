"""草稿預覽／發佈工具：讓 Claude 能透過 GitHub Actions 讀取 WordPress 草稿內容，
或在使用者確認後把草稿改成正式發佈。

用法：
    python draft_tool.py fetch <post_id>     # 印出草稿內容 JSON（供 workflow log 讀取）
    python draft_tool.py publish <post_id>   # 把該篇文章狀態改成 publish
"""
import json
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


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("fetch", "publish"):
        raise SystemExit("用法：python draft_tool.py fetch|publish <post_id>")
    action, post_id = sys.argv[1], int(sys.argv[2])
    (fetch if action == "fetch" else publish)(post_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — CLI 最外層，統一顯示友善錯誤
        raise SystemExit(f"❌ 發生錯誤：{exc}")
