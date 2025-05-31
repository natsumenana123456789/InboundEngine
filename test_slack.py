import requests
import json
import yaml

def load_config():
    with open('config/config.yml', 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def test_slack_webhook():
    config = load_config()
    webhook_url = config['auto_post_bot']['slack_webhook_url']
    accounts = config['auto_post_bot']['twitter_accounts']
    
    account_list = "\n".join([f"• {acc['account_id']}" for acc in accounts])
    
    message = {
        "text": "🔍 設定テスト\n\n*登録されているアカウント:*\n" + account_list + "\n\n*投稿設定:*\n" + 
                f"• 1日の投稿数: {config['auto_post_bot']['posting_settings']['posts_per_account']}件\n" +
                f"• 投稿間隔: {config['auto_post_bot']['posting_settings']['min_interval_hours']}時間\n" +
                f"• 投稿時間帯: {config['auto_post_bot']['schedule_settings']['start_hour']}時-{config['auto_post_bot']['schedule_settings']['end_hour']}時"
    }
    
    try:
        response = requests.post(webhook_url, json=message)
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンス: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhook URLは有効です")
        else:
            print("❌ Webhook URLは無効です")
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {str(e)}")

if __name__ == "__main__":
    test_slack_webhook() 