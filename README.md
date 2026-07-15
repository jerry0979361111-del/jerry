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

---

## 不想開電腦？用 GitHub Actions 在雲端跑（推薦）

程式碼放在 GitHub 後，可以直接用 GitHub 的雲端環境執行，**不需要自己的電腦開機**、免費。

### 一次性設定：把金鑰存進 GitHub

到你的 GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，新增下列 4 個 secret：

| 名稱 | 值 |
|---|---|
| `ANTHROPIC_API_KEY` | 你的 Claude 金鑰 |
| `WP_BASE_URL` | 你的網站網址，例：`https://example.com` |
| `WP_USERNAME` | WordPress 使用者名稱 |
| `WP_APP_PASSWORD` | WordPress 應用程式密碼 |

（選填）想改模型或發佈狀態，可在同頁的 **Variables** 分頁新增 `CLAUDE_MODEL`、`WP_POST_STATUS`、`ENABLE_WEB_SEARCH`、`ARTICLE_LANGUAGE`。

### 每次要寫文章時

1. 到 repo 上方的 **Actions** 分頁
2. 左側點 **「生成文章並上架到 WordPress 草稿」**
3. 右側點 **「Run workflow」**，輸入主題 → 執行
4. 約 2–3 分鐘後，到 WordPress 後台「文章 → 草稿」查看

> Secret 一旦存入就無法再讀出（只能覆寫），金鑰不會外洩、也不會出現在執行紀錄裡。

## 給員工用的網頁版（不需 GitHub 帳號）

`app.py` 是一個網頁服務：員工打開網址、輸入主題與**存取密碼**、按送出，就會生成文章並存到 WordPress 草稿。適合團隊使用——員工完全不用碰你的 GitHub。

本機測試：

```bash
pip install -r requirements.txt
# .env 需額外設一個 APP_PASSWORD（員工要輸入的通行碼）
uvicorn app:app --reload
# 打開 http://127.0.0.1:8000
```

### 部署到 Render.com（免費、永遠在線）

1. 到 <https://render.com> 用 GitHub 註冊登入
2. 點 **New → Blueprint**，選這個 repo（它會讀取 `render.yaml`）
3. Render 會要你填下列環境變數（不會寫進程式碼）：

   | 變數 | 值 |
   |---|---|
   | `APP_PASSWORD` | 你自訂一組給員工輸入的通行碼 |
   | `ANTHROPIC_API_KEY` | Claude 金鑰 |
   | `WP_BASE_URL` | `https://www.mejia.au` |
   | `WP_USERNAME` | WordPress 使用者名稱 |
   | `WP_APP_PASSWORD` | WordPress 應用程式密碼 |

4. 部署完成後會得到一個網址（如 `https://ai-article-writer.onrender.com`）
5. 把**網址**與**存取密碼**發給員工即可，他們開網址就能用

> 免費方案閒置一段時間會休眠，第一位使用者開啟時需多等約 30 秒喚醒，屬正常。

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

## SEO / GEO / AIO 優化做了什麼

每篇文章生成時會自動：

- **選定焦點關鍵字**，放進 H1 標題、內文第一句、meta description，並在全文自然出現多次
- **內文至少 800 字**、4–6 個 H2 段落、文末 FAQ（滿足 Rank Math 長度與問答要求）
- **自動填入 Rank Math 欄位**（焦點關鍵字 / SEO 標題 / Meta 描述）— 需先做下方一次性設定
- **從你的媒體庫挑相關圖片**當精選圖與內文插圖（只用你網站自己的圖，不用外部圖）

### 一次性設定：讓程式能自動填 Rank Math 欄位

Rank Math 的 SEO 欄位預設不開放 API 寫入，需在你的網站註冊一次。**最簡單的方式**是裝免費外掛 **Code Snippets**（外掛 → 安裝外掛 → 搜尋「Code Snippets」→ 安裝並啟用），然後新增一個 snippet，貼上：

```php
add_action('init', function () {
    foreach (['rank_math_focus_keyword', 'rank_math_title', 'rank_math_description'] as $key) {
        register_post_meta('post', $key, [
            'type' => 'string',
            'single' => true,
            'show_in_rest' => true,
            'auth_callback' => function () { return current_user_can('edit_posts'); },
        ]);
    }
}, 99);
```

存檔並啟用（Active）即可。之後生成的文章就會自動帶入焦點關鍵字與 SEO 標題／描述。

> 沒做這步也能用——文章一樣寫得很完整，只是你打開草稿時要自己在 Rank Math 手動填一次焦點關鍵字（程式選的關鍵字也會放在文章標籤裡供參考）。

## 常見問題

**媒體庫找不到相關圖片會怎樣？**
會略過配圖、照常發文。想提高命中率，請幫媒體庫的圖片加上有意義的**標題 / 替代文字（alt）**，程式才找得到相關圖。

**之後想接 SignalSurf 自動選題？**
目前是手動輸入主題。之後可把 `generator + wordpress` 包成一個 webhook 端點，由 SignalSurf 的訊號自動觸發（需要它的 webhook 文件）。

## 注意事項

- `.env` 已列入 `.gitignore`，金鑰不會被 commit。
- 大量自動發佈 AI 內容且未經審核，可能被 Google 判定為低品質內容——請維持人工審核，這也是預設存草稿的原因。
