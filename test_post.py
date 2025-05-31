import yaml
import tweepy
from discord_webhook import DiscordWebhook, DiscordEmbed
import logging
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    with open('config/config.yml', 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def get_twitter_client(account_config):
    client = tweepy.Client(
        consumer_key=account_config['consumer_key'],
        consumer_secret=account_config['consumer_secret'],
        access_token=account_config['access_token'],
        access_token_secret=account_config['access_token_secret']
    )
    return client

def send_discord_notification(webhook_url, account, status, details=""):
    try:
        color = 0x00ff00 if status == "成功" else 0xff0000
        emoji = "✅" if status == "成功" else "❌"
        
        embed = DiscordEmbed(
            title=f"{emoji} テスト投稿{status}",
            color=color
        )
        
        embed.add_embed_field(
            name="アカウント",
            value=f"📱 {account}",
            inline=False
        )
        
        if details:
            embed.add_embed_field(
                name="詳細情報",
                value=f"```{details}```",
                inline=False
            )
            
        webhook = DiscordWebhook(url=webhook_url)
        webhook.add_embed(embed)
        response = webhook.execute()
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"Discord通知エラー: {str(e)}")
        return False

def test_post():
    config = load_config()
    
    # ZaikerLongアカウントの設定を取得
    account_config = None
    for account in config['auto_post_bot']['twitter_accounts']:
        if account['account_id'] == 'ZaikerLong':
            account_config = account
            break
    
    if not account_config:
        raise ValueError("ZaikerLongアカウントの設定が見つかりません")
    
    # Twitter APIクライアントを初期化
    client = get_twitter_client(account_config)
    
    # Discord Webhook URL
    webhook_url = config['auto_post_bot']['discord_notification']['webhook_url']
    
    try:
        # テスト投稿を実行
        test_text = f"テスト投稿\n実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n#テスト"
        response = client.create_tweet(text=test_text)
        
        # 成功通知
        success_details = f"ツイートID: {response.data['id']}\n投稿内容: {test_text}"
        send_discord_notification(webhook_url, "ZaikerLong", "成功", success_details)
        logger.info("テスト投稿が成功しました")
        
    except Exception as e:
        # エラー通知
        error_details = f"エラー: {str(e)}"
        send_discord_notification(webhook_url, "ZaikerLong", "失敗", error_details)
        logger.error(f"テスト投稿でエラーが発生しました: {str(e)}")

if __name__ == "__main__":
    test_post() 