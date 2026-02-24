#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
mkdir -p logs
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ▶️ Запуск gocalendar..." >> logs/worklog.txt
python gocalendar.py 2>> logs/errors.txt
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⏹ gocalendar остановлен (exit $?)" >> logs/worklog.txt
