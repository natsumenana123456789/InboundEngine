# InboundEngine - 自動投稿Bot管理システム

## 📋 概要

InboundEngineは、X (旧Twitter) への自動投稿を効率的に管理するシステムです。Googleスプレッドシートから投稿データを取得し、複数アカウントでの自動投稿、およびDiscordへの通知機能を提供します。

**主な機能:**
- Googleスプレッドシートからのデータ取得と投稿ステータスの更新
- 複数アカウント対応 (アカウントごとの有効/無効設定可能)
- Discordへの通知機能 (日次スケジュールサマリー、投稿結果、エラー通知)
- 画像および動画の投稿対応 (Google Drive経由)
- 同一コンテンツ投稿エラーを回避するためのランダムスペース挿入機能
- 動画の同一性判定を回避するためのメタデータ変更機能 (ffmpeg利用)
- Twitter APIのレート制限を考慮したエラーハンドリングと通知

## 🚀 システムアーキテクチャ

### コアエンジン (`engine_core/`)
- `main.py`: システムのエントリーポイント。コマンドライン引数により動作を制御します。
- `workflow_manager.py`: 投稿スケジュールの生成、実行、結果通知など、システム全体のワークフローを管理します。
- `config.py`: 設定ファイル (`config.yml`) の読み込みと管理を行います。
- `spreadsheet_manager.py`: `gspread`ライブラリを使用し、Googleスプレッドシートとの連携（データ読み込み、ステータス更新）を担います。
- `twitter_client.py`: `tweepy`ライブラリを使用し、Twitter API (v2 Text, v1.1 Media) を介した投稿処理、メディアアップロード、レート制限対応などを行います。
- `discord_notifier.py`: `requests`ライブラリを使用し、Discordへの各種通知処理を行います。
- `scheduler/post_scheduler.py`: スプレッドシートから投稿データを取得し、指定された日付の投稿スケジュールファイル (JSON形式) を生成します。
- `scheduler/scheduled_post_executor.py`: 生成されたスケジュールファイルに基づき、個々の投稿を実行し、結果を記録・通知します。

### 設定管理
- `config/config.template.yml`: 設定ファイルのテンプレートです。APIキーなどのシークレット情報はプレースホルダーとして記述されています。
- `generate_config.py`: プロジェクトルートにあるPythonスクリプト。`config.template.yml` と環境変数 (GitHub ActionsのSecretsなど) を元に、実行時に `config/config.yml` を生成します。
- `config/config.yml`: アプリケーションの動作設定ファイル。このファイルはGitの管理対象外です (`.gitignore` に記載)。

### 定期実行
- **GitHub Actions**: `.github/workflows/auto-post-bot.yml` の定義に基づき、毎日定時 (日本時間午前7時) に `main.py` が実行され、その日の投稿処理が行われます。

## 🛠️ セットアップと実行

### 必要なもの
- Python 3.10 以降
- Twitter APIキー (Consumer Key, Consumer Secret, Access Token, Access Token Secret, Bearer Token)
- Google Cloud Platformプロジェクトとサービスアカウントキー (Google Sheets API, Google Drive API有効化)
- Discord Webhook URL
- `ffmpeg` (動画投稿機能を利用する場合、実行環境にインストールされていること)

### ローカルでの実行手順
1.  このリポジトリをクローンします。
    ```bash
    git clone https://github.com/natsumenana123456789/InboundEngine.git
    cd InboundEngine
    ```
2.  Pythonの仮想環境を作成し、有効化します。(例: `venv`)
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # macOS / Linux
    # .venv\\Scripts\\activate    # Windows
    ```
3.  必要なライブラリをインストールします。
    ```bash
    pip install -r requirements.txt
    pip install pyyaml # generate_config.py のために必要
    ```
4.  設定ファイルを準備します。
    - **方法A (推奨):** `config/config.template.yml` を参考に、必要な情報をプレースホルダー部分に記述した上で、ファイル名を `config/config.yml` として保存します。Googleサービスアカウントの認証情報JSONファイルは `config/credentials.json` (または `config.yml` で指定したパス) に配置します。
    - **方法B (GitHub Actionsと同様の方法):**
        1.  `config/config.template.yml` はそのまま使用します。
        2.  テンプレート内のプレースホルダーに対応する環境変数を設定します (例: `GSPREAD_CREDENTIALS_JSON` にサービスアカウントJSONの中身を文字列で設定)。
        3.  `python generate_config.py` を実行すると、`config/config.yml` が生成されます。
5.  `main.py` を実行します。
    ```bash
    # 例: 特定の日付のスケジュールを生成
    python main.py --generate-schedule --date YYYY-MM-DD

    # 例: 特定の日付のスケジュール処理を実行 (投稿実行、Discord通知など)
    python main.py --date YYYY-MM-DD

    # 例: 手動テスト用のスケジュールで即時処理 (config.ymlのtest_schedule_fileを使用)
    python run_manual_test.py --account_id YOUR_TEST_ACCOUNT_ID
    ```
    利用可能なオプションの詳細は `python main.py --help` で確認できます。

### GitHub Actions での自動実行
1.  お使いのGitHubリポジトリの `Settings` > `Secrets and variables` > `Actions` で、以下の情報を **Secrets** として登録します。
    - `GSPREAD_CREDENTIALS_JSON`: GoogleサービスアカウントのJSONキーファイルの中身全体 (文字列)。
    - `DISCORD_WEBHOOK_URL`: DiscordのWebhook URL。
    - `TWITTER_CONSUMER_KEY_アカウントID` (例: `TWITTER_CONSUMER_KEY_USER1`)
    - `TWITTER_CONSUMER_SECRET_アカウントID`
    - `TWITTER_ACCESS_TOKEN_アカウントID`
    - `TWITTER_ACCESS_TOKEN_SECRET_アカウントID`
    - `TWITTER_BEARER_TOKEN_アカウントID`
    - `SPREADSHEET_ID_アカウントID`
    (上記「アカウントID」部分は、`config.template.yml` の `twitter_accounts` セクションの `account_id` に対応させてください。)
2.  `.github/workflows/auto-post-bot.yml` の設定に基づき、プッシュやスケジュールトリガーで自動的にジョブが実行されます。

## ⚙️ 設定項目 (`config/config.yml`)

主要な設定項目は以下の通りです。詳細は `config/config.template.yml` を参照してください。

- `common`: ログレベル、ログディレクトリ、スケジュールファイルパスなど。
- `gspread`: Googleスプレッドシート認証情報。
- `discord`: Discord通知設定。
- `twitter_accounts`: 投稿に使用するTwitterアカウント情報 (APIキー、スプレッドシートID、ワークシート名、有効フラグなど) のリスト。
- `ffmpeg`: `ffmpeg`の実行パス。
- `columns`: スプレッドシートで使用する列名定義。

## 📇 アカウント追加・管理手順

1.  **Twitter Developer Portal での準備:**
    - 新しいTwitterアプリを作成 (または既存のアプリを使用) し、必要なAPIキー (Consumer Key/Secret, Access Token/Secret, Bearer Token) を取得します。
2.  **Googleスプレッドシートの準備:**
    - 新しいアカウント用のワークシートを作成 (または既存のスプレッドシートにシートを追加) します。
    - `config.yml` の `columns` で定義されたヘッダー行を設定します。
3.  **`config/config.yml` (または `config.template.yml`) の更新:**
    - `twitter_accounts` リストに新しいアカウントの情報を追加します。
      ```yaml
      twitter_accounts:
        - account_id: "新しいアカウントの識別子" # 例: MyNewAccount
          consumer_key: "YOUR_CONSUMER_KEY"
          consumer_secret: "YOUR_CONSUMER_SECRET"
          access_token: "YOUR_ACCESS_TOKEN"
          access_token_secret: "YOUR_ACCESS_TOKEN_SECRET"
          bearer_token: "YOUR_BEARER_TOKEN"
          spreadsheet_id: "対象スプレッドシートのID"
          worksheet_name: "対象ワークシート名"
          enabled: true # trueで有効、falseで無効
        # ... 他のアカウント設定 ...
      ```
4.  **(GitHub Actions利用時) Secretsの追加:**
    - 手順1で取得したAPIキーとスプレッドシートIDを、新しいアカウントIDに対応する名前でGitHubリポジトリのSecretsに追加します。

## 📊 スプレッドシートの形式

各アカウントのワークシートは、`config.yml` の `columns` で定義された列を持つ必要があります。
デフォルトの列構成例:
- `投稿日時` (post_datetime): 投稿予定日時 (YYYY-MM-DD HH:MM:SS 形式、JST)。
- `投稿内容` (post_text): ツイート本文。
- `画像・動画URL` (media_url): 投稿するメディアのGoogle Drive共有URL (閲覧可能リンク)。
- `ALTテキスト` (alt_text): 画像の代替テキスト。
- `投稿ステータス` (status): "未処理", "投稿済み", "エラー" など。システムが自動更新。
- `投稿TweetID` (posted_tweet_id): 投稿されたツイートのID。システムが自動更新。
- `最終投稿日時` (last_posted_at): この行のコンテンツが最後に投稿された日時。システムが自動更新。
- `エラーメッセージ` (error_message): 投稿失敗時のエラー内容。システムが自動更新。

**注意点:**
- `投稿日時` はJSTで記述し、システムはこれをUTCとして解釈・処理します。
- Google DriveのメディアURLは、リンクを知っている全員が閲覧可能な共有設定にしてください。

## 📁 ディレクトリ構造 (主要なもの)

\`\`\`
InboundEngine/
├── .github/workflows/         # GitHub Actions ワークフロー定義
│   └── auto-post-bot.yml
├── config/
│   ├── config.template.yml    # 設定ファイルテンプレート
│   └── (credentials.json)     # gspread認証情報ファイル (gitignore対象)
├── engine_core/               # メインロジック
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── post_scheduler.py
│   │   └── scheduled_post_executor.py
│   ├── __init__.py
│   ├── config.py
│   ├── discord_notifier.py
│   ├── spreadsheet_manager.py
│   ├── twitter_client.py
│   └── workflow_manager.py
├── docs/
│   └── system_redesign_plan.md # システム再設計に関するドキュメント
├── logs/                      # ログファイル、スケジュールファイル保存先 (gitignore対象)
├── .gitignore
├── generate_config.py         # config.yml 生成スクリプト
├── main.py                    # メインエントリーポイント
├── README.md                  # このファイル
├── requirements.txt           # Python依存ライブラリ
└── run_manual_test.py         # 手動テスト実行用スクリプト (開発用)
\`\`\`

## 💡 トラブルシューティング・FAQ (今後追記)
- (例) レート制限エラーが頻発する場合の確認点
- (例) 特定のアカウントの投稿がスキップされる場合の確認点

## 📋 定期実行の設定

### crontab設定例（推奨）
```bash
# crontabを編集
crontab -e

# 毎朝8時にスケジュール生成＋Slack通知
0 8 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --generate-schedule >> logs/cron_schedule_generation.log 2>&1

# 毎日9時、13時、17時に投稿実行
0 9,13,17 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --execute-now >> logs/cron_execute_posts.log 2>&1
```

### スケジュール管理の詳細
```bash
# 当日のスケジュール確認
cat schedule.txt

# 実行済み投稿の確認
cat executed.txt

# スケジュールの手動再生成
rm schedule.txt
python schedule_posts.py
```

## 📞 緊急時の連絡先・対応

### 1. Bot停止方法
```bash
# 実行中プロセスの確認
ps aux | grep python

# 強制停止（必要に応じて）
pkill -f "post_tweet"
pkill -f "schedule_posts"
```

### 2. 手動投稿での緊急対応
```bash
# 特定アカウントのみテスト投稿
python -c "
from bots.auto_post_bot.post_tweet import *
# 手動でのテスト実行コード
"

# スケジュールをリセットして再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## ☁️ クラウド運用（推奨）

### 🎯 GitHub Actions（最推奨）

#### **コスト**: 🟢 **完全無料**
- プライベートリポジトリでも月2,000分無料
- 1日4回実行 = 月約240分 → **実質無料**

#### **運用の簡単さ**: 🟢 **最簡単**
- Git push だけで自動デプロイ
- ゼロメンテナンション（サーバー管理不要）
- Web UIでログ確認可能

#### **DevOps**: 🟢 **最も簡単**
- Secrets管理が組み込み
- 手動実行ボタンあり
- 自動スケーリング

### 🚀 GitHub Actions 完全デプロイ手順

#### 1. リポジトリ準備
```bash
# プライベートリポジトリ作成（機密情報があるため）
gh repo create InboundEngine-Bot --private
git remote add origin https://github.com/yourusername/InboundEngine-Bot.git
git push -u origin main
```

#### 2. GitHub Secrets 設定 ⚙️
`Settings > Secrets and variables > Actions` で以下を設定:

