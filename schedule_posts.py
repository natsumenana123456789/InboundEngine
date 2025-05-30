import os
import datetime
import random
import argparse

POSTS_PER_ACCOUNT = 1  # 1アカウントあたりの投稿回数
START_HOUR = 10
END_HOUR = 22
MIN_INTERVAL_MINUTES = 10
SCHEDULE_FILE = 'logs/schedule.txt'
EXECUTED_FILE = 'logs/executed.txt'

# config.ymlからアカウントを読み取り
try:
    from config import config_loader
    
    def get_accounts():
        """config.ymlから有効なアカウントIDリストを取得"""
        try:
            config = config_loader.get_bot_config("auto_post_bot")
            twitter_accounts = config.get('twitter_accounts', [])
            if twitter_accounts:
                account_ids = [acc.get('username') or acc.get('account_id') for acc in twitter_accounts]
                account_ids = [acc for acc in account_ids if acc]  # 空でないものだけ
                print(f"config.ymlから {len(account_ids)} 個のアカウントを取得: {account_ids}")
                return account_ids
            else:
                print("⚠️ config.ymlにtwitter_accountsが設定されていません")
                return []
        except Exception as e:
            print(f"config.yml読み込みエラー: {e}")
            return []
    
    print("config.ymlからアカウント情報を読み取ります")
except ImportError:
    print("⚠️ config_loaderのインポートに失敗しました")
    def get_accounts():
        return []

# Slack通知用
try:
    from utils.slack_notify import notify_slack
except ImportError:
    notify_slack = None

def send_schedule_to_slack(acc_times):
    if notify_slack is None:
        print("Slack通知機能が利用できません")
        return
    try:
        from config import config_loader
        config = config_loader.get_bot_config("auto_post_bot")
        webhook_url = config.get("slack_webhook_url")
        if not webhook_url:
            print("slack_webhook_urlが設定されていません")
            return
        msg = "\n".join([f"{acc}: {t.strftime('%Y-%m-%d %H:%M:%S')}" for acc, t in acc_times])
        text = f"📅 本日の自動投稿スケジュール\n```\n{msg}\n```"
        notify_slack(text, webhook_url)
        print("Slackにスケジュールを通知しました")
    except Exception as e:
        print(f"Slack通知エラー: {e}")

