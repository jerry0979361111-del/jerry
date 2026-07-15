"""透過 WordPress REST API 把文章發成草稿（或指定狀態）。"""
import base64
from typing import Any

import requests

import config

_AUTH_HEADER = "Basic " + base64.b64encode(
    f"{config.WP_USERNAME}:{config.WP_APP_PASSWORD}".encode()
).decode()


def _resolve_tag_ids(tag_names: list[str]) -> list[int]:
    """把標籤名稱轉成 ID；不存在就建立。失敗就略過該標籤（不擋發文）。"""
    ids: list[int] = []
    endpoint = f"{config.WP_BASE_URL}/wp-json/wp/v2/tags"
    for name in tag_names:
        name = (name or "").strip()
        if not name:
            continue
        try:
            found = requests.get(
                endpoint,
                headers={"Authorization": _AUTH_HEADER},
                params={"search": name},
                timeout=30,
            ).json()
            match = next((t for t in found if t.get("name") == name), None)
            if match:
                ids.append(match["id"])
                continue
            created = requests.post(
                endpoint,
                headers={"Authorization": _AUTH_HEADER},
                json={"name": name},
                timeout=30,
            )
            if created.ok:
                ids.append(created.json()["id"])
        except (requests.RequestException, ValueError, KeyError):
            continue  # 標籤非關鍵，出錯就跳過
    return ids


def publish_draft(article: dict[str, Any]) -> dict[str, Any]:
    """把 generator 產出的文章發到 WordPress，回傳 WP 的文章物件。"""
    payload: dict[str, Any] = {
        "title": article["title"],
        "content": article["content_html"],
        "excerpt": article.get("meta_description", ""),
        "status": config.WP_POST_STATUS,
    }
    if article.get("slug"):
        payload["slug"] = article["slug"]

    tag_ids = _resolve_tag_ids(article.get("tags", []))
    if tag_ids:
        payload["tags"] = tag_ids

    resp = requests.post(
        f"{config.WP_BASE_URL}/wp-json/wp/v2/posts",
        headers={"Authorization": _AUTH_HEADER},
        json=payload,
        timeout=60,
    )

    if not resp.ok:
        raise RuntimeError(
            f"發佈到 WordPress 失敗（HTTP {resp.status_code}）：{resp.text[:500]}"
        )
    return resp.json()
