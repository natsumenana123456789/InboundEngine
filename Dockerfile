# Python 3.9のベースイメージを使用
FROM python:3.9-slim

# 必要なシステムパッケージのインストール
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Chromeのインストール
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# 必要なPythonパッケージのインストール
COPY auto_post_bot/requirements.txt auto_post_bot_requirements.txt
COPY curate_bot/requirements.txt curate_bot_requirements.txt
RUN pip install --no-cache-dir -r auto_post_bot_requirements.txt -r curate_bot_requirements.txt

# ChromeDriverのインストール前にChromeのバージョンを確認
RUN google-chrome --version

# ChromeDriverのインストール（バージョンは後で合わせて修正）
# ENV CHROMEDRIVER_VERSION=123.0.6312.86
# RUN wget -q "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" \
#     && unzip chromedriver_linux64.zip \
#     && mv chromedriver /usr/local/bin/ \
#     && rm chromedriver_linux64.zip

# アプリケーションコードのコピー
COPY auto_post_bot /app/auto_post_bot
COPY curate_bot /app/curate_bot
COPY chrome_profiles /app/chrome_profiles

# 定期実行用のcron設定
COPY docker/crontab /etc/cron.d/app-cron
RUN chmod 0644 /etc/cron.d/app-cron
RUN crontab /etc/cron.d/app-cron

# 環境変数の設定
ENV PYTHONUNBUFFERED=1

# 起動スクリプトの作成
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ENTRYPOINT ["/entrypoint.sh"]