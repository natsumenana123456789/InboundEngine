from oauth_handler import OAuthHandler

def test_oauth():
    handler = OAuthHandler()
    try:
        credentials = handler.get_credentials()
        print("認証成功！")
        print(f"トークン有効期限: {credentials.expiry}")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    test_oauth() 