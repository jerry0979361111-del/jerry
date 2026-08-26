"""生成「澳洲房產週報」：從權威澳洲房產網站找本週熱門報導，整理成原創繁體中文週報。

重要：這不是逐篇翻譯轉貼。規則見 _DIGEST_SYSTEM_PROMPT——只做原創摘要/分析，
單一來源只能短引用並附連結回原文，圖表/表格一律自己依數據重新製作。
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import generator  # 重用 _extract_json / _run_loop / client

_SOURCES = [
    ("realestate.com.au", "https://www.realestate.com.au/news/"),
    ("domain.com.au", "https://www.domain.com.au/news/"),
    ("SQM Research", "https://sqmresearch.com.au/"),
    ("Cotality (前 CoreLogic)", "https://www.cotality.com/au"),
]

_CATEGORIES = [
    "房產教學指引",
    "房地產新聞",
    "房價和租金趨勢",
    "房市專欄評論",
    "貸款利率",
    "財務會計稅務法律規定更新",
    "房產熱搜話題",
]

_DIGEST_WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 20}

_DIGEST_SYSTEM_PROMPT = """你是資深澳洲房地產內容編輯，負責製作給台灣受眾看的「澳洲房產週報」。

你會參考以下權威來源本週的報導與資料做選題，但**絕對不是翻譯或轉貼**：
- realestate.com.au、domain.com.au（房產新聞/教學/專欄）
- SQM Research（空置率、庫存等數據研究）
- Cotality（前 CoreLogic，房價指數等數據研究）

**硬性規則（違反視為失敗）：**
1. 禁止整段或整篇翻譯任何來源文章。你要做的是：讀懂內容 → 用自己的話重新分析、統整、加上對台灣讀者的意義（例如對海外買家、留學家庭、移民的影響）。
2. 引用單一來源的原文，一次最多 15 個中文字或 25 個英文字，必須加引號，且緊接著標明來源網站與可點擊連結。
3. 任何表格、圖表都必須是你**自己依據數據重新製作**的 HTML `<table>`，不得複製或模仿原網站的圖表圖片/版型；每個表格下方要加一行資料來源標注。
4. 文章整體結構、段落安排由你自主組織成一篇「週報」，不可照搬任一來源網站單篇文章的段落結構或標題命名。
5. 不確定、無法查證的數字寧可不寫，不可杜撰。
6. 每個主題段落結尾都要有一行「資料來源」，附上該段引用資料的原文連結。

GEO/AIO 優化：開頭給一句可被 AI 直接引用的整體結論句；每段第一句是可摘要的事實陳述；文末 FAQ。"""

_DIGEST_TASK_TEMPLATE = """請製作「{date_label}」這一週的澳洲房產週報，繁體中文撰寫，給台灣的海外置產者/留學生家庭/移民申請人閱讀。

**執行步驟：**
1. 用 web_search 分別搜尋下列來源本週（過去 7 天內）的文章與資料（可用 site: 搜尋語法，例如
   `site:realestate.com.au news`、`site:domain.com.au news`、`site:sqmresearch.com.au`、
   `site:cotality.com/au` 或 `corelogic home value index`）：
{source_list}
2. 從搜尋結果中，**優先挑選「有數據表格/圖表」與「討論度高、熱搜」的報導**。
3. 依下列分類整理，不需每類都有，但盡量涵蓋資料最豐富的 4–6 類：
{category_list}
4. 每個分類寫成一個 `<h2>` 段落：
   - 段落開頭第一句是可被 AI 摘要引用的結論句（含具體數據）
   - 接著 2–3 段原創分析（不是翻譯），並說明對台灣讀者（海外買家/留學家庭/移民申請人）的實際意義
   - 若有數據，用 `<table>` 呈現（自己重新製表，欄位可為城市/地區、數值、與上期比較等）
   - 段落最後一行：`<p>資料來源：<a href="原文網址" target="_blank" rel="noopener nofollow">網站名稱｜文章標題</a></p>`
5. 全文開頭一段「本週重點摘要」（3–5 條 bullet，GEO 用，AI 可直接引用）。
6. 文末 `<h2>常見問題</h2>` 帶 3–5 組 `<h3>問題</h3><p>回答</p>`（用台灣讀者真正會問的口吻，例如稅務、貸款、簽證相關）。
7. 內文長度至少 2000 個中文字（不含 HTML 標籤）。
8. SEO：你選定的焦點關鍵字（focus_keyword）除了放進標題與 meta_description，還必須：
   - 出現在「本週重點摘要」這個開頭段落的 `<h2>` 標題裡（例如標題可以是「本週{{焦點關鍵字}}重點摘要」）
   - 自然出現在全文第一句話裡
   - 在全文中再自然出現 2–3 次（例如段落間的過渡句、小結句），不要為了湊數而生硬堆疊或影響閱讀流暢度

完成後，**只輸出一個 JSON 物件**（不要有其他文字、不要用程式碼框包住）：

{{
  "focus_keyword": "本週焦點關鍵字（例：雪梨房價、RBA 利率、澳洲房市 等 2-6 字，避免使用「週報」）",
  "title": "H1 主標題，只呈現本週最重要的重點本身，自然包含焦點關鍵字，60 字內；不要加入日期、日期範圍，也不要出現「週報」兩字",
  "slug": "url-friendly-english-slug",
  "meta_description": "150 字內，開頭含焦點關鍵字並帶行動誘因",
  "content_html": "週報 HTML 內文（不要包含 <h1>，依上方步驟 4-6 撰寫）",
  "image_query": "用來在媒體庫搜尋配圖的 2-3 個關鍵詞，逗號分隔（例：澳洲,房地產,雪梨）",
  "tags": ["標籤1", "標籤2", "標籤3"],
  "sources": [
    {{"site": "來源網站名稱", "title": "被引用文章的標題", "url": "原文網址"}}
  ]
}}

sources 陣列請列出本文實際引用/取材的每一篇原文（供讀者與 AI 溯源，也是給你自己在文中附連結用的清單）。"""


def _week_label() -> str:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=7)
    return f"{start.isoformat()} ~ {today.isoformat()}"


def generate_weekly_digest() -> dict[str, Any]:
    source_list = "\n".join(f"   - {name}（{url}）" for name, url in _SOURCES)
    category_list = "\n".join(f"   - {c}" for c in _CATEGORIES)
    prompt = _DIGEST_TASK_TEMPLATE.format(
        date_label=_week_label(),
        source_list=source_list,
        category_list=category_list,
    )
    messages = [{"role": "user", "content": prompt}]
    text = generator._run_loop(
        messages, [_DIGEST_WEB_SEARCH_TOOL], max_tokens=16000, system=_DIGEST_SYSTEM_PROMPT
    )
    return generator._extract_json(text)
