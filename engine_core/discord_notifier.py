import requests
import logging
from typing import Optional, Dict, Any, List

# このモジュールがengine_coreパッケージ内にあることを想定してConfigをインポート
# ただし、DiscordNotifier自体はConfigに直接依存せず、Webhook URLは外部から渡される想定
# from .config import Config # 通常はWorkflow層などでConfigからWebhook URLを取得して渡す

logger = logging.getLogger(__name__)

class DiscordNotifier:
    def __init__(self, webhook_url: str):
        if not webhook_url:
            msg = "Discord Webhook URLが設定されていません。"
            logger.error(msg)
            raise ValueError(msg)
        self.webhook_url = webhook_url

    def send_message(self, message: Optional[str] = None, embeds: Optional[List[Dict[str, Any]]] = None, username: Optional[str] = None) -> bool:
        """
        Discordにメッセージまたは埋め込みコンテンツを送信する。
        両方指定された場合は、両方送信しようとします (Discordの仕様によります)。
        """
        if not message and not embeds:
            logger.warning("送信するメッセージも埋め込みコンテンツもありません。")
            return False

        payload = {}
        if message:
            payload['content'] = message
        if embeds:
            payload['embeds'] = embeds
        if username:
            payload['username'] = username # ボットの表示名を一時的に変更
        
        try:
            logger.info(f"Discord通知送信開始: Webhook={self.webhook_url[:30]}..., Content='{str(message)[:30]}...', Embeds?={'Yes' if embeds else 'No'}")
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()  # 2xx 以外のステータスコードで例外を発生
            logger.info(f"Discord通知成功。ステータスコード: {response.status_code}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Discord通知失敗: {e}", exc_info=True)
            # 特に4xx, 5xx系のエラー詳細もログに出力される
            if e.response is not None:
                logger.error(f"Discord APIエラーレスポンス: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Discord通知中の予期せぬエラー: {e}", exc_info=True)
            return False

    def send_simple_notification(self, title: str, description: str, color: int = 0x00ff00, error: bool = False) -> bool:
        """簡易的な通知用埋め込みメッセージを送信する。"""
        embed = {
            "title": title,
            "description": description,
            "color": 0xff0000 if error else color, # エラー時は赤色
            "timestamp": datetime.utcnow().isoformat() # UTCタイムスタンプ
        }
        return self.send_message(embeds=[embed])


if __name__ == '__main__':
    import os # if __name__ 内でのみ使用
    from datetime import datetime # if __name__ 内でのみ使用

    logging.basicConfig(level=logging.DEBUG)
    logger.info("DiscordNotifierのテストを開始します。")

    # テストには実際のDiscord Webhook URLが必要です。
    # 環境変数やconfigファイルから読み込むことを推奨します。
    # 重要：実際のWebhook URLをコードにハードコーディングしないでください。
    
    # 環境変数からWebhook URLを読み込む例
    test_webhook_url = os.environ.get("TEST_DISCORD_WEBHOOK_URL") 
    # または、Config経由で取得する（Configのパス解決に注意）
    # try:
    #     from config import Config
    #     project_root_for_config = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    #     config_instance = Config(config_path=os.path.join(project_root_for_config, "config/config.yml"))
    #     test_webhook_url = config_instance.get_discord_webhook_url("default_notification") # configにtestingセクションなど作ると良い
    # except ImportError:
    #     logger.warning("Configモジュールが見つからないため、環境変数からWebhook URLを試みます。")
    #     pass # 環境変数がなければそのままNone

    if not test_webhook_url:
        logger.warning("TEST_DISCORD_WEBHOOK_URL環境変数が設定されていないため、Discord通知テストをスキップします。")
    else:
        try:
            notifier = DiscordNotifier(webhook_url=test_webhook_url)

            logger.info("単純なテキストメッセージのテスト...")
            success_text = notifier.send_message(f"これは DiscordNotifier からのテストメッセージです。({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})", username="テストボット")
            if success_text:
                logger.info("テキストメッセージ送信成功。")
            else:
                logger.error("テキストメッセージ送信失敗。")

            logger.info("埋め込みメッセージのテスト...")
            embed_data = [
                {
                    "title": "テスト通知",
                    "description": "これは埋め込みメッセージのテストです。\n複数行もOK！",
                    "color": 0x3498db, # 青っぽい色
                    "fields": [
                        {"name": "フィールド1", "value": "値1", "inline": True},
                        {"name": "フィールド2", "value": "値2", "inline": True}
                    ],
                    "footer": {"text": f"フッターテスト {datetime.now().year}"},
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
            success_embed = notifier.send_message(embeds=embed_data, username="詳細通知ボット")
            if success_embed:
                logger.info("埋め込みメッセージ送信成功。")
            else:
                logger.error("埋め込みメッセージ送信失敗。")
            
            logger.info("簡易通知メソッド (成功風) のテスト...")
            success_simple_ok = notifier.send_simple_notification(
                title="処理完了通知", 
                description="バッチ処理が正常に完了しました。詳細はログを確認してください。"
            )
            if success_simple_ok: logger.info("簡易通知(成功)送信成功。")
            else: logger.error("簡易通知(成功)送信失敗。")

            logger.info("簡易通知メソッド (エラー風) のテスト...")
            success_simple_err = notifier.send_simple_notification(
                title="重大なエラー発生", 
                description="システム処理中にクリティカルなエラーが発生しました。至急確認してください。",
                error=True
            )
            if success_simple_err: logger.info("簡易通知(エラー)送信成功。")
            else: logger.error("簡易通知(エラー)送信失敗。")


        except ValueError as ve:
            logger.error(f"設定エラー: {ve}")
        except Exception as e:
            logger.error(f"DiscordNotifierのテスト中に予期せぬエラー: {e}", exc_info=True) 