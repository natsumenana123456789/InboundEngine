# InboundEngine システム再設計計画書

## 1. はじめに

本計画書は、InboundEngineプロジェクトの既存機能を活かしつつ、より堅牢で保守性の高いシステムを構築するための再設計プランを定義する。
主な目的は、手続き的なコードとオブジェクト指向のコードが混在している現状を解消し、全体の構造をオブジェクト指向に基づいて整理することである。

## 2. 基本方針

-   **完全オブジェクト指向化:** 全てのコアロジックをクラスとして再設計する。
-   **`engine_core` への集約:** 新しく `engine_core` ディレクトリを作成し、全てのビジネスロジックとドメインロジックをここに集約する。
-   **既存ロジックの活用:** 古い `src` ディレクトリやルートディレクトリ直下のPythonスクリプト内の既存ロジックは、新しいクラス構造に移植・統合する形で最大限活用する。
-   **設定の一元管理:** 全ての動作設定は `config/config.yml` に集約し、`engine_core` 内の専用設定管理クラスを通じてアクセスする。
-   **明確なエントリーポイント:** `main.py` をオブジェクト指向化されたシステムのメインエントリーポイントとし、既存の `schedule_posts.py` はコマンドラインインターフェース（CLI）ラッパーとして機能させる。

## 3. 目標ディレクトリ構造

```
InboundEngine/
├── engine_core/                # 新設: コアロジック集約ディレクトリ
│   ├── __init__.py
│   ├── config.py               # Configクラス (設定管理)
│   ├── spreadsheet.py          # SpreadsheetManagerクラス
│   ├── twitter.py              # TwitterClientクラス
│   ├── notifier.py             # DiscordNotifierクラス (および将来の通知手段)
│   ├── scheduler/              # スケジューリング関連モジュール
│   │   ├── __init__.py
│   │   ├── planner.py          # PostSchedulerクラス (計画生成)
│   │   └── executor.py         # ScheduledPostExecutorクラス (計画実行)
│   └── workflow.py             # WorkflowManagerクラス (全体の統括)
├── config/                     # 設定ファイルディレクトリ
│   ├── config.yml              # 全ての動作設定
│   └── gspread-key.json        # Googleサービスアカウントキー
├── docs/                       # ドキュメントディレクトリ
│   └── system_redesign_plan.md # 本計画書
├── logs/                       # ログファイルディレクトリ
│   ├── schedule.txt            # 生成された投稿スケジュール計画
│   └── executed.txt            # 実行済み投稿記録
├── tests/                      # テストコードディレクトリ
│   ├── engine_core/            # engine_core内のクラスに対応するテスト
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_spreadsheet.py
│   │   ├── test_twitter.py
│   │   ├── test_notifier.py
│   │   ├── scheduler/
│   │   │   ├── __init__.py
│   │   │   ├── test_planner.py
│   │   │   └── test_executor.py
│   │   └── test_workflow.py
│   └── integration/            # 結合テスト
│       └── test_full_workflow.py
├── venv/                       # Python仮想環境 (Git管理外推奨)
├── .gitignore
├── README.md
├── requirements.txt
├── schedule_posts.py           # 既存CLIエントリーポイント (engine_coreを呼び出すように改修)
└── main.py                     # 新メインエントリーポイント (オブジェクト指向版)
```

## 4. 主要クラスの役割と責務

### 4.1. `engine_core/config.py: Config`
-   **責務:** 設定ファイル (`config/config.yml`, `config/gspread-key.json`) の読み込み、解析、キャッシュ、および設定値へのアクセスインターフェース提供。
-   **主な機能:**
    -   YAMLファイルのロードと検証。
    -   Googleサービスアカウントキーへのパス解決。
    -   特定セクション/キーの設定値取得。
    -   アクティブアカウント情報の解決（既存 `config_loader.py` の機能）。
-   **移行元:** `config/config_loader.py` の全機能。

### 4.2. `engine_core/spreadsheet.py: SpreadsheetManager`
-   **責務:** Googleスプレッドシートとのインタラクション（投稿候補の取得、投稿後のステータス更新）。
-   **主な機能:**
    -   `Config` オブジェクト経由でスプレッドシートID、列定義、認証情報を取得し初期化。
    -   指定ワークシートから投稿可能な記事候補を選択（「利用許可」フラグ、「最終利用日時」順）。
    -   投稿後、スプレッドシートの「利用済み回数」と「最終利用日時」を更新。
-   **移行元:** `src/spreadsheet/manager.py` のロジック。

### 4.3. `engine_core/twitter.py: TwitterClient`
-   **責務:** Twitter API を介したツイート投稿。
-   **主な機能:**
    -   アカウント固有のAPIキーセットで初期化。
    *   テキストおよび画像URLを受け取りツイートを実行。
    *   エラーハンドリング（APIエラー、認証エラー等）。
-   **移行元:** `src/twitter/twitter_client.py` のロジック。

### 4.4. `engine_core/notifier.py: DiscordNotifier`
-   **責務:** Discordへの通知メッセージ送信。
-   **主な機能:**
    -   Webhook URLで初期化。
    -   指定されたメッセージ（テキスト、埋め込み）をDiscordに送信。
-   **移行元:** `src/notifiers/discord_notifier.py` のロジック。

