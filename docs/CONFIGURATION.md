# 設定ガイド

このドキュメントでは、アプリケーションの設定方法について説明します。設定は主に `config/config.yml` ファイルと、GitHub Actions を使用する際の Secrets を通じて行われます。

## 設定ファイル (`config/config.yml`)

アプリケーションの主要な動作は `config/config.yml` ファイルによって制御されます。このファイルは `config/config.template.yml` を元に `generate_config.py` スクリプト（またはGitHub Actionsワークフロー）によって生成されます。

### テンプレート (`config.template.yml`)

`config.template.yml` は以下の主要なセクションで構成されています：

```yaml
common:
  log_level: "INFO" # ログレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  logs_directory: "logs" # ログファイルの保存先
  file_paths:
    google_key_file: "gspread-key.json" # Googleサービスアカウントキーのファイル名 (configディレクトリからの相対パス)

# Twitter API v1.1 & v2 (tweepy用)
# グローバルなキーを設定する場合 (generate_config.pyが対応している場合)
# twitter_api:
#   bearer_token: "{{ TWITTER_BEARER_TOKEN_GLOBAL }}"
#   consumer_key: "{{ TWITTER_CONSUMER_KEY_GLOBAL }}"
#   consumer_secret: "{{ TWITTER_CONSUMER_SECRET_GLOBAL }}"
#   access_token: "{{ TWITTER_ACCESS_TOKEN_GLOBAL }}"
#   access_token_secret: "{{ TWITTER_ACCESS_TOKEN_SECRET_GLOBAL }}"

auto_post_bot:
  # Discord通知設定
  discord_notification:
    webhook_url: "{{ DISCORD_WEBHOOK_URL }}" # DiscordのWebhook URL
    notify_daily_schedule_summary: true # 日次スケジュールサマリーを通知するか

  # Google Sheetsからのデータ取得設定
  google_sheets_source:
    # spreadsheet_id: "{{ SPREADSHEET_ID_COMMON }}" # 共通のスプレッドシートID (アカウント別設定がない場合のデフォルト)
    pass # アカウント毎にspreadsheet_idとworksheet_nameを指定する

  # 投稿スケジューリング設定
  schedule_settings:
    start_hour: 9 # 投稿を開始する時間 (24時間表記、JST)
    end_hour: 22 # 投稿を終了する時間 (この時間になったら次の投稿はしない, JST)
    min_interval_minutes: 30 # 投稿間の最短間隔（分）
    # 以下のファイル名は common.logs_directory からの相対パスで指定
    schedule_file: "schedule.json" # 生成されたスケジュールを保存するファイル名
    executed_file: "executed_posts.log" # 実行済み投稿のログファイル名
    test_schedule_file: "test_schedule.json" # テスト用スケジュールファイル
    test_executed_file: "test_executed_posts.log" # テスト用実行ログ
    max_posts_per_hour_globally: 5 # 1時間あたりの最大投稿数 (全体)

  # 投稿内容に関する設定
  posting_settings:
    # posts_per_account: 2 # 1アカウントあたりの1日のデフォルト投稿数 (アカウント個別設定で上書き可能)
    # text_processing:
    #   insert_random_spaces: true # ランダムスペース挿入機能の有効化
    #   num_spaces_to_insert: 3    # 挿入するスペースの最大数
    pass

  # スプレッドシートのカラム名定義 (SpreadsheetManagerが使用)
  columns:
    - "ID"
    - "本文"
    - "画像/動画URL"
    - "投稿可能"
    - "最終投稿日時"
    - "投稿済み回数"
    # - "投稿タイプ" # 必要に応じて追加
    # - "文字数"   # 必要に応じて追加

  # 投稿に使用するTwitterアカウントのリスト
  twitter_accounts:
    # --- アカウント1の設定例 ---
    - account_id: "{{ ACCOUNT1_ID }}" # このアカウントの一意な識別子 (ログや通知で使用)
      enabled: true # このアカウント設定を有効にするか (true/false)
      consumer_key: "{{ ACCOUNT1_CONSUMER_KEY }}"
      consumer_secret: "{{ ACCOUNT1_CONSUMER_SECRET }}"
      access_token: "{{ ACCOUNT1_ACCESS_TOKEN }}"
      access_token_secret: "{{ ACCOUNT1_ACCESS_TOKEN_SECRET }}"
      bearer_token: "{{ ACCOUNT1_BEARER_TOKEN }}" # オプション (v2 APIの一部の読み取り専用エンドポイントで使用)
      # アカウントごとのGoogle Sheets設定 (google_sheets_source.spreadsheet_id がない場合、または上書きする場合)
      google_sheets_source:
        spreadsheet_id: "{{ ACCOUNT1_SPREADSHEET_ID }}" # このアカウントが使用するスプレッドシートのID
        worksheet_name: "{{ ACCOUNT1_WORKSHEET_NAME }}" # このアカウントが使用するワークシート名
      # posts_today: 3 # このアカウントの今日の投稿数 (日によって変更したい場合など。なければposting_settings.posts_per_accountが適用)

    # --- アカウント2の設定例 ---
    # - account_id: "{{ ACCOUNT2_ID }}"
    #   enabled: true
    #   consumer_key: "{{ ACCOUNT2_CONSUMER_KEY }}"
    #   consumer_secret: "{{ ACCOUNT2_CONSUMER_SECRET }}"
    #   access_token: "{{ ACCOUNT2_ACCESS_TOKEN }}"
    #   access_token_secret: "{{ ACCOUNT2_ACCESS_TOKEN_SECRET }}"
    #   bearer_token: "{{ ACCOUNT2_BEARER_TOKEN }}"
    #   google_sheets_source:
    #     spreadsheet_id: "{{ ACCOUNT2_SPREADSHEET_ID }}"
    #     worksheet_name: "{{ ACCOUNT2_WORKSHEET_NAME }}"
    #   # posts_today: 1

# gspreadライブラリが直接JSON文字列を読み込む場合の設定
# generate_config.py側で環境変数から直接json文字列を埋め込むことを想定
# gspread:
#   credentials_json: "{{ GSPREAD_CREDENTIALS_JSON }}"
```

