# Auto Post Bot (Twitter & Google Sheets)

このプロジェクトは、Googleスプレッドシートをデータソースとして利用し、設定されたスケジュールに基づいてTwitter（現X）へ自動投稿を行うPythonスクリリプトです。GitHub Actionsと連携して、定期的な投稿やスケジュール更新を自動化することも可能です。

## 主な機能

*   **複数アカウント対応**: 複数のTwitterアカウントからの投稿を管理できます。
*   **Googleスプレッドシート連携**: 投稿内容（テキスト、画像/動画URL）をGoogleスプレッドシートで一元管理。
*   **柔軟なスケジューリング**:
    *   投稿時間帯の設定（例: 毎日9時～21時の間）。
    *   投稿間の最小間隔設定。
*   **自動投稿実行**: スケジュールに基づいて、投稿可能なコンテンツを自動でツイートします。
*   **メディア投稿**: 画像や動画（URL指定）の添付に対応。
*   **Discord通知**: 投稿実行時、スケジュール生成時、エラー発生時などにDiscordへ通知。
*   **GitHub Actions連携**: 定期的なスケジュール生成と投稿実行を自動化。
*   **手動実行オプション**: コマンドラインやGitHub Actions経由で即時投稿やスケジュール生成が可能。
*   **ログ機能**: 実行状況やエラーをファイルに記録。

## 目次

