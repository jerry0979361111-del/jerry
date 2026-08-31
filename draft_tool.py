"""草稿預覽／發佈工具：讓 Claude 能透過 GitHub Actions 讀取 WordPress 草稿內容，
或在使用者確認後把草稿改成正式發佈。

用法：
    python draft_tool.py fetch <post_id>          # 印出草稿內容 JSON（供 workflow log 讀取）
    python draft_tool.py publish <post_id>        # 把該篇文章狀態改成 publish
    python draft_tool.py strip_sources <post_id>  # 移除文末重複的「資料來源」彙總清單
    python draft_tool.py replace_text <post_id>      # 用環境變數 OLD_TEXT/NEW_TEXT 做一次文字取代
    python draft_tool.py add_category <post_id>      # 用環境變數 CATEGORY_NAME 把文章加進分類（保留原有分類，查無則自動建立）
    python draft_tool.py remove_category <post_id>   # 用環境變數 CATEGORY_NAME 把文章從該分類移除（保留其他分類）
    python draft_tool.py move_category <post_id>     # 用環境變數 CATEGORY_NAME/PARENT_CATEGORY_NAME 把分類移到另一個分類底下，post_id 可帶任意數字
    python draft_tool.py list_categories <post_id>   # 印出網站所有分類（含 parent 階層），post_id 可帶任意數字
    python draft_tool.py set_title <post_id>         # 用環境變數 TITLE 更新文章標題
    python draft_tool.py fix_hero_image <post_id>    # 把精選圖＋內文第一張插圖換成一張最近沒用過的圖
    python draft_tool.py trash_post <post_id>        # 把文章移到回收桶（可從後台復原，非永久刪除）
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


def add_category(post_id: int) -> None:
    """把文章加進指定分類（保留原有分類，不覆蓋；查無該分類則自動建立），分類名稱來自 CATEGORY_NAME 環境變數。"""
    name = os.environ.get("CATEGORY_NAME", "").strip()
    if not name:
        raise SystemExit("缺少 CATEGORY_NAME 環境變數。")
    result = wordpress.add_post_categories(post_id, [name])
    _print_json({"id": post_id, "category": name, **result})


def remove_category(post_id: int) -> None:
    """把文章從指定分類移除（保留其他分類），分類名稱來自 CATEGORY_NAME 環境變數。"""
    name = os.environ.get("CATEGORY_NAME", "").strip()
    if not name:
        raise SystemExit("缺少 CATEGORY_NAME 環境變數。")
    result = wordpress.remove_post_categories(post_id, [name])
    _print_json({"id": post_id, "category": name, **result})


def move_category(post_id: int) -> None:  # post_id 不使用，僅為保持統一介面
    """把 CATEGORY_NAME 分類移到 PARENT_CATEGORY_NAME 分類底下（查無則自動建立）。"""
    name = os.environ.get("CATEGORY_NAME", "").strip()
    parent_name = os.environ.get("PARENT_CATEGORY_NAME", "").strip()
    if not name or not parent_name:
        raise SystemExit("缺少 CATEGORY_NAME 或 PARENT_CATEGORY_NAME 環境變數。")
    applied = wordpress.move_category(name, parent_name)
    _print_json({"category": name, "parent": parent_name, "applied": applied})


def list_categories(post_id: int) -> None:  # post_id 不使用，僅為保持統一介面
    _print_json({"categories": wordpress.list_categories()})


def set_title(post_id: int) -> None:
    """更新文章標題，新標題來自 TITLE 環境變數。"""
    title = os.environ.get("TITLE", "").strip()
    if not title:
        raise SystemExit("缺少 TITLE 環境變數。")
    post = wordpress.update_post_title(post_id, title)
    _print_json({"id": post_id, "title": (post.get("title") or {}).get("rendered", title)})


def fix_hero_image(post_id: int) -> None:
    """把文章的精選圖＋內文第一張插圖，換成一張「澳洲房產週報」分類最近沒用過的圖。"""
    post = wordpress.get_post(post_id)
    content = (post.get("content") or {}).get("rendered", "")
    current_hero = post.get("featured_media")

    exclude_ids = set(wordpress.list_category_featured_media("澳洲房產週報", count=8))
    if current_hero:
        exclude_ids.add(current_hero)

    candidates = wordpress.list_media(per_page=40, search="澳洲 房地產")
    if len(candidates) < 8:
        seen = {c["id"] for c in candidates}
        candidates += [m for m in wordpress.list_media(per_page=40) if m["id"] not in seen]

    fresh = [c for c in candidates if c["id"] not in exclude_ids and c.get("source_url")]
    if not fresh:
        raise SystemExit("媒體庫裡找不到還沒用過的圖可以替換。")
    new_media = fresh[0]

    wordpress.set_featured_media(post_id, new_media["id"])

    new_content, count = re.subn(
        r"<figure><img[^>]*/></figure>",
        '<figure><img decoding="async" src="{src}" alt="{alt}" style="max-width:100%;height:auto"/></figure>'.format(
            src=new_media["source_url"], alt=new_media.get("alt", "")
        ),
        content,
        count=1,
    )
    if count:
        wordpress.update_post_content(post_id, new_content)

    _print_json(
        {
            "id": post_id,
            "old_featured_media": current_hero,
            "new_featured_media": new_media["id"],
            "new_image_url": new_media["source_url"],
            "content_updated": bool(count),
        }
    )


def trash_post(post_id: int) -> None:
    """把文章移到回收桶（可從 WordPress 後台復原，非永久刪除）。"""
    result = wordpress.trash_post(post_id)
    _print_json({"id": post_id, "status": result.get("status", ""), "trashed": True})


_ACTIONS = {
    "fetch": fetch,
    "publish": publish,
    "strip_sources": strip_sources,
    "replace_text": replace_text,
    "add_category": add_category,
    "remove_category": remove_category,
    "move_category": move_category,
    "list_categories": list_categories,
    "set_title": set_title,
    "fix_hero_image": fix_hero_image,
    "trash_post": trash_post,
}


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in _ACTIONS:
        raise SystemExit(
            "用法：python draft_tool.py "
            "fetch|publish|strip_sources|replace_text|add_category|remove_category|move_category|"
            "list_categories|set_title|fix_hero_image|trash_post "
            "<post_id>"
        )
    action, post_id = sys.argv[1], int(sys.argv[2])
    _ACTIONS[action](post_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — CLI 最外層，統一顯示友善錯誤
        raise SystemExit(f"❌ 發生錯誤：{exc}")
