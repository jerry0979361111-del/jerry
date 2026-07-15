# WordPress AI 文章產生器（SEO / GEO / AIO）

輸入一個主題，用 Claude 自動生成同時符合 **SEO**、**GEO**、**AIO** 的文章，並自動上架到你的 WordPress 網站草稿夾。

- **SEO** — 傳統搜尋引擎（Google）：關鍵字、標題結構、內鏈建議
- **GEO** — 讓 ChatGPT / Perplexity / Google AI Overviews 引用你：可摘要的結論句、事實陳述
- **AIO** — AI Overviews 問答優化：文末 FAQ

生成的文章預設存成**草稿**，方便人工審核後再上架（強烈建議，AI 內容務必先審）。

---

## 運作流程

```
輸入主題 ──▶ Claude 生成（含 web search 抓最新資料）──▶ WordPress REST API ──▶ 草稿夾
```

## 安裝

需要 Python 3.10+。

```bash
pip install -r requirements.txt
cp .env.example .env
```

然後編輯 `.env`，填入下列資訊：

| 變數 | 說明 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 金鑰，來自 <https://console.anthropic.com> |
| `WP_BASE_URL` | 你的 WordPress 網址，例：`https://example.com` |
| `WP_USERNAME` | WordPress 使用者名稱 |
| `WP_APP_PASSWORD` | **應用程式密碼**（不是登入密碼，見下方） |

### 如何取得 WordPress 應用程式密碼

1. 登入 WordPress 後台
2. 左側選單 → **使用者** → **個人資料**
3. 捲到最下方 **「應用程式密碼」**，輸入名稱（例：`ai-writer`）→ 點「新增」
4. 複製產生的密碼（形如 `xxxx xxxx xxxx xxxx xxxx xxxx`）貼進 `.env`

> 找不到「應用程式密碼」欄位？它需要網站在 HTTPS 下才會顯示；若仍沒有，可能是被安全外掛停用，需先啟用。

## 使用

```bash
# 直接帶主題
python main.py "2026 年 SEO 趨勢有哪些"

# 或不帶參數，互動式輸入
python main.py
```

跑完會印出文章 ID 與後台編輯連結，到 WordPress 後台的「文章 → 草稿」即可看到並審核。

## 設定選項（.env）

| 變數 | 預設 | 說明 |
|---|---|---|
| `CLAUDE_MODEL` | `claude-opus-4-8` | 想省成本可改 `claude-sonnet-5` |
| `ENABLE_WEB_SEARCH` | `1` | `1` 開啟 web search 抓最新資料；`0` 關閉（更快、更省） |
| `WP_POST_STATUS` | `draft` | `draft` 草稿 / `pending` 待審 / `publish` 直接上架 |
| `ARTICLE_LANGUAGE` | `繁體中文` | 文章語言 |

## 檔案結構

| 檔案 | 職責 |
|---|---|
| `main.py` | 指令列進入點 |
| `generator.py` | 呼叫 Claude 生成 SEO/GEO/AIO 文章 |
| `wordpress.py` | 透過 REST API 發佈到 WordPress |
| `config.py` | 讀取 `.env` 設定 |

## 常見問題

**meta description 有進到 Yoast / RankMath 嗎？**
目前 meta description 會寫進 WordPress 的「摘要（excerpt）」欄位。若你用 Yoast 或 RankMath 並想同步它們專屬的 meta 欄位，需要額外對接該外掛的欄位（可再擴充，跟我說一聲）。

**之後想接 SignalSurf 自動選題？**
目前是手動輸入主題。之後可把 `generator + wordpress` 包成一個 webhook 端點，由 SignalSurf 的訊號自動觸發（需要它的 webhook 文件）。

## 注意事項

- `.env` 已列入 `.gitignore`，金鑰不會被 commit。
- 大量自動發佈 AI 內容且未經審核，可能被 Google 判定為低品質內容——請維持人工審核，這也是預設存草稿的原因。