- [セットアップ](#セットアップ)
- [設定方法](#設定方法)
- [使い方](#使い方)
- [GitHub Actionsでの自動実行](#github-actionsでの自動実行)
- [トラブルシューティング](./docs/TROUBLESHOOTING.md)
- [ディレクトリ構造](#ディレクトリ構造)
- [技術スタック](#技術スタック)
- [今後の展望](#今後の展望)
- [ライセンス](#ライセンス)

## セットアップ

### 前提条件

*   Python 3.10
*   pip (Python パッケージインストーラ)
*   Git

### インストール手順

1.  **リポジトリをクローン:**
    ```bash
    git clone https://github.com/your-username/your-repository-name.git # ご自身のものに置き換えてください
    cd your-repository-name
    ```
2.  **仮想環境の作成と有効化 (推奨):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # macOS/Linux の場合
    # venv\\Scripts\\activate   # Windows の場合
    ```
3.  **必要なライブラリのインストール:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **設定ファイルの準備:** (詳細は[設定方法](#設定方法)セクションを参照)
    *   開発環境では、`config/app_config.dev.json` ファイルを作成し、必要な設定をJSON形式で記述します。
    *   本番環境やCI/CD（GitHub Actionsなど）では、環境変数 `APP_CONFIG_JSON` を設定します。この環境変数には、設定情報全体のJSON文字列を格納します。

## 設定方法

アプリケーションの設定は、JSON形式で行います。読み込まれる設定の優先順位は以下の通りです。

1.  **環境変数 `APP_CONFIG_JSON`**: 設定情報全体のJSON文字列。設定されていれば最優先で読み込まれます。主に本番環境やCI/CD環境での使用を想定しています。
2.  **`config/app_config.dev.json` ファイル**: 開発時に便利なローカル設定ファイル。環境変数 `APP_CONFIG_JSON` が設定されていない場合に読み込まれます。

設定ファイル/環境変数に含めるJSONの基本的な構造は以下のようになります。実際の値はご自身の環境に合わせて設定してください。

```json
{
    "common": {
        "log_level": "INFO", // DEBUG, INFO, WARNING, ERROR, CRITICAL
        "logs_directory": "logs"
    },
    "google_sheets": {
        "spreadsheet_id": "YOUR_SPREADSHEET_ID",
        "service_account_credentials": {
            // Google Cloud Platform からダウンロードしたサービスアカウントキーのJSONオブジェクト全体をここに記述
            "type": "service_account",
            "project_id": "your-gcp-project-id",
            "private_key_id": "your-private-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
            "client_email": "your-service-account-email@your-gcp-project-id.iam.gserviceaccount.com",
            "client_id": "...",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "..."
        }
    },
    "twitter_accounts": [
        {
            "account_id": "your_twitter_account_id_1", // 任意の識別子
            "enabled": true, // このアカウント設定を有効にするか
            "consumer_key": "YOUR_CONSUMER_KEY",
            "consumer_secret": "YOUR_CONSUMER_SECRET",
            "access_token": "YOUR_ACCESS_TOKEN",
            "access_token_secret": "YOUR_ACCESS_TOKEN_SECRET",
            "google_sheets_source": { // このアカウントが参照するスプレッドシートのシート名
                "worksheet_name": "シート名1"
            },
            "posts_today": 1 // このアカウントの1日の最大投稿数 (省略時は共通設定を参照)
        }
        // 他のアカウント設定があれば追加
    ],
    "discord_webhook_url": "YOUR_DISCORD_WEBHOOK_URL_FOR_APP_NOTIFICATIONS", // アプリケーションからの通知用
    "auto_post_bot": {
        "columns": [ // スプレッドシートのカラム名定義
            "ID", "本文", "文字数", "画像/動画URL", "投稿可能", "投稿済み回数", "最終投稿日時"
        ],
        "schedule_settings": { // 投稿スケジューリングに関する設定
            "start_hour": 9,    // 投稿を開始する時間 (24時間表記)
            "end_hour": 21,     // 投稿を終了する時間
            "min_interval_minutes": 30, // 投稿間の最短間隔 (分)
            "max_posts_per_hour_globally": 5, // 1時間あたりの全アカウント合計の最大投稿数
            "schedule_file": "schedule.json", // 生成されるスケジュールファイル名 (logsディレクトリ内)
            "executed_file": "executed_posts.log", // 実行済みログファイル名 (logsディレクトリ内)
            "test_schedule_file": "test_schedule.json", // 手動テスト用スケジュールファイル名
            "test_executed_file": "test_executed_posts.log" // 手動テスト用実行済みログファイル名
        },
        "posting_settings": {
            "posts_per_account": 1 // アカウント毎の1日のデフォルト投稿数
        },
        "discord_notification": { // Discord通知の詳細設定
            "enabled": true, // アプリケーションからのDiscord通知を有効にするか
            "notify_daily_schedule_summary": true // 日次スケジュールサマリーを通知するか
        }
    }
}
```

より詳細な設定オプションについては、`engine_core/config.py` 内の `Config` クラスの各`get_...`メソッドや、それらを利用している各モジュールの実装を参照してください。([詳細ドキュメント](./docs/CONFIGURATION.md) も後日更新予定です。)

## 使い方

基本的な実行は `main.py` スクリプトで行います。

```bash
python main.py [オプション]
```

主なオプション:
*   `--workflow <ワークフロー名>`: 指定したワークフローを実行します。
    *   `daily_schedule`: その日の投稿スケジュールを生成します。
    *   `execute_scheduled_posts`: 現在時刻に基づいてスケジュールされた投稿を実行します。
*   `--manual-test <アカウントID>`: 指定したアカウントIDで即時テスト投稿を実行します。
    *   例: `python main.py --manual-test your_twitter_account_id_1`
*   `--log-level <レベル>`: ログレベルを上書きします (例: DEBUG, INFO, WARNING, ERROR, CRITICAL)。

コマンドラインオプションの詳細は `--help` で確認できます。
```bash
python main.py --help
```
([詳細ドキュメント](./docs/USAGE.md) も後日更新予定です。)

## GitHub Actionsでの自動実行

`.github/workflows/auto-post-bot.yml` にて、GitHub Actionsによる自動実行ワークフローが定義されています。
このワークフローは、毎日定刻（デフォルトは日本時間午前9時）にスケジュール生成と投稿実行を自動で行います。

### 必要なSecrets

このワークフローを正しく動作させるためには、リポジトリのSecretsに以下の情報を設定する必要があります。

1.  **`APP_CONFIG_JSON`**:
    *   上記[設定方法](#設定方法)で説明したJSON文字列全体を、本番環境用の値に置き換えて設定します。
    *   APIキーやアクセストークンなどの機密情報を含みます。
2.  **`DISCORD_WEBHOOK_URL`**:
    *   GitHub Actionsの**ワークフロー自体が失敗した際に通知を送るため**のDiscord Webhook URLです。
    *   （`APP_CONFIG_JSON`内に設定するアプリケーション通知用のWebhook URLとは別でも、同じでも構いませんが、役割が異なります。）

([詳細ドキュメント](./docs/GITHUB_ACTIONS.md) も後日更新予定です。)

## ディレクトリ構造

```
.
├── .github/workflows/        # GitHub Actions ワークフローファイル
│   └── auto-post-bot.yml
├── config/                     # 設定関連ディレクトリ
│   └── app_config.dev.json.example # 開発用設定ファイルのサンプル
├── docs/                     # 詳細ドキュメント (更新中)
│   ├── CONFIGURATION.md
│   ├── USAGE.md
│   ├── GITHUB_ACTIONS.md
│   └── TROUBLESHOOTING.md
├── engine_core/              # メインロジック (Pythonモジュール)
│   ├── __init__.py
│   ├── config.py             # 設定読み込み
│   ├── discord_notifier.py   # Discord通知
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── post_scheduler.py # 投稿スケジュール生成
│   │   └── scheduled_post_executor.py # 投稿実行
│   ├── spreadsheet_manager.py# Google Sheets操作
│   ├── twitter_client.py     # Twitter API操作
│   └── workflow_manager.py   # 各処理フローの管理
├── logs/                     # ログファイルやスケジュールファイルが保存されるディレクトリ (自動生成)
├── main.py                   # メイン実行スクリプト
├── requirements.txt          # Pythonライブラリの依存関係
└── README.md                 # このファイル
```

## 技術スタック

*   Python 3.10
*   Tweepy (Twitter API v1.1 & v2)
*   gspread (Google Sheets API)
*   google-auth (Google API認証)
*   GitHub Actions (CI/CD、自動実行)

## 今後の展望

*   より高度なスケジューリングオプション（曜日指定、特定日除外など）。
*   複数メディア（画像+動画など）の投稿サポート。
*   ウェブUIによる設定・管理インターフェース。
*   対応SNSの拡充（Instagram, Facebookなど）。
*   より詳細なエラーハンドリングとリトライ機構。
*   詳細ドキュメント (`docs` ディレクトリ内) の全面的な更新。

## ライセンス

このプロジェクトは [MIT License](LICENSE) の下で公開されています。