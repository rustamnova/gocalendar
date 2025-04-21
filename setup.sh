#!/bin/bash

echo "🚀 Начинаем установку бота GoCalendar..."

# === Переменные ===
GIT_TOKEN="GIT_TOKEN_REMOVED_2"
GIT_USER="rustamnova"
GIT_REPO="gocalendar"
CLONE_URL="https://${GIT_TOKEN}@github.com/${GIT_USER}/${GIT_REPO}.git"
PROJECT_DIR="$HOME/$GIT_REPO"

# === 1. Очистка старой версии ===
echo "🧹 Удаляем старую версию..."
rm -rf "$PROJECT_DIR"

# === 2. Клонирование ===
echo "📦 Клонируем проект..."
git clone "$CLONE_URL" "$PROJECT_DIR"
if [ $? -ne 0 ]; then
  echo "❌ Ошибка клонирования. Проверь токен и доступ к репозиторию."
  exit 1
fi

cd "$PROJECT_DIR" || exit

# === 3. Установка системных зависимостей ===
echo "🔧 Устанавливаем системные библиотеки..."
apt update
apt install -y build-essential python3-dev libffi-dev libssl-dev git

# === 4. Виртуальное окружение ===
echo "🐍 Создаем виртуальное окружение..."
python3 -m venv venv
source venv/bin/activate

# === 5. Установка Python-зависимостей ===
echo "📚 Устанавливаем Python-библиотеки..."
cat <<EOF > requirements.txt
requests
beautifulsoup4
aiogram==2.25.2
google-api-python-client
google-auth
python-dateutil
google
openai
aiohttp
EOF

pip install --upgrade pip
pip install -r requirements.txt

# === 6. Запуск в screen  ===
echo "📺 Запускаем бота в screen-сессии..."
screen -dmS gocalendar bash -c "cd $PROJECT_DIR && source venv/bin/activate && python gocalendar.py"

echo "✅ Бот запущен в screen. Чтобы войти: screen -r gocalendar"

