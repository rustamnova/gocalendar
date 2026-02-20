#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
mkdir -p logs
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [start.sh] Запуск gocalendar..." >> logs/install.txt
exec python gocalendar.py 2>> logs/errors.txt
