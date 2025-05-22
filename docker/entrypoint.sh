#!/bin/bash

# cronの起動
service cron start

# ログファイルの作成
touch /var/log/cron.log

# アプリケーションの起動
cd /app/auto_post_bot
python post_tweet.py