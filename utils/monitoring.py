import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class MonitoringSystem:
    def __init__(self):
        self.stats: Dict[str, Any] = {
            'success_count': 0,
            'failure_count': 0,
            'last_error': None,
            'last_success_time': None,
            'account_stats': {}  # アカウントごとの統計
        }
        
    def notify_slack(self, message: str, webhook_url: str) -> bool:
        """Slack通知の基本実装"""
        try:
            payload = {
                "text": message,
                "username": "Auto Post Bot",
                "icon_emoji": ":robot_face:"
            }
            response = requests.post(webhook_url, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack通知エラー: {e}")
            return False

    def record_post_result(self, account_id: str, success: bool, error: Optional[Exception] = None):
        """投稿結果の記録"""
        # アカウントごとの統計を初期化
        if account_id not in self.stats['account_stats']:
            self.stats['account_stats'][account_id] = {
                'success_count': 0,
                'failure_count': 0,
                'last_error': None,
                'last_success_time': None
            }
            
        # 全体の統計を更新
        if success:
            self.stats['success_count'] += 1
            self.stats['last_success_time'] = datetime.now()
            self.stats['account_stats'][account_id]['success_count'] += 1
            self.stats['account_stats'][account_id]['last_success_time'] = datetime.now()
        else:
            self.stats['failure_count'] += 1
            self.stats['last_error'] = str(error)
            self.stats['account_stats'][account_id]['failure_count'] += 1
            self.stats['account_stats'][account_id]['last_error'] = str(error)

    def get_account_stats(self, account_id: str) -> Dict[str, Any]:
        """アカウントごとの統計を取得"""
        return self.stats['account_stats'].get(account_id, {
            'success_count': 0,
            'failure_count': 0,
            'last_error': None,
            'last_success_time': None
        })

    def reset_stats(self):
        """統計情報のリセット"""
        self.stats = {
            'success_count': 0,
            'failure_count': 0,
            'last_error': None,
            'last_success_time': None,
            'account_stats': {}
        }

class DailyReporter:
    def __init__(self, monitoring_system: MonitoringSystem):
        self.monitoring = monitoring_system
        
    def generate_daily_report(self) -> str:
        """日次レポートの生成"""
        total = self.monitoring.stats['success_count'] + self.monitoring.stats['failure_count']
        if total == 0:
            return "本日の投稿はありませんでした。"
            
        success_rate = (self.monitoring.stats['success_count'] / total) * 100
        
        report = f"""
📊 本日の投稿レポート
-------------------
全体の統計:
成功: {self.monitoring.stats['success_count']}件
失敗: {self.monitoring.stats['failure_count']}件
成功率: {success_rate:.1f}%

アカウント別の統計:
"""
        # アカウントごとの統計を追加
        for account_id, stats in self.monitoring.stats['account_stats'].items():
            account_total = stats['success_count'] + stats['failure_count']
            account_success_rate = (stats['success_count'] / account_total * 100) if account_total > 0 else 0
            report += f"""
{account_id}:
  成功: {stats['success_count']}件
  失敗: {stats['failure_count']}件
  成功率: {account_success_rate:.1f}%
"""
            
        if self.monitoring.stats['last_error']:
            report += f"\n最後のエラー: {self.monitoring.stats['last_error']}"
            
        return report

    def send_daily_report(self, webhook_url: str) -> bool:
        """日次レポートの生成と送信"""
        report = self.generate_daily_report()
        return self.monitoring.notify_slack(report, webhook_url) 