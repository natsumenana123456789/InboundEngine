import requests

def notify_slack(message, webhook_url):
    """Slack Incoming Webhookでメッセージを送信"""
    payload = {"text": message}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Slack通知に失敗しました: {e}") 