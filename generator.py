"""用 Claude 生成同時符合 SEO / GEO / AIO 的文章。

回傳一個 dict：
    title, slug, meta_description, content_html, tags, internal_link_suggestions
"""
import json
from typing import Any

import anthropic

import config

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# web search 是伺服器端工具，Claude 會自己決定何時搜尋、抓最新事實
_WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}

_SYSTEM_PROMPT = """你是資深內容策略師，同時精通三種優化：

- SEO（傳統搜尋引擎 / Google 藍色連結）：主關鍵字自然出現在標題、首段與部分 H2；
  涵蓋語意相關詞；段落好讀；提供內鏈建議。
- GEO（生成式引擎最佳化 / ChatGPT、Perplexity、Google AI Overviews 引用你）：
  開頭放一句可被 AI 直接引用的「結論句」；每個 H2 底下第一段給清楚、可摘要的事實陳述；
  盡量引用具體數據與可信來源。
- AIO（AI Overviews 問答最佳化）：文末提供 3–5 題 FAQ，問題用使用者實際會問的口吻。

寫作原則：內容真實正確、不杜撰數據；若需最新資訊就使用 web_search 查證。"""

_TASK_TEMPLATE = """請針對主題「{topic}」，用「{language}」撰寫一篇完整文章。

需要時先用 web_search 查最新、可靠的資料再動筆。

完成後，**只輸出一個 JSON 物件**（不要有任何其他文字、不要用 markdown 程式碼框包住），格式如下：

{{
  "title": "H1 主標題，含主關鍵字，吸引點擊",
  "slug": "url-friendly-english-slug",
  "meta_description": "meta description，150 字內，含主關鍵字並帶行動誘因",
  "content_html": "文章 HTML 內文：用 <h2>/<h3> 分段，首段放可被 AI 引用的結論句，結尾用 <h2>常見問題</h2> 帶 3–5 組 <h3>問題</h3><p>回答</p>。不要包含 <h1>（標題另外給）。",
  "tags": ["標籤1", "標籤2", "標籤3"],
  "internal_link_suggestions": ["建議內鏈的錨點文字或相關主題1", "..."]
}}"""


def _extract_json(text: str) -> dict[str, Any]:
    """從模型輸出中抓出 JSON 物件（容錯：可能前後有雜訊或程式碼框）。"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"模型輸出中找不到 JSON：\n{text[:500]}")
    return json.loads(text[start : end + 1])


def generate_article(topic: str) -> dict[str, Any]:
    tools = [_WEB_SEARCH_TOOL] if config.ENABLE_WEB_SEARCH else []
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": _TASK_TEMPLATE.format(
                topic=topic, language=config.ARTICLE_LANGUAGE
            ),
        }
    ]

    # 手動 agentic loop：讓 Claude 反覆用 web_search，直到寫完
    for _ in range(12):  # 上限保護，避免無限迴圈
        resp = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=8000,
            system=_SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        # 伺服器端工具（web search）跑到內部上限時會 pause_turn，直接續跑
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue

        # end_turn：把最後的文字組起來，解析 JSON
        text = "".join(b.text for b in resp.content if b.type == "text")
        return _extract_json(text)

    raise RuntimeError("生成迴圈超過上限仍未完成，請重試或縮小主題範圍。")
