# アプリケーションの利用方法

このドキュメントでは、アプリケーションのローカルでの実行方法、コマンドライン引数、および関連する操作について説明します。

## 必要なもの

*   Python 3.8 以降
*   pip (Python パッケージインストーラ)
*   Git (ソースコードの取得に)

## ローカルでのセットアップと実行

1.  **リポジトリのクローン:**
    ```bash
    git clone https://github.com/your-username/your-repository-name.git
    cd your-repository-name
    ```

2.  **仮想環境の作成と有効化 (推奨):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # macOS/Linux
    # venv\Scripts\activate   # Windows
    ```

3.  **必要なライブラリのインストール:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **設定ファイルの準備:**
    *   `config/` ディレクトリを作成します (`mkdir config`)。
    *   `config/config.template.yml` を `config/config.yml` にコピーします。
    *   `config/config.yml` を開き、必要な情報を編集します（APIキー、スプレッドシートIDなど）。詳細は [CONFIGURATION.md](./CONFIGURATION.md) を参照してください。
    *   Google Cloud Platform でサービスアカウントを作成し、キーファイル（JSON形式）をダウンロードします。そのファイル名を `config.yml` の `common.file_paths.google_key_file` で指定した名前に変更し、`config/` ディレクトリに配置します。

5.  **スクリプトの実行:**

    *   **投稿スケジュールの生成:**
        ```bash
        python main.py --generate-schedule
        ```
        オプション:
        *   `--date YYYY-MM-DD`: 特定の日付のスケジュールを生成します（デフォルトは当日）。
        *   `--force-regenerate`: 既存のスケジュールファイルを上書きして再生成します。
        *   `--info`: 詳細なログを出力します。
        *   `--debug`: さらに詳細なデバッグログを出力します。

    *   **予約投稿の実行:**
        ```bash
        python main.py --process-now
        ```
        オプション:
        *   `--date YYYY-MM-DD`: 特定の日付のスケジュールに基づいて投稿を実行します（デフォルトは当日）。
        *   `--info`: 詳細なログを出力します。
        *   `--debug`: さらに詳細なデバッグログを出力します。

    *   **特定のアカウントのみを対象にする (上級者向け):**
        `main.py` を直接編集するか、カスタムスクリプトで `WorkflowManager` を使用することで、特定のアカウントIDを指定して処理を実行できます。これは主にデバッグや個別テスト用です。

        例 (コード内で直接指定する場合):
        ```python
        # In your custom script or for testing in main.py
        # config = Config('config/config.yml')
        # manager = WorkflowManager(config, target_accounts=['your_specific_account_id'])
        # manager.generate_daily_schedule()
        # or
        # manager.process_scheduled_posts()
        ```

## コマンドライン引数

`main.py` は以下のコマンドライン引数を受け付けます:

*   `--generate-schedule`: その日の投稿スケジュールを生成します。新しい投稿は `schedule_settings.schedule_file` で指定されたファイルに保存されます。
*   `--process-now`: `schedule_settings.schedule_file` に基づいて、現在時刻までに投稿されるべき未投稿のツイートを処理します。
*   `--date YYYY-MM-DD`: `--generate-schedule` または `--process-now` と共に使用し、対象の日付を指定します。省略した場合は現在の日付が使用されます。
*   `--force-regenerate`: `--generate-schedule` と共に使用し、既存のスケジュールファイルが存在する場合でも強制的に再生成します。
*   `--info`: INFOレベル以上のログをコンソールに出力します。
*   `--debug`: DEBUGレベル以上のログをコンソールに出力します。
*   `--dry-run`: 投稿やスプレッドシートの更新を実際には行わず、シミュレーション実行します。ログで動作を確認できます。
*   `--test-tweet`: 設定ファイル内の最初のアカウントでテストツイート（内容は固定）を1件投稿し、設定やAPI接続を確認します。

## 手動テスト実行スクリプト

`run_manual_test.py` スクリプトは、開発やテスト目的で特定の機能を簡単に実行するために用意されています。

```bash
python run_manual_test.py
```
このスクリプトは、設定ファイル (`config/config.yml`) を読み込み、`WorkflowManager` を使用して以下のいずれかのアクションを実行するように促します:
1.  **スケジュール生成 (test_schedule.json)**
2.  **スケジュールされた投稿の実行 (test_schedule.json を使用)**
3.  **単一投稿テスト (最初の有効なアカウントを使用)**

テスト用のスケジュールファイル (`test_schedule.json`) や実行ログ (`test_executed_posts.log`) は `logs/` ディレクトリに保存されます。

## スケジュール管理の詳細

*   **スケジュールファイル:** `schedule.json` (デフォルト名) にJSON形式で保存されます。各エントリには投稿時刻、アカウントID、スプレッドシートの行番号などが含まれます。
*   **実行済みログ:** `executed_posts.log` (デフォルト名) に投稿済みの情報が記録され、再投稿を防ぎます。
*   **再生成:** `--force-regenerate` オプション付きで `--generate-schedule` を実行すると、既存のスケジュールファイルは上書きされ、新しいスケジュールが作成されます。
*   **投稿間隔:** `config.yml` の `schedule_settings.min_interval_minutes` で最小投稿間隔を設定できます。
*   **営業時間:** `schedule_settings.start_hour` と `schedule_settings.end_hour` で、投稿が許可される時間帯を指定できます。

詳細は `config/config.template.yml` 内のコメントも参照してください。 