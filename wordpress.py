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


def list_media(per_page: int = 60, search: str = "") -> list[dict[str, Any]]:
    """列出媒體庫中的圖片（只取需要的欄位），供挑選配圖用。

    給 search 時會用關鍵字搜尋（比對標題/替代文字/檔名），較容易找到相關圖。
    """
    params: dict[str, Any] = {
        "media_type": "image",
        "per_page": per_page,
        "orderby": "date",
        "order": "desc",
        "_fields": "id,source_url,alt_text,title,media_details",
    }
    if search:
        params["search"] = search
    try:
        resp = requests.get(f"{_API}/media", headers=_HEADERS, params=params, timeout=30)
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


def list_reference_posts(query: str, count: int) -> list[dict[str, Any]]:
    """抓站上已發佈的文章當風格/結構範本（可用關鍵字篩選，如「移民」）。"""
    if count <= 0:
        return []
    params: dict[str, Any] = {
        "status": "publish",
        "per_page": count,
        "orderby": "date",
        "order": "desc",
        "_fields": "title,content,link",
    }
    if query:
        params["search"] = query
    try:
        resp = requests.get(f"{_API}/posts", headers=_HEADERS, params=params, timeout=30)
        if not resp.ok:
            return []
        items = resp.json()
    except (requests.RequestException, ValueError):
        return []

    return [
        {
            "title": (p.get("title") or {}).get("rendered", ""),
            "content_html": (p.get("content") or {}).get("rendered", ""),
            "link": p.get("link", ""),
        }
        for p in items
    ]


def _resolve_term_id(endpoint: str, name: str) -> int | None:
    """查詢分類法詞彙（分類／標籤共用），查無則自動建立，回傳 ID。"""
    name = (name or "").strip()
    if not name:
        return None
    try:
        found = requests.get(endpoint, headers=_HEADERS, params={"search": name}, timeout=30).json()
        match = next((t for t in found if t.get("name") == name), None)
        if match:
            return match["id"]
        created = requests.post(endpoint, headers=_HEADERS, json={"name": name}, timeout=30)
        if created.ok:
            return created.json()["id"]
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None


def _resolve_tag_ids(tag_names: list[str]) -> list[int]:
    endpoint = f"{_API}/tags"
    return [tid for tid in (_resolve_term_id(endpoint, name) for name in tag_names) if tid]


def list_categories() -> list[dict[str, Any]]:
    """列出網站所有分類（含上下層 parent 關係），用來對照分類導覽結構。"""
    resp = requests.get(
        f"{_API}/categories",
        headers=_HEADERS,
        params={"per_page": 100, "_fields": "id,name,parent,count"},
        timeout=30,
    )
    if not resp.ok:
        return []
    return resp.json()


def _resolve_category_ids(category_names: list[str]) -> list[int]:
    endpoint = f"{_API}/categories"
    return [cid for cid in (_resolve_term_id(endpoint, name) for name in category_names) if cid]


def list_category_featured_media(category_name: str, count: int = 6) -> list[int]:
    """列出某分類最近 N 篇文章使用過的精選圖 media id（用來避免首圖每次重複）。"""
    cat_id = _resolve_term_id(f"{_API}/categories", category_name)
    if not cat_id:
        return []
    try:
        resp = requests.get(
            f"{_API}/posts",
            headers=_HEADERS,
            params={
                "categories": cat_id,
                "per_page": count,
                "orderby": "date",
                "order": "desc",
                "_fields": "featured_media",
            },
            timeout=30,
        )
        if not resp.ok:
            return []
        return [p["featured_media"] for p in resp.json() if p.get("featured_media")]
    except (requests.RequestException, ValueError, KeyError):
        return []


def _get_post_category_ids(post_id: int) -> list[int]:
    resp = requests.get(
        f"{_API}/posts/{post_id}", headers=_HEADERS, params={"_fields": "categories"}, timeout=30
    )
    return resp.json().get("categories", []) if resp.ok else []


