import os
import pytest
import yaml
from datetime import datetime
from src.notifiers.discord_notifier import DiscordNotifier

class TestDiscordNotificationIntegration:
    """Discord通知機能の統合テスト"""

    @pytest.fixture
    def config(self):
        """テスト用の設定を読み込む"""
        config_path = os.path.join(os.path.dirname(__file__), "../../config.yml")
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def notifier(self, config):
        """実際のWebhook URLを使用してNotifierを初期化"""
        webhook_url = config["notifiers"]["discord"]["webhook_url"]
        return DiscordNotifier(webhook_url=webhook_url)

    def test_notification_workflow(self, notifier):
        """通知ワークフローの統合テスト
        
        以下のシナリオをテスト：
        1. 処理開始通知
        2. 進捗状況の通知
        3. エラー発生時の通知
        4. 処理完了通知
        """
        # 1. 処理開始通知
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = notifier.send_embed(
            title="処理開始",
            description=f"バッチ処理を開始します\n開始時刻: {start_time}",
            color="#0000ff"
        )
        assert result is True

        # 2. 進捗状況の通知
        progress_fields = {
            "処理済み": "10件",
            "残り": "20件",
            "予想完了時刻": "約10分後"
        }
        result = notifier.send_embed(
            title="進捗状況",
            description="バッチ処理実行中...",
            fields=progress_fields,
            color="#00ff00"
        )
        assert result is True

        # 3. エラー発生時の通知
        error_details = {
            "エラーコード": "E001",
            "発生時刻": datetime.now().strftime("%H:%M:%S"),
            "影響範囲": "一部の処理がスキップされました",
            "対応状況": "自動リトライ中"
        }
        result = notifier.send_error(
            "データ処理中にエラーが発生しました",
            error_details
        )
        assert result is True

        # 4. 処理完了通知
        completion_fields = {
            "処理件数": "30件",
            "成功": "28件",
            "失敗": "2件",
            "所要時間": "15分"
        }
        result = notifier.send_embed(
            title="処理完了",
            description="バッチ処理が完了しました",
            fields=completion_fields,
            color="#00ff00"
        )
        assert result is True

    def test_error_recovery_workflow(self, notifier):
        """エラーからの復旧ワークフローの統合テスト
        
        以下のシナリオをテスト：
        1. エラー発生通知
        2. リトライ開始通知
        3. 復旧完了通知
        """
        # 1. エラー発生通知
        error_time = datetime.now().strftime("%H:%M:%S")
        result = notifier.send_error(
            "ネットワークエラーが発生しました",
            {
                "発生時刻": error_time,
                "エラー詳細": "接続タイムアウト",
                "状態": "自動復旧を開始します"
            }
        )
        assert result is True

        # 2. リトライ開始通知
        result = notifier.send_embed(
            title="リトライ開始",
            description="自動復旧処理を開始します",
            fields={
                "リトライ回数": "1回目",
                "対象処理": "データ同期",
                "開始時刻": datetime.now().strftime("%H:%M:%S")
            },
            color="#ffff00"
        )
        assert result is True

        # 3. 復旧完了通知
        result = notifier.send_embed(
            title="復旧完了",
            description="エラーから正常に復旧しました",
            fields={
                "復旧時刻": datetime.now().strftime("%H:%M:%S"),
                "復旧方法": "自動リトライ",
                "状態": "正常稼働中"
            },
            color="#00ff00"
        )
        assert result is True 