import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple, List
import random # random をインポート

# 親パッケージのモジュールをインポート
from ..config import Config
from ..spreadsheet_manager import SpreadsheetManager
from ..twitter_client import TwitterClient, RateLimitError # RateLimitError をインポート
from ..discord_notifier import DiscordNotifier
from .post_scheduler import ScheduledPost
# from ..utils.rate_limiter import RateLimiter # コメントアウト

logger = logging.getLogger(__name__)

class ScheduledPostExecutor:
    def __init__(self, config: Config, spreadsheet_manager: SpreadsheetManager):
        self.config = config
        self.spreadsheet_manager = spreadsheet_manager
        self.executed_file_path = config.get("auto_post_bot.schedule_settings.executed_file", "logs/executed_test.txt")
        self.twitter_clients: Dict[str, TwitterClient] = {}
        self.default_discord_notifier = DiscordNotifier(config.get_discord_webhook_url())

        # self.rate_limiter = RateLimiter(calls=5, period=60) # コメントアウト

    def _insert_random_spaces(self, text: str, num_spaces_to_insert: int = 3) -> str:
        """テキスト中の指定された句読点・記号の後に、最大指定個数まで、50%の確率で半角スペースを挿入する。"""
        if not text or num_spaces_to_insert <= 0:
            return text

        target_chars = ['、', '。', '！', '？']
        candidate_indices = [] # スペースを挿入する可能性のある文字の「後」のインデックスを格納

        for i, char in enumerate(text):
            if char in target_chars:
                # 記号の直後 (i+1) を候補とする
                # ただし、文字列の末尾や、既にスペースが連続している場合は避けるなどの考慮も可能だが、まずはシンプルに
                if i + 1 < len(text): # 文字列の末尾でないことを確認
                    candidate_indices.append(i + 1)
        
        if not candidate_indices:
            return text

        # 実際にスペースを挿入するインデックスを選定
        num_actual_candidates = min(len(candidate_indices), num_spaces_to_insert)
        
        # 候補箇所からランダムに選ぶ (重複なし)
        # candidate_indices が num_actual_candidates より少ない場合は全て選ばれる
        chosen_candidate_indices = random.sample(candidate_indices, num_actual_candidates)

        # 挿入対象のインデックスを保存 (後でまとめて処理するため)
        # 50%の確率で挿入を実行
        indices_to_insert_space = []
        for index in chosen_candidate_indices:
            if random.random() < 0.5: # 50%の確率
                indices_to_insert_space.append(index)

        if not indices_to_insert_space:
            return text

        # テキストをリストに変換して挿入処理
        text_list = list(text)
        
        # 後ろから挿入することで、前の挿入によるインデックスのズレを防ぐ
        indices_to_insert_space.sort(reverse=True)
        
        for index in indices_to_insert_space:
            # 既にスペースがある場合は挿入しない (簡易的な重複防止)
            # ただし、このロジックだと連続スペースを完全に防ぐわけではない
            # より厳密には、挿入前に text_list[index-1] がスペースでないかなどを確認
            if index == 0 or text_list[index -1] != ' ': # 先頭でない、かつ前の文字がスペースでない
                 if index < len(text_list) and text_list[index] != ' ': # 現在地がスペースでない
                    text_list.insert(index, ' ')
                 elif index == len(text_list): # 末尾への挿入の場合
                    text_list.append(' ')


        return "".join(text_list)

    def _split_text_for_tweet(self, text: str, max_length: int = 280) -> List[str]:
        """テキストをXの文字数制限に基づいて分割する。"""
        if not text:
            return []

        # URLは t.co で短縮されるため、実際の文字数カウントはより複雑になるが、
        # ここでは単純な文字数で分割する。
        # TODO: URLの文字数カウントを考慮した分割ロジックの改善
        # TODO: 句読点や改行を考慮した分割ロジックの改善

        parts = []
        current_pos = 0
        while current_pos < len(text):
            # 残りテキストがmax_length以下なら、そのまま追加して終了
            if len(text) - current_pos <= max_length:
                parts.append(text[current_pos:])
                break
            
            # max_lengthで区切るが、単語の途中で区切らないようにする（簡易処理）
            # 後方からスペースを探し、見つかればそこで区切る
            split_pos = current_pos + max_length
            if split_pos < len(text): # 分割点候補がテキスト長を超えない場合
                # max_lengthの位置から遡って最初のスペースや句読点を探す
                # 優先順位: 改行 > 句読点（。、！） > スペース
                best_split_char_pos = -1
                # 改行文字を探す
                newline_pos = text.rfind('\n', current_pos, split_pos)
                if newline_pos != -1:
                    best_split_char_pos = newline_pos + 1 # 改行文字の次で分割
                else:
                    # 句読点（。、！）を探す
                    punctuation_chars = ['。', '！', '？'] # ？も追加
                    for char_to_find in punctuation_chars:
                        punc_pos = text.rfind(char_to_find, current_pos, split_pos)
                        if punc_pos != -1 and punc_pos + 1 > best_split_char_pos:
                            best_split_char_pos = punc_pos + 1 # 句読点の次で分割
                    
                    # スペースを探す (句読点が見つからなかった場合)
                    if best_split_char_pos == -1: 
                        space_pos = text.rfind(' ', current_pos, split_pos)
                        if space_pos != -1:
                            best_split_char_pos = space_pos + 1 # スペースの次で分割
                
                if best_split_char_pos != -1 and best_split_char_pos > current_pos:
                    split_pos = best_split_char_pos
                # 適切な分割点が見つからない場合は、max_lengthで強制的に分割
                # （この場合、単語の途中になる可能性が高い）

            parts.append(text[current_pos:split_pos].strip()) # 前後の空白を削除
            current_pos = split_pos
            while current_pos < len(text) and text[current_pos].isspace(): # 分割後の先頭の空白をスキップ
                current_pos += 1
        
        # 空の文字列がpartsに含まれていたら除去
        return [part for part in parts if part]

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

        # === ランダムスペース挿入処理 ===
        original_text_length = len(text_content)
        text_content = self._insert_random_spaces(text_content)
        if len(text_content) > original_text_length:
            logger.info(f"アカウント '{account_id}' (記事ID: {article_id}) の本文にランダムスペースを挿入しました。 (変更後文字数: {len(text_content)})")
        # === ランダムスペース挿入処理 完了 ===

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

        # === ツイート本文を分割 ===
        current_max_length = 130 # 修正後: 常に130字で分割
        logger.info(f"ツイート本文の最大長を {current_max_length} 文字で分割します。(日本語テキスト向け調整)")

        tweet_parts = self._split_text_for_tweet(text_content, max_length=current_max_length)

        if not tweet_parts:
            logger.warning(f"アカウント '{account_id}' (記事ID: {article_id}) の本文が分割後空になりました。投稿をスキップします。")
            self._notify_failure(account_id, worksheet_name, f"記事ID '{article_id}' の本文が分割後空", scheduled_time, article_id, text_content)
            return None
        
        logger.info(f"アカウント '{account_id}' (記事ID: {article_id}) の本文を {len(tweet_parts)} 件に分割しました。")

        # 3. Twitterに投稿
        posted_tweet_ids: List[str] = []
        first_tweet_id: Optional[str] = None
        final_tweet_id_for_reporting: Optional[str] = None # スプレッドシート等に記録する代表ID

        try:
            for i, part_text in enumerate(tweet_parts):
                logger.info(f"アカウント '{account_id}' (記事ID: {article_id}) で分割投稿 ({i+1}/{len(tweet_parts)}) 実行 (長さ: {len(part_text)}): Text='{part_text}'") # 変更後 (長さ情報追加)
                
                current_posted_tweet_data: Optional[Dict[str, Any]] = None

                if i == 0: # 最初のツイート
                    if media_url:
                        current_posted_tweet_data = twitter_client.post_with_media_url(text=part_text, media_url=media_url)
                    else:
                        current_posted_tweet_data = twitter_client.post_tweet(text=part_text)
                    
                    if current_posted_tweet_data and current_posted_tweet_data.get("id"):
                        first_tweet_id = str(current_posted_tweet_data.get("id"))
                        posted_tweet_ids.append(first_tweet_id)
                        final_tweet_id_for_reporting = first_tweet_id # 代表IDをセット
                        logger.info(f"アカウント '{account_id}' (記事ID: {article_id}) の分割投稿 ({i+1}/{len(tweet_parts)}) 成功。Tweet ID: {first_tweet_id}")
                    else:
                        logger.error(f"アカウント '{account_id}' (記事ID: {article_id}) の最初のツイート投稿に失敗。API応答不正。")
                        # この時点で失敗した場合はposted_tweet_idsは空なので、後続の削除処理はスキップされる
                        raise Exception("最初のツイート投稿失敗 (API応答不正)") # 後続の except ブロックで処理
                else: # 2番目以降のツイート (リプライ)
                    if not first_tweet_id: # 通常ありえないが念のため
                        logger.error("リプライ先のツイートIDがありません。スレッド投稿を中止します。")
                        raise Exception("リプライ先のID不明")
                    
                    # 直前のツイートIDにリプライする
                    reply_to_id = posted_tweet_ids[-1]
                    current_posted_tweet_data = twitter_client.post_reply(text=part_text, in_reply_to_tweet_id=reply_to_id)
                    
                    if current_posted_tweet_data and current_posted_tweet_data.get("id"):
                        current_tweet_id = str(current_posted_tweet_data.get("id"))
                        posted_tweet_ids.append(current_tweet_id)
                        logger.info(f"アカウント '{account_id}' (記事ID: {article_id}) の分割投稿 ({i+1}/{len(tweet_parts)}) 成功。Tweet ID: {current_tweet_id}")
                    else:
                        logger.error(f"アカウント '{account_id}' (記事ID: {article_id}) のリプライ投稿 ({i+1}/{len(tweet_parts)}) に失敗。API応答不正。")
                        raise Exception(f"リプライ投稿 ({i+1}/{len(tweet_parts)}) 失敗 (API応答不正)")

        except RateLimitError as rle:
            logger.error(f"アカウント '{account_id}' (記事ID: {article_id}) のツイート投稿中にレート制限エラー: {str(rle)}")
            reason = "Twitter APIレート制限が発生しました (HTTP 429)。"
            jst = timezone(timedelta(hours=9), name='JST')
            if rle.remaining_seconds is not None:
                reason += f" リセットまで約 {rle.remaining_seconds} 秒"
                if rle.reset_at_utc:
                    reset_at_jst = rle.reset_at_utc.astimezone(jst)
                    reason += f" (予定時刻: {reset_at_jst.strftime('%Y-%m-%d %H:%M:%S')} JST)"
            elif rle.reset_at_utc:
                reset_at_jst = rle.reset_at_utc.astimezone(jst)
                reason += f" リセット予定時刻: {reset_at_jst.strftime('%Y-%m-%d %H:%M:%S')} JST"
            
            self._notify_failure(account_id, worksheet_name, reason, scheduled_time, article_id, text_content)
            # 失敗したツイート群を削除
            if posted_tweet_ids:
                logger.info(f"レート制限エラー発生のため、投稿済みツイート {len(posted_tweet_ids)} 件を削除します: {posted_tweet_ids}")
                for tweet_id_to_delete in reversed(posted_tweet_ids): # 新しいものから削除
                    delete_success = twitter_client.delete_tweet(tweet_id_to_delete)
                    if delete_success:
                        logger.info(f"ツイート {tweet_id_to_delete} の削除成功。")
                    else:
                        logger.warning(f"ツイート {tweet_id_to_delete} の削除失敗。手動確認が必要な場合があります。")
            return None

        except Exception as e: # RateLimitError以外の予期せぬエラー
            logger.error(f"アカウント '{account_id}' (記事ID: {article_id}) のツイート投稿中に予期せぬエラー: {e}", exc_info=True)
            self._notify_failure(account_id, worksheet_name, f"ツイート投稿中の予期せぬエラー: {e}", scheduled_time, article_id, text_content)
            # 失敗したツイート群を削除
            if posted_tweet_ids:
                logger.info(f"予期せぬエラー発生のため、投稿済みツイート {len(posted_tweet_ids)} 件を削除します: {posted_tweet_ids}")
                for tweet_id_to_delete in reversed(posted_tweet_ids):
                    delete_success = twitter_client.delete_tweet(tweet_id_to_delete)
                    if delete_success:
                        logger.info(f"ツイート {tweet_id_to_delete} の削除成功。")
                    else:
                        logger.warning(f"ツイート {tweet_id_to_delete} の削除失敗。手動確認が必要な場合があります。")
            return None

        if not final_tweet_id_for_reporting:
            # このルートを通ることは稀だが、万が一全ての投稿が成功したように見えても
            # final_tweet_id_for_reporting がセットされていない場合 (ロジックのバグなど)
            logger.error(f"アカウント '{account_id}' (記事ID: {article_id}) のツイート投稿完了後、報告用Tweet IDが不明です。")
            self._notify_failure(account_id, worksheet_name, "ツイートAPI応答エラー (最終ID不明)", scheduled_time, article_id, text_content)
            return None
        
        logger.info(f"アカウント '{account_id}' (記事ID: {article_id}) のツイート投稿（全 {len(tweet_parts)} 件）成功。代表Tweet ID: {final_tweet_id_for_reporting}")

        # 4. スプレッドシートのステータスを更新 (代表IDを使用)
        now_utc = datetime.now(timezone.utc)
        try:
            update_success = self.spreadsheet_manager.update_post_status(worksheet_name, row_index, now_utc)
            if not update_success:
                # 更新失敗は致命的ではないかもしれないが、警告は出す
                logger.warning(f"アカウント '{account_id}' (記事ID: {article_id}, 行: {row_index}) のスプレッドシート更新に失敗しました。")
                # 通知にも追記する
                self._notify_success(account_id, worksheet_name, article_id, final_tweet_id_for_reporting, scheduled_time, text_content, warning_message="スプレッドシート更新失敗")
            else:
                self._notify_success(account_id, worksheet_name, article_id, final_tweet_id_for_reporting, scheduled_time, text_content)
        except Exception as e:
            logger.error(f"アカウント '{account_id}' (記事ID: {article_id}, 行: {row_index}) のスプレッドシート更新中にエラー: {e}", exc_info=True)
            self._notify_success(account_id, worksheet_name, article_id, final_tweet_id_for_reporting, scheduled_time, text_content, warning_message=f"スプレッドシート更新エラー: {e}")
            # ここではツイート自体は成功しているのでTrueを返す

        return final_tweet_id_for_reporting

    def _notify_success(self, account_id: str, worksheet_name: str, article_id: str, tweet_id: str, scheduled_time: datetime, text_content: Optional[str], warning_message: Optional[str] = None):
        if not self.default_discord_notifier:
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
            self.default_discord_notifier.send_simple_notification(title, description, color=0xffa500) # オレンジ色
        else:
            self.default_discord_notifier.send_simple_notification(title, description, color=0x00ff00) # 緑色

    def _notify_failure(self, account_id: str, worksheet_name: Optional[str], reason: str, scheduled_time: datetime, article_id: Optional[str] = None, text_content: Optional[str] = None):
        if not self.default_discord_notifier:
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
        self.default_discord_notifier.send_simple_notification(title, description, error=True)
    
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

    def _get_twitter_client(self, account_id: str) -> Optional[TwitterClient]:
        if account_id in self.twitter_clients:
            return self.twitter_clients[account_id]
        else:
            account_details = self.config.get_active_twitter_account_details(account_id)
            if account_details:
                twitter_client = TwitterClient(
                    consumer_key=account_details['consumer_key'],
                    consumer_secret=account_details['consumer_secret'],
                    access_token=account_details['access_token'],
                    access_token_secret=account_details['access_token_secret'],
                    bearer_token=account_details.get('bearer_token')
                )
                self.twitter_clients[account_id] = twitter_client
                return twitter_client
            else:
                return None

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
            spreadsheet_manager=spreadsheet_mgr
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