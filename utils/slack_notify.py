import requests

def notify_slack(message, webhook_url, level=None):
    """
    Slack Incoming Webhookでメッセージを送信
    
    Args:
        message (str): 送信するメッセージ
        webhook_url (str): Slack Incoming WebhookのURL
        level (str, optional): メッセージのレベル（info, warning, error）
    """
    # レベルに応じた絵文字を設定
    emoji = {
        'info': ':information_source:',
        'warning': ':warning:',
        'error': ':x:',
    }.get(level, ':robot_face:')
    
    payload = {
        "text": message,
        "username": "Auto Post Bot",
        "icon_emoji": emoji
    }
    
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print(f"Slack通知を送信しました: {message}")
        return True
    except Exception as e:
        print(f"Slack通知に失敗しました: {e}")
        return False 