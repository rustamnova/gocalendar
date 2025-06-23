#!/bin/bash

# Переход в папку скрипта
cd "$(dirname "$0")"

# Активация виртуального окружения
source venv/bin/activate

# Имя бота
BOT_NAME="gocalendar"

# Файлы логов
STDOUT_LOG="log.txt"
STDERR_LOG="error.log"

# Создание логов, если их нет
touch "$STDOUT_LOG" "$STDERR_LOG"

# Запуск с логированием
echo "[ $(date) ] ▶️ Запуск бота $BOT_NAME..." >> "$STDOUT_LOG"
exec python "$BOT_NAME.py" >> "$STDOUT_LOG" 2>> "$STDERR_LOG"
