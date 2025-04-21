#!/bin/bash

echo "🚀 Начинаем установку бота GoCalendar..."

# Перейти в домашнюю директорию
cd ~

# Удалить старую копию при необходимости
rm -rf gocalendar

# Клонировать свежую версию
git clone https://<rustamnova>:<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>@github.com/rustamnova/gocalendar.git
cd gocalendar

# Обновить apt и установить зависимости для сборки Python пакетов
apt update && apt install -y build-essential python3-dev git

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Обновить pip
pip install --upgrade pip

# Установить зависимости
pip install -r requirements.txt

# Запустить бота
echo "✅ Все готово. Запускаем GoCalendar..."
python gocalendar.py