### 4.5. `engine_core/scheduler/planner.py: PostScheduler`
-   **責務:** 1日分の投稿スケジュール計画の生成。
-   **主な機能:**
    -   `Config` オブジェクトからスケジュール生成ルール（活動時間帯、アカウント毎の投稿数、最小投稿間隔など）を取得し初期化。
    -   対象アカウントリストに対し、ランダム性や分散を考慮して投稿時刻を計画。
    -   生成したスケジュール計画（アカウントIDと予定時刻のリスト）を返す。
-   **移行元:** `schedule_posts.py` のスケジュール生成ロジック。補助的に旧 `src/scheduler.py` の時間検証ロジックも内部で参考にする。

### 4.6. `engine_core/scheduler/executor.py: ScheduledPostExecutor`
-   **責務:** 計画されたスケジュールに基づき、期限の来た投稿を実行する。
-   **主な機能:**
    -   `Config`, `SpreadsheetManager`, `DiscordNotifier` のインスタンスをコンストラクタで受け取る。
    -   指定されたアカウントIDと予定時刻に基づき、以下の処理を実行：
        1.  `SpreadsheetManager` から記事候補を取得。
        2.  記事があれば、`Config` からTwitter APIキーを取得し `TwitterClient` を動的に初期化。
        3.  `TwitterClient` でツイート投稿。
        4.  成功なら `SpreadsheetManager` でスプレッドシートを更新。
        5.  処理結果を `DiscordNotifier` で通知（特にエラー時）。
    -   投稿の成否や記事の有無などの実行結果を返す。
-   **移行元:** `schedule_posts.py` の `--now` 時の投稿実行ロジック。

### 4.7. `engine_core/workflow.py: WorkflowManager`
-   **責務:** システム全体のワークフロー（スケジュール生成、投稿実行）を統括し、各コンポーネントを協調させる。
-   **主な機能:**
    -   `Config` を初期化し、それを用いて他の主要コンポーネント (`PostScheduler`, `ScheduledPostExecutor`, `SpreadsheetManager`, `DiscordNotifier`) をインスタンス化し保持。
    -   `generate_schedule_and_notify()`:
        1.  `PostScheduler` でスケジュールを生成。
        2.  結果を `logs/schedule.txt` に保存 (ファイルI/Oはこのクラスが担当)。
        3.  `DiscordNotifier` で完了通知。
    -   `process_scheduled_posts()`:
        1.  `logs/schedule.txt` と `logs/executed.txt` を読み込み、現在時刻で実行すべきタスクを特定 (ファイルI/Oはこのクラスが担当)。
        2.  特定した各タスクについて `ScheduledPostExecutor.execute_due_posts()` を呼び出し実行。
        3.  実行結果に基づき `logs/executed.txt` を更新。

## 5. エントリーポイント

### 5.1. `main.py`
-   新しいオブジェクト指向システムのメインエントリーポイント。
-   コマンドライン引数を解析（例: `--generate-schedule`, `--execute-posts`）。
-   `WorkflowManager` をインスタンス化し、引数に応じて適切なメソッドを呼び出す。

### 5.2. `schedule_posts.py` (CLIラッパー)
-   既存のコマンドラインインターフェースを維持し、下位互換性を提供。
-   内部で `main.py` をサブプロセスとして呼び出すか、`WorkflowManager` のメソッドを直接呼び出すように改修。
-   既存のcronジョブなどがそのまま利用可能になることを目指す。

## 6. 移行・実装ステップ

1.  **ディレクトリ構造作成:** 上記「3. 目標ディレクトリ構造」に従い、`engine_core` および関連ディレクトリ、空のPythonファイルを作成。
2.  **`engine_core/config.py (Configクラス)` の実装:** 旧 `config/config_loader.py` の機能を完全に移植・統合。
3.  **コア機能クラスの実装:**
    -   `SpreadsheetManager` (`engine_core/spreadsheet.py`): 旧 `src/spreadsheet/manager.py` からロジック移植。
    -   `TwitterClient` (`engine_core/twitter.py`): 旧 `src/twitter/twitter_client.py` からロジック移植。
    -   `DiscordNotifier` (`engine_core/notifier.py`): 旧 `src/notifiers/discord_notifier.py` からロジック移植。
4.  **スケジューリング関連クラスの実装:**
    -   `PostScheduler` (`engine_core/scheduler/planner.py`): 旧 `schedule_posts.py` のスケジュール生成ロジックを移植。
    -   `ScheduledPostExecutor` (`engine_core/scheduler/executor.py`): 旧 `schedule_posts.py` の `--now` 時実行ロジックを移植。
5.  **`WorkflowManager` (`engine_core/workflow.py`) の実装:** 各コンポーネントを統括するロジックを実装。スケジュールファイル・実行済みファイルのI/Oも担当。
6.  **`main.py` の実装:** コマンドライン引数処理と `WorkflowManager` の呼び出し。
7.  **`schedule_posts.py` の改修:** `main.py` または `WorkflowManager` を呼び出すCLIラッパーとして機能するように変更。
8.  **テスト:** 各クラスの単体テストを作成・実行。`main.py` または `schedule_posts.py` を通じた結合テストを実施。
9.  **ドキュメント更新:** `README.md` に新しい構造、実行方法などを記載。

## 7. その他

-   古い `src` ディレクトリ内のPythonファイル群および `config/config_loader.py` は、上記移行ステップ完了後、プロジェクトから削除する。
-   テストコードも新しいディレクトリ構造に合わせて `tests/engine_core/` 以下に配置・整理する。 