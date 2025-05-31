#!/usr/bin/env python3
import os
import sys
import argparse
from discord_webhook import DiscordWebhook, DiscordEmbed
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_push_notification(webhook_url, repo, commit, author, branch):
    """
    Gitプッシュ時のDiscord通知を送信
    """
    try:
        webhook = DiscordWebhook(url=webhook_url)
        
        # 埋め込みメッセージを作成
        embed = DiscordEmbed(
            title="🔄 スクリプトが更新されました",
            color="5763719"  # 緑色
        )
        
        # フィールドを追加
        embed.add_embed_field(name="リポジトリ", value=repo, inline=True)
        embed.add_embed_field(name="コミット", value=commit, inline=True)
        embed.add_embed_field(name="作成者", value=author, inline=True)
        embed.add_embed_field(name="ブランチ", value=branch, inline=True)
        
        # 埋め込みメッセージを追加して送信
        webhook.add_embed(embed)
        response = webhook.execute()
        
        if response.status_code == 200:
            logger.info("Discord通知送信成功")
            return True
        else:
            logger.error(f"Discord通知送信失敗: ステータスコード {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Discord通知送信エラー: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Discord通知送信スクリプト')
    parser.add_argument('--type', required=True, choices=['push'], help='通知タイプ')
    parser.add_argument('--repo', help='リポジトリ名')
    parser.add_argument('--commit', help='コミットメッセージ')
    parser.add_argument('--author', help='作成者')
    parser.add_argument('--branch', help='ブランチ名')
    
    args = parser.parse_args()
    
    # Discord Webhook URLを環境変数から取得
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        logger.error("DISCORD_WEBHOOK_URLが設定されていません")
        sys.exit(1)
    
    if args.type == 'push':
        success = send_push_notification(
            webhook_url=webhook_url,
            repo=args.repo,
            commit=args.commit,
            author=args.author,
            branch=args.branch
        )
        
        if not success:
            sys.exit(1)

if __name__ == '__main__':
    main() 