**🔑 必須Secrets:**
```
# 共通設定
GOOGLE_SHEETS_KEY: (gspread-key.json の内容をまるごと)
SLACK_WEBHOOK_URL: (Slack Webhook URL)
TWITTER_BEARER_TOKEN: (X API Bearer Token - 共通)

# jadiAngkat アカウント用 (Account1)
ACCOUNT1_CONSUMER_KEY: (jadiAngkat用 Consumer Key)
ACCOUNT1_CONSUMER_SECRET: (jadiAngkat用 Consumer Secret)
ACCOUNT1_ACCESS_TOKEN: (jadiAngkat用 Access Token)
ACCOUNT1_ACCESS_TOKEN_SECRET: (jadiAngkat用 Access Token Secret)
ACCOUNT1_EMAIL: (jadiAngkatのメールアドレス)

# hinataHHHHHH アカウント用 (Account2)
ACCOUNT2_CONSUMER_KEY: (hinataHHHHHH用 Consumer Key)
ACCOUNT2_CONSUMER_SECRET: (hinataHHHHHH用 Consumer Secret)
ACCOUNT2_ACCESS_TOKEN: (hinataHHHHHH用 Access Token)
ACCOUNT2_ACCESS_TOKEN_SECRET: (hinataHHHHHH用 Access Token Secret)
ACCOUNT2_EMAIL: (hinataHHHHHHのメールアドレス)
```

**💡 Secrets設定の簡潔リスト:**
```
GOOGLE_SHEETS_KEY
SLACK_WEBHOOK_URL
TWITTER_BEARER_TOKEN
ACCOUNT1_CONSUMER_KEY
ACCOUNT1_CONSUMER_SECRET
ACCOUNT1_ACCESS_TOKEN
ACCOUNT1_ACCESS_TOKEN_SECRET
ACCOUNT1_EMAIL
ACCOUNT2_CONSUMER_KEY
ACCOUNT2_CONSUMER_SECRET
ACCOUNT2_ACCESS_TOKEN
ACCOUNT2_ACCESS_TOKEN_SECRET
ACCOUNT2_EMAIL
```

#### 3. 自動実行スケジュール 📅
設定済みの実行スケジュール:
- **毎朝8時**: スケジュール生成 + Slack通知
- **毎日10時、14時、18時、21時**: 自動投稿実行
- **Git push時**: 「スクリプトが更新されました。」Slack通知

#### 4. 手動実行オプション 🔧
GitHub Actions画面で「Run workflow」ボタンから:
- `post`: 投稿実行
- `schedule`: 通常スケジュール生成
- `schedule-now`: 現在時刻以降でスケジュール生成

#### 5. Slack通知の詳細 📱

**📢 Git Push通知:**
```
🔄 スクリプトが更新されました。
Repository: user/InboundEngine-Bot
Commit: feat: 新機能追加
Author: user
Branch: main
```

**📅 スケジュール通知（改善版）:**
```
📅 自動投稿スケジュール

• jadiAngkat: 05/30 17:33 (約1時間54分後)
• hinataHHHHHH: 05/30 21:27 (約5時間48分後)

📊 合計2件 | 2アカウント
⏰ 生成時刻: 2025-05-30 15:38:15
```

**🌙 夜間実行時の通知:**
```
🌙 夜間スケジュール生成完了 （営業時間外のため翌日に設定）

• jadiAngkat: 05/31 11:15 (約12時間37分後)
• hinataHHHHHH: 05/31 16:42 (約18時間4分後)

📊 合計2件 | 2アカウント | 本日0件・翌日2件
⏰ 生成時刻: 2025-05-30 23:15:30
```

### 🔧 その他のクラウドオプション

#### **Railway** ($5/月の無料クレジット)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

#### **AWS EC2 t2.micro** (1年間無料)
- より多くの設定が必要
- Linux サーバー管理スキル必要

#### **Google Cloud Run** (月200万リクエスト無料)
- Dockerfile が必要
- GCP の設定が複雑

### ✅ GitHub Actions の利点

- **完全無料** (プライベートリポジトリでも実質無料)
- **ゼロメンテナンス** (サーバー管理不要)
- **自動スケーリング** (必要に応じてリソース調整)
- **ログ管理** (Web UIで確認可能)
- **手動実行** (緊急時にボタン一つで実行)
- **セキュリティ** (Secrets 管理が組み込み)
- **DevOps** (Git push で自動デプロイ)

### 📋 移行手順

#### 1. ローカル → クラウド移行
```bash
# 機密情報をGitHub Secretsに移行
# テスト実行で動作確認
# ローカル cron を停止
# GitHub Actions を有効化
```

#### 2. 段階的移行
1. 最初は手動実行のみでテスト
2. 動作確認後にスケジュール実行を有効化
3. ローカル実行を徐々に停止

**結論: GitHub Actions が最もコスト効率と運用効率のバランスが良く、DevOps も最も簡単です！** 🎉

## 📊 実際の運用ログ例

### 正常実行時のログ
```
2025-05-30 14:59:37,071 - INFO - ===== Auto Post Bot 開始 =====
2025-05-30 14:59:38,817 - INFO - 48 件の投稿ストックを取得しました。
2025-05-30 14:59:38,819 - INFO - [DEBUG] 全8件中、最終投稿日時が最も古い投稿を選択しました
2025-05-30 14:59:44,834 - INFO - ツイート投稿成功。Tweet ID: 1928330467050410158
2025-05-30 14:59:45,161 - INFO - Slack通知を送信しました
2025-05-30 14:59:49,048 - INFO - 投稿ID 3 のステータスを '投稿完了' に更新しました
```

### スケジュール生成時のログ
```
新しいスケジュールを作成しました:
jadiAngkat,2025-05-30 09:15:00
hinataHHHHHH,2025-05-30 14:32:00
jadiAngkat,2025-05-30 18:45:00
Slackにスケジュールを通知しました
```

### エラー発生時のログ例
```
2025-05-30 15:00:00,000 - ERROR - Twitter APIクライアントの初期化に失敗しました
2025-05-30 15:00:00,001 - ERROR - Google Sheetsからのデータ取得中にエラーが発生しました
2025-05-30 15:00:00,002 - ERROR - メディアのダウンロードに失敗しました
```

## ❓ よくある質問（FAQ）

### Q: 投稿が実行されないのですが？
**A**: 以下を確認してください：
1. スプレッドシートに投稿データがあるか
2. API認証情報が正しいか
3. スケジュールが正しく生成されているか（`schedule.txt`を確認）

### Q: 同じ投稿が何度も実行されます
**A**: スプレッドシートの「最終投稿日時」列が正しく更新されていない可能性があります。Google Sheetsの権限とサービスアカウントキーを確認してください。

### Q: 動画投稿でエラーが出ます
**A**: 
1. FFmpegがインストールされているか確認
2. 動画ファイルサイズが512MB以下か確認
3. Google DriveのURLが正しいか確認

### Q: Slack通知が来ません
**A**: `config/config.yml`の`slack`セクションでWebhook URLが正しく設定されているか確認してください。

### Q: スケジュールが生成されません
**A**: 
1. `schedule_posts.py`の設定値を確認
2. アカウント数と投稿回数の設定が適切か確認
3. 営業時間設定（START_HOUR, END_HOUR）を確認

### Q: PC移動後に動作しません
**A**: 
1. インターネット接続を確認
2. 仮想環境が正しく有効化されているか確認
3. `which python`で正しいPythonが使用されているか確認
4. スケジュールファイルが存在するか確認（`ls schedule.txt executed.txt`）

### Q: 投稿順序を変更したい
**A**: スプレッドシートの「最終投稿日時」列を編集することで、投稿順序を制御できます。古い日時のものから優先的に投稿されます。

### Q: 複数アカウントを同時実行したい
**A**: 現在のシステムは各アカウントを順次実行します。完全な同時実行には改修が必要です。

### Q: スケジュールを手動で調整したい
**A**: `schedule.txt`ファイルを直接編集するか、`schedule_posts.py`の設定値を変更してスケジュールを再生成してください。

## 🔗 関連リソース

- **X API Documentation**: https://developer.twitter.com/en/docs
- **Google Sheets API**: https://developers.google.com/sheets/api
- **FFmpeg**: https://ffmpeg.org/
- **ログファイル場所**: `logs/auto_post_logs/app.log`
- **設定ファイル**: `config/config.yml`
- **スケジュールファイル**: `schedule.txt` / `executed.txt`

---
**最終更新**: 2025年1月  
**バージョン**: 2.0.0 

## 🎯 システム概要

X（Twitter）での自動投稿を行うシステムです。Google スプレッドシートから投稿データを取得し、スケジュールに従って自動投稿を実行します。

### 主要機能
- 📊 Google スプレッドシートからの投稿データ取得
- 🤖 X API を使用した自動投稿
- 📅 スケジュール管理システム
- 📹 動画メタデータ変換（FFmpeg）
- 🔀 ランダムスペース挿入（検出回避）
- 📱 Slack 通知
- 🧵 ツリー投稿対応（長文自動分割）

## 🔧 アカウント管理

すべてのアカウント情報は `config/config.yml` で一元管理されます。

### 🔄 新しいアカウント追加手順

