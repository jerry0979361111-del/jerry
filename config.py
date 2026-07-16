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


def _optional(key: str, default: str) -> str:
    """選填變數：未設定或設成空字串時，一律套用預設值。

    （GitHub Actions 在變數未定義時會傳空字串，需要這層保護。）
    """
    value = os.getenv(key, "").strip()
    return value if value else default


# ── Claude ──────────────────────────────────────────────
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
CLAUDE_MODEL = _optional("CLAUDE_MODEL", "claude-opus-4-8")
ENABLE_WEB_SEARCH = _optional("ENABLE_WEB_SEARCH", "1") == "1"

# ── WordPress ───────────────────────────────────────────
WP_BASE_URL = _require("WP_BASE_URL").rstrip("/")
WP_USERNAME = _require("WP_USERNAME")
# 應用程式密碼裡的空格不影響驗證，這裡去掉讓貼上更方便
WP_APP_PASSWORD = _require("WP_APP_PASSWORD").replace(" ", "")
WP_POST_STATUS = _optional("WP_POST_STATUS", "draft")

# ── 文章 ────────────────────────────────────────────────
ARTICLE_LANGUAGE = _optional("ARTICLE_LANGUAGE", "繁體中文")

# 參考既有文章的結構/風格：用關鍵字篩選站上已發佈文章當範本
REFERENCE_QUERY = _optional("REFERENCE_QUERY", "移民")
REFERENCE_COUNT = int(_optional("REFERENCE_COUNT", "2"))

# 保底配圖：AI 找不到夠相關的圖時，仍用媒體庫最接近的一張（1=開 0=關）
IMAGE_FALLBACK = _optional("IMAGE_FALLBACK", "1") == "1"
