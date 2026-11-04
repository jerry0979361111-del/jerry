"""Notion 建案資料庫 → 官網（WordPress）自動同步。

定期檢查 Notion「澳洲房地產建案資料庫」裡標記為「網站上架」、且未被
「禁止公開」、但尚未同步過的建案（「已同步官網」未勾選），自動發佈成
WordPress 文章草稿，並在 Notion 該筆資料打勾「已同步官網」，避免下次重複發文。

用法：
    python notion_sync.py

供 GitHub Actions 排程呼叫（見 .github/workflows/notion-listing-sync.yml），
也可手動執行測試。
"""
from typing import Any

import requests

import config
import wordpress

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _require_notion_config() -> None:
    if not config.NOTION_API_KEY:
        raise SystemExit(
            "缺少必要環境變數 NOTION_API_KEY，請到 Notion 建立內部整合（Integration）取得密鑰，"
            "並把「澳洲房地產建案資料庫」分享給該整合，詳見 README。"
        )


def _notion_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.NOTION_API_KEY}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _rich_text(prop: dict[str, Any] | None) -> str:
    """把 Notion rich_text / title 屬性拼成純文字。"""
    if not prop:
        return ""
    parts = prop.get("rich_text") or prop.get("title") or []
    return "".join(p.get("plain_text", "") for p in parts).strip()


def _select(prop: dict[str, Any] | None) -> str:
    if not prop:
        return ""
    sel = prop.get("select")
    return (sel or {}).get("name", "") if sel else ""


def _url(prop: dict[str, Any] | None) -> str:
    return (prop or {}).get("url") or ""


def fetch_unsynced_listings() -> list[dict[str, Any]]:
    """查詢資料庫：網站上架=是、禁止公開=否、已同步官網=否（或未設定）的建案列表。"""
    payload: dict[str, Any] = {
        "filter": {
            "and": [
                {"property": "網站上架", "checkbox": {"equals": True}},
                {"property": "禁止公開", "checkbox": {"equals": False}},
                {"property": "已同步官網", "checkbox": {"equals": False}},
            ]
        },
        "page_size": 50,
    }
    results: list[dict[str, Any]] = []
    url = f"{_NOTION_API}/databases/{config.NOTION_DATABASE_ID}/query"
    while True:
        resp = requests.post(url, headers=_notion_headers(), json=payload, timeout=30)
        if not resp.ok:
            raise RuntimeError(
                f"查詢 Notion 資料庫失敗（HTTP {resp.status_code}）：{resp.text[:500]}"
            )
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return results


def _page_to_article(page: dict[str, Any]) -> dict[str, Any]:
    """把一筆 Notion 建案資料轉成 WordPress 文章欄位（標題／內文 HTML／分類）。"""
    props = page["properties"]
    name = _rich_text(props.get("建案名"))
    city = _select(props.get("城市"))
    region = _rich_text(props.get("區域"))
    address = _rich_text(props.get("地址"))
    building_type = _select(props.get("建物型態"))
    sale_status = _select(props.get("銷售狀態"))
    developer = _rich_text(props.get("開發商"))
    price_range = _rich_text(props.get("價格帶"))
    start_price = _rich_text(props.get("網站起價"))
    intro = _rich_text(props.get("網站簡介"))
    drive_link = _url(props.get("Drive連結"))

    location = "・".join(x for x in [city, region] if x)
    title = f"{name}｜{location}建案介紹" if location else f"{name}｜建案介紹"

    rows = [
        ("地址", address),
        ("城市／區域", location),
        ("建物型態", building_type),
        ("銷售狀態", sale_status),
        ("開發商", developer),
        ("起價", start_price),
        ("價格帶", price_range),
    ]
    table_rows = "".join(
        f"<tr><th style='text-align:left;padding:6px 12px;background:#f7f7f7'>{k}</th>"
        f"<td style='padding:6px 12px'>{v}</td></tr>"
        for k, v in rows
        if v
    )

    content_html = (f"<p>{intro}</p>" if intro else "") + (
        f"<table style='width:100%;border-collapse:collapse;margin:16px 0'>{table_rows}</table>"
        if table_rows
        else ""
    )
    if drive_link:
        content_html += f"<p><a href=\"{drive_link}\" target=\"_blank\" rel=\"noopener\">更多資料／圖片</a></p>"

    return {
        "title": title,
        "content_html": content_html,
        "meta_description": intro[:155],
        "tags": [t for t in [building_type] if t],
        "focus_keyword": name,
        "_category_names": [c for c in [city, sale_status] if c],
    }


def _mark_synced(page_id: str) -> None:
    resp = requests.patch(
        f"{_NOTION_API}/pages/{page_id}",
        headers=_notion_headers(),
        json={"properties": {"已同步官網": {"checkbox": True}}},
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(
            f"更新 Notion 同步狀態失敗（HTTP {resp.status_code}）：{resp.text[:500]}"
        )


def sync_new_listings() -> list[dict[str, Any]]:
    """主流程：找出未同步建案 → 發佈到 WordPress → Notion 打勾已同步。回傳發佈結果列表。

    單筆發佈失敗不會中斷整批，只會記錄錯誤、且不會打勾（下次會重試）。
    """
    _require_notion_config()
    listings = fetch_unsynced_listings()
    published: list[dict[str, Any]] = []
    for page in listings:
        article = _page_to_article(page)
        category_names = article.pop("_category_names")
        try:
            post = wordpress.publish_draft(article, category_names=category_names)
        except Exception as exc:  # noqa: BLE001 — 單筆失敗不中斷整批，留給下次重試
            published.append({"title": article["title"], "error": str(exc)})
            continue
        _mark_synced(page["id"])
        published.append(
            {
                "title": article["title"],
                "post_id": post["id"],
                "edit_url": f"{config.WP_BASE_URL}/wp-admin/post.php?post={post['id']}&action=edit",
            }
        )
    return published


if __name__ == "__main__":
    results = sync_new_listings()
    if not results:
        print("✅ 沒有新建案需要同步（所有「網站上架」的建案都已同步過）。")
    else:
        print(f"同步結果（共 {len(results)} 筆）：")
        for r in results:
            if "error" in r:
                print(f"  ❌ {r['title']}：{r['error']}")
            else:
                print(f"  ✅ {r['title']} → {r['edit_url']}")
        print(f"\n狀態：{config.WP_POST_STATUS}（草稿請記得到後台人工審核後再正式發佈）。")
