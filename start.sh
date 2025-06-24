#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

STDOUT_LOG="log.txt"
STDERR_LOG="error.log"
touch "$STDOUT_LOG" "$STDERR_LOG"

echo "[ $(date) ] 🚀 Запуск Python-бота..." >> "$STDOUT_LOG"

# Запускаем первый .py-файл в директории
exec python "$(ls *.py | head -n 1)" >> "$STDOUT_LOG" 2>> "$STDERR_LOG"
