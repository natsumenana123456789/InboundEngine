import tweepy
import webbrowser
import time

# config.ymlからAPI KeyとAPI Key Secretを読み込む想定
# このスクリプト単体で動かすため、簡易的に直接入力するか、
# config_loader.py を使って読み込むようにする。
# ここでは、実行時にユーザーに入力を促す形にする。

print("X Developer AppのAPI KeyとAPI Key Secretを入力してください。")
consumer_key = input("API Key (Consumer Key): ").strip()
consumer_secret = input("API Key Secret (Consumer Secret): ").strip()

if not consumer_key or not consumer_secret:
    print("❌ API KeyとAPI Key Secretの両方が必要です。処理を終了します。")
    exit()

try:
    # OAuth1UserHandler を使用
    auth = tweepy.OAuth1UserHandler(
        consumer_key, consumer_secret,
        callback="oob"  # "oob" (Out-of-Band) を指定するとPINコード認証になる
    )
    print("\n以下のURLをブラウザで開いて認証し、表示されたPINコードを入力してください:")
    print(auth.get_authorization_url())

    # ブラウザを自動で開く試み (環境によっては動作しない場合がある)
    try:
        webbrowser.open(auth.get_authorization_url())
    except Exception:
        print("自動でブラウザを開けませんでした。手動で上記のURLを開いてください。")

    verifier = input("PINコードを入力してください: ").strip()

    access_token, access_token_secret = auth.get_access_token(verifier)

    print("\n🎉 認証に成功しました！以下の情報をconfig.ymlなどに保存してください。")
    print(f"  Access Token: {access_token}")
    print(f"  Access Token Secret: {access_token_secret}")

    # 取得したトークンでAPIクライアントを作成し、ユーザー情報を確認してみる (任意)
    print("\n取得したトークンでAPIをテストします...")
    # client_v1_for_test = tweepy.API(auth) # API v1.1 client APIは使わないのでClientで統一
    
    client_v2_for_test = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    
    try:
        response = client_v2_for_test.get_me(user_fields=["username", "name", "id"])
        if response.data:
            me_v2 = response.data
            print(f"\n[API v2] 認証ユーザー情報:")
            print(f"  ID: {me_v2.id}")
            print(f"  Username (Screen Name): {me_v2.username}")
            print(f"  Name: {me_v2.name}")
            print("\n✅ トークンは正常に機能しているようです。")
        else:
            print("\n⚠️ [API v2] ユーザー情報の取得に失敗しました。レスポンスが空です。")
            if response.errors:
                print(f"  エラー: {response.errors}")


    except Exception as e:
        print(f"\n❌ 取得したトークンでのAPIテスト中にエラーが発生しました: {e}")
        print("   トークン自体は取得できている可能性があります。上記の値を確認してください。")


except tweepy.TweepyException as e:
    print(f"❌ Tweepy関連のエラーが発生しました: {e}")
except Exception as e:
    print(f"❌ 不明なエラーが発生しました: {e}") 