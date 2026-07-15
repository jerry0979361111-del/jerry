"""指令列進入點：輸入主題 → 生成 SEO/GEO/AIO 文章 → 發到 WordPress 草稿夾。

用法：
    python main.py "你的文章主題"
    python main.py                # 不帶參數會互動式詢問主題
"""
import sys

import config
import generator
import wordpress


def main() -> None:
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:]).strip()
    else:
        topic = input("請輸入文章主題：").strip()

    if not topic:
        raise SystemExit("主題不可為空。")

    print(f"\n🧠 正在用 {config.CLAUDE_MODEL} 生成文章：「{topic}」")
    if config.ENABLE_WEB_SEARCH:
        print("   （已開啟 web search，會查最新資料，過程約需 1–3 分鐘）")
    article = generator.generate_article(topic)
    print(f"✅ 生成完成：{article['title']}")

    print(f"\n📤 正在發佈到 WordPress（狀態：{config.WP_POST_STATUS}）…")
    post = wordpress.publish_draft(article)

    edit_url = f"{config.WP_BASE_URL}/wp-admin/post.php?post={post['id']}&action=edit"
    print("✅ 已上架！")
    print(f"   文章 ID：{post['id']}")
    print(f"   狀態　：{post.get('status')}")
    print(f"   編輯連結：{edit_url}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception as exc:  # noqa: BLE001 — CLI 最外層，統一顯示友善錯誤
        raise SystemExit(f"\n❌ 發生錯誤：{exc}")
