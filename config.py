"""集中管理環境變數設定。"""
import os

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise SystemExit(
            f"缺少必要環境變數 {key}，請複製 .env.example 成 .env 並填寫。"
        )
    return value


# ── Claude ──────────────────────────────────────────────
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8").strip()
ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "1").strip() == "1"

# ── WordPress ───────────────────────────────────────────
WP_BASE_URL = _require("WP_BASE_URL").rstrip("/")
WP_USERNAME = _require("WP_USERNAME")
# 應用程式密碼裡的空格不影響驗證，這裡去掉讓貼上更方便
WP_APP_PASSWORD = _require("WP_APP_PASSWORD").replace(" ", "")
WP_POST_STATUS = os.getenv("WP_POST_STATUS", "draft").strip()

# ── 文章 ────────────────────────────────────────────────
ARTICLE_LANGUAGE = os.getenv("ARTICLE_LANGUAGE", "繁體中文").strip()