#### 1. X Developer Portal での準備
1. [X Developer Portal](https://developer.twitter.com/) にアクセス
2. 新しいアプリケーションを作成
3. API Keys を取得:
   - Consumer Key
   - Consumer Secret  
   - Access Token
   - Access Token Secret

#### 2. config.yml への追加
`config/config.yml` の `twitter_accounts` セクションに追加:

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      email: "メールアドレス"
      username: "ユーザー名"
      password: "パスワード（参考用）"
      consumer_key: "取得したConsumer Key"
      consumer_secret: "取得したConsumer Secret"
      access_token: "取得したAccess Token"
      access_token_secret: "取得したAccess Token Secret"
      google_sheets_source:
        enabled: true
        worksheet_name: "ワークシート名"
```

#### 3. スケジュール設定に追加
`config/config.yml` の `auto_post_bot.twitter_accounts` リストに、アカウントごとの `posts_today` (任意) や `worksheet_name` を設定します。
`schedule_posts.py` の `ACCOUNTS` リストは廃止され、`config.yml` で一元管理されます。

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      # ... (consumer_keyなどのAPI情報)
      google_sheets_source:
        enabled: true
        worksheet_name: "新しいワークシート名"
      posts_today: 2 # このアカウントの1日の投稿数 (省略可)
    # ... 他のアカウント ...
```

#### 4. スプレッドシート準備
Google スプレッドシートに新しいワークシートを作成し、以下の列を設定:
- ID
- 投稿タイプ
- 最終投稿日時
- 文字数
- 本文
- 画像/動画URL
- 投稿可能（チェックボックス）
- 投稿済み回数

## 📊 スプレッドシートへのデータ追加手順

### 1. 基本的な投稿データ形式
| ID | 投稿タイプ | 最終投稿日時 | 文字数 | 本文 | 画像/動画URL | 投稿可能 | 投稿済み回数 |
|----|-----------|-------------|--------|------|-------------|----------|-------------|
| 1  | 通常投稿   | 2025-01-01 10:00:00 | 50 | 投稿内容... | https://drive.google.com/... | ✅ | 0 |

### 2. 重要な注意点
- **ID**: 各行に一意のIDを設定
- **本文**: 文字数制限（280文字以下）を考慮
- **画像/動画URL**: Google Driveの共有URLを使用
- **最終投稿日時**: 古い日時のものから優先的に投稿される
- **投稿可能**: ✅ チェック済みの投稿のみが実行対象（未チェックは除外）
- **投稿アカウント判別**: ワークシート名で自動判別（都内メンエス→jadiAngkat、都内セクキャバ→hinataHHHHHH）

### 3. Google Drive メディアファイルの準備
1. 画像・動画をGoogle Driveにアップロード
2. 「リンクを知っている全員が閲覧可」に設定
3. 共有URLをスプレッドシートに貼り付け

## 📝 新しい投稿を追加する手順

### 1. コンテンツ準備フェーズ
```bash
# メディアファイルの準備（推奨ファイル形式）
# 画像: JPG, PNG (5MB以下)
# 動画: MP4 (512MB以下、2分20秒以下)
```

### 2. Google Drive へのアップロード
1. **フォルダ組織化**:
   - アカウント別フォルダを作成（例：`jadiAngkat_media`）
   - 日付別サブフォルダで整理（例：`2025-01-30`）

2. **アップロード手順**:
   ```
   1. Google Drive にログイン
   2. 対象フォルダを開く
   3. ファイルをドラッグ&ドロップ
   4. アップロード完了を確認
   ```

3. **共有設定**:
   ```
   1. ファイルを右クリック → 「共有」
   2. 「リンクを知っている全員」に変更
   3. 「閲覧者」権限を確認
   4. 「リンクをコピー」をクリック
   ```

### 3. スプレッドシート更新の詳細手順

#### ステップ1: 新しい行の追加
1. Google Sheets で該当のワークシートを開く
2. 最下行の下に新しい行を挿入
3. ID列に連番を入力（既存の最大ID + 1）

#### ステップ2: 基本情報の入力
```
ID: 連番（例：49）
投稿タイプ: 通常投稿
最終投稿日時: 優先度に応じた日時（古い日時 = 高優先度）
文字数: 本文の文字数（自動計算も可）
本文: 投稿内容（280文字以下）
画像/動画URL: Google Driveの共有URL
投稿可能: ✅
投稿済み回数: 0（初期値）
```

#### ステップ3: 本文作成のベストプラクティス
- **文字数確認**: 280文字以下に収める
- **ハッシュタグ**: 適切なハッシュタグを含める
- **改行**: 読みやすさを考慮した改行
- **絵文字**: 適度な絵文字の使用

#### ステップ4: 投稿可能フラグの設定
- **✅ チェック済み**: 投稿対象に含まれる
- **❌ 未チェック**: 投稿から除外される
- **用途例**: 
  - 下書き状態の投稿を一時的に無効化
  - 季節限定投稿の期間外での無効化
  - テスト投稿の本番環境での除外

### 4. 優先度設定による投稿順序制御

#### 高優先度（すぐに投稿したい）
```
最終投稿日時: 2020-01-01 00:00:00
```

#### 通常優先度
```
最終投稿日時: 現在日時の1日前
```

#### 低優先度（後回しにしたい）
```
最終投稿日時: 現在日時
```

### 5. 投稿後の自動更新確認

投稿実行後、以下が自動更新されます：
- **最終投稿日時**: 投稿実行時刻に更新
- **投稿済み回数**: +1 されて更新
- **ステータス**: （設定によって「投稿完了」に更新）

### 6. 品質チェックポイント

#### 投稿前チェックリスト
- [ ] 本文の誤字脱字確認
- [ ] 文字数制限（280文字以下）
- [ ] メディアファイルの表示確認
- [ ] URL の動作確認
- [ ] アカウント名の正確性
- [ ] 優先度設定の妥当性

#### メディアファイルチェック
- [ ] ファイル形式が対応しているか
- [ ] ファイルサイズが制限内か
- [ ] 画質・音質が適切か
- [ ] Google Drive の共有設定が正しいか

### 7. 大量投稿追加時の効率化

#### CSVインポート方法
1. Excel または Google Sheets でデータを準備
2. CSV形式でエクスポート
3. Google Sheets の「ファイル」→「インポート」
4. 既存データに追加する設定で実行

#### 一括メディアアップロード
1. Google Drive デスクトップアプリを使用
2. ローカルフォルダで整理してから同期
3. 一括で共有設定を変更

### 8. トラブル時の対処法

#### スプレッドシート更新が反映されない
```bash
# 権限確認
# Google Sheets の共有設定を確認
# サービスアカウントがエディター権限を持っているか確認

# 手動で同期確認
python -c "
from bots.auto_post_bot.post_tweet import get_posts_from_sheet
posts = get_posts_from_sheet('jadiAngkat')
print(f'取得件数: {len(posts)}')
"
```

#### メディアダウンロードエラー
1. Google Drive URL の形式確認
2. 共有設定の確認
3. ファイルサイズの確認
4. インターネット接続の確認

## ⚠️ エラーパターンと対応方法

### 1. API認証エラー
**症状**: `Twitter APIクライアントの初期化に失敗`
**アラート**: Slack に「❌ 投稿失敗」通知
**対応**:
```bash
# API キーの確認
grep -A 10 "twitter_api:" config/config.yml

# 権限確認（X Developer Portal で確認）
# - Read and write permissions が設定されているか
# - アクセストークンが最新か
```

### 2. スプレッドシート接続エラー
**症状**: `Google Sheetsからのデータ取得中にエラー`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# サービスアカウントキーの確認
ls -la config/gspread-key.json

# スプレッドシート名の確認
grep "sheet_name:" config/config.yml
```

### 3. メディアダウンロードエラー
**症状**: `メディアのダウンロードに失敗`
**アラート**: ログに「画像のダウンロード中にエラー」
**対応**:
- Google Drive URLの共有設定を確認
- インターネット接続状況を確認
- URL形式が正しいか確認

### 4. FFmpeg関連エラー
**症状**: `動画メタデータ変換中にエラー`
**対応**:
```bash
# FFmpegのインストール確認
ffmpeg -version

# macOSの場合、再インストール
brew install ffmpeg
```

### 5. スケジュール生成エラー
**症状**: `10分以上離れた時刻が見つかりませんでした`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# schedule_posts.pyの設定を確認・調整
# MIN_INTERVAL_MINUTES の値を小さくする
# START_HOUR と END_HOUR の範囲を広げる
# POSTS_PER_ACCOUNT の値を小さくする
```

## 💻 PC移動時の注意点

### 1. カフェなど公共Wi-Fi使用時
```bash
# VPN接続の確認（推奨）
# API制限やセキュリティ考慮

# 手動実行でテスト
python -m bots.auto_post_bot.post_tweet

# エラーがないことを確認してから定期実行
```

### 2. 環境の持ち運び手順
```bash
# 1. 仮想環境の有効化確認
source .venv/bin/activate
which python  # プロジェクト内のpythonが使われているか確認

# 2. 依存関係の確認
pip list | grep tweepy
pip list | grep gspread

# 3. 設定ファイルの確認
ls -la config/

# 4. ログディレクトリの確認
ls -la logs/auto_post_logs/

# 5. スケジュールファイルの確認
ls -la schedule.txt executed.txt
```

### 3. トラブルシューティング
```bash
# パスの確認
pwd
ls -la

# Python環境の確認
python --version
pip --version

# 必要に応じて依存関係の再インストール
pip install -r requirements.txt

# スケジュールファイルの再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## 📋 定期実行の設定

### crontab設定例（推奨）
```bash
# crontabを編集
crontab -e

# 毎朝8時にスケジュール生成＋Slack通知
0 8 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --generate-schedule >> logs/cron_schedule_generation.log 2>&1

# 毎日9時、13時、17時に投稿実行
0 9,13,17 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --execute-now >> logs/cron_execute_posts.log 2>&1
```

### スケジュール管理の詳細
```bash
# 当日のスケジュール確認
cat schedule.txt

# 実行済み投稿の確認
cat executed.txt

# スケジュールの手動再生成
rm schedule.txt
python schedule_posts.py
```

## 📞 緊急時の連絡先・対応

### 1. Bot停止方法
```bash
# 実行中プロセスの確認
ps aux | grep python

# 強制停止（必要に応じて）
pkill -f "post_tweet"
pkill -f "schedule_posts"
```

### 2. 手動投稿での緊急対応
```bash
# 特定アカウントのみテスト投稿
python -c "
from bots.auto_post_bot.post_tweet import *
# 手動でのテスト実行コード
"

# スケジュールをリセットして再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## ☁️ クラウド運用（推奨）

### 🎯 GitHub Actions（最推奨）

#### **コスト**: 🟢 **完全無料**
- プライベートリポジトリでも月2,000分無料
- 1日4回実行 = 月約240分 → **実質無料**

#### **運用の簡単さ**: 🟢 **最簡単**
- Git push だけで自動デプロイ
- ゼロメンテナンション（サーバー管理不要）
- Web UIでログ確認可能

#### **DevOps**: 🟢 **最も簡単**
- Secrets管理が組み込み
- 手動実行ボタンあり
- 自動スケーリング

### 🚀 GitHub Actions 完全デプロイ手順

#### 1. リポジトリ準備
```bash
# プライベートリポジトリ作成（機密情報があるため）
gh repo create InboundEngine-Bot --private
git remote add origin https://github.com/yourusername/InboundEngine-Bot.git
git push -u origin main
```

#### 2. GitHub Secrets 設定 ⚙️
`Settings > Secrets and variables > Actions` で以下を設定:

**🔑 必須Secrets:**
```
# 共通設定
GOOGLE_SHEETS_KEY: (gspread-key.json の内容をまるごと)
SLACK_WEBHOOK_URL: (Slack Webhook URL)
TWITTER_BEARER_TOKEN: (X API Bearer Token - 共通)

# jadiAngkat アカウント用 (Account1)
ACCOUNT1_CONSUMER_KEY: (jadiAngkat用 Consumer Key)
ACCOUNT1_CONSUMER_SECRET: (jadiAngkat用 Consumer Secret)
ACCOUNT1_ACCESS_TOKEN: (jadiAngkat用 Access Token)
ACCOUNT1_ACCESS_TOKEN_SECRET: (jadiAngkat用 Access Token Secret)
ACCOUNT1_EMAIL: (jadiAngkatのメールアドレス)

# hinataHHHHHH アカウント用 (Account2)
ACCOUNT2_CONSUMER_KEY: (hinataHHHHHH用 Consumer Key)
ACCOUNT2_CONSUMER_SECRET: (hinataHHHHHH用 Consumer Secret)
ACCOUNT2_ACCESS_TOKEN: (hinataHHHHHH用 Access Token)
ACCOUNT2_ACCESS_TOKEN_SECRET: (hinataHHHHHH用 Access Token Secret)
ACCOUNT2_EMAIL: (hinataHHHHHHのメールアドレス)
```

**💡 Secrets設定の簡潔リスト:**
```
GOOGLE_SHEETS_KEY
SLACK_WEBHOOK_URL
TWITTER_BEARER_TOKEN
ACCOUNT1_CONSUMER_KEY
ACCOUNT1_CONSUMER_SECRET
ACCOUNT1_ACCESS_TOKEN
ACCOUNT1_ACCESS_TOKEN_SECRET
ACCOUNT1_EMAIL
ACCOUNT2_CONSUMER_KEY
ACCOUNT2_CONSUMER_SECRET
ACCOUNT2_ACCESS_TOKEN
ACCOUNT2_ACCESS_TOKEN_SECRET
ACCOUNT2_EMAIL
```

#### 3. 自動実行スケジュール 📅
設定済みの実行スケジュール:
- **毎朝8時**: スケジュール生成 + Slack通知
- **毎日10時、14時、18時、21時**: 自動投稿実行
- **Git push時**: 「スクリプトが更新されました。」Slack通知

#### 4. 手動実行オプション 🔧
GitHub Actions画面で「Run workflow」ボタンから:
- `post`: 投稿実行
- `schedule`: 通常スケジュール生成
- `schedule-now`: 現在時刻以降でスケジュール生成

#### 5. Slack通知の詳細 📱

**📢 Git Push通知:**
```
🔄 スクリプトが更新されました。
Repository: user/InboundEngine-Bot
Commit: feat: 新機能追加
Author: user
Branch: main
```

**📅 スケジュール通知（改善版）:**
```
📅 自動投稿スケジュール

• jadiAngkat: 05/30 17:33 (約1時間54分後)
• hinataHHHHHH: 05/30 21:27 (約5時間48分後)

📊 合計2件 | 2アカウント
⏰ 生成時刻: 2025-05-30 15:38:15
```

**🌙 夜間実行時の通知:**
```
🌙 夜間スケジュール生成完了 （営業時間外のため翌日に設定）

• jadiAngkat: 05/31 11:15 (約12時間37分後)
• hinataHHHHHH: 05/31 16:42 (約18時間4分後)

📊 合計2件 | 2アカウント | 本日0件・翌日2件
⏰ 生成時刻: 2025-05-30 23:15:30
```

### 🔧 その他のクラウドオプション

#### **Railway** ($5/月の無料クレジット)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

#### **AWS EC2 t2.micro** (1年間無料)
- より多くの設定が必要
- Linux サーバー管理スキル必要

#### **Google Cloud Run** (月200万リクエスト無料)
- Dockerfile が必要
- GCP の設定が複雑

### ✅ GitHub Actions の利点

- **完全無料** (プライベートリポジトリでも実質無料)
- **ゼロメンテナンス** (サーバー管理不要)
- **自動スケーリング** (必要に応じてリソース調整)
- **ログ管理** (Web UIで確認可能)
- **手動実行** (緊急時にボタン一つで実行)
- **セキュリティ** (Secrets 管理が組み込み)
- **DevOps** (Git push で自動デプロイ)

### 📋 移行手順

#### 1. ローカル → クラウド移行
```bash
# 機密情報をGitHub Secretsに移行
# テスト実行で動作確認
# ローカル cron を停止
# GitHub Actions を有効化
```

#### 2. 段階的移行
1. 最初は手動実行のみでテスト
2. 動作確認後にスケジュール実行を有効化
3. ローカル実行を徐々に停止

**結論: GitHub Actions が最もコスト効率と運用効率のバランスが良く、DevOps も最も簡単です！** 🎉

## 📊 実際の運用ログ例

### 正常実行時のログ
```
2025-05-30 14:59:37,071 - INFO - ===== Auto Post Bot 開始 =====
2025-05-30 14:59:38,817 - INFO - 48 件の投稿ストックを取得しました。
2025-05-30 14:59:38,819 - INFO - [DEBUG] 全8件中、最終投稿日時が最も古い投稿を選択しました
2025-05-30 14:59:44,834 - INFO - ツイート投稿成功。Tweet ID: 1928330467050410158
2025-05-30 14:59:45,161 - INFO - Slack通知を送信しました
2025-05-30 14:59:49,048 - INFO - 投稿ID 3 のステータスを '投稿完了' に更新しました
```

### スケジュール生成時のログ
```
新しいスケジュールを作成しました:
jadiAngkat,2025-05-30 09:15:00
hinataHHHHHH,2025-05-30 14:32:00
jadiAngkat,2025-05-30 18:45:00
Slackにスケジュールを通知しました
```

### エラー発生時のログ例
```
2025-05-30 15:00:00,000 - ERROR - Twitter APIクライアントの初期化に失敗しました
2025-05-30 15:00:00,001 - ERROR - Google Sheetsからのデータ取得中にエラーが発生しました
2025-05-30 15:00:00,002 - ERROR - メディアのダウンロードに失敗しました
```

## ❓ よくある質問（FAQ）

### Q: 投稿が実行されないのですが？
**A**: 以下を確認してください：
1. スプレッドシートに投稿データがあるか
2. API認証情報が正しいか
3. スケジュールが正しく生成されているか（`schedule.txt`を確認）

### Q: 同じ投稿が何度も実行されます
**A**: スプレッドシートの「最終投稿日時」列が正しく更新されていない可能性があります。Google Sheetsの権限とサービスアカウントキーを確認してください。

### Q: 動画投稿でエラーが出ます
**A**: 
1. FFmpegがインストールされているか確認
2. 動画ファイルサイズが512MB以下か確認
3. Google DriveのURLが正しいか確認

### Q: Slack通知が来ません
**A**: `config/config.yml`の`slack`セクションでWebhook URLが正しく設定されているか確認してください。

### Q: スケジュールが生成されません
**A**: 
1. `schedule_posts.py`の設定値を確認
2. アカウント数と投稿回数の設定が適切か確認
3. 営業時間設定（START_HOUR, END_HOUR）を確認

### Q: PC移動後に動作しません
**A**: 
1. インターネット接続を確認
2. 仮想環境が正しく有効化されているか確認
3. `which python`で正しいPythonが使用されているか確認
4. スケジュールファイルが存在するか確認（`ls schedule.txt executed.txt`）

### Q: 投稿順序を変更したい
**A**: スプレッドシートの「最終投稿日時」列を編集することで、投稿順序を制御できます。古い日時のものから優先的に投稿されます。

### Q: 複数アカウントを同時実行したい
**A**: 現在のシステムは各アカウントを順次実行します。完全な同時実行には改修が必要です。

### Q: スケジュールを手動で調整したい
**A**: `schedule.txt`ファイルを直接編集するか、`schedule_posts.py`の設定値を変更してスケジュールを再生成してください。

## 🔗 関連リソース

- **X API Documentation**: https://developer.twitter.com/en/docs
- **Google Sheets API**: https://developers.google.com/sheets/api
- **FFmpeg**: https://ffmpeg.org/
- **ログファイル場所**: `logs/auto_post_logs/app.log`
- **設定ファイル**: `config/config.yml`
- **スケジュールファイル**: `schedule.txt` / `executed.txt`

---
**最終更新**: 2025年1月  
**バージョン**: 2.0.0 

## 🎯 システム概要

X（Twitter）での自動投稿を行うシステムです。Google スプレッドシートから投稿データを取得し、スケジュールに従って自動投稿を実行します。

### 主要機能
- 📊 Google スプレッドシートからの投稿データ取得
- 🤖 X API を使用した自動投稿
- 📅 スケジュール管理システム
- 📹 動画メタデータ変換（FFmpeg）
- 🔀 ランダムスペース挿入（検出回避）
- 📱 Slack 通知
- 🧵 ツリー投稿対応（長文自動分割）

## 🔧 アカウント管理

すべてのアカウント情報は `config/config.yml` で一元管理されます。

### 🔄 新しいアカウント追加手順

#### 1. X Developer Portal での準備
1. [X Developer Portal](https://developer.twitter.com/) にアクセス
2. 新しいアプリケーションを作成
3. API Keys を取得:
   - Consumer Key
   - Consumer Secret  
   - Access Token
   - Access Token Secret

#### 2. config.yml への追加
`config/config.yml` の `twitter_accounts` セクションに追加:

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      email: "メールアドレス"
      username: "ユーザー名"
      password: "パスワード（参考用）"
      consumer_key: "取得したConsumer Key"
      consumer_secret: "取得したConsumer Secret"
      access_token: "取得したAccess Token"
      access_token_secret: "取得したAccess Token Secret"
      google_sheets_source:
        enabled: true
        worksheet_name: "ワークシート名"
```

#### 3. スケジュール設定に追加
`config/config.yml` の `auto_post_bot.twitter_accounts` リストに、アカウントごとの `posts_today` (任意) や `worksheet_name` を設定します。
`schedule_posts.py` の `ACCOUNTS` リストは廃止され、`config.yml` で一元管理されます。

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      # ... (consumer_keyなどのAPI情報)
      google_sheets_source:
        enabled: true
        worksheet_name: "新しいワークシート名"
      posts_today: 2 # このアカウントの1日の投稿数 (省略可)
    # ... 他のアカウント ...
```

#### 4. スプレッドシート準備
Google スプレッドシートに新しいワークシートを作成し、以下の列を設定:
- ID
- 投稿タイプ
- 最終投稿日時
- 文字数
- 本文
- 画像/動画URL
- 投稿可能（チェックボックス）
- 投稿済み回数

## 📊 スプレッドシートへのデータ追加手順

### 1. 基本的な投稿データ形式
| ID | 投稿タイプ | 最終投稿日時 | 文字数 | 本文 | 画像/動画URL | 投稿可能 | 投稿済み回数 |
|----|-----------|-------------|--------|------|-------------|----------|-------------|
| 1  | 通常投稿   | 2025-01-01 10:00:00 | 50 | 投稿内容... | https://drive.google.com/... | ✅ | 0 |

### 2. 重要な注意点
- **ID**: 各行に一意のIDを設定
- **本文**: 文字数制限（280文字以下）を考慮
- **画像/動画URL**: Google Driveの共有URLを使用
- **最終投稿日時**: 古い日時のものから優先的に投稿される
- **投稿可能**: ✅ チェック済みの投稿のみが実行対象（未チェックは除外）
- **投稿アカウント判別**: ワークシート名で自動判別（都内メンエス→jadiAngkat、都内セクキャバ→hinataHHHHHH）

### 3. Google Drive メディアファイルの準備
1. 画像・動画をGoogle Driveにアップロード
2. 「リンクを知っている全員が閲覧可」に設定
3. 共有URLをスプレッドシートに貼り付け

## 📝 新しい投稿を追加する手順

### 1. コンテンツ準備フェーズ
```bash
# メディアファイルの準備（推奨ファイル形式）
# 画像: JPG, PNG (5MB以下)
# 動画: MP4 (512MB以下、2分20秒以下)
```

### 2. Google Drive へのアップロード
1. **フォルダ組織化**:
   - アカウント別フォルダを作成（例：`jadiAngkat_media`）
   - 日付別サブフォルダで整理（例：`2025-01-30`）

2. **アップロード手順**:
   ```
   1. Google Drive にログイン
   2. 対象フォルダを開く
   3. ファイルをドラッグ&ドロップ
   4. アップロード完了を確認
   ```

3. **共有設定**:
   ```
   1. ファイルを右クリック → 「共有」
   2. 「リンクを知っている全員」に変更
   3. 「閲覧者」権限を確認
   4. 「リンクをコピー」をクリック
   ```

### 3. スプレッドシート更新の詳細手順

#### ステップ1: 新しい行の追加
1. Google Sheets で該当のワークシートを開く
2. 最下行の下に新しい行を挿入
3. ID列に連番を入力（既存の最大ID + 1）

#### ステップ2: 基本情報の入力
```
ID: 連番（例：49）
投稿タイプ: 通常投稿
最終投稿日時: 優先度に応じた日時（古い日時 = 高優先度）
文字数: 本文の文字数（自動計算も可）
本文: 投稿内容（280文字以下）
画像/動画URL: Google Driveの共有URL
投稿可能: ✅
投稿済み回数: 0（初期値）
```

#### ステップ3: 本文作成のベストプラクティス
- **文字数確認**: 280文字以下に収める
- **ハッシュタグ**: 適切なハッシュタグを含める
- **改行**: 読みやすさを考慮した改行
- **絵文字**: 適度な絵文字の使用

#### ステップ4: 投稿可能フラグの設定
- **✅ チェック済み**: 投稿対象に含まれる
- **❌ 未チェック**: 投稿から除外される
- **用途例**: 
  - 下書き状態の投稿を一時的に無効化
  - 季節限定投稿の期間外での無効化
  - テスト投稿の本番環境での除外

### 4. 優先度設定による投稿順序制御

#### 高優先度（すぐに投稿したい）
```
最終投稿日時: 2020-01-01 00:00:00
```

#### 通常優先度
```
最終投稿日時: 現在日時の1日前
```

#### 低優先度（後回しにしたい）
```
最終投稿日時: 現在日時
```

### 5. 投稿後の自動更新確認

投稿実行後、以下が自動更新されます：
- **最終投稿日時**: 投稿実行時刻に更新
- **投稿済み回数**: +1 されて更新
- **ステータス**: （設定によって「投稿完了」に更新）

### 6. 品質チェックポイント

#### 投稿前チェックリスト
- [ ] 本文の誤字脱字確認
- [ ] 文字数制限（280文字以下）
- [ ] メディアファイルの表示確認
- [ ] URL の動作確認
- [ ] アカウント名の正確性
- [ ] 優先度設定の妥当性

#### メディアファイルチェック
- [ ] ファイル形式が対応しているか
- [ ] ファイルサイズが制限内か
- [ ] 画質・音質が適切か
- [ ] Google Drive の共有設定が正しいか

### 7. 大量投稿追加時の効率化

#### CSVインポート方法
1. Excel または Google Sheets でデータを準備
2. CSV形式でエクスポート
3. Google Sheets の「ファイル」→「インポート」
4. 既存データに追加する設定で実行

#### 一括メディアアップロード
1. Google Drive デスクトップアプリを使用
2. ローカルフォルダで整理してから同期
3. 一括で共有設定を変更

### 8. トラブル時の対処法

#### スプレッドシート更新が反映されない
```bash
# 権限確認
# Google Sheets の共有設定を確認
# サービスアカウントがエディター権限を持っているか確認

# 手動で同期確認
python -c "
from bots.auto_post_bot.post_tweet import get_posts_from_sheet
posts = get_posts_from_sheet('jadiAngkat')
print(f'取得件数: {len(posts)}')
"
```

#### メディアダウンロードエラー
1. Google Drive URL の形式確認
2. 共有設定の確認
3. ファイルサイズの確認
4. インターネット接続の確認

## ⚠️ エラーパターンと対応方法

### 1. API認証エラー
**症状**: `Twitter APIクライアントの初期化に失敗`
**アラート**: Slack に「❌ 投稿失敗」通知
**対応**:
```bash
# API キーの確認
grep -A 10 "twitter_api:" config/config.yml

# 権限確認（X Developer Portal で確認）
# - Read and write permissions が設定されているか
# - アクセストークンが最新か
```

### 2. スプレッドシート接続エラー
**症状**: `Google Sheetsからのデータ取得中にエラー`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# サービスアカウントキーの確認
ls -la config/gspread-key.json

# スプレッドシート名の確認
grep "sheet_name:" config/config.yml
```

### 3. メディアダウンロードエラー
**症状**: `メディアのダウンロードに失敗`
**アラート**: ログに「画像のダウンロード中にエラー」
**対応**:
- Google Drive URLの共有設定を確認
- インターネット接続状況を確認
- URL形式が正しいか確認

### 4. FFmpeg関連エラー
**症状**: `動画メタデータ変換中にエラー`
**対応**:
```bash
# FFmpegのインストール確認
ffmpeg -version

# macOSの場合、再インストール
brew install ffmpeg
```

### 5. スケジュール生成エラー
**症状**: `10分以上離れた時刻が見つかりませんでした`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# schedule_posts.pyの設定を確認・調整
# MIN_INTERVAL_MINUTES の値を小さくする
# START_HOUR と END_HOUR の範囲を広げる
# POSTS_PER_ACCOUNT の値を小さくする
```

## 💻 PC移動時の注意点

### 1. カフェなど公共Wi-Fi使用時
```bash
# VPN接続の確認（推奨）
# API制限やセキュリティ考慮

# 手動実行でテスト
python -m bots.auto_post_bot.post_tweet

# エラーがないことを確認してから定期実行
```

### 2. 環境の持ち運び手順
```bash
# 1. 仮想環境の有効化確認
source .venv/bin/activate
which python  # プロジェクト内のpythonが使われているか確認

# 2. 依存関係の確認
pip list | grep tweepy
pip list | grep gspread

# 3. 設定ファイルの確認
ls -la config/

# 4. ログディレクトリの確認
ls -la logs/auto_post_logs/

# 5. スケジュールファイルの確認
ls -la schedule.txt executed.txt
```

### 3. トラブルシューティング
```bash
# パスの確認
pwd
ls -la

# Python環境の確認
python --version
pip --version

# 必要に応じて依存関係の再インストール
pip install -r requirements.txt

# スケジュールファイルの再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## 📋 定期実行の設定

### crontab設定例（推奨）
```bash
# crontabを編集
crontab -e

# 毎朝8時にスケジュール生成＋Slack通知
0 8 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --generate-schedule >> logs/cron_schedule_generation.log 2>&1

# 毎日9時、13時、17時に投稿実行
0 9,13,17 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --execute-now >> logs/cron_execute_posts.log 2>&1
```

### スケジュール管理の詳細
```bash
# 当日のスケジュール確認
cat schedule.txt

# 実行済み投稿の確認
cat executed.txt

# スケジュールの手動再生成
rm schedule.txt
python schedule_posts.py
```

## 📞 緊急時の連絡先・対応

### 1. Bot停止方法
```bash
# 実行中プロセスの確認
ps aux | grep python

# 強制停止（必要に応じて）
pkill -f "post_tweet"
pkill -f "schedule_posts"
```

### 2. 手動投稿での緊急対応
```bash
# 特定アカウントのみテスト投稿
python -c "
from bots.auto_post_bot.post_tweet import *
# 手動でのテスト実行コード
"

# スケジュールをリセットして再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## ☁️ クラウド運用（推奨）

### 🎯 GitHub Actions（最推奨）

#### **コスト**: 🟢 **完全無料**
- プライベートリポジトリでも月2,000分無料
- 1日4回実行 = 月約240分 → **実質無料**

#### **運用の簡単さ**: 🟢 **最簡単**
- Git push だけで自動デプロイ
- ゼロメンテナンション（サーバー管理不要）
- Web UIでログ確認可能

#### **DevOps**: 🟢 **最も簡単**
- Secrets管理が組み込み
- 手動実行ボタンあり
- 自動スケーリング

### 🚀 GitHub Actions 完全デプロイ手順

#### 1. リポジトリ準備
```bash
# プライベートリポジトリ作成（機密情報があるため）
gh repo create InboundEngine-Bot --private
git remote add origin https://github.com/yourusername/InboundEngine-Bot.git
git push -u origin main
```

#### 2. GitHub Secrets 設定 ⚙️
`Settings > Secrets and variables > Actions` で以下を設定:

**🔑 必須Secrets:**
```
# 共通設定
GOOGLE_SHEETS_KEY: (gspread-key.json の内容をまるごと)
SLACK_WEBHOOK_URL: (Slack Webhook URL)
TWITTER_BEARER_TOKEN: (X API Bearer Token - 共通)

# jadiAngkat アカウント用 (Account1)
ACCOUNT1_CONSUMER_KEY: (jadiAngkat用 Consumer Key)
ACCOUNT1_CONSUMER_SECRET: (jadiAngkat用 Consumer Secret)
ACCOUNT1_ACCESS_TOKEN: (jadiAngkat用 Access Token)
ACCOUNT1_ACCESS_TOKEN_SECRET: (jadiAngkat用 Access Token Secret)
ACCOUNT1_EMAIL: (jadiAngkatのメールアドレス)

# hinataHHHHHH アカウント用 (Account2)
ACCOUNT2_CONSUMER_KEY: (hinataHHHHHH用 Consumer Key)
ACCOUNT2_CONSUMER_SECRET: (hinataHHHHHH用 Consumer Secret)
ACCOUNT2_ACCESS_TOKEN: (hinataHHHHHH用 Access Token)
ACCOUNT2_ACCESS_TOKEN_SECRET: (hinataHHHHHH用 Access Token Secret)
ACCOUNT2_EMAIL: (hinataHHHHHHのメールアドレス)
```

**💡 Secrets設定の簡潔リスト:**
```
GOOGLE_SHEETS_KEY
SLACK_WEBHOOK_URL
TWITTER_BEARER_TOKEN
ACCOUNT1_CONSUMER_KEY
ACCOUNT1_CONSUMER_SECRET
ACCOUNT1_ACCESS_TOKEN
ACCOUNT1_ACCESS_TOKEN_SECRET
ACCOUNT1_EMAIL
ACCOUNT2_CONSUMER_KEY
ACCOUNT2_CONSUMER_SECRET
ACCOUNT2_ACCESS_TOKEN
ACCOUNT2_ACCESS_TOKEN_SECRET
ACCOUNT2_EMAIL
```

#### 3. 自動実行スケジュール 📅
設定済みの実行スケジュール:
- **毎朝8時**: スケジュール生成 + Slack通知
- **毎日10時、14時、18時、21時**: 自動投稿実行
- **Git push時**: 「スクリプトが更新されました。」Slack通知

#### 4. 手動実行オプション 🔧
GitHub Actions画面で「Run workflow」ボタンから:
- `post`: 投稿実行
- `schedule`: 通常スケジュール生成
- `schedule-now`: 現在時刻以降でスケジュール生成

#### 5. Slack通知の詳細 📱

**📢 Git Push通知:**
```
🔄 スクリプトが更新されました。
Repository: user/InboundEngine-Bot
Commit: feat: 新機能追加
Author: user
Branch: main
```

**📅 スケジュール通知（改善版）:**
```
📅 自動投稿スケジュール

• jadiAngkat: 05/30 17:33 (約1時間54分後)
• hinataHHHHHH: 05/30 21:27 (約5時間48分後)

📊 合計2件 | 2アカウント
⏰ 生成時刻: 2025-05-30 15:38:15
```

**🌙 夜間実行時の通知:**
```
🌙 夜間スケジュール生成完了 （営業時間外のため翌日に設定）

• jadiAngkat: 05/31 11:15 (約12時間37分後)
• hinataHHHHHH: 05/31 16:42 (約18時間4分後)

📊 合計2件 | 2アカウント | 本日0件・翌日2件
⏰ 生成時刻: 2025-05-30 23:15:30
```

### 🔧 その他のクラウドオプション

#### **Railway** ($5/月の無料クレジット)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

#### **AWS EC2 t2.micro** (1年間無料)
- より多くの設定が必要
- Linux サーバー管理スキル必要

#### **Google Cloud Run** (月200万リクエスト無料)
- Dockerfile が必要
- GCP の設定が複雑

### ✅ GitHub Actions の利点

- **完全無料** (プライベートリポジトリでも実質無料)
- **ゼロメンテナンス** (サーバー管理不要)
- **自動スケーリング** (必要に応じてリソース調整)
- **ログ管理** (Web UIで確認可能)
- **手動実行** (緊急時にボタン一つで実行)
- **セキュリティ** (Secrets 管理が組み込み)
- **DevOps** (Git push で自動デプロイ)

### 📋 移行手順

#### 1. ローカル → クラウド移行
```bash
# 機密情報をGitHub Secretsに移行
# テスト実行で動作確認
# ローカル cron を停止
# GitHub Actions を有効化
```

#### 2. 段階的移行
1. 最初は手動実行のみでテスト
2. 動作確認後にスケジュール実行を有効化
3. ローカル実行を徐々に停止

**結論: GitHub Actions が最もコスト効率と運用効率のバランスが良く、DevOps も最も簡単です！** 🎉

## 📊 実際の運用ログ例

### 正常実行時のログ
```
2025-05-30 14:59:37,071 - INFO - ===== Auto Post Bot 開始 =====
2025-05-30 14:59:38,817 - INFO - 48 件の投稿ストックを取得しました。
2025-05-30 14:59:38,819 - INFO - [DEBUG] 全8件中、最終投稿日時が最も古い投稿を選択しました
2025-05-30 14:59:44,834 - INFO - ツイート投稿成功。Tweet ID: 1928330467050410158
2025-05-30 14:59:45,161 - INFO - Slack通知を送信しました
2025-05-30 14:59:49,048 - INFO - 投稿ID 3 のステータスを '投稿完了' に更新しました
```

### スケジュール生成時のログ
```
新しいスケジュールを作成しました:
jadiAngkat,2025-05-30 09:15:00
hinataHHHHHH,2025-05-30 14:32:00
jadiAngkat,2025-05-30 18:45:00
Slackにスケジュールを通知しました
```

### エラー発生時のログ例
```
2025-05-30 15:00:00,000 - ERROR - Twitter APIクライアントの初期化に失敗しました
2025-05-30 15:00:00,001 - ERROR - Google Sheetsからのデータ取得中にエラーが発生しました
2025-05-30 15:00:00,002 - ERROR - メディアのダウンロードに失敗しました
```

## ❓ よくある質問（FAQ）

### Q: 投稿が実行されないのですが？
**A**: 以下を確認してください：
1. スプレッドシートに投稿データがあるか
2. API認証情報が正しいか
3. スケジュールが正しく生成されているか（`schedule.txt`を確認）

### Q: 同じ投稿が何度も実行されます
**A**: スプレッドシートの「最終投稿日時」列が正しく更新されていない可能性があります。Google Sheetsの権限とサービスアカウントキーを確認してください。

### Q: 動画投稿でエラーが出ます
**A**: 
1. FFmpegがインストールされているか確認
2. 動画ファイルサイズが512MB以下か確認
3. Google DriveのURLが正しいか確認

### Q: Slack通知が来ません
**A**: `config/config.yml`の`slack`セクションでWebhook URLが正しく設定されているか確認してください。

### Q: スケジュールが生成されません
**A**: 
1. `schedule_posts.py`の設定値を確認
2. アカウント数と投稿回数の設定が適切か確認
3. 営業時間設定（START_HOUR, END_HOUR）を確認

### Q: PC移動後に動作しません
**A**: 
1. インターネット接続を確認
2. 仮想環境が正しく有効化されているか確認
3. `which python`で正しいPythonが使用されているか確認
4. スケジュールファイルが存在するか確認（`ls schedule.txt executed.txt`）

### Q: 投稿順序を変更したい
**A**: スプレッドシートの「最終投稿日時」列を編集することで、投稿順序を制御できます。古い日時のものから優先的に投稿されます。

### Q: 複数アカウントを同時実行したい
**A**: 現在のシステムは各アカウントを順次実行します。完全な同時実行には改修が必要です。

### Q: スケジュールを手動で調整したい
**A**: `schedule.txt`ファイルを直接編集するか、`schedule_posts.py`の設定値を変更してスケジュールを再生成してください。

## 🔗 関連リソース

- **X API Documentation**: https://developer.twitter.com/en/docs
- **Google Sheets API**: https://developers.google.com/sheets/api
- **FFmpeg**: https://ffmpeg.org/
- **ログファイル場所**: `logs/auto_post_logs/app.log`
- **設定ファイル**: `config/config.yml`
- **スケジュールファイル**: `schedule.txt` / `executed.txt`

---
**最終更新**: 2025年1月  
**バージョン**: 2.0.0 

## 🎯 システム概要

X（Twitter）での自動投稿を行うシステムです。Google スプレッドシートから投稿データを取得し、スケジュールに従って自動投稿を実行します。

### 主要機能
- 📊 Google スプレッドシートからの投稿データ取得
- 🤖 X API を使用した自動投稿
- 📅 スケジュール管理システム
- 📹 動画メタデータ変換（FFmpeg）
- 🔀 ランダムスペース挿入（検出回避）
- 📱 Slack 通知
- 🧵 ツリー投稿対応（長文自動分割）

## 🔧 アカウント管理

すべてのアカウント情報は `config/config.yml` で一元管理されます。

### 🔄 新しいアカウント追加手順

#### 1. X Developer Portal での準備
1. [X Developer Portal](https://developer.twitter.com/) にアクセス
2. 新しいアプリケーションを作成
3. API Keys を取得:
   - Consumer Key
   - Consumer Secret  
   - Access Token
   - Access Token Secret

#### 2. config.yml への追加
`config/config.yml` の `twitter_accounts` セクションに追加:

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      email: "メールアドレス"
      username: "ユーザー名"
      password: "パスワード（参考用）"
      consumer_key: "取得したConsumer Key"
      consumer_secret: "取得したConsumer Secret"
      access_token: "取得したAccess Token"
      access_token_secret: "取得したAccess Token Secret"
      google_sheets_source:
        enabled: true
        worksheet_name: "ワークシート名"
```

#### 3. スケジュール設定に追加
`config/config.yml` の `auto_post_bot.twitter_accounts` リストに、アカウントごとの `posts_today` (任意) や `worksheet_name` を設定します。
`schedule_posts.py` の `ACCOUNTS` リストは廃止され、`config.yml` で一元管理されます。

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      # ... (consumer_keyなどのAPI情報)
      google_sheets_source:
        enabled: true
        worksheet_name: "新しいワークシート名"
      posts_today: 2 # このアカウントの1日の投稿数 (省略可)
    # ... 他のアカウント ...
```

#### 4. スプレッドシート準備
Google スプレッドシートに新しいワークシートを作成し、以下の列を設定:
- ID
- 投稿タイプ
- 最終投稿日時
- 文字数
- 本文
- 画像/動画URL
- 投稿可能（チェックボックス）
- 投稿済み回数

## 📊 スプレッドシートへのデータ追加手順

### 1. 基本的な投稿データ形式
| ID | 投稿タイプ | 最終投稿日時 | 文字数 | 本文 | 画像/動画URL | 投稿可能 | 投稿済み回数 |
|----|-----------|-------------|--------|------|-------------|----------|-------------|
| 1  | 通常投稿   | 2025-01-01 10:00:00 | 50 | 投稿内容... | https://drive.google.com/... | ✅ | 0 |

### 2. 重要な注意点
- **ID**: 各行に一意のIDを設定
- **本文**: 文字数制限（280文字以下）を考慮
- **画像/動画URL**: Google Driveの共有URLを使用
- **最終投稿日時**: 古い日時のものから優先的に投稿される
- **投稿可能**: ✅ チェック済みの投稿のみが実行対象（未チェックは除外）
- **投稿アカウント判別**: ワークシート名で自動判別（都内メンエス→jadiAngkat、都内セクキャバ→hinataHHHHHH）

### 3. Google Drive メディアファイルの準備
1. 画像・動画をGoogle Driveにアップロード
2. 「リンクを知っている全員が閲覧可」に設定
3. 共有URLをスプレッドシートに貼り付け

## 📝 新しい投稿を追加する手順

### 1. コンテンツ準備フェーズ
```bash
# メディアファイルの準備（推奨ファイル形式）
# 画像: JPG, PNG (5MB以下)
# 動画: MP4 (512MB以下、2分20秒以下)
```

### 2. Google Drive へのアップロード
1. **フォルダ組織化**:
   - アカウント別フォルダを作成（例：`jadiAngkat_media`）
   - 日付別サブフォルダで整理（例：`2025-01-30`）

2. **アップロード手順**:
   ```
   1. Google Drive にログイン
   2. 対象フォルダを開く
   3. ファイルをドラッグ&ドロップ
   4. アップロード完了を確認
   ```

3. **共有設定**:
   ```
   1. ファイルを右クリック → 「共有」
   2. 「リンクを知っている全員」に変更
   3. 「閲覧者」権限を確認
   4. 「リンクをコピー」をクリック
   ```

### 3. スプレッドシート更新の詳細手順

#### ステップ1: 新しい行の追加
1. Google Sheets で該当のワークシートを開く
2. 最下行の下に新しい行を挿入
3. ID列に連番を入力（既存の最大ID + 1）

#### ステップ2: 基本情報の入力
```
ID: 連番（例：49）
投稿タイプ: 通常投稿
最終投稿日時: 優先度に応じた日時（古い日時 = 高優先度）
文字数: 本文の文字数（自動計算も可）
本文: 投稿内容（280文字以下）
画像/動画URL: Google Driveの共有URL
投稿可能: ✅
投稿済み回数: 0（初期値）
```

#### ステップ3: 本文作成のベストプラクティス
- **文字数確認**: 280文字以下に収める
- **ハッシュタグ**: 適切なハッシュタグを含める
- **改行**: 読みやすさを考慮した改行
- **絵文字**: 適度な絵文字の使用

#### ステップ4: 投稿可能フラグの設定
- **✅ チェック済み**: 投稿対象に含まれる
- **❌ 未チェック**: 投稿から除外される
- **用途例**: 
  - 下書き状態の投稿を一時的に無効化
  - 季節限定投稿の期間外での無効化
  - テスト投稿の本番環境での除外

### 4. 優先度設定による投稿順序制御

#### 高優先度（すぐに投稿したい）
```
最終投稿日時: 2020-01-01 00:00:00
```

#### 通常優先度
```
最終投稿日時: 現在日時の1日前
```

#### 低優先度（後回しにしたい）
```
最終投稿日時: 現在日時
```

### 5. 投稿後の自動更新確認

投稿実行後、以下が自動更新されます：
- **最終投稿日時**: 投稿実行時刻に更新
- **投稿済み回数**: +1 されて更新
- **ステータス**: （設定によって「投稿完了」に更新）

### 6. 品質チェックポイント

#### 投稿前チェックリスト
- [ ] 本文の誤字脱字確認
- [ ] 文字数制限（280文字以下）
- [ ] メディアファイルの表示確認
- [ ] URL の動作確認
- [ ] アカウント名の正確性
- [ ] 優先度設定の妥当性

#### メディアファイルチェック
- [ ] ファイル形式が対応しているか
- [ ] ファイルサイズが制限内か
- [ ] 画質・音質が適切か
- [ ] Google Drive の共有設定が正しいか

### 7. 大量投稿追加時の効率化

#### CSVインポート方法
1. Excel または Google Sheets でデータを準備
2. CSV形式でエクスポート
3. Google Sheets の「ファイル」→「インポート」
4. 既存データに追加する設定で実行

#### 一括メディアアップロード
1. Google Drive デスクトップアプリを使用
2. ローカルフォルダで整理してから同期
3. 一括で共有設定を変更

### 8. トラブル時の対処法

#### スプレッドシート更新が反映されない
```bash
# 権限確認
# Google Sheets の共有設定を確認
# サービスアカウントがエディター権限を持っているか確認

# 手動で同期確認
python -c "
from bots.auto_post_bot.post_tweet import get_posts_from_sheet
posts = get_posts_from_sheet('jadiAngkat')
print(f'取得件数: {len(posts)}')
"
```

#### メディアダウンロードエラー
1. Google Drive URL の形式確認
2. 共有設定の確認
3. ファイルサイズの確認
4. インターネット接続の確認

## ⚠️ エラーパターンと対応方法

### 1. API認証エラー
**症状**: `Twitter APIクライアントの初期化に失敗`
**アラート**: Slack に「❌ 投稿失敗」通知
**対応**:
```bash
# API キーの確認
grep -A 10 "twitter_api:" config/config.yml

# 権限確認（X Developer Portal で確認）
# - Read and write permissions が設定されているか
# - アクセストークンが最新か
```

### 2. スプレッドシート接続エラー
**症状**: `Google Sheetsからのデータ取得中にエラー`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# サービスアカウントキーの確認
ls -la config/gspread-key.json

# スプレッドシート名の確認
grep "sheet_name:" config/config.yml
```

### 3. メディアダウンロードエラー
**症状**: `メディアのダウンロードに失敗`
**アラート**: ログに「画像のダウンロード中にエラー」
**対応**:
- Google Drive URLの共有設定を確認
- インターネット接続状況を確認
- URL形式が正しいか確認

### 4. FFmpeg関連エラー
**症状**: `動画メタデータ変換中にエラー`
**対応**:
```bash
# FFmpegのインストール確認
ffmpeg -version

# macOSの場合、再インストール
brew install ffmpeg
```

### 5. スケジュール生成エラー
**症状**: `10分以上離れた時刻が見つかりませんでした`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# schedule_posts.pyの設定を確認・調整
# MIN_INTERVAL_MINUTES の値を小さくする
# START_HOUR と END_HOUR の範囲を広げる
# POSTS_PER_ACCOUNT の値を小さくする
```

## 💻 PC移動時の注意点

### 1. カフェなど公共Wi-Fi使用時
```bash
# VPN接続の確認（推奨）
# API制限やセキュリティ考慮

# 手動実行でテスト
python -m bots.auto_post_bot.post_tweet

# エラーがないことを確認してから定期実行
```

### 2. 環境の持ち運び手順
```bash
# 1. 仮想環境の有効化確認
source .venv/bin/activate
which python  # プロジェクト内のpythonが使われているか確認

# 2. 依存関係の確認
pip list | grep tweepy
pip list | grep gspread

# 3. 設定ファイルの確認
ls -la config/

# 4. ログディレクトリの確認
ls -la logs/auto_post_logs/

# 5. スケジュールファイルの確認
ls -la schedule.txt executed.txt
```

### 3. トラブルシューティング
```bash
# パスの確認
pwd
ls -la

# Python環境の確認
python --version
pip --version

# 必要に応じて依存関係の再インストール
pip install -r requirements.txt

# スケジュールファイルの再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## 📋 定期実行の設定

### crontab設定例（推奨）
```bash
# crontabを編集
crontab -e

# 毎朝8時にスケジュール生成＋Slack通知
0 8 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --generate-schedule >> logs/cron_schedule_generation.log 2>&1

# 毎日9時、13時、17時に投稿実行
0 9,13,17 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --execute-now >> logs/cron_execute_posts.log 2>&1
```

### スケジュール管理の詳細
```bash
# 当日のスケジュール確認
cat schedule.txt

# 実行済み投稿の確認
cat executed.txt

# スケジュールの手動再生成
rm schedule.txt
python schedule_posts.py
```

## 📞 緊急時の連絡先・対応

### 1. Bot停止方法
```bash
# 実行中プロセスの確認
ps aux | grep python

# 強制停止（必要に応じて）
pkill -f "post_tweet"
pkill -f "schedule_posts"
```

### 2. 手動投稿での緊急対応
```bash
# 特定アカウントのみテスト投稿
python -c "
from bots.auto_post_bot.post_tweet import *
# 手動でのテスト実行コード
"

# スケジュールをリセットして再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## ☁️ クラウド運用（推奨）

### 🎯 GitHub Actions（最推奨）

#### **コスト**: 🟢 **完全無料**
- プライベートリポジトリでも月2,000分無料
- 1日4回実行 = 月約240分 → **実質無料**

#### **運用の簡単さ**: 🟢 **最簡単**
- Git push だけで自動デプロイ
- ゼロメンテナンション（サーバー管理不要）
- Web UIでログ確認可能

#### **DevOps**: 🟢 **最も簡単**
- Secrets管理が組み込み
- 手動実行ボタンあり
- 自動スケーリング

### 🚀 GitHub Actions 完全デプロイ手順

#### 1. リポジトリ準備
```bash
# プライベートリポジトリ作成（機密情報があるため）
gh repo create InboundEngine-Bot --private
git remote add origin https://github.com/yourusername/InboundEngine-Bot.git
git push -u origin main
```

#### 2. GitHub Secrets 設定 ⚙️
`Settings > Secrets and variables > Actions` で以下を設定:

**🔑 必須Secrets:**
```
# 共通設定
GOOGLE_SHEETS_KEY: (gspread-key.json の内容をまるごと)
SLACK_WEBHOOK_URL: (Slack Webhook URL)
TWITTER_BEARER_TOKEN: (X API Bearer Token - 共通)

# jadiAngkat アカウント用 (Account1)
ACCOUNT1_CONSUMER_KEY: (jadiAngkat用 Consumer Key)
ACCOUNT1_CONSUMER_SECRET: (jadiAngkat用 Consumer Secret)
ACCOUNT1_ACCESS_TOKEN: (jadiAngkat用 Access Token)
ACCOUNT1_ACCESS_TOKEN_SECRET: (jadiAngkat用 Access Token Secret)
ACCOUNT1_EMAIL: (jadiAngkatのメールアドレス)

# hinataHHHHHH アカウント用 (Account2)
ACCOUNT2_CONSUMER_KEY: (hinataHHHHHH用 Consumer Key)
ACCOUNT2_CONSUMER_SECRET: (hinataHHHHHH用 Consumer Secret)
ACCOUNT2_ACCESS_TOKEN: (hinataHHHHHH用 Access Token)
ACCOUNT2_ACCESS_TOKEN_SECRET: (hinataHHHHHH用 Access Token Secret)
ACCOUNT2_EMAIL: (hinataHHHHHHのメールアドレス)
```

**💡 Secrets設定の簡潔リスト:**
```
GOOGLE_SHEETS_KEY
SLACK_WEBHOOK_URL
TWITTER_BEARER_TOKEN
ACCOUNT1_CONSUMER_KEY
ACCOUNT1_CONSUMER_SECRET
ACCOUNT1_ACCESS_TOKEN
ACCOUNT1_ACCESS_TOKEN_SECRET
ACCOUNT1_EMAIL
ACCOUNT2_CONSUMER_KEY
ACCOUNT2_CONSUMER_SECRET
ACCOUNT2_ACCESS_TOKEN
ACCOUNT2_ACCESS_TOKEN_SECRET
ACCOUNT2_EMAIL
```

#### 3. 自動実行スケジュール 📅
設定済みの実行スケジュール:
- **毎朝8時**: スケジュール生成 + Slack通知
- **毎日10時、14時、18時、21時**: 自動投稿実行
- **Git push時**: 「スクリプトが更新されました。」Slack通知

#### 4. 手動実行オプション 🔧
GitHub Actions画面で「Run workflow」ボタンから:
- `post`: 投稿実行
- `schedule`: 通常スケジュール生成
- `schedule-now`: 現在時刻以降でスケジュール生成

#### 5. Slack通知の詳細 📱

**📢 Git Push通知:**
```
🔄 スクリプトが更新されました。
Repository: user/InboundEngine-Bot
Commit: feat: 新機能追加
Author: user
Branch: main
```

**📅 スケジュール通知（改善版）:**
```
📅 自動投稿スケジュール

• jadiAngkat: 05/30 17:33 (約1時間54分後)
• hinataHHHHHH: 05/30 21:27 (約5時間48分後)

📊 合計2件 | 2アカウント
⏰ 生成時刻: 2025-05-30 15:38:15
```

**🌙 夜間実行時の通知:**
```
🌙 夜間スケジュール生成完了 （営業時間外のため翌日に設定）

• jadiAngkat: 05/31 11:15 (約12時間37分後)
• hinataHHHHHH: 05/31 16:42 (約18時間4分後)

📊 合計2件 | 2アカウント | 本日0件・翌日2件
⏰ 生成時刻: 2025-05-30 23:15:30
```

### 🔧 その他のクラウドオプション

#### **Railway** ($5/月の無料クレジット)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

#### **AWS EC2 t2.micro** (1年間無料)
- より多くの設定が必要
- Linux サーバー管理スキル必要

#### **Google Cloud Run** (月200万リクエスト無料)
- Dockerfile が必要
- GCP の設定が複雑

### ✅ GitHub Actions の利点

- **完全無料** (プライベートリポジトリでも実質無料)
- **ゼロメンテナンス** (サーバー管理不要)
- **自動スケーリング** (必要に応じてリソース調整)
- **ログ管理** (Web UIで確認可能)
- **手動実行** (緊急時にボタン一つで実行)
- **セキュリティ** (Secrets 管理が組み込み)
- **DevOps** (Git push で自動デプロイ)

### 📋 移行手順

#### 1. ローカル → クラウド移行
```bash
# 機密情報をGitHub Secretsに移行
# テスト実行で動作確認
# ローカル cron を停止
# GitHub Actions を有効化
```

#### 2. 段階的移行
1. 最初は手動実行のみでテスト
2. 動作確認後にスケジュール実行を有効化
3. ローカル実行を徐々に停止

**結論: GitHub Actions が最もコスト効率と運用効率のバランスが良く、DevOps も最も簡単です！** 🎉

## 📊 実際の運用ログ例

### 正常実行時のログ
```
2025-05-30 14:59:37,071 - INFO - ===== Auto Post Bot 開始 =====
2025-05-30 14:59:38,817 - INFO - 48 件の投稿ストックを取得しました。
2025-05-30 14:59:38,819 - INFO - [DEBUG] 全8件中、最終投稿日時が最も古い投稿を選択しました
2025-05-30 14:59:44,834 - INFO - ツイート投稿成功。Tweet ID: 1928330467050410158
2025-05-30 14:59:45,161 - INFO - Slack通知を送信しました
2025-05-30 14:59:49,048 - INFO - 投稿ID 3 のステータスを '投稿完了' に更新しました
```

### スケジュール生成時のログ
```
新しいスケジュールを作成しました:
jadiAngkat,2025-05-30 09:15:00
hinataHHHHHH,2025-05-30 14:32:00
jadiAngkat,2025-05-30 18:45:00
Slackにスケジュールを通知しました
```

### エラー発生時のログ例
```
2025-05-30 15:00:00,000 - ERROR - Twitter APIクライアントの初期化に失敗しました
2025-05-30 15:00:00,001 - ERROR - Google Sheetsからのデータ取得中にエラーが発生しました
2025-05-30 15:00:00,002 - ERROR - メディアのダウンロードに失敗しました
```

## ❓ よくある質問（FAQ）

### Q: 投稿が実行されないのですが？
**A**: 以下を確認してください：
1. スプレッドシートに投稿データがあるか
2. API認証情報が正しいか
3. スケジュールが正しく生成されているか（`schedule.txt`を確認）

### Q: 同じ投稿が何度も実行されます
**A**: スプレッドシートの「最終投稿日時」列が正しく更新されていない可能性があります。Google Sheetsの権限とサービスアカウントキーを確認してください。

### Q: 動画投稿でエラーが出ます
**A**: 
1. FFmpegがインストールされているか確認
2. 動画ファイルサイズが512MB以下か確認
3. Google DriveのURLが正しいか確認

### Q: Slack通知が来ません
**A**: `config/config.yml`の`slack`セクションでWebhook URLが正しく設定されているか確認してください。

### Q: スケジュールが生成されません
**A**: 
1. `schedule_posts.py`の設定値を確認
2. アカウント数と投稿回数の設定が適切か確認
3. 営業時間設定（START_HOUR, END_HOUR）を確認

### Q: PC移動後に動作しません
**A**: 
1. インターネット接続を確認
2. 仮想環境が正しく有効化されているか確認
3. `which python`で正しいPythonが使用されているか確認
4. スケジュールファイルが存在するか確認（`ls schedule.txt executed.txt`）

### Q: 投稿順序を変更したい
**A**: スプレッドシートの「最終投稿日時」列を編集することで、投稿順序を制御できます。古い日時のものから優先的に投稿されます。

### Q: 複数アカウントを同時実行したい
**A**: 現在のシステムは各アカウントを順次実行します。完全な同時実行には改修が必要です。

### Q: スケジュールを手動で調整したい
**A**: `schedule.txt`ファイルを直接編集するか、`schedule_posts.py`の設定値を変更してスケジュールを再生成してください。

## 🔗 関連リソース

- **X API Documentation**: https://developer.twitter.com/en/docs
- **Google Sheets API**: https://developers.google.com/sheets/api
- **FFmpeg**: https://ffmpeg.org/
- **ログファイル場所**: `logs/auto_post_logs/app.log`
- **設定ファイル**: `config/config.yml`
- **スケジュールファイル**: `schedule.txt` / `executed.txt`

---
**最終更新**: 2025年1月  
**バージョン**: 2.0.0 

## 🎯 システム概要

X（Twitter）での自動投稿を行うシステムです。Google スプレッドシートから投稿データを取得し、スケジュールに従って自動投稿を実行します。

### 主要機能
- 📊 Google スプレッドシートからの投稿データ取得
- 🤖 X API を使用した自動投稿
- 📅 スケジュール管理システム
- 📹 動画メタデータ変換（FFmpeg）
- 🔀 ランダムスペース挿入（検出回避）
- 📱 Slack 通知
- 🧵 ツリー投稿対応（長文自動分割）

## 🔧 アカウント管理

すべてのアカウント情報は `config/config.yml` で一元管理されます。

### 🔄 新しいアカウント追加手順

#### 1. X Developer Portal での準備
1. [X Developer Portal](https://developer.twitter.com/) にアクセス
2. 新しいアプリケーションを作成
3. API Keys を取得:
   - Consumer Key
   - Consumer Secret  
   - Access Token
   - Access Token Secret

#### 2. config.yml への追加
`config/config.yml` の `twitter_accounts` セクションに追加:

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      email: "メールアドレス"
      username: "ユーザー名"
      password: "パスワード（参考用）"
      consumer_key: "取得したConsumer Key"
      consumer_secret: "取得したConsumer Secret"
      access_token: "取得したAccess Token"
      access_token_secret: "取得したAccess Token Secret"
      google_sheets_source:
        enabled: true
        worksheet_name: "ワークシート名"
```

#### 3. スケジュール設定に追加
`config/config.yml` の `auto_post_bot.twitter_accounts` リストに、アカウントごとの `posts_today` (任意) や `worksheet_name` を設定します。
`schedule_posts.py` の `ACCOUNTS` リストは廃止され、`config.yml` で一元管理されます。

```yaml
auto_post_bot:
  twitter_accounts:
    - account_id: "新アカウント名"
      # ... (consumer_keyなどのAPI情報)
      google_sheets_source:
        enabled: true
        worksheet_name: "新しいワークシート名"
      posts_today: 2 # このアカウントの1日の投稿数 (省略可)
    # ... 他のアカウント ...
```

#### 4. スプレッドシート準備
Google スプレッドシートに新しいワークシートを作成し、以下の列を設定:
- ID
- 投稿タイプ
- 最終投稿日時
- 文字数
- 本文
- 画像/動画URL
- 投稿可能（チェックボックス）
- 投稿済み回数

## 📊 スプレッドシートへのデータ追加手順

### 1. 基本的な投稿データ形式
| ID | 投稿タイプ | 最終投稿日時 | 文字数 | 本文 | 画像/動画URL | 投稿可能 | 投稿済み回数 |
|----|-----------|-------------|--------|------|-------------|----------|-------------|
| 1  | 通常投稿   | 2025-01-01 10:00:00 | 50 | 投稿内容... | https://drive.google.com/... | ✅ | 0 |

### 2. 重要な注意点
- **ID**: 各行に一意のIDを設定
- **本文**: 文字数制限（280文字以下）を考慮
- **画像/動画URL**: Google Driveの共有URLを使用
- **最終投稿日時**: 古い日時のものから優先的に投稿される
- **投稿可能**: ✅ チェック済みの投稿のみが実行対象（未チェックは除外）
- **投稿アカウント判別**: ワークシート名で自動判別（都内メンエス→jadiAngkat、都内セクキャバ→hinataHHHHHH）

### 3. Google Drive メディアファイルの準備
1. 画像・動画をGoogle Driveにアップロード
2. 「リンクを知っている全員が閲覧可」に設定
3. 共有URLをスプレッドシートに貼り付け

## 📝 新しい投稿を追加する手順

### 1. コンテンツ準備フェーズ
```bash
# メディアファイルの準備（推奨ファイル形式）
# 画像: JPG, PNG (5MB以下)
# 動画: MP4 (512MB以下、2分20秒以下)
```

### 2. Google Drive へのアップロード
1. **フォルダ組織化**:
   - アカウント別フォルダを作成（例：`jadiAngkat_media`）
   - 日付別サブフォルダで整理（例：`2025-01-30`）

2. **アップロード手順**:
   ```
   1. Google Drive にログイン
   2. 対象フォルダを開く
   3. ファイルをドラッグ&ドロップ
   4. アップロード完了を確認
   ```

3. **共有設定**:
   ```
   1. ファイルを右クリック → 「共有」
   2. 「リンクを知っている全員」に変更
   3. 「閲覧者」権限を確認
   4. 「リンクをコピー」をクリック
   ```

### 3. スプレッドシート更新の詳細手順

#### ステップ1: 新しい行の追加
1. Google Sheets で該当のワークシートを開く
2. 最下行の下に新しい行を挿入
3. ID列に連番を入力（既存の最大ID + 1）

#### ステップ2: 基本情報の入力
```
ID: 連番（例：49）
投稿タイプ: 通常投稿
最終投稿日時: 優先度に応じた日時（古い日時 = 高優先度）
文字数: 本文の文字数（自動計算も可）
本文: 投稿内容（280文字以下）
画像/動画URL: Google Driveの共有URL
投稿可能: ✅
投稿済み回数: 0（初期値）
```

#### ステップ3: 本文作成のベストプラクティス
- **文字数確認**: 280文字以下に収める
- **ハッシュタグ**: 適切なハッシュタグを含める
- **改行**: 読みやすさを考慮した改行
- **絵文字**: 適度な絵文字の使用

#### ステップ4: 投稿可能フラグの設定
- **✅ チェック済み**: 投稿対象に含まれる
- **❌ 未チェック**: 投稿から除外される
- **用途例**: 
  - 下書き状態の投稿を一時的に無効化
  - 季節限定投稿の期間外での無効化
  - テスト投稿の本番環境での除外

### 4. 優先度設定による投稿順序制御

#### 高優先度（すぐに投稿したい）
```
最終投稿日時: 2020-01-01 00:00:00
```

#### 通常優先度
```
最終投稿日時: 現在日時の1日前
```

#### 低優先度（後回しにしたい）
```
最終投稿日時: 現在日時
```

### 5. 投稿後の自動更新確認

投稿実行後、以下が自動更新されます：
- **最終投稿日時**: 投稿実行時刻に更新
- **投稿済み回数**: +1 されて更新
- **ステータス**: （設定によって「投稿完了」に更新）

### 6. 品質チェックポイント

#### 投稿前チェックリスト
- [ ] 本文の誤字脱字確認
- [ ] 文字数制限（280文字以下）
- [ ] メディアファイルの表示確認
- [ ] URL の動作確認
- [ ] アカウント名の正確性
- [ ] 優先度設定の妥当性

#### メディアファイルチェック
- [ ] ファイル形式が対応しているか
- [ ] ファイルサイズが制限内か
- [ ] 画質・音質が適切か
- [ ] Google Drive の共有設定が正しいか

### 7. 大量投稿追加時の効率化

#### CSVインポート方法
1. Excel または Google Sheets でデータを準備
2. CSV形式でエクスポート
3. Google Sheets の「ファイル」→「インポート」
4. 既存データに追加する設定で実行

#### 一括メディアアップロード
1. Google Drive デスクトップアプリを使用
2. ローカルフォルダで整理してから同期
3. 一括で共有設定を変更

### 8. トラブル時の対処法

#### スプレッドシート更新が反映されない
```bash
# 権限確認
# Google Sheets の共有設定を確認
# サービスアカウントがエディター権限を持っているか確認

# 手動で同期確認
python -c "
from bots.auto_post_bot.post_tweet import get_posts_from_sheet
posts = get_posts_from_sheet('jadiAngkat')
print(f'取得件数: {len(posts)}')
"
```

#### メディアダウンロードエラー
1. Google Drive URL の形式確認
2. 共有設定の確認
3. ファイルサイズの確認
4. インターネット接続の確認

## ⚠️ エラーパターンと対応方法

### 1. API認証エラー
**症状**: `Twitter APIクライアントの初期化に失敗`
**アラート**: Slack に「❌ 投稿失敗」通知
**対応**:
```bash
# API キーの確認
grep -A 10 "twitter_api:" config/config.yml

# 権限確認（X Developer Portal で確認）
# - Read and write permissions が設定されているか
# - アクセストークンが最新か
```

### 2. スプレッドシート接続エラー
**症状**: `Google Sheetsからのデータ取得中にエラー`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# サービスアカウントキーの確認
ls -la config/gspread-key.json

# スプレッドシート名の確認
grep "sheet_name:" config/config.yml
```

### 3. メディアダウンロードエラー
**症状**: `メディアのダウンロードに失敗`
**アラート**: ログに「画像のダウンロード中にエラー」
**対応**:
- Google Drive URLの共有設定を確認
- インターネット接続状況を確認
- URL形式が正しいか確認

### 4. FFmpeg関連エラー
**症状**: `動画メタデータ変換中にエラー`
**対応**:
```bash
# FFmpegのインストール確認
ffmpeg -version

# macOSの場合、再インストール
brew install ffmpeg
```

### 5. スケジュール生成エラー
**症状**: `10分以上離れた時刻が見つかりませんでした`
**アラート**: ログファイルにエラー記録
**対応**:
```bash
# schedule_posts.pyの設定を確認・調整
# MIN_INTERVAL_MINUTES の値を小さくする
# START_HOUR と END_HOUR の範囲を広げる
# POSTS_PER_ACCOUNT の値を小さくする
```

## 💻 PC移動時の注意点

### 1. カフェなど公共Wi-Fi使用時
```bash
# VPN接続の確認（推奨）
# API制限やセキュリティ考慮

# 手動実行でテスト
python -m bots.auto_post_bot.post_tweet

# エラーがないことを確認してから定期実行
```

### 2. 環境の持ち運び手順
```bash
# 1. 仮想環境の有効化確認
source .venv/bin/activate
which python  # プロジェクト内のpythonが使われているか確認

# 2. 依存関係の確認
pip list | grep tweepy
pip list | grep gspread

# 3. 設定ファイルの確認
ls -la config/

# 4. ログディレクトリの確認
ls -la logs/auto_post_logs/

# 5. スケジュールファイルの確認
ls -la schedule.txt executed.txt
```

### 3. トラブルシューティング
```bash
# パスの確認
pwd
ls -la

# Python環境の確認
python --version
pip --version

# 必要に応じて依存関係の再インストール
pip install -r requirements.txt

# スケジュールファイルの再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## 📋 定期実行の設定

### crontab設定例（推奨）
```bash
# crontabを編集
crontab -e

# 毎朝8時にスケジュール生成＋Slack通知
0 8 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --generate-schedule >> logs/cron_schedule_generation.log 2>&1

# 毎日9時、13時、17時に投稿実行
0 9,13,17 * * * cd /path/to/InboundEngine && source .venv/bin/activate && python main.py --execute-now >> logs/cron_execute_posts.log 2>&1
```

### スケジュール管理の詳細
```bash
# 当日のスケジュール確認
cat schedule.txt

# 実行済み投稿の確認
cat executed.txt

# スケジュールの手動再生成
rm schedule.txt
python schedule_posts.py
```

## 📞 緊急時の連絡先・対応

### 1. Bot停止方法
```bash
# 実行中プロセスの確認
ps aux | grep python

# 強制停止（必要に応じて）
pkill -f "post_tweet"
pkill -f "schedule_posts"
```

### 2. 手動投稿での緊急対応
```bash
# 特定アカウントのみテスト投稿
python -c "
from bots.auto_post_bot.post_tweet import *
# 手動でのテスト実行コード
"

# スケジュールをリセットして再生成
rm schedule.txt executed.txt
python schedule_posts.py
```

## ☁️ クラウド運用（推奨）

### 🎯 GitHub Actions（最推奨）

#### **コスト**: 🟢 **完全無料**
- プライベートリポジトリでも月2,000分無料
- 1日4回実行 = 月約240分 → **実質無料**

#### **運用の簡単さ**: 🟢 **最簡単**
- Git push だけで自動デプロイ
- ゼロメンテナンション（サーバー管理不要）
- Web UIでログ確認可能

#### **DevOps**: 🟢 **最も簡単**
- Secrets管理が組み込み
- 手動実行ボタンあり
- 自動スケーリング

### 🚀 GitHub Actions 完全デプロイ手順

#### 1. リポジトリ準備
```bash
# プライベートリポジトリ作成（機密情報があるため）
gh repo create InboundEngine-Bot --private
git remote add origin https://github.com/yourusername/InboundEngine-Bot.git
git push -u origin main
```

#### 2. GitHub Secrets 設定 ⚙️
`Settings > Secrets and variables > Actions` で以下を設定:

**🔑 必須Secrets:**
```
# 共通設定
GOOGLE_SHEETS_KEY: (gspread-key.json の内容をまるごと)
SLACK_WEBHOOK_URL: (Slack Webhook URL)
TWITTER_BEARER_TOKEN: (X API Bearer Token - 共通)

# jadiAngkat アカウント用 (Account1)
ACCOUNT1_CONSUMER_KEY: (jadiAngkat用 Consumer Key)
ACCOUNT1_CONSUMER_SECRET: (jadiAngkat用 Consumer Secret)
ACCOUNT1_ACCESS_TOKEN: (jadiAngkat用 Access Token)
ACCOUNT1_ACCESS_TOKEN_SECRET: (jadiAngkat用 Access Token Secret)
ACCOUNT1_EMAIL: (jadiAngkatのメールアドレス)

# hinataHHHHHH アカウント用 (Account2)
ACCOUNT2_CONSUMER_KEY: (hinataHHHHHH用 Consumer Key)
ACCOUNT2_CONSUMER_SECRET: (hinataHHHHHH用 Consumer Secret)
ACCOUNT2_ACCESS_TOKEN: (hinataHHHHHH用 Access Token)
ACCOUNT2_ACCESS_TOKEN_SECRET: (hinataHHHHHH用 Access Token Secret)
ACCOUNT2_EMAIL: (hinataHHHHHHのメールアドレス)
```

**💡 Secrets設定の簡潔リスト:**
```
GOOGLE_SHEETS_KEY
SLACK_WEBHOOK_URL
TWITTER_BEARER_TOKEN
ACCOUNT1_CONSUMER_KEY
ACCOUNT1_CONSUMER_SECRET
ACCOUNT1_ACCESS_TOKEN
ACCOUNT1_ACCESS_TOKEN_SECRET
ACCOUNT1_EMAIL
ACCOUNT2_CONSUMER_KEY
ACCOUNT2_CONSUMER_SECRET
ACCOUNT2_ACCESS_TOKEN
ACCOUNT2_ACCESS_TOKEN_SECRET
ACCOUNT2_EMAIL
```

#### 3. 自動実行スケジュール 📅
設定済みの実行スケジュール:
- **毎朝8時**: スケジュール生成 + Slack通知
- **毎日10時、14時、18時、21時**: 自動投稿実行
- **Git push時**: 「スクリプトが更新されました。」Slack通知

#### 4. 手動実行オプション 🔧
GitHub Actions画面で「Run workflow」ボタンから:
- `post`: 投稿実行
- `schedule`: 通常スケジュール生成
- `schedule-now`: 現在時刻以降でスケジュール生成

#### 5. Slack通知の詳細 📱

**📢 Git Push通知:**
```
🔄 スクリプトが更新されました。
Repository: user/InboundEngine-Bot
Commit: feat: 新機能追加
Author: user
Branch: main
```

**📅 スケジュール通知（改善版）:**
```
📅 自動投稿スケジュール

• jadiAngkat: 05/30 17:33 (約1時間54分後)
• hinataHHHHHH: 05/30 21:27 (約5時間48分後)

📊 合計2件 | 2アカウント
⏰ 生成時刻: 2025-05-30 15:38:15
```

**🌙 夜間実行時の通知:**
```
🌙 夜間スケジュール生成完了 （営業時間外のため翌日に設定）

• jadiAngkat: 05/31 11:15 (約12時間37分後)
• hinataHHHHHH: 05/31 16:42 (約18時間4分後)

📊 合計2件 | 2アカウント | 本日0件・翌日2件
⏰ 生成時刻: 2025-05-30 23:15:30
```

### 🔧 その他のクラウドオプション

#### **Railway** ($5/月の無料クレジット)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

#### **AWS EC2 t2.micro** (1年間無料)
- より多くの設定が必要
- Linux サーバー管理スキル必要

#### **Google Cloud Run** (月200万リクエスト無料)
- Dockerfile が必要
- GCP の設定が複雑

### ✅ GitHub Actions の利点

- **完全無料** (プライベートリポジトリでも実質無料)
- **ゼロメンテナンス** (サーバー管理不要)
- **自動スケーリング** (必要に応じてリソース調整)
- **ログ管理** (Web UIで確認可能)
- **手動実行** (緊急時にボタン一つで実行)
- **セキュリティ** (Secrets 管理が組み込み)
- **DevOps** (Git push で自動デプロイ)

### 📋 移行手順

#### 1. ローカル → クラウド移行
```bash
# 機密情報をGitHub Secretsに移行
# テスト実行で動作確認
# ローカル cron を停止
# GitHub Actions を有効化
```

#### 2. 段階的移行
1. 最初は手動実行のみでテスト
2. 動作確認後にスケジュール実行を有効化
3. ローカル実行を徐々に停止

**結論: GitHub Actions が最もコスト効率と運用効率のバランスが良く、DevOps も最も簡単です！** 🎉

## 📊 実際の運用ログ例

### 正常実行時のログ
```
2025-05-30 14:59:37,071 - INFO - ===== Auto Post Bot 開始 =====
2025-05-30 14:59:38,817 - INFO - 48 件の投稿ストックを取得しました。
2025-05-30 14:59:38,819 - INFO - [DEBUG] 全8件中、最終投稿日時が最も古い投稿を選択しました
2025-05-30 14:59:44,834 - INFO - ツイート投稿成功。Tweet ID: 1928330467050410158
2025-05-30 14:59:45,161 - INFO - Slack通知を送信しました
2025-05-30 14:59:49,048 - INFO - 投稿ID 3 のステータスを '投稿完了' に更新しました
```

### スケジュール生成時のログ
```
新しいスケジュールを作成しました:
jadiAngkat,2025-05-30 09:15:00
hinataHHHHHH,2025-05-30 14:32:00
jadiAngkat,2025-05-30 18:45:00
Slackにスケジュールを通知しました
```

### エラー発生時のログ例
```
2025-05-30 15:00:00,000 - ERROR - Twitter APIクライアントの初期化に失敗しました
2025-05-30 15:00:00,001 - ERROR - Google Sheetsからのデータ取得中にエラーが発生しました
2025-05-30 15:00:00,002 - ERROR - メディアのダウンロードに失敗しました
```

## ❓ よくある質問（FAQ）

### Q: 投稿が実行されないのですが？
**A**: 以下を確認してください：
1. スプレッドシートに投稿データがあるか
2. API認証情報が正しいか
3. スケジュールが正しく生成されているか（`schedule.txt`を確認）

### Q: 同じ投稿が何度も実行されます
**A**: スプレッドシートの「最終投稿日時」列が正しく更新されていない可能性があります。Google Sheetsの権限とサービスアカウントキーを確認してください。

### Q: 動画投稿でエラーが出ます
**A**: 
1. FFmpegがインストールされているか確認
2. 動画ファイルサイズが512MB以下か確認
3. Google DriveのURLが正しいか確認

### Q: Slack通知が来ません
**A**: `config/config.yml`の`slack`セクションでWebhook URLが正しく設定されているか確認してください。

### Q: スケジュールが生成されません
**A**: 
1. `schedule_posts.py`の設定値を確認
2. アカウント数と投稿回数の設定が適切か確認
3. 営業時間設定（START_HOUR, END_HOUR）を確認

### Q: PC移動後に動作しません
**A**: 
1. インターネット接続を確認
2. 仮想環境が正しく有効化されているか確認
3. `which python`で正しいPythonが使用されているか確認
4. スケジュールファイルが存在するか確認（`ls schedule.txt executed.txt`）

### Q: 投稿順序を変更したい
**A**: スプレッドシートの「最終投稿日時」列を編集することで、投稿順序を制御できます。古い日時のものから優先的に投稿されます。

### Q: 複数アカウントを同時実行したい
**A**: 現在のシステムは各アカウントを順次実行します。完全な同時実行には改修が必要です。

### Q: スケジュールを手動で調整したい
**A**: `schedule.txt`ファイルを直接編集するか、`schedule_posts.py`の設定値を変更してスケジュールを再生成してください。

## 🔗 関連リソース

- **X API Documentation**: https://developer.twitter.com/en/docs
- **Google Sheets API**: https://developers.google.com/sheets/api
- **FFmpeg**: https://ffmpeg.org/
- **ログファイル場所**: `logs/auto_post_logs/app.log`
- **設定ファイル**: `config/config.yml`
- **スケジュールファイル**: `schedule.txt` / `executed.txt`

---
**最終更新**: 2025年1月  
**バージョン**: 2.0.0 

## 🎯 システム概要

X（Twitter）での自動投稿を行うシステムです。Google スプレッドシートから投稿データを取得し、スケジュールに従って自動投稿を実行します。

### 主要機能
- 📊 Google スプレッドシートからの投稿データ取得
- 🤖 X API を使用した自動投稿
- 📅 スケジュール管理システム
- 📹 動画メタデータ変換（FFmpeg）
- 🔀 ランダムスペース挿入（検出回避）
- 📱 Slack 通知
- 🧵 ツリー投稿対応（長文自動分割）

## 🔧 アカウント管理

すべてのアカウント情報は `config/config.yml` 