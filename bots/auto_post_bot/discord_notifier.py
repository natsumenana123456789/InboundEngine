#!/usr/bin/env python3
import os
import sys
import argparse
from discord_webhook import DiscordWebhook, DiscordEmbed
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscordNotifier:
    """Discord通知クラス"""
    
    def __init__(self, webhook_url):
        """
        Args:
            webhook_url (str): DiscordのWebhook URL
        """
        self.webhook_url = webhook_url
    
    def send_notification(self, embed):
        """
        通知を送信する
        
        Args:
            embed (DiscordEmbed): 送信する埋め込みメッセージ
            
        Returns:
            bool: 送信成功ならTrue、失敗ならFalse
        """
        try:
            webhook = DiscordWebhook(url=self.webhook_url)
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
    
    def send_schedule_notification(self, schedule_data):
        """
        スケジュール通知を送信
        
        Args:
            schedule_data (dict): アカウントごとの投稿時刻リスト
            
        Returns:
            bool: 送信成功ならTrue、失敗ならFalse
        """
        embed = DiscordEmbed(
            title="📅 投稿スケジュール",
            color=0x57F287  # 緑色
        )
        
        for account, times in schedule_data.items():
            times_str = "\n".join([f"• {t}" for t in times])
            embed.add_embed_field(
                name=f"📱 {account}",
                value=f"```{times_str}```",
                inline=False
            )
        
        return self.send_notification(embed)
    
    def send_post_notification(self, account, status, details=""):
        """
        投稿結果通知を送信
        
        Args:
            account (str): アカウント名
            status (str): ステータス（"成功" or "失敗"）
            details (str, optional): 詳細情報
            
        Returns:
            bool: 送信成功ならTrue、失敗ならFalse
        """
        color = 0x57F287 if status == "成功" else 0xED4245  # 緑 or 赤
        emoji = "✅" if status == "成功" else "❌"
        
        embed = DiscordEmbed(
            title=f"{emoji} 投稿{status}",
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
        
        return self.send_notification(embed)

def send_push_notification(webhook_url, repo, commit, author, branch):
    """
    Gitプッシュ時のDiscord通知を送信
    """
    try:
        webhook = DiscordWebhook(url=webhook_url)
        
        # 埋め込みメッセージを作成
        embed = DiscordEmbed(
            title="🔄 スクリプトが更新されました",
            color=0x57F287  # 緑色
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