# Python 3.9のベースイメージを使用
FROM python:3.9-slim

# 環境変数の設定 (Debianフロントエンドを非対話的にする)
ENV DEBIAN_FRONTEND=noninteractive

# 必要なシステムパッケージのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    cron \
    tesseract-ocr \
    tesseract-ocr-jpn \
    tesseract-ocr-eng \
    # Chromeの依存関係 (不足している場合があるため明示)
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    ca-certificates \
    fonts-ipafont-gothic \
    # その他、git など必要に応じて追加
    git \
    && rm -rf /var/lib/apt/lists/*

# Google Chrome (stable) のインストール
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# requirements.txt のコピーとPythonパッケージのインストール
COPY bots/auto_post_bot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN rm /app/requirements.txt

COPY bots/curate_bot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
# RUN rm /app/requirements.txt # curate_bot が最後なので、削除は任意

# COPY bots/analyze_bot/requirements.txt /app/
# RUN pip install --no-cache-dir -r /app/analyze_bot_requirements.txt

# アプリケーションコードのコピー
COPY bots /app/bots
COPY config /app/config
COPY utils /app/utils
# COPY tests /app/tests/ # テストを実行する場合

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"
# Tesseractが日本語と英語のデータファイルを見つけられるようにTESSDATA_PREFIXを設定
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# (cronを使用する場合の設定は、entrypoint.sh等で対応するためここではコメントアウト)
# COPY docker/crontab /etc/cron.d/app-cron
# RUN chmod 0644 /etc/cron.d/app-cron
# RUN crontab /etc/cron.d/app-cron

# (entrypoint.shも後で定義)
# COPY docker/entrypoint.sh /entrypoint.sh
# RUN chmod +x /entrypoint.sh
# ENTRYPOINT ["/entrypoint.sh"]

# コンテナが起動し続けるようにする（開発・テスト用）
# 最終的なコマンドは、実行したいタスクに合わせて変更
CMD ["tail", "-f", "/dev/null"]