def generate_multi_account_schedule(start_from_now=False):
    """スケジュールを生成する
    
    Args:
        start_from_now (bool): Trueの場合、現在時刻以降からスケジュール生成
    """
    today = datetime.date.today()
    now = datetime.datetime.now()
    
    # 開始時刻の決定
    if start_from_now and now.date() == today:
        # 現在時刻以降で、かつ10分後以降から開始
        start_time = now + datetime.timedelta(minutes=MIN_INTERVAL_MINUTES)
        start_hour = start_time.hour
        start_minute = start_time.minute
        
        # 営業時間外の場合は翌日の営業開始時間に設定
        if start_hour >= END_HOUR:
            print(f"⏰ 現在時刻 {now.strftime('%H:%M')} は営業時間外です")
            tomorrow = today + datetime.timedelta(days=1)
            print(f"📅 翌日 ({tomorrow.strftime('%Y-%m-%d')}) の {START_HOUR}:00 からスケジュール生成します")
            today = tomorrow
            start_hour = START_HOUR
            start_minute = 0
        else:
            print(f"⏰ 現在時刻 {now.strftime('%H:%M')} 以降でスケジュール生成します")
    else:
        # 通常の営業開始時間から
        start_hour = START_HOUR
        start_minute = 0
        print(f"⏰ 営業時間 {START_HOUR}:00-{END_HOUR}:00 でスケジュール生成します")
    
    all_times = []  # (アカウント, datetime) のリスト
    used_times = []
    
    for acc in get_accounts():
        for _ in range(POSTS_PER_ACCOUNT):
            # 10分以上離れた時刻をランダムに探す
            for attempt in range(100):  # 最大100回試行
                if start_from_now and now.date() == today:
                    # 現在時刻以降の範囲で生成
                    if start_hour >= END_HOUR - 1:
                        # 時間が足りない場合は翌日
                        tomorrow = today + datetime.timedelta(days=1)
                        hour = random.randint(START_HOUR, END_HOUR - 1)
                        minute = random.randint(0, 59)
                        dt = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, 0)
                        print(f"⚠️ 本日の残り時間が不足のため、翌日に設定: {dt.strftime('%Y-%m-%d %H:%M')}")
                    else:
                        hour = random.randint(start_hour, END_HOUR - 1)
                        if hour == start_hour:
                            minute = random.randint(start_minute, 59)
                        else:
                            minute = random.randint(0, 59)
                        dt = datetime.datetime(today.year, today.month, today.day, hour, minute, 0)
                        
                        # 現在時刻より前になってしまった場合は再試行
                        if dt <= now + datetime.timedelta(minutes=MIN_INTERVAL_MINUTES):
                            continue
                else:
                    # 通常の営業時間内で生成
                    hour = random.randint(START_HOUR, END_HOUR - 1)
                    minute = random.randint(0, 59)
                    dt = datetime.datetime(today.year, today.month, today.day, hour, minute, 0)
                
                # 既存の全時刻と10分以上離れているかチェック
                if all(abs((dt - t).total_seconds()) >= MIN_INTERVAL_MINUTES*60 for _, t in used_times):
                    used_times.append((acc, dt))
                    break
            else:
                # 100回試行しても見つからない場合のフォールバック
                if start_from_now:
                    print(f"⚠️ アカウント {acc} の適切な時刻が見つからないため、翌日に設定します")
                    tomorrow = today + datetime.timedelta(days=1)
                    fallback_hour = random.randint(START_HOUR, END_HOUR - 1)
                    fallback_minute = random.randint(0, 59)
                    fallback_dt = datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, fallback_hour, fallback_minute, 0)
                    used_times.append((acc, fallback_dt))
                else:
                    raise Exception(f'アカウント {acc} の10分以上離れた時刻が見つかりませんでした')
    
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
    # logsディレクトリが存在しない場合は作成
    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    
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
    # logsディレクトリが存在しない場合は作成
    os.makedirs(os.path.dirname(EXECUTED_FILE), exist_ok=True)
    
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
    
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description='自動投稿スケジュール管理')
    parser.add_argument('--mark-executed', nargs=2, metavar=('ACCOUNT', 'DATETIME'),
                       help='指定された投稿を実行済みとしてマーク')
    parser.add_argument('--now', action='store_true',
                       help='現在時刻以降でスケジュールを生成（中途半端な時間からでも対応）')
    parser.add_argument('--force-regenerate', action='store_true',
                       help='既存のスケジュールがあっても強制的に再生成')
    
    args = parser.parse_args()
    
    # mark-executedオプションで呼ばれた場合
    if args.mark_executed:
        acc, datetime_str = args.mark_executed
        dt = datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        mark_executed(acc, dt)
        return

    now = datetime.datetime.now()
    schedule = read_schedule()
    
    # スケジュール生成条件の判定
    should_regenerate = False
    
    if args.force_regenerate:
        print("🔄 強制再生成モードでスケジュールを作成します")
        should_regenerate = True
    elif not schedule:
        print("📅 スケジュールファイルが存在しないため、新規作成します")
        should_regenerate = True
    elif schedule[0][1].date() != now.date():
        print(f"📅 既存スケジュールが別日付 ({schedule[0][1].date()}) のため、新規作成します")
        should_regenerate = True
    elif args.now:
        print("⏰ --nowオプションが指定されたため、現在時刻以降でスケジュールを再生成します")
        should_regenerate = True
    
    # スケジュール生成または読み込み
    if should_regenerate:
        acc_times = generate_multi_account_schedule(start_from_now=args.now)
        write_schedule(acc_times)
        print(f'✅ 新しいスケジュールを作成しました:')
        for acc, t in acc_times:
            relative_time = ""
            time_diff = (t - now).total_seconds()
            if time_diff > 0:
                hours = int(time_diff // 3600)
                minutes = int((time_diff % 3600) // 60)
                if hours > 0:
                    relative_time = f" (約{hours}時間{minutes}分後)"
                else:
                    relative_time = f" (約{minutes}分後)"
            print(f'  {acc}: {t.strftime("%Y-%m-%d %H:%M:%S")}{relative_time}')
        send_schedule_to_slack(acc_times)
        schedule = acc_times
    else:
        print('📋 既存のスケジュールを使用します')

    executed = read_executed()
    # 未実行分だけ抽出
    pending = [(acc, t) for acc, t in schedule if f'{acc},{t.strftime("%Y-%m-%d %H:%M:%S")}' not in executed and t > now]
    
    if pending:
        print(f'⏳ 未実行スケジュール ({len(pending)}件):')
        for acc, t in pending:
            time_diff = (t - now).total_seconds()
            relative_time = ""
            if time_diff > 0:
                hours = int(time_diff // 3600)
                minutes = int((time_diff % 3600) // 60)
                if hours > 0:
                    relative_time = f" (約{hours}時間{minutes}分後)"
                else:
                    relative_time = f" (約{minutes}分後)"
            print(f'  {acc}: {t.strftime("%Y-%m-%d %H:%M:%S")}{relative_time}')
            schedule_at_command(acc, t)
    else:
        print('✅ 未実行のスケジュールはありません')

if __name__ == '__main__':
    main() 