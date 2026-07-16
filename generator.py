"""用 Claude 生成同時符合 SEO / GEO / AIO 的文章，並從媒體庫挑選圖片。"""
import json
import re
from typing import Any

import anthropic

import config

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

_WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}

_SYSTEM_PROMPT = """你是資深內容策略師，同時精通三種優化：

- SEO（Google）：選定一個明確的「焦點關鍵字」，讓它自然出現在 H1 標題、第一句話、
  meta description、以及全文多次（約每 100–150 字出現一次，但不堆砌）。
- GEO（讓 ChatGPT / Perplexity / Google AI Overviews 引用你）：開頭放一句可被 AI 直接
  引用的結論句；每個 H2 底下第一段給清楚、可摘要的事實陳述；引用具體數據與可信來源。
- AIO（AI Overviews 問答優化）：文末提供 3–5 題 FAQ，用使用者真正會問的口吻。

品質底線：內容真實正確、不杜撰數據；需要最新資訊就用 web_search 查證。"""

_TASK_TEMPLATE = """請針對主題「{topic}」，用「{language}」撰寫一篇**完整、有深度**的文章。

需要時先用 web_search 查最新可靠資料再動筆。

**硬性要求（務必做到，否則 SEO 分數會很低）：**
1. 內文長度**至少 1500 個中文字**（不含 HTML 標籤），越充實越好。
2. 先決定一個明確的「焦點關鍵字」（focus_keyword），2–4 個字最理想。
3. 焦點關鍵字必須出現在：H1 標題、內文第一句、meta description、以及全文自然出現多次（密度約 1%）。
4. 內文用 **4–6 個 <h2> 段落**，每個 <h2> 下至少 2 段文字；適當時用 <ul>/<ol> 條列。
5. **至少一個 <h2> 或 <h3> 小標要包含焦點關鍵字。**
6. 內文中自然加入 **1 個指向權威外部網站的超連結**（<a href="..."> 指向政府/官方/權威來源，例如官方移民或統計網站）。
7. 文末用 <h2>常見問題</h2> 帶 3–5 組 <h3>問題</h3><p>回答</p>。

完成後，**只輸出一個 JSON 物件**（不要有任何其他文字、不要用程式碼框包住）：

{{
  "focus_keyword": "焦點關鍵字（2–4 字）",
  "title": "H1 主標題，必須包含焦點關鍵字，吸引點擊，60 字內",
  "slug": "url-friendly-english-slug",
  "meta_description": "meta description，150 字內，開頭就含焦點關鍵字並帶行動誘因",
  "content_html": "文章 HTML 內文（至少 800 字）：首段第一句含焦點關鍵字且為可被 AI 引用的結論句；用 <h2>/<h3> 分段；結尾含 FAQ。不要包含 <h1>。",
  "image_query": "用來在媒體庫搜尋配圖的 2–3 個關鍵詞，逗號分隔",
  "tags": ["標籤1", "標籤2", "標籤3"]
}}"""

_IMAGE_PICK_PROMPT = """文章主題：「{topic}」

以下是網站媒體庫的圖片清單（JSON）。請挑出最適合當這篇文章「精選圖」的一張，
以及最多 2 張適合插入內文的圖。只能從清單裡挑，若沒有任何相關的就回傳 null / 空陣列。

媒體清單：
{candidates}

**只輸出 JSON**：
{{"featured_media_id": 數字或 null, "inline_media_ids": [數字, ...]}}"""


def _extract_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"模型輸出中找不到 JSON：\n{text[:500]}")
    return json.loads(text[start : end + 1])


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _summarize_reference(post: dict[str, Any]) -> str:
    """把一篇範本文章濃縮成「結構骨架 + 開頭語氣」，讓 AI 參考而非抄襲。"""
    html = post.get("content_html", "")
    headings = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html, flags=re.I | re.S)
    outline = "\n".join(f"  - {_strip_tags(h)}" for h in headings[:12]) or "  （無明顯小標）"
    intro = _strip_tags(html)[:220]
    return f"標題：{_strip_tags(post.get('title', ''))}\n段落結構：\n{outline}\n開頭語氣：{intro}…"


def _reference_block(references: list[dict[str, Any]] | None) -> str:
    if not references:
        return ""
    blocks = "\n\n".join(_summarize_reference(p) for p in references)
    return (
        "\n\n【本站既有文章範例】請**沿用相似的段落結構、小標命名風格、語氣與深度**，"
        "但內容要針對本次主題全新撰寫，不可抄襲或改寫既有文章：\n\n" + blocks
    )


def _internal_link_note(links: list[str] | None) -> str:
    links = [ln for ln in (links or []) if ln][:3]
    if not links:
        return ""
    joined = "\n".join(f"  - {ln}" for ln in links)
    return (
        "\n\n【內部連結】請在內文中自然嵌入 **1 個 <a href> 超連結**，指向下列其中一個本站既有文章"
        "（用相關的錨點文字，不要用「這裡」）：\n" + joined
    )


def _run_loop(messages: list[dict], tools: list, max_tokens: int) -> str:
    """執行 agentic loop（處理 web search 的 pause_turn），回傳最後的文字。"""
    for _ in range(12):
        resp = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=_SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        return "".join(b.text for b in resp.content if b.type == "text")
    raise RuntimeError("生成迴圈超過上限仍未完成，請重試或縮小主題範圍。")


def generate_article(
    topic: str,
    references: list[dict[str, Any]] | None = None,
    internal_links: list[str] | None = None,
) -> dict[str, Any]:
    tools = [_WEB_SEARCH_TOOL] if config.ENABLE_WEB_SEARCH else []
    prompt = (
        _TASK_TEMPLATE.format(topic=topic, language=config.ARTICLE_LANGUAGE)
        + _reference_block(references)
        + _internal_link_note(internal_links)
    )
    messages = [{"role": "user", "content": prompt}]
    return _extract_json(_run_loop(messages, tools, max_tokens=16000))


def choose_images(topic: str, candidates: list[dict]) -> dict[str, Any]:
    """讓 Claude 從媒體庫候選圖片中挑出精選圖與內文插圖。"""
    if not candidates:
        return {"featured_media_id": None, "inline_media_ids": []}
    slim = [
        {
            "id": c["id"],
            "title": c.get("title", ""),
            "alt": c.get("alt", ""),
            "filename": c.get("filename", ""),
        }
        for c in candidates
    ]
    resp = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": _IMAGE_PICK_PROMPT.format(
                    topic=topic,
                    candidates=json.dumps(slim, ensure_ascii=False),
                ),
            }
        ],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        data = _extract_json(text)
        return {
            "featured_media_id": data.get("featured_media_id"),
            "inline_media_ids": data.get("inline_media_ids") or [],
        }
    except (ValueError, json.JSONDecodeError):
        return {"featured_media_id": None, "inline_media_ids": []}
