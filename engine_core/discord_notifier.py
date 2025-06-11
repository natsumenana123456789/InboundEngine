import requests
import logging
from datetime import datetime, timezone, timedelta # datetimeクラスを直接インポート
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
            log_message_parts = [
                f"Discord通知送信開始: Webhook={self.webhook_url[:30]}...",
                f"Content='{str(message)[:30]}...'",
                f"Embeds?={'Yes' if embeds else 'No'}"
            ]
            if embeds and isinstance(embeds, list) and len(embeds) > 0 and isinstance(embeds[0], dict) and 'description' in embeds[0]:
                log_message_parts.append(f", FirstEmbedDesc='{str(embeds[0]['description'])[:50]}...'" )
            logger.info(" ".join(log_message_parts))

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

    def send_schedule_summary_notification(self, scheduled_posts: List[Dict[str, Any]], target_date_str: str, bot_username: Optional[str] = "スケジュール通知") -> bool:
        """指定された日付の投稿スケジュール概要をDiscordに通知する。"""
        if not scheduled_posts:
            title = f"{target_date_str} の投稿スケジュール"
            description = "本日の投稿予定はありません。"
            color = 0x808080 # グレー
            return self.send_simple_notification(title, description, color=color)

        jst = timezone(timedelta(hours=9), name='JST')
        
        # アカウントごとにグループ化し、時刻でソート
        posts_by_account: Dict[str, List[Dict[str, Any]]] = {}
        for post in scheduled_posts:
            account_id = post.get("account_id", "不明なアカウント")
            if account_id not in posts_by_account:
                posts_by_account[account_id] = []
            posts_by_account[account_id].append(post)
        
        for account_id in posts_by_account:
            posts_by_account[account_id].sort(key=lambda p: p.get("scheduled_time"))

        embed_description_parts = [f"**🗓️ {target_date_str} の投稿スケジュール ({len(scheduled_posts)}件)**\n"]

        for account_id, posts in posts_by_account.items():
            embed_description_parts.append(f"\n**アカウント: {account_id} ({len(posts)}件)**")
            for post in posts:
                scheduled_time_utc = post.get("scheduled_time") # WorkflowManagerからはdatetimeオブジェクトで渡される想定
                worksheet_name = post.get("worksheet_name", "(シート名不明)")
                
                time_str_jst = "(時刻不明)"
                if isinstance(scheduled_time_utc, datetime):
                    # JSTに変換してフォーマット
                    scheduled_time_jst = scheduled_time_utc.astimezone(jst)
                    time_str_jst = scheduled_time_jst.strftime("%H:%M") 
                elif isinstance(scheduled_time_utc, str): # 文字列の場合も一応対応 (ISOフォーマット想定)
                    try:
                        dt_utc = datetime.fromisoformat(scheduled_time_utc.replace('Z', '+00:00'))
                        dt_jst = dt_utc.astimezone(jst)
                        time_str_jst = dt_jst.strftime("%H:%M")
                    except ValueError:
                        logger.warning(f"スケジュール時刻文字列のパース失敗: {scheduled_time_utc}")
                        time_str_jst = scheduled_time_utc # パース失敗時はそのまま表示
                
                embed_description_parts.append(f"- `{time_str_jst} JST` : {worksheet_name}")
        
        embed_description = "\n".join(embed_description_parts)
        
        # Discordの埋め込みメッセージのdescriptionは4096文字制限があるため、長すぎる場合は分割送信などを検討する必要がある
        # ここでは一旦、長すぎる場合は警告を出すのみ
        if len(embed_description) > 4000: # 少し余裕を持たせる
            logger.warning("生成されたスケジュールサマリーが長すぎるため、Discord通知が失敗する可能性があります。")
            # TODO: 必要に応じてメッセージ分割ロジックを実装

        embed = {
            "title": f"投稿スケジュール ({target_date_str})",
            "description": embed_description,
            "color": 0x1E90FF,  # DodgerBlue
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return self.send_message(embeds=[embed], username=bot_username)

    def send_status_table(self, title: str, headers: List[str], data: List[List[str]], color: int = 0x000000):
        """
        ステータス情報をテーブル形式で送信する。
        :param title: Embedのタイトル
        :param headers: テーブルのヘッダー (可変長)
        :param data: テーブルのデータ (各行の要素数はヘッダーと一致させる)
        :param color: Embedの左側の色
        """
        if not self.webhook_url:
            logger.warning("Discord Webhook URLが設定されていないため、通知をスキップしました。")
            return

        num_columns = len(headers)
        if num_columns == 0 or any(len(row) != num_columns for row in data):
            logger.error(f"テーブル通知のヘッダーまたはデータの形式が不正です。各行の列数はヘッダー({num_columns}列)と一致する必要があります。")
            return

        embed = {
            "title": title,
            "color": color,
            "fields": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # ヘッダーをフィールドとして追加 (インラインで並べる)
        for header in headers:
            embed["fields"].append({"name": f"**{header}**", "value": "\u200b", "inline": True})

        # 各行のデータをフィールドとして追加 (インラインで並べる)
        for row in data:
            for i, cell in enumerate(row):
                # 空のセルでも高さを揃えるためにゼロ幅スペースを入れる
                value = str(cell) if cell is not None and str(cell).strip() != "" else "\u200b"
                embed["fields"].append({"name": "\u200b", "value": value, "inline": True})
        
        # 3列や4列の場合、最後の要素の後に空のインラインフィールドを追加すると改行が揃うことがある
        # ただし、Discordのクライアントや表示幅によって挙動が変わるため、常にうまくいくとは限らない
        # if num_columns % 3 != 0:
        #    embed["fields"].append({"name": "\u200b", "value": "\u200b", "inline": True})

        payload = {"embeds": [embed]}
        
        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Discord通知成功（テーブル形式）。ステータスコード: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Discord通知（テーブル形式）の送信中にエラーが発生しました: {e}")

if __name__ == '__main__':
    import os # if __name__ 内でのみ使用

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

            logger.info("スケジュールサマリーのテスト...")
            scheduled_posts = [
                {"account_id": "Account1", "scheduled_time": "2024-04-01T10:00:00", "worksheet_name": "Worksheet1"},
                {"account_id": "Account2", "scheduled_time": "2024-04-01T11:00:00", "worksheet_name": "Worksheet2"},
                {"account_id": "Account1", "scheduled_time": "2024-04-01T12:00:00", "worksheet_name": "Worksheet3"},
            ]
            success_schedule_summary = notifier.send_schedule_summary_notification(
                scheduled_posts=scheduled_posts,
                target_date_str="2024年4月1日",
                bot_username="スケジュール通知ボット"
            )
            if success_schedule_summary:
                logger.info("スケジュールサマリー送信成功。")
            else:
                logger.error("スケジュールサマリー送信失敗。")

        except ValueError as ve:
            logger.error(f"設定エラー: {ve}")
        except Exception as e:
            logger.error(f"DiscordNotifierのテスト中に予期せぬエラー: {e}", exc_info=True) 