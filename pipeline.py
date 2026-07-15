"""端到端流程：主題 → 生成文章 → 從媒體庫挑圖 → 上架到 WordPress 草稿。

main.py（指令列）與 app.py（網頁）都呼叫這裡，避免邏輯重複。
"""
from typing import Any

import generator
import wordpress
import config


def _insert_inline_images(html: str, images: list[dict[str, str]]) -> str:
    """把內文插圖插在第 2 個（含）之後的每個 <h2> 之前；沒有 <h2> 就附加在最後。"""
    if not images:
        return html

    figures = [
        f'<figure><img src="{img["source_url"]}" alt="{img["alt"]}" '
        f'style="max-width:100%;height:auto"/></figure>'
        for img in images
    ]

    parts: list[str] = []
    rest = html
    h2_seen = 0
    fig_i = 0
    while fig_i < len(figures):
        pos = rest.find("<h2")
        if pos == -1:
            break
        h2_seen += 1
        if h2_seen == 1:  # 跳過第一個 h2，避免圖片緊貼開頭
            parts.append(rest[: pos + 3])
            rest = rest[pos + 3 :]
            continue
        parts.append(rest[:pos])          # h2 之前的內容
        parts.append(figures[fig_i])      # 插入圖片
        fig_i += 1
        parts.append(rest[pos : pos + 3])  # "<h2"
        rest = rest[pos + 3 :]
    parts.append(rest)

    result = "".join(parts)
    if fig_i < len(figures):  # 還有沒插完的圖（h2 不夠），附加在最後
        result += "".join(figures[fig_i:])
    return result


def create_draft(topic: str) -> dict[str, Any]:
    """回傳 {post_id, title, edit_url, focus_keyword, image_used}。"""
    # 抓站上既有文章當結構/風格範本（例如移民文章）
    references = wordpress.list_reference_posts(
        config.REFERENCE_QUERY, config.REFERENCE_COUNT
    )
    article = generator.generate_article(topic, references=references)

    # 從媒體庫挑圖（只用網站自己的圖）
    candidates = wordpress.list_media()
    picks = generator.choose_images(topic, candidates)
    by_id = {c["id"]: c for c in candidates}

    inline_imgs = [
        {"source_url": by_id[mid]["source_url"], "alt": by_id[mid]["alt"] or article["title"]}
        for mid in picks["inline_media_ids"]
        if mid in by_id and by_id[mid]["source_url"]
    ]
    article["content_html"] = _insert_inline_images(article["content_html"], inline_imgs)

    featured_id = picks["featured_media_id"] if picks["featured_media_id"] in by_id else None
    post = wordpress.publish_draft(article, featured_media_id=featured_id)

    return {
        "post_id": post["id"],
        "title": article["title"],
        "focus_keyword": article.get("focus_keyword", ""),
        "image_used": bool(featured_id or inline_imgs),
        "edit_url": f"{config.WP_BASE_URL}/wp-admin/post.php?post={post['id']}&action=edit",
    }
