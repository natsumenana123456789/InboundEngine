import os
import time
from datetime import datetime
from src.notifiers.discord_notifier import DiscordNotifier

def main():
    # 実際のWebhook URLを環境変数から取得
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL environment variable is not set")
        return

    notifier = DiscordNotifier(webhook_url=webhook_url)

    # 1. 基本的な通知テスト
    print("1. 基本的な通知テスト")
    notifier.send_embed(
        title="実機テスト：基本通知",
        description="基本的な通知のテストです",
        fields={
            "テスト時刻": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "環境": "開発環境",
            "テスト種別": "実機テスト"
        },
        color="#00ff00"
    )
    time.sleep(2)  # Discord APIの制限を考慮

    # 2. エラー通知テスト
    print("2. エラー通知テスト")
    notifier.send_error(
        "実機テスト：エラー通知",
        {
            "エラー種別": "TestError",
            "発生時刻": datetime.now().strftime("%H:%M:%S"),
            "スタックトレース": "長いスタックトレース...\n" * 3  # 長いテキストの表示確認
        }
    )
    time.sleep(2)

    # 3. レート制限テスト
    print("3. レート制限テスト")
    for i in range(5):  # 短時間に複数回送信
        notifier.send_embed(
            title=f"実機テスト：レート制限 ({i+1}/5)",
            description="レート制限のテストです",
            fields={
                "送信回数": f"{i+1}回目",
                "送信時刻": datetime.now().strftime("%H:%M:%S")
            },
            color="#ffff00"
        )
        time.sleep(1)  # 1秒間隔で送信

if __name__ == "__main__":
    main() 