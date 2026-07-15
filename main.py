"""指令列進入點：輸入主題 → 生成 SEO/GEO/AIO 文章 → 發到 WordPress 草稿夾。

用法：
    python main.py "你的文章主題"
    python main.py                # 不帶參數會互動式詢問主題
"""
import sys

import config
import pipeline


def main() -> None:
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:]).strip()
    else:
        topic = input("請輸入文章主題：").strip()

    if not topic:
        raise SystemExit("主題不可為空。")

    print(f"\n🧠 正在用 {config.CLAUDE_MODEL} 生成文章：「{topic}」")
    if config.ENABLE_WEB_SEARCH:
        print("   （已開啟 web search，會查最新資料 + 配圖，過程約需 2–3 分鐘）")

    result = pipeline.create_draft(topic)

    print("✅ 已上架到草稿夾！")
    print(f"   標題　　：{result['title']}")
    print(f"   焦點關鍵字：{result['focus_keyword']}")
    print(f"   配圖　　：{'已加入' if result['image_used'] else '媒體庫中無相關圖片，略過'}")
    print(f"   編輯連結：{result['edit_url']}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception as exc:  # noqa: BLE001 — CLI 最外層，統一顯示友善錯誤
        raise SystemExit(f"\n❌ 發生錯誤：{exc}")
