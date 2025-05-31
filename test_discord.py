import yaml
from bots.auto_post_bot.discord_notifier import DiscordNotifier

def load_config():
    with open('config/config.yml', 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def test_discord_webhook():
    config = load_config()
    webhook_url = config['auto_post_bot']['discord_notification']['webhook_url']
    
    notifier = DiscordNotifier(webhook_url)
    
    # テスト用のスケジュールデータ
    schedule_data = {
        "hinataMaking": [
            "10:00",
            "13:00",
            "16:00",
            "19:00",
            "22:00"
        ],
        "ZaikerLong": [
            "10:30",
            "13:30",
            "16:30",
            "19:30",
            "21:30"
        ]
    }
    
    print("スケジュール通知をテスト送信中...")
    success = notifier.send_schedule_notification(schedule_data)
    print("スケジュール通知:", "成功" if success else "失敗")
    
    print("\n投稿成功通知をテスト送信中...")
    success = notifier.send_post_notification(
        account="hinataMaking",
        status="成功",
        details="投稿ID: 12345\n画像: example.jpg"
    )
    print("投稿成功通知:", "成功" if success else "失敗")
    
    print("\n投稿失敗通知をテスト送信中...")
    success = notifier.send_post_notification(
        account="ZaikerLong",
        status="失敗",
        details="エラー: API制限に到達しました"
    )
    print("投稿失敗通知:", "成功" if success else "失敗")

if __name__ == "__main__":
    test_discord_webhook() 