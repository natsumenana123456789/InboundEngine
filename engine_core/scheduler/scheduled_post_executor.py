import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

# 親パッケージのモジュールをインポート
from ..config import Config
from ..spreadsheet_manager import SpreadsheetManager
from ..twitter_client import TwitterClient
from ..discord_notifier import DiscordNotifier
from .post_scheduler import ScheduledPost

logger = logging.getLogger(__name__)

class ScheduledPostExecutor:
    def __init__(self, 
                 config: Config, 
                 spreadsheet_manager: SpreadsheetManager,
                 executed_file_path: str):
        self.config = config
        self.spreadsheet_manager = spreadsheet_manager
        self.executed_file_path = executed_file_path
        
        # DiscordNotifierは都度Webhook URLを指定して初期化するか、汎用的なものを保持
        # ここでは汎用的な通知先ID "default_notification" を使用する想定
        default_webhook_url = self.config.get_discord_webhook_url("default_notification")
        if default_webhook_url:
            self.default_notifier = DiscordNotifier(webhook_url=default_webhook_url)
            logger.info("デフォルトDiscord通知クライアントを初期化しました。")
        else:
            self.default_notifier = None
            logger.warning("デフォルトのDiscord Webhook URLが設定されていません。通知は送信されません。")

    def execute_post(self, scheduled_post: ScheduledPost) -> Optional[str]:
        """
        計画された1件の投稿を実行し、成功した場合は tweet_id を、失敗した場合は None を返す。
        """
        account_id = scheduled_post['account_id']
        worksheet_name = scheduled_post['worksheet_name']
        scheduled_time = scheduled_post['scheduled_time']

        logger.info(f"投稿実行開始: Account='{account_id}', Worksheet='{worksheet_name}', ScheduledTime={scheduled_time.strftime('%Y-%m-%d %H:%M')}")

        if not worksheet_name:
            logger.error(f"アカウント '{account_id}' のワークシート名が指定されていません。投稿をスキップします。")
            self._notify_failure(account_id, worksheet_name, "ワークシート名未指定", scheduled_time)
            return None

        # 1. スプレッドシートから投稿候補を取得
        try:
            post_candidate = self.spreadsheet_manager.get_post_candidate(worksheet_name)
        except Exception as e:
            logger.error(f"アカウント '{account_id}' (ワークシート: {worksheet_name}) の記事候補取得中にエラー: {e}", exc_info=True)
            self._notify_failure(account_id, worksheet_name, f"記事候補取得エラー: {e}", scheduled_time)
            return None

        if not post_candidate:
            logger.info(f"アカウント '{account_id}' (ワークシート: {worksheet_name}) に投稿可能な記事が見つかりませんでした。")
            # 記事がない場合は通知しないか、別途設定で制御しても良い
            # self._notify_no_content(account_id, worksheet_name, scheduled_time)
            return None
        
        article_id = post_candidate.get('id', '不明')
        text_content = post_candidate.get('text')
        media_url = post_candidate.get('media_url')
        row_index = post_candidate.get('row_index')

        if not text_content:
            logger.warning(f"アカウント '{account_id}' (記事ID: {article_id}, 行: {row_index}) の本文が空です。投稿をスキップします。")
            # 本文が空の場合でも、その情報を通知に含めるため text_content はそのまま渡す
            self._notify_failure(account_id, worksheet_name, f"記事ID '{article_id}' の本文が空", scheduled_time, article_id, text_content)
            return None

        # 2. TwitterClientを初期化
        account_details = self.config.get_active_twitter_account_details(account_id)
        if not account_details:
            logger.error(f"アカウント '{account_id}' のTwitter APIキー設定が見つかりません。")
            self._notify_failure(account_id, worksheet_name, "APIキー設定なし", scheduled_time, article_id, text_content)
            return None
        
        try:
            twitter_client = TwitterClient(
                consumer_key=account_details['consumer_key'],
                consumer_secret=account_details['consumer_secret'],
                access_token=account_details['access_token'],
                access_token_secret=account_details['access_token_secret'],
                bearer_token=account_details.get('bearer_token')
            )
        except ValueError as ve:
            logger.error(f"アカウント '{account_id}' のTwitterClient初期化失敗: {ve}", exc_info=True)
            self._notify_failure(account_id, worksheet_name, f"TwitterClient初期化エラー: {ve}", scheduled_time, article_id, text_content)
            return None

        # 3. Twitterに投稿
        logger.info(f"アカウント '{account_id}' (記事ID: {article_id}) で投稿実行: Text='{text_content[:30]}...', Media='{media_url or 'なし'}'")
        posted_tweet_data = None
        try:
            if media_url:
                posted_tweet_data = twitter_client.post_with_media_url(text=text_content, media_url=media_url)
            else:
                posted_tweet_data = twitter_client.post_tweet(text=text_content)
        except Exception as e: # post_with_media_url内でエラーはキャッチ・ログされるが、念のため
            logger.error(f"アカウント '{account_id}' (記事ID: {article_id}) のツイート投稿中に予期せぬ最上位エラー: {e}", exc_info=True)
            self._notify_failure(account_id, worksheet_name, f"ツイート投稿エラー: {e}", scheduled_time, article_id, text_content)
            return None

        if not posted_tweet_data or not posted_tweet_data.get("id"):
            logger.error(f"アカウント '{account_id}' (記事ID: {article_id}) のツイート投稿に失敗しました。APIからの応答が不正です。")
            # 失敗理由はTwitterClient側でログ出力されているはず
            self._notify_failure(account_id, worksheet_name, "ツイートAPI応答エラー", scheduled_time, article_id, text_content)
            return None
        
        tweet_id = str(posted_tweet_data.get("id"))
        logger.info(f"アカウント '{account_id}' (記事ID: {article_id}) のツイート成功。Tweet ID: {tweet_id}")

        # 4. スプレッドシートのステータスを更新
        now_utc = datetime.now(timezone.utc)
        try:
            update_success = self.spreadsheet_manager.update_post_status(worksheet_name, row_index, now_utc)
            if not update_success:
                # 更新失敗は致命的ではないかもしれないが、警告は出す
                logger.warning(f"アカウント '{account_id}' (記事ID: {article_id}, 行: {row_index}) のスプレッドシート更新に失敗しました。")
                # 通知にも追記する
                self._notify_success(account_id, worksheet_name, article_id, tweet_id, scheduled_time, text_content, warning_message="スプレッドシート更新失敗")
            else:
                self._notify_success(account_id, worksheet_name, article_id, tweet_id, scheduled_time, text_content)
        except Exception as e:
            logger.error(f"アカウント '{account_id}' (記事ID: {article_id}, 行: {row_index}) のスプレッドシート更新中にエラー: {e}", exc_info=True)
            self._notify_success(account_id, worksheet_name, article_id, tweet_id, scheduled_time, text_content, warning_message=f"スプレッドシート更新エラー: {e}")
            # ここではツイート自体は成功しているのでTrueを返す

        return tweet_id

    def _notify_success(self, account_id: str, worksheet_name: str, article_id: str, tweet_id: str, scheduled_time: datetime, text_content: Optional[str], warning_message: Optional[str] = None):
        if not self.default_notifier:
            return
        title = f"✅ [成功] {account_id} ツイート投稿完了"
        description = (
            f"アカウント: `{account_id}`\n"
            f"ワークシート: `{worksheet_name}`\n"
            f"実行時刻: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        if text_content:
            processed_text = text_content[:50].replace('\n', ' ')
            description += f"\n本文冒頭: `{processed_text}...`"
        if warning_message:
            description += f"\n\n⚠️ **警告:** {warning_message}"
            self.default_notifier.send_simple_notification(title, description, color=0xffa500) # オレンジ色
        else:
            self.default_notifier.send_simple_notification(title, description, color=0x00ff00) # 緑色

    def _notify_failure(self, account_id: str, worksheet_name: Optional[str], reason: str, scheduled_time: datetime, article_id: Optional[str] = None, text_content: Optional[str] = None):
        if not self.default_notifier:
            return
        title = f"❌ [失敗] {account_id} ツイート投稿失敗"
        description = (
            f"アカウント: `{account_id}`\n"
            f"ワークシート: `{worksheet_name or 'N/A'}`\n"
            f"エラー理由: {reason}"
        )
        if text_content:
            processed_text = text_content[:50].replace('\n', ' ')
            description += f"\n試行本文冒頭: `{processed_text}...`"
        self.default_notifier.send_simple_notification(title, description, error=True)
    
    # def _notify_no_content(self, account_id: str, worksheet_name: str, scheduled_time: datetime):
    #     if not self.default_notifier:
    #         return
    #     title = f"ℹ️ [情報] {account_id} 投稿記事なし"
    #     description = (
    #         f"アカウント: `{account_id}`\n"
    #         f"ワークシート: `{worksheet_name}`\n"
    #         f"予定時刻: `{scheduled_time.strftime('%Y-%m-%d %H:%M')}`\n"
    #         f"INFO: 投稿可能な記事が見つかりませんでした。"
    #     )
    #     self.default_notifier.send_simple_notification(title, description, color=0x0000ff) # 青色

if __name__ == '__main__':
    import os
    from .post_scheduler import PostScheduler

    logging.basicConfig(level=logging.DEBUG)
    logger.info("ScheduledPostExecutorのテストを開始します。")

    try:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_file_path = os.path.join(project_root, "config/config.yml")
        
        config_instance = Config(config_path=config_file_path)
        spreadsheet_mgr = SpreadsheetManager(config=config_instance)
        
        # テスト用の実行済みファイルパス (configから読むか、固定のテスト用パス)
        test_executed_file = config_instance.get("auto_post_bot.schedule_settings.executed_file", "logs/executed_test.txt")
        
        executor = ScheduledPostExecutor(
            config=config_instance, 
            spreadsheet_manager=spreadsheet_mgr,
            executed_file_path=test_executed_file
        )
        
        # テスト用にPostSchedulerで1件スケジュールを生成してみる
        schedule_conf = config_instance.get_schedule_config()
        if not schedule_conf:
            raise ValueError("config.ymlからschedule_settingsが見つかりません。")

        posts_schedule_dict = config_instance.get_posts_per_account_schedule() or {}
        # PostSchedulerの初期化に必要な引数を渡す
        planner = PostScheduler(
            config=config_instance,
            start_hour=schedule_conf.get("start_hour", 9),
            end_hour=schedule_conf.get("end_hour", 21),
            min_interval_minutes=schedule_conf.get("min_interval_minutes", 30),
            posts_per_account_schedule=posts_schedule_dict,
            schedule_file_path=schedule_conf.get("schedule_file", "logs/schedule.txt"), # 通常のスケジュールファイルパス
            max_posts_per_hour_globally=schedule_conf.get("max_posts_per_hour_globally")
        )
        today_schedule = planner.generate_schedule_for_day(datetime.today().date())
        
        if not today_schedule:
            logger.info("本日のテスト用スケジュールが生成されませんでした。configを確認してください。")
        else:
            test_post_entry = today_schedule[0] # 最初の1件でテスト
            logger.info(f"以下のスケジュールエントリで投稿実行テストを行います: {test_post_entry}")
            
            result_tweet_id = executor.execute_post(test_post_entry)
            
            if result_tweet_id:
                logger.info(f"テスト投稿実行成功。Account: {test_post_entry['account_id']}, Tweet ID: {result_tweet_id}")
            else:
                logger.error(f"テスト投稿実行失敗または投稿なし。Account: {test_post_entry['account_id']}")

    except ValueError as ve:
        logger.error(f"設定エラー: {ve}", exc_info=True)
    except ImportError as ie:
        logger.error(f"インポートエラー: {ie}. engine_coreのルートからテストを実行しているか確認してください。", exc_info=True)
    except Exception as e:
        logger.error(f"ScheduledPostExecutorのテスト中に予期せぬエラー: {e}", exc_info=True) 