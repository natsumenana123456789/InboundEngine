import logging
import os
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
import atexit

from .config import Config
from .utils.logging_utils import get_logger
from .spreadsheet_manager import SpreadsheetManager
from .discord_notifier import DiscordNotifier
from .scheduler.scheduled_post_executor import ScheduledPostExecutor

logger = get_logger(__name__)

class WorkflowManager:
    """
    投稿ワークフロー全体を管理するクラス。
    司令塔として機能し、投稿タイミングの判断、ワーカープロセスの起動、通知を行う。
    """
    def __init__(self, config: Config):
        self.config = config
        self.logs_dir = self.config.get("common.logs_directory", "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.lock_file_path = os.path.join(self.logs_dir, "commander.lock")

        schedule_settings = self.config.get_schedule_config()
        if not schedule_settings:
            raise ValueError("Configにスケジュール設定 (schedule_settings) が見つかりません。")

        last_post_times_filename = schedule_settings.get("last_post_times_file")
        if not last_post_times_filename:
            raise ValueError("Configに最終投稿時刻ファイル (last_post_times_file) の設定がありません。")
        self.last_post_times_path = os.path.join(self.logs_dir, last_post_times_filename)

        # コアコンポーネントの初期化
        self.spreadsheet_manager = SpreadsheetManager(config=self.config)
        self.post_executor = ScheduledPostExecutor(
            config=self.config,
            spreadsheet_manager=self.spreadsheet_manager
        )
        
        discord_webhook_url = self.config.get_discord_webhook_url()
        if discord_webhook_url:
            self.notifier = DiscordNotifier(webhook_url=discord_webhook_url)
            logger.info("Discord通知クライアントを初期化しました。")
        else:
            self.notifier = None
            logger.info("Discord Webhook URLが設定されていないため、通知は行われません。")

        logger.info("WorkflowManager初期化完了。")

    def _acquire_lock(self) -> bool:
        """ロックファイルを作成して処理の多重実行を防ぐ。"""
        if os.path.exists(self.lock_file_path):
            logger.warning("ロックファイルが既に存在します。他の司令塔プロセスが実行中の可能性があります。処理を中止します。")
            return False
        try:
            with open(self.lock_file_path, 'w') as f:
                f.write(str(os.getpid()))
            # プロセス終了時にロックファイルを確実に削除する
            atexit.register(self._release_lock)
            logger.info(f"ロックを取得しました: {self.lock_file_path}")
            return True
        except IOError as e:
            logger.error(f"ロックファイルの作成に失敗しました: {e}", exc_info=True)
            return False

    def _release_lock(self):
        """ロックファイルを削除する。"""
        if os.path.exists(self.lock_file_path):
            try:
                os.remove(self.lock_file_path)
                logger.info(f"ロックを解放しました: {self.lock_file_path}")
            except IOError as e:
                logger.error(f"ロックファイルの削除に失敗しました: {e}", exc_info=True)

    def _read_last_post_times(self) -> Dict[str, datetime]:
        """最終投稿時刻を記録したJSONファイルを読み込む。"""
        if not os.path.exists(self.last_post_times_path):
            return {}
        try:
            with open(self.last_post_times_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content:
                    return {}
                data = json.loads(content)
            
            last_times: Dict[str, datetime] = {}
            for acc_id, time_str in data.items():
                try:
                    # ISO 8601形式の文字列をdatetimeオブジェクト（タイムゾーン情報付き）に変換
                    if isinstance(time_str, str):
                        # オプション: 'Z'で終わる古い形式にも対応
                        if time_str.endswith('Z'):
                            time_str = time_str[:-1] + '+00:00'
                        last_times[acc_id] = datetime.fromisoformat(time_str)
                    else:
                        logger.warning(f"アカウント {acc_id} の最終投稿時刻 '{time_str}' の形式が不正です（文字列ではありません）。")
                except (ValueError, TypeError) as e:
                    logger.warning(f"アカウント {acc_id} の最終投稿時刻 '{time_str}' のパースに失敗しました。スキップします。エラー: {e}")
            return last_times
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"最終投稿時刻ファイル '{self.last_post_times_path}' の読み込みに失敗しました: {e}", exc_info=True)
            return {} # エラー発生時は空の辞書を返す

    def _write_last_post_times(self, last_times: Dict[str, datetime]):
        """最終投稿時刻をJSONファイルに書き込む。"""
        serializable_data = {acc_id: dt.isoformat() for acc_id, dt in last_times.items()}
        try:
            with open(self.last_post_times_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            logger.error(f"最終投稿時刻ファイル '{self.last_post_times_path}' の書き込みに失敗しました: {e}", exc_info=True)

    def launch_pending_posts(self):
        """
        [司令塔機能] 投稿時間になったアカウントを検出し、ワーカープロセスを起動する。
        多重起動を防ぐロック機構と、1実行1投稿の制限を設ける。
        """
        if not self._acquire_lock():
            return
            
        logger.info("司令塔プロセス開始: 投稿時間になったアカウントのワーカーを起動します。")
        
        interval_hours = self.config.get_post_interval_hours()
        if not interval_hours:
            logger.error("投稿間隔時間 (post_interval_hours) が設定されていないため、処理を中止します。")
            return

        active_accounts = self.config.get_active_twitter_accounts()
        if not active_accounts:
            logger.info("処理対象のアクティブなアカウントがありません。")
            return

        last_post_times = self._read_last_post_times()
        now_utc = datetime.now(timezone.utc)
        
        accounts_to_post_candidates: List[Tuple[Dict[str, any], datetime]] = []
        for account in active_accounts:
            account_id = account["account_id"]
            last_post_time = last_post_times.get(account_id, datetime.min.replace(tzinfo=timezone.utc))

            if now_utc >= last_post_time + timedelta(hours=interval_hours):
                accounts_to_post_candidates.append((account, last_post_time))

        if not accounts_to_post_candidates:
            logger.info("現時点で投稿対象となるアカウントはありません。")
            return

        # 最終投稿日時が最も古いアカウントを1つだけ選ぶ
        accounts_to_post_candidates.sort(key=lambda x: x[1])
        account_to_post, _ = accounts_to_post_candidates[0]
        
        # 投稿対象アカウント（1件）の最終投稿日時を先に更新（ロック）
        last_post_times[account_to_post["account_id"]] = now_utc
        self._write_last_post_times(last_post_times)
        logger.info(f"アカウント '{account_to_post['account_id']}' の最終投稿日時を更新しました。")

        # Discord通知
        if self.notifier:
            self._notify_status_to_discord([account_to_post], active_accounts)
            
        # ワーカープロセスを起動
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_py_path = os.path.join(project_root, "main.py")

        account_id = account_to_post["account_id"]
        try:
            command = [
                sys.executable, 
                main_py_path,
            ]
            # 親プロセスがconfigパスを指定されていた場合のみ、ワーカーにも引き継ぐ
            if self.config.config_path:
                command.extend(["--config", self.config.config_path])
            command.extend(["--worker", account_id])

            logger.info(f"ワーカープロセスを起動します: `{' '.join(command)}`")
            
            # ログをリアルタイムでキャプチャしつつ、ワーカーの完了を待つ
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                 logger.error(f"ワーカープロセス `main.py --worker {account_id}` がエラーで終了しました (終了コード: {process.returncode})", exc_info=False)
                 if stdout:
                     logger.error(f"ワーカーの標準出力:\n{stdout}")
                 if stderr:
                     logger.error(f"ワーカーの標準エラー出力:\n{stderr}")
            else:
                 logger.info(f"ワーカープロセス `main.py --worker {account_id}` が正常に完了しました。")
                 if stdout:
                     logger.info(f"ワーカーの標準出力:\n{stdout}")

        except Exception as e:
            logger.error(f"ワーカープロセス `main.py --worker {account_id}` の起動自体に失敗: {e}", exc_info=True)

        logger.info("司令塔プロセスを終了します。")

    def _notify_status_to_discord(self, accounts_to_post, active_accounts):
        """現在の全アカウントのステータスをDiscordにテーブル形式で通知する。"""
        if not self.notifier:
            return
            
        jst = timezone(timedelta(hours=9), 'JST')
        interval_hours = self.config.get_post_interval_hours()
        title = f"🚀 {len(accounts_to_post)}件の並列投稿を開始"
        headers = ["アカウント", "ステータス", "最終投稿 (JST)", "次回投稿予定 (JST)"]
        table_data = []

        # この時点での最新の最終投稿時刻を再読み込みして正確な情報を表示
        current_last_post_times = self._read_last_post_times()

        for account in active_accounts:
            account_id = account["account_id"]
            last_post_time_utc = current_last_post_times.get(account_id)
            
            is_posting_now = any(acc["account_id"] == account_id for acc in accounts_to_post)
            
            status = ""
            if is_posting_now:
                status = "▶️ 投稿開始"
            elif last_post_time_utc:
                status = "⏳ 待機中"
            else:
                status = "✅ 初回待機"

            last_post_str = last_post_time_utc.astimezone(jst).strftime('%m-%d %H:%M') if last_post_time_utc else "─"
            
            next_post_str = "─"
            if last_post_time_utc and interval_hours:
                next_post_due_utc = last_post_time_utc + timedelta(hours=interval_hours)
                next_post_str = next_post_due_utc.astimezone(jst).strftime('%m-%d %H:%M')
            
            table_data.append([f"`{account_id}`", status, f"`{last_post_str}`", f"`{next_post_str}`"])
        
        # 実行中のアカウントが先頭に来るようにソート
        table_data.sort(key=lambda row: not row[1].startswith("▶️"))

        self.notifier.send_status_table(
            title=title,
            headers=headers,
            data=table_data,
            color=0x2ECC71 # Green
        )

    def execute_worker_post(self, account_id: str):
        """
        [ワーカー機能] 指定されたアカウントIDの投稿処理を実際に実行する。
        """
        logger.info(f"--- ワーカー実行 (アカウントID: {account_id}) ---")
        
        account_details = self.config.get_active_twitter_account_details(account_id)
        if not account_details:
            logger.error(f"ワーカー処理失敗: アカウントID '{account_id}' が見つからないか、無効です。")
            return

        worksheet_name = account_details.get("spreadsheet_worksheet")
        if not worksheet_name:
            logger.error(f"ワーカー処理失敗: アカウント '{account_id}' にワークシート名が設定されていません。")
            return

        logger.info(f"投稿処理を実行します: Account='{account_id}', Worksheet='{worksheet_name}'")
        
        scheduled_post = {
            "account_id": account_id,
            "scheduled_time": datetime.now(timezone.utc),
            "worksheet_name": worksheet_name
        }

        try:
            tweet_id = self.post_executor.execute_post(scheduled_post)
            if tweet_id:
                logger.info(f"ワーカー処理成功。アカウント '{account_id}' の投稿が完了しました。Tweet ID: {tweet_id}")
                if self.notifier:
                    self.notifier.send_simple_notification(
                        title=f"✅ 投稿成功: `{account_id}`",
                        description=f"Tweet ID: `{tweet_id}`",
                        color=0x3498DB # Blue
                    )
            else:
                # 投稿に至らなかった場合（例：投稿可能な記事がない）
                logger.warning(f"ワーカー処理は正常に完了しましたが、アカウント '{account_id}' の投稿は実行されませんでした（条件未達）。")
                if self.notifier:
                    self.notifier.send_simple_notification(
                        title=f"🤔 投稿スキップ: `{account_id}`",
                        description="投稿可能な記事が見つからなかったため、今回の処理はスキップされました。",
                        color=0xF1C40F # Yellow
                    )
        except Exception as e:
            logger.error(f"ワーカー処理中に予期せぬエラーが発生しました (アカウント: {account_id}): {e}", exc_info=True)
            if self.notifier:
                self.notifier.send_simple_notification(
                    title=f"⚠️ ワーカー処理失敗: `{account_id}`",
                    description=f"アカウント `{account_id}` の投稿処理でエラーが発生しました。詳細はログを確認してください。",
                    color=0xE74C3C # Red
                )
            # エラーを再送出し、呼び出し元（main.py）に失敗を伝播させる
            raise
        finally:
            logger.info(f"--- ワーカー完了 (アカウントID: {account_id}) ---")

    def run_manual_test_post(self, account_id: str):
        """
        [手動テスト機能] 指定されたアカウントで投稿を一件テスト実行する。
        時刻のチェックなどをスキップする。
        """
        logger.info(f"--- 手動テスト投稿開始 (アカウントID: {account_id}) ---")
        account_details = self.config.get_active_twitter_account_details(account_id)
        if not account_details:
            logger.error(f"テスト投稿失敗: アカウントID '{account_id}' が見つからないか、無効です。")
            return
            
        worksheet_name = account_details.get("spreadsheet_worksheet")
        if not worksheet_name:
            logger.error(f"テスト投稿失敗: アカウント '{account_id}' にワークシート名が設定されていません。")
            return

        logger.info(f"テスト投稿を実行します: Account='{account_id}', Worksheet='{worksheet_name}'")
        
        scheduled_post = {
            "account_id": account_id,
            "scheduled_time": datetime.now(timezone.utc),
            "worksheet_name": worksheet_name
        }

        try:
            tweet_id = self.post_executor.execute_post(scheduled_post)
            if tweet_id:
                success_message = f"Tweet ID: `{tweet_id}`\nhttps://twitter.com/user/status/{tweet_id}"
                print(f"\n✅ テスト投稿成功！")
                print(f"   アカウント: {account_id}")
                print(f"   投稿URL: https://twitter.com/user/status/{tweet_id}")
                if self.notifier:
                    self.notifier.send_simple_notification(
                        title=f"✅ [Test] 投稿成功: `{account_id}`",
                        description=success_message,
                        color=0x3498DB # Blue
                    )
            else:
                print(f"\n✅ テスト処理は完了しましたが、投稿は実行されませんでした（投稿可能な記事がなかった可能性があります）。")
                if self.notifier:
                    self.notifier.send_simple_notification(
                        title=f"🤔 [Test] 投稿スキップ: `{account_id}`",
                        description="投稿可能な記事が見つからなかったため、今回の処理はスキップされました。",
                        color=0xF1C40F # Yellow
                    )

        except Exception as e:
            logger.error(f"手動テスト投稿中にエラーが発生しました: {e}", exc_info=True)
            print(f"\n❌ テスト投稿中にエラーが発生しました。詳細はログファイルを確認してください。")
            if self.notifier:
                self.notifier.send_simple_notification(
                    title=f"⚠️ [Test] 処理失敗: `{account_id}`",
                    description=f"手動テスト投稿処理でエラーが発生しました。\n`{str(e)}`",
                    color=0xE74C3C # Red
                )
        finally:
            logger.info(f"--- 手動テスト投稿完了 (アカウントID: {account_id}) ---")