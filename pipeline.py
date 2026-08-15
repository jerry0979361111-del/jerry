"""端到端流程：主題／週報 → 生成文章 → 從媒體庫挑圖 → 上架到 WordPress 草稿。

main.py（指令列）與 app.py（網頁）都呼叫這裡，避免邏輯重複。
"""
from typing import Any

import au_property_digest
import generator
import wordpress
import config


def _insert_inline_images(html: str, images: list[dict[str, str]]) -> str:
    """把圖片依序插在每個 <h2> 之前（第 1 張在第一個 <h2> 前＝介於前言與首段之間）。"""
    if not images:
        return html

    figures = [
        f'<figure><img src="{img["source_url"]}" alt="{img["alt"]}" '
        f'style="max-width:100%;height:auto"/></figure>'
        for img in images
    ]

    parts: list[str] = []
    rest = html
    fig_i = 0
    while fig_i < len(figures):
        pos = rest.find("<h2")
        if pos == -1:
            break
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


def _publish_article(
    article: dict[str, Any], image_query: str = "", category_names: list[str] = ()
) -> dict[str, Any]:
    """共用流程：挑圖、插入內文、發佈到 WordPress 草稿。回傳 {post_id, title, edit_url, ...}。"""
    focus = (article.get("focus_keyword") or "").strip()
    # 讓網址包含焦點關鍵字（修正 Rank Math「關鍵字未出現在 URL」；中文網址會自動編碼）
    if focus and not article.get("slug"):
        article["slug"] = focus

    # 從媒體庫挑圖（只用網站自己的圖）：先用關鍵字搜尋，再用最新圖片補齊
    candidates = wordpress.list_media(per_page=40, search=image_query or focus)
    if len(candidates) < 8:
        seen = {c["id"] for c in candidates}
        candidates += [m for m in wordpress.list_media(per_page=40) if m["id"] not in seen]

    picks = generator.choose_images(article["title"], candidates)
    by_id = {c["id"]: c for c in candidates}

    # 決定主圖（hero）：AI 精選 → AI 第一張插圖 →（可關閉的保底）最相關的候選圖
    hero_id = picks["featured_media_id"] if picks["featured_media_id"] in by_id else None
    if hero_id is None:
        hero_id = next((m for m in picks["inline_media_ids"] if m in by_id), None)
    if hero_id is None and config.IMAGE_FALLBACK and candidates:
        hero_id = candidates[0]["id"]  # 候選已依關鍵字排序，取最相關的一張

    # 內文插圖 = hero + AI 額外挑的插圖（去重、最多 2 張），alt 帶入焦點關鍵字
    inline_ids: list[int] = []
    if hero_id:
        inline_ids.append(hero_id)
    for mid in picks["inline_media_ids"]:
        if mid in by_id and mid not in inline_ids:
            inline_ids.append(mid)
    inline_ids = inline_ids[:2]

    inline_imgs = [
        {"source_url": by_id[mid]["source_url"], "alt": focus or by_id[mid]["alt"] or article["title"]}
        for mid in inline_ids
        if by_id[mid]["source_url"]
    ]
    article["content_html"] = _insert_inline_images(article["content_html"], inline_imgs)

    featured_id = hero_id
    post = wordpress.publish_draft(article, featured_media_id=featured_id, category_names=category_names)

    return {
        "post_id": post["id"],
        "title": article["title"],
        "focus_keyword": focus,
        "image_used": bool(featured_id or inline_imgs),
        "media_candidates": len(candidates),
        "featured_set": bool(featured_id),
        "inline_count": len(inline_imgs),
        "edit_url": f"{config.WP_BASE_URL}/wp-admin/post.php?post={post['id']}&action=edit",
    }


def create_draft(topic: str, style: str = "", audience: str = "") -> dict[str, Any]:
    """回傳 {post_id, title, edit_url, focus_keyword, image_used}。"""
    # 抓站上既有文章當結構/風格範本（例如移民文章）
    references = wordpress.list_reference_posts(
        config.REFERENCE_QUERY, config.REFERENCE_COUNT
    )
    internal_links = [r["link"] for r in references if r.get("link")]
    article = generator.generate_article(
        topic,
        references=references,
        internal_links=internal_links,
        style=style,
        audience=audience,
    )
    result = _publish_article(article)
    result["reference_count"] = len(references)
    return result


def create_weekly_digest_draft() -> dict[str, Any]:
    """生成澳洲房產週報（原創整理＋引述連結回原文＋自製表格）並上架到 WordPress 草稿。

    回傳 {post_id, title, edit_url, focus_keyword, image_used, source_count, ...}。
    """
    article = au_property_digest.generate_weekly_digest()

    # 不額外附加彙總清單：Claude 已在每個段落結尾寫了「資料來源：連結」，
    # 這裡只取數量做診斷用，避免文末重複列出一次。
    sources = article.pop("sources", None) or []

    result = _publish_article(
        article,
        image_query=article.get("image_query", "澳洲 房地產"),
        category_names=["澳洲房產週報", "澳洲買家指南"],
    )
    result["source_count"] = len(sources)
    return result
