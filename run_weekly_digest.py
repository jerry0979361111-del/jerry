"""澳洲房產週報：從權威澳洲房產網站取材，整理成原創繁體中文週報 → 上架到 WordPress 草稿。

用法：
    python run_weekly_digest.py

供 GitHub Actions 每週排程呼叫，也可手動執行測試。
"""
import config
import pipeline


def main() -> None:
    print(f"\n🧠 正在用 {config.CLAUDE_MODEL} 生成澳洲房產週報…")
    if config.ENABLE_WEB_SEARCH:
        print("   （已開啟 web search，會查詢 realestate.com.au / domain.com.au / SQM Research / Cotality 本週資料，過程約需 3-5 分鐘）")

    result = pipeline.create_weekly_digest_draft()

    print("✅ 已上架到草稿夾！")
    print(f"   標題　　　：{result['title']}")
    print(f"   焦點關鍵字：{result['focus_keyword']}")
    print(f"   引用來源數：{result['source_count']} 篇")
    print(
        f"   配圖　　　：候選 {result['media_candidates']} 張／"
        f"精選圖 {'有' if result['featured_set'] else '無'}／"
        f"內文插圖 {result['inline_count']} 張"
    )
    print(f"   編輯連結：{result['edit_url']}")
    print("\n⚠️ 內容為 AI 整理自多個來源，請務必人工審核（含引用是否適當、連結是否正確）後再發佈。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — CLI 最外層，統一顯示友善錯誤
        raise SystemExit(f"\n❌ 發生錯誤：{exc}")
