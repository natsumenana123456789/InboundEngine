import os
import datetime
import random

# ACCOUNTS = ['jadiAngkat', 'account2', 'account3']  # 複数アカウント名
POSTS_PER_ACCOUNT = 1  # 1アカウントあたりの投稿回数
START_HOUR = 10
END_HOUR = 22
MIN_INTERVAL_MINUTES = 10
SCHEDULE_FILE = 'logs/schedule.txt'
EXECUTED_FILE = 'logs/executed.txt'

# ハイブリッドアカウント管理システムをインポート
try:
    from config.account_management import AccountManager
    from config import config_loader
    account_manager = AccountManager()
    
    def get_accounts():
        """スプレッドシート、またはconfig.ymlから有効なアカウントIDリストを取得"""
        # 1. ハイブリッドシステムを試行
        try:
            scheduler_accounts = account_manager.get_scheduler_accounts()
            if scheduler_accounts:
                print(f"ハイブリッドシステムから {len(scheduler_accounts)} 個のアカウントを取得: {scheduler_accounts}")
                return scheduler_accounts
        except Exception as e:
            print(f"ハイブリッドシステムからの取得に失敗: {e}")
        
        # 2. config.ymlからフォールバック
        try:
            config = config_loader.get_bot_config("auto_post_bot")
            twitter_accounts = config.get('twitter_accounts', [])
            if twitter_accounts:
                account_ids = [acc.get('username') or acc.get('account_id') for acc in twitter_accounts]
                account_ids = [acc for acc in account_ids if acc]  # 空でないものだけ
                print(f"config.ymlから {len(account_ids)} 個のアカウントを取得: {account_ids}")
                return account_ids
        except Exception as e:
            print(f"config.ymlからの取得に失敗: {e}")
            
        # 3. 最終フォールバック
        print("⚠️ 全ての方法でアカウント取得に失敗。固定リストを使用")
        return ['jadiAngkat', 'account2', 'account3']
    
    print("ハイブリッドアカウント管理システムを使用します（config.yml対応）")
except ImportError:
    # フォールバック: 従来の固定リスト
    def get_accounts():
        try:
            from config import config_loader
            config = config_loader.get_bot_config("auto_post_bot")
            twitter_accounts = config.get('twitter_accounts', [])
            if twitter_accounts:
                account_ids = [acc.get('username') or acc.get('account_id') for acc in twitter_accounts]
                account_ids = [acc for acc in account_ids if acc]
                print(f"config.ymlから {len(account_ids)} 個のアカウントを取得: {account_ids}")
                return account_ids
        except Exception as e:
            print(f"config.yml読み込みエラー: {e}")
        
        print("⚠️ 固定アカウントリストを使用します")
        return ['jadiAngkat', 'account2', 'account3']
    
    print("⚠️ ハイブリッドシステムが利用できません。config.yml方式を使用します")

# Slack通知用
try:
    from utils.slack_notify import notify_slack
except ImportError:
    notify_slack = None

def send_schedule_to_slack(acc_times):
    if notify_slack is None:
        print("Slack通知機能が利用できません")
        return
    msg = "\n".join([f"{acc}: {t.strftime('%Y-%m-%d %H:%M:%S')}" for acc, t in acc_times])
    text = f"本日の自動投稿スケジュール\n```\n{msg}\n```"
    notify_slack(text)
    print("Slackにスケジュールを通知しました")

def generate_multi_account_schedule():
    today = datetime.date.today()
    all_times = []  # (アカウント, datetime) のリスト
    used_times = []
    for acc in get_accounts():
        for _ in range(POSTS_PER_ACCOUNT):
            # 10分以上離れた時刻をランダムに探す
            for _ in range(100):  # 最大100回試行
                hour = random.randint(START_HOUR, END_HOUR - 1)
                minute = random.randint(0, 59)
                dt = datetime.datetime(today.year, today.month, today.day, hour, minute, 0)
                # 既存の全時刻と10分以上離れているか
                if all(abs((dt - t).total_seconds()) >= MIN_INTERVAL_MINUTES*60 for _, t in used_times):
                    used_times.append((acc, dt))
                    break
            else:
                raise Exception('10分以上離れた時刻が見つかりませんでした')
    # 時刻順にソート
    all_times = sorted(used_times, key=lambda x: x[1])
    return all_times

def read_schedule():
    if not os.path.exists(SCHEDULE_FILE):
        return []
    with open(SCHEDULE_FILE, 'r') as f:
        lines = f.readlines()
    result = []
    for line in lines:
        if line.strip():
            acc, dtstr = line.strip().split(',', 1)
            dt = datetime.datetime.strptime(dtstr, '%Y-%m-%d %H:%M:%S')
            result.append((acc, dt))
    return result

def write_schedule(acc_times):
    with open(SCHEDULE_FILE, 'w') as f:
        for acc, t in acc_times:
            f.write(f'{acc},{t.strftime("%Y-%m-%d %H:%M:%S")}\n')

def read_executed():
    if not os.path.exists(EXECUTED_FILE):
        return set()
    with open(EXECUTED_FILE, 'r') as f:
        lines = f.readlines()
    return set(line.strip() for line in lines if line.strip())

def mark_executed(acc, dt):
    with open(EXECUTED_FILE, 'a') as f:
        f.write(f'{acc},{dt.strftime("%Y-%m-%d %H:%M:%S")}\n')
    print(f"[mark_executed] {acc},{dt.strftime('%Y-%m-%d %H:%M:%S')} を実行済みに記録しました")

def schedule_at_command(acc, dt):
    # テスト用: 実際にはechoでコマンド内容を表示
    at_time = dt.strftime('%H:%M %m/%d/%Y')
    cmd = f"echo 'python3 bots/auto_post_bot/post_tweet.py --account {acc} && python3 schedule_posts.py --mark-executed {acc} {dt.strftime('%Y-%m-%d %H:%M:%S')}' | at {at_time}"
    print(f"[at予約] {cmd}")
    # 実際にatコマンドを使う場合は下記を有効化
    # os.system(cmd)

def main():
    import sys
    # mark-executedオプションで呼ばれた場合
    if len(sys.argv) > 3 and sys.argv[1] == '--mark-executed':
        acc = sys.argv[2]
        dt = datetime.datetime.strptime(sys.argv[3], '%Y-%m-%d %H:%M:%S')
        mark_executed(acc, dt)
        return

    now = datetime.datetime.now()
    schedule = read_schedule()
    # 今日のスケジュールがなければ新規作成
    if not schedule or schedule[0][1].date() != now.date():
        acc_times = generate_multi_account_schedule()
        write_schedule(acc_times)
        print(f'新しいスケジュールを作成しました:')
        for acc, t in acc_times:
            print(f'{acc},{t.strftime("%Y-%m-%d %H:%M:%S")}')
        send_schedule_to_slack(acc_times)
        schedule = acc_times
    else:
        print('既存のスケジュールを使用します')

    executed = read_executed()
    # 未実行分だけ抽出
    pending = [(acc, t) for acc, t in schedule if f'{acc},{t.strftime("%Y-%m-%d %H:%M:%S")}' not in executed and t > now]
    print(f'未実行スケジュール:')
    for acc, t in pending:
        print(f'{acc},{t.strftime("%Y-%m-%d %H:%M:%S")}')
        schedule_at_command(acc, t)

if __name__ == '__main__':
    main() 