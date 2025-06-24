#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

BOT_NAME=$(basename "$(pwd)")
STDOUT_LOG="log.txt"
STDERR_LOG="error.log"

touch "$STDOUT_LOG" "$STDERR_LOG"

echo "[ $(date) ] ▶️ Запуск бота $BOT_NAME..." >> "$STDOUT_LOG"

exec python "$BOT_NAME.py" >> "$STDOUT_LOG" 2>> "$STDERR_LOG"