### `generate_config.py` による設定ファイルの生成
このスクリプトは、`config/config.template.yml` を読み込み、`{{ PLACEHOLDER }}` 形式のプレースホルダーを対応する環境変数の値で置き換えて `config/config.yml` を生成します。
ローカルで実行する場合、事前に必要な環境変数を設定しておく必要があります。

### GitHub Actions Secrets

GitHub Actions を使用して自動実行する場合、以下の Secrets をリポジトリに設定する必要があります。これらの Secret はワークフロー内で環境変数として `generate_config.py` に渡されます。

**必須のSecrets:**

*   `GOOGLE_SHEETS_KEY`: Google Cloud Service Account の JSON キーファイルの内容全体をコピー＆ペーストしてください。
*   `DISCORD_WEBHOOK_URL`: 通知を送信するためのDiscord Webhook URL。

**アカウントごとのSecrets (例: アカウント1):**
これらは `config.template.yml` 内の `{{ ACCOUNT1_... }}` プレースホルダーに対応します。
アカウントを追加する場合は、`ACCOUNT2_...`, `ACCOUNT3_...` のように連番で Secrets を追加してください。

*   `ACCOUNT1_ID`: アカウントの一意な識別子 (例: `MyTwitterAccount1`)。
*   `ACCOUNT1_CONSUMER_KEY`: Twitter API Consumer Key。
*   `ACCOUNT1_CONSUMER_SECRET`: Twitter API Consumer Secret。
*   `ACCOUNT1_ACCESS_TOKEN`: Twitter API Access Token。
*   `ACCOUNT1_ACCESS_TOKEN_SECRET`: Twitter API Access Token Secret。
*   `ACCOUNT1_BEARER_TOKEN`: (オプション) Twitter API Bearer Token。
*   `ACCOUNT1_SPREADSHEET_ID`: このアカウントが使用するGoogleスプレッドシートのID。
*   `ACCOUNT1_WORKSHEET_NAME`: このアカウントが使用するスプレッドシート内のワークシート名。

**例: Secrets 設定の簡潔リスト**
```
# 一般
DISCORD_WEBHOOK_URL
GOOGLE_SHEETS_KEY

# アカウント1
ACCOUNT1_ID
ACCOUNT1_CONSUMER_KEY
ACCOUNT1_CONSUMER_SECRET
ACCOUNT1_ACCESS_TOKEN
ACCOUNT1_ACCESS_TOKEN_SECRET
ACCOUNT1_BEARER_TOKEN  # オプション
ACCOUNT1_SPREADSHEET_ID
ACCOUNT1_WORKSHEET_NAME

# アカウント2 (必要に応じて)
# ACCOUNT2_ID
# ACCOUNT2_CONSUMER_KEY
# ... (以下同様)
```

### スプレッドシートの形式

投稿内容はGoogleスプレッドシートで管理されます。以下の列構造を想定しています（`config.yml` の `columns` 設定で変更可能）。

| ID (任意) | 本文        | 画像/動画URL (任意) | 投稿可能 (TRUE/FALSE) | 最終投稿日時 (自動更新) | 投稿済み回数 (自動更新) |
|-----------|-------------|----------------------|----------------------|-------------------------|-----------------------|
| 1         | 今日の天気は... | https://.../image.jpg | TRUE                 |                         | 0                     |
| 2         | お知らせ...   |                      | TRUE                 |                         | 0                     |

- **ID**: 投稿を識別するための一意のID（省略可能）。
- **本文**: ツイートの本文。
- **画像/動画URL**: 添付する画像のURL。複数指定する場合はカンマ区切り。動画URLも同様。
- **投稿可能**: `TRUE` の場合のみ投稿対象となります。`FALSE` の場合や空欄の場合はスキップされます。
- **最終投稿日時**: ボットが自動で更新します。この列の日時が古いものから優先的に投稿されます。
- **投稿済み回数**: ボットが自動で更新します。

`config.yml` の `auto_post_bot.columns` で、実際に使用するカラム名を指定してください。 