def add_post_categories(post_id: int, category_names: list[str]) -> dict[str, Any]:
    """把文章「加進」指定分類（保留原本已有的分類，不覆蓋；查無該分類則自動建立）。"""
    new_ids = _resolve_category_ids(category_names)
    merged = sorted(set(_get_post_category_ids(post_id)) | set(new_ids))
    resp = requests.post(
        f"{_API}/posts/{post_id}", headers=_HEADERS, json={"categories": merged}, timeout=30
    )
    if not resp.ok:
        raise RuntimeError(f"更新文章分類失敗（HTTP {resp.status_code}）：{resp.text[:500]}")
    return {"applied_ids": new_ids, "categories": merged}


def remove_post_categories(post_id: int, category_names: list[str]) -> dict[str, Any]:
    """把文章從指定分類移除（保留其他分類）。"""
    remove_ids = set(_resolve_category_ids(category_names))
    remaining = sorted(set(_get_post_category_ids(post_id)) - remove_ids)
    resp = requests.post(
        f"{_API}/posts/{post_id}", headers=_HEADERS, json={"categories": remaining}, timeout=30
    )
    if not resp.ok:
        raise RuntimeError(f"更新文章分類失敗（HTTP {resp.status_code}）：{resp.text[:500]}")
    return {"removed_ids": sorted(remove_ids), "categories": remaining}


def move_category(category_name: str, parent_name: str) -> bool:
    """把分類移到另一個分類底下（依名稱操作，查無則自動建立）。"""
    endpoint = f"{_API}/categories"
    cat_id = _resolve_term_id(endpoint, category_name)
    parent_id = _resolve_term_id(endpoint, parent_name)
    if not cat_id or not parent_id:
        return False
    resp = requests.post(f"{endpoint}/{cat_id}", headers=_HEADERS, json={"parent": parent_id}, timeout=30)
    return resp.ok


def publish_draft(
    article: dict[str, Any],
    featured_media_id: int | None = None,
    category_names: list[str] = (),
) -> dict[str, Any]:
    """發佈文章到 WordPress，設定精選圖／分類，並嘗試填入 Rank Math SEO 欄位。"""
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

    category_ids = _resolve_category_ids(list(category_names))
    if category_ids:
        payload["categories"] = category_ids

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


def get_post(post_id: int) -> dict[str, Any]:
    """取得單篇文章完整內容（含 meta），用於預覽草稿。"""
    resp = requests.get(
        f"{_API}/posts/{post_id}",
        headers=_HEADERS,
        params={
            "context": "edit",
            "_fields": "id,title,content,excerpt,link,slug,status,featured_media,meta",
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"讀取文章失敗（HTTP {resp.status_code}）：{resp.text[:500]}")
    return resp.json()


def get_media_url(media_id: int | None) -> str:
    """依 media ID 查詢圖片網址；查無或 media_id 為空則回傳空字串。"""
    if not media_id:
        return ""
    try:
        resp = requests.get(
            f"{_API}/media/{media_id}", headers=_HEADERS, params={"_fields": "source_url"}, timeout=30
        )
        return resp.json().get("source_url", "") if resp.ok else ""
    except (requests.RequestException, ValueError):
        return ""


def set_post_status(post_id: int, status: str) -> dict[str, Any]:
    """更新文章狀態（例如把草稿改成 publish 正式發佈）。"""
    resp = requests.post(
        f"{_API}/posts/{post_id}", headers=_HEADERS, json={"status": status}, timeout=30
    )
    if not resp.ok:
        raise RuntimeError(f"更新文章狀態失敗（HTTP {resp.status_code}）：{resp.text[:500]}")
    return resp.json()


def update_post_content(post_id: int, content_html: str) -> dict[str, Any]:
    """覆寫文章內文（用於修正既有草稿內容）。"""
    resp = requests.post(
        f"{_API}/posts/{post_id}", headers=_HEADERS, json={"content": content_html}, timeout=30
    )
    if not resp.ok:
        raise RuntimeError(f"更新文章內容失敗（HTTP {resp.status_code}）：{resp.text[:500]}")
    return resp.json()


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
