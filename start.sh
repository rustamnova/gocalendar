#!/bin/bash
cd "$(dirname "$0")"
BOT_NAME=$(basename "$(pwd)")
source venv/bin/activate
mkdir -p logs
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ▶️ Запуск $BOT_NAME..." >> logs/worklog.txt
python $BOT_NAME.py 2>> logs/errors.txt
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⏹ $BOT_NAME остановлен (exit $?)" >> logs/worklog.txt
