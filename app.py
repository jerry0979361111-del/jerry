"""給員工用的網頁版：輸入主題 → 生成 SEO/GEO/AIO 文章 → 上架到 WordPress 草稿。

- 用存取密碼（APP_PASSWORD）保護，避免網址外流被亂用。
- 生成需時 2–3 分鐘，採背景執行 + 狀態頁自動更新。
"""
import os
import threading
import uuid
from html import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import pipeline

APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()

app = FastAPI(title="AI 文章產生器")

# 簡易背景任務儲存（單機、記憶體內；適合小團隊內部使用）
JOBS: dict[str, dict] = {}


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html>
<html lang="zh-Hant"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif;
         max-width: 560px; margin: 0 auto; padding: 24px; color: #1a1a1a;
         background: #f7f7f8; }}
  h1 {{ font-size: 1.4rem; }}
  .card {{ background: #fff; border-radius: 14px; padding: 24px;
           box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  label {{ display: block; font-weight: 600; margin: 16px 0 6px; }}
  input {{ width: 100%; padding: 12px; font-size: 1rem; border: 1px solid #ccc;
           border-radius: 8px; }}
  button {{ width: 100%; margin-top: 20px; padding: 14px; font-size: 1.05rem;
            font-weight: 600; color: #fff; background: #2563eb; border: 0;
            border-radius: 8px; cursor: pointer; }}
  button:hover {{ background: #1d4ed8; }}
  .muted {{ color: #666; font-size: .9rem; }}
  .err {{ color: #b91c1c; font-weight: 600; }}
  .ok {{ color: #15803d; font-weight: 600; }}
  a.btn {{ display: inline-block; margin-top: 16px; padding: 10px 16px;
           background: #16a34a; color: #fff; border-radius: 8px;
           text-decoration: none; }}
  .spin {{ display:inline-block; width:16px; height:16px; border:3px solid #ddd;
           border-top-color:#2563eb; border-radius:50%; animation:spin 1s linear infinite;
           vertical-align:-3px; margin-right:8px; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head><body>{body}</body></html>""")


@app.get("/", response_class=HTMLResponse)
def home(error: str = ""):
    err_html = f'<p class="err">{escape(error)}</p>' if error else ""
    return _page("AI 文章產生器", f"""
<h1>✍️ AI 文章產生器</h1>
<div class="card">
  {err_html}
  <form method="post" action="/generate">
    <label>文章主題</label>
    <input name="topic" placeholder="例：墨爾本必吃美食推薦" required autofocus>
    <label>存取密碼</label>
    <input name="password" type="password" placeholder="請向管理員索取" required>
    <button type="submit">生成並上架到草稿</button>
  </form>
  <p class="muted">送出後會生成文章並存到 WordPress 草稿夾，約需 2–3 分鐘。</p>
</div>""")


def _run_job(job_id: str, topic: str) -> None:
    try:
        result = pipeline.create_draft(topic)
        JOBS[job_id].update(
            status="done",
            title=result["title"],
            edit_url=result["edit_url"],
        )
    except Exception as exc:  # noqa: BLE001 — 背景任務統一收斂錯誤
        JOBS[job_id].update(status="error", error=str(exc))


@app.post("/generate")
def generate(topic: str = Form(...), password: str = Form(...)):
    if not APP_PASSWORD:
        return RedirectResponse("/?error=" + escape("伺服器尚未設定 APP_PASSWORD"), 303)
    if password != APP_PASSWORD:
        return RedirectResponse("/?error=" + escape("存取密碼錯誤"), 303)

    topic = topic.strip()
    if not topic:
        return RedirectResponse("/?error=" + escape("主題不可為空"), 303)

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "running", "topic": topic, "title": None,
                    "edit_url": None, "error": None}
    threading.Thread(target=_run_job, args=(job_id, topic), daemon=True).start()
    return RedirectResponse(f"/status/{job_id}", 303)


@app.get("/status/{job_id}", response_class=HTMLResponse)
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return RedirectResponse("/?error=" + escape("找不到這筆任務"), 303)

    topic = escape(job["topic"])
    if job["status"] == "running":
        body = f"""
<h1>生成中…</h1>
<div class="card">
  <p><span class="spin"></span>正在生成並上架：「{topic}」</p>
  <p class="muted">約需 2–3 分鐘，本頁會自動更新，請不要關閉。</p>
</div>
<meta http-equiv="refresh" content="5">"""
    elif job["status"] == "done":
        body = f"""
<h1>✅ 完成！</h1>
<div class="card">
  <p class="ok">已生成並存到 WordPress 草稿夾</p>
  <p><strong>{escape(job['title'])}</strong></p>
  <a class="btn" href="{escape(job['edit_url'])}" target="_blank">前往 WordPress 編輯／審核</a>
  <p style="margin-top:20px"><a href="/">← 再寫一篇</a></p>
</div>"""
    else:  # error
        body = f"""
<h1>❌ 發生錯誤</h1>
<div class="card">
  <p class="err">主題「{topic}」生成失敗</p>
  <p class="muted">{escape(job['error'] or '')}</p>
  <p style="margin-top:20px"><a href="/">← 返回重試</a></p>
</div>"""
    return _page("任務狀態", body)


@app.get("/healthz")
def healthz():
    return {"ok": True}
