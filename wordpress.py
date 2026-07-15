"""WordPress REST API：媒體庫查詢、發佈草稿、填入 Rank Math SEO 欄位。"""
import base64
from typing import Any

import requests

import config

_AUTH_HEADER = "Basic " + base64.b64encode(
    f"{config.WP_USERNAME}:{config.WP_APP_PASSWORD}".encode()
).decode()
_HEADERS = {"Authorization": _AUTH_HEADER}
_API = f"{config.WP_BASE_URL}/wp-json/wp/v2"


def list_media(per_page: int = 60) -> list[dict[str, Any]]:
    """列出媒體庫中的圖片（只取需要的欄位），供挑選配圖用。"""
    try:
        resp = requests.get(
            f"{_API}/media",
            headers=_HEADERS,
            params={
                "media_type": "image",
                "per_page": per_page,
                "orderby": "date",
                "order": "desc",
                "_fields": "id,source_url,alt_text,title,media_details",
            },
            timeout=30,
        )
        if not resp.ok:
            return []
        items = resp.json()
    except (requests.RequestException, ValueError):
        return []

    result = []
    for m in items:
        result.append(
            {
                "id": m["id"],
                "source_url": m.get("source_url", ""),
                "alt": m.get("alt_text", ""),
                "title": (m.get("title") or {}).get("rendered", ""),
                "filename": (m.get("media_details") or {}).get("file", ""),
            }
        )
    return result


def _resolve_tag_ids(tag_names: list[str]) -> list[int]:
    ids: list[int] = []
    endpoint = f"{_API}/tags"
    for name in tag_names:
        name = (name or "").strip()
        if not name:
            continue
        try:
            found = requests.get(
                endpoint, headers=_HEADERS, params={"search": name}, timeout=30
            ).json()
            match = next((t for t in found if t.get("name") == name), None)
            if match:
                ids.append(match["id"])
                continue
            created = requests.post(
                endpoint, headers=_HEADERS, json={"name": name}, timeout=30
            )
            if created.ok:
                ids.append(created.json()["id"])
        except (requests.RequestException, ValueError, KeyError):
            continue
    return ids


def publish_draft(
    article: dict[str, Any], featured_media_id: int | None = None
) -> dict[str, Any]:
    """發佈文章到 WordPress，設定精選圖，並嘗試填入 Rank Math SEO 欄位。"""
    payload: dict[str, Any] = {
        "title": article["title"],
        "content": article["content_html"],
        "excerpt": article.get("meta_description", ""),
        "status": config.WP_POST_STATUS,
    }
    if article.get("slug"):
        payload["slug"] = article["slug"]
    if featured_media_id:
        payload["featured_media"] = featured_media_id

    tag_ids = _resolve_tag_ids(article.get("tags", []))
    if tag_ids:
        payload["tags"] = tag_ids

    resp = requests.post(f"{_API}/posts", headers=_HEADERS, json=payload, timeout=60)
    if not resp.ok:
        raise RuntimeError(
            f"發佈到 WordPress 失敗（HTTP {resp.status_code}）：{resp.text[:500]}"
        )
    post = resp.json()

    _set_rank_math_meta(
        post["id"],
        focus_keyword=article.get("focus_keyword", ""),
        seo_title=article["title"],
        seo_description=article.get("meta_description", ""),
    )
    return post


def _set_rank_math_meta(
    post_id: int, focus_keyword: str, seo_title: str, seo_description: str
) -> bool:
    """嘗試寫入 Rank Math 的焦點關鍵字 / SEO 標題 / Meta 描述。

    需要網站先註冊這些 meta 給 REST（見 README 的一次性設定）。
    失敗不影響文章本身，只回傳 False。
    """
    if not focus_keyword:
        return False
    try:
        resp = requests.post(
            f"{_API}/posts/{post_id}",
            headers=_HEADERS,
            json={
                "meta": {
                    "rank_math_focus_keyword": focus_keyword,
                    "rank_math_title": seo_title,
                    "rank_math_description": seo_description,
                }
            },
            timeout=30,
        )
        return resp.ok
    except requests.RequestException:
        return False
