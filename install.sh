#!/bin/bash

echo "🚀 Установка GoCalendar Bot..."

# === Настройка переменных ===
BOT_NAME="gocalendar"
BOT_DIR="/root/.bots/$BOT_NAME"
ENV_FILE="$BOT_DIR/.env"
SESSION_NAME="$BOT_NAME"

# === Запрос переменных окружения ===
echo "📥 Вставьте весь .env (GITHUB_TOKEN, BOT_TOKEN, OPENAI_API_KEY), затем нажмите Ctrl+D:"
mkdir -p "$BOT_DIR"
cat > "$ENV_FILE"
echo "✅ .env сохранён в $ENV_FILE"

# === Загрузка переменных ===
source "$ENV_FILE"

# === Проверка переменных ===
if [[ -z "$GITHUB_TOKEN" || -z "$BOT_TOKEN" || -z "$OPENAI_API_KEY" ]]; then
  echo "❌ Один из токенов не задан. Проверь содержимое .env"
  exit 1
fi

# === Проверка GitHub-доступа ===
echo "🔐 Проверка доступа к приватному репозиторию..."
git ls-remote https://rustamnova:$GITHUB_TOKEN@github.com/rustamnova/$BOT_NAME.git &>/dev/null
if [ $? -ne 0 ]; then
  echo "❌ Ошибка авторизации в GitHub. Проверь GITHUB_TOKEN."
  exit 1
fi

# === Установка зависимостей ===
echo "📦 Установка зависимостей..."
apt update
apt install -y software-properties-common git screen python-is-python3
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.12 python3.12-venv python3.12-dev libffi-dev libssl-dev ffmpeg build-essential

# === Очистка и клонирование проекта ===
echo "🌐 Клонируем $BOT_NAME в $BOT_DIR..."
rm -rf "$BOT_DIR"
git clone https://rustamnova:$GITHUB_TOKEN@github.com/rustamnova/$BOT_NAME.git "$BOT_DIR" || {
  echo "❌ Ошибка клонирования репозитория."
  exit 1
}

cd "$BOT_DIR" || { echo "❌ Не удалось перейти в директорию $BOT_DIR"; exit 1; }

# === Создание виртуального окружения ===
echo "🐍 Создаём виртуальное окружение..."
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# === Создание start.sh ===
echo "⚙️ Создаём start.sh..."
cat <<EOF > start.sh
#!/bin/bash
cd "\$(dirname "\$0")"
source venv/bin/activate
touch log.txt
echo "[\$(date)] Запуск $BOT_NAME..." >> log.txt
python gocalendar.py >> log.txt 2>&1
EOF

chmod +x start.sh

# === Запуск screen-сессии ===
if screen -list | grep -q "\\.${SESSION_NAME}"; then
  echo "🧹 Завершаем старую screen-сессию..."
  screen -S "$SESSION_NAME" -X quit
fi

echo "📺 Запускаем бота в новой screen-сессии: $SESSION_NAME"
screen -dmS "$SESSION_NAME" "$BOT_DIR/start.sh"

echo "✅ Бот $BOT_NAME установлен и запущен!"
echo "ℹ️ Подключиться: screen -r $SESSION_NAME"
