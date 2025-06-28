#!/bin/bash

echo "🚀 Универсальная установка Telegram-бота..."

WORKDIR="/root/.bots"
mkdir -p "$WORKDIR"

# === Шаг 1: Получение .env ===
echo "📥 Вставьте .env файл (GITHUB_TOKEN, BOT_TOKEN, OPENAI_API_KEY, REPO_URL), затем нажмите Ctrl+D:"
ENV_TEMP=$(mktemp)
cat > "$ENV_TEMP"
source "$ENV_TEMP"

# === Проверка переменных ===
if [[ -z "$GITHUB_TOKEN" || -z "$BOT_TOKEN" || -z "$REPO_URL" ]]; then
  echo "❌ Не заданы GITHUB_TOKEN, BOT_TOKEN или REPO_URL"
  exit 1
fi

# === Шаг 2: Клонирование репозитория ===
REPO=$(echo "$REPO_URL" | sed -E 's|https://github.com/||;s|\.git$||')
BOT_NAME=$(basename "$REPO")
BOT_DIR="$WORKDIR/$BOT_NAME"
LOG_DIR="$BOT_DIR/logs"
INSTALL_LOG="$LOG_DIR/install.log"

mkdir -p "$LOG_DIR"
echo "[ $(date) ] 🚧 Установка $BOT_NAME" > "$INSTALL_LOG"

echo "🌐 Клонируем репозиторий $REPO_URL → $BOT_DIR" | tee -a "$INSTALL_LOG"
rm -rf "$BOT_DIR"
git clone https://$GITHUB_TOKEN@github.com/$REPO.git "$BOT_DIR" >> "$INSTALL_LOG" 2>&1 || {
  echo "❌ Ошибка клонирования" | tee -a "$INSTALL_LOG"
  exit 1
}

cp "$ENV_TEMP" "$BOT_DIR/.env"
rm "$ENV_TEMP"
cd "$BOT_DIR" || exit 1

if [ ! -f "$BOT_NAME.py" ]; then
  echo "❌ Не найден файл $BOT_NAME.py" | tee -a "$INSTALL_LOG"
  exit 1
fi

echo "📦 Установка зависимостей..." | tee -a "$INSTALL_LOG"
apt update >> "$INSTALL_LOG" 2>&1
apt install -y python3.12 python3.12-venv python3.12-dev git screen ffmpeg build-essential >> "$INSTALL_LOG" 2>&1

echo "🐍 Настройка Python-окружения..." | tee -a "$INSTALL_LOG"
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip >> "$INSTALL_LOG" 2>&1
pip install -r requirements.txt >> "$INSTALL_LOG" 2>&1 || true

echo "⚙️ Генерация start.sh..." | tee -a "$INSTALL_LOG"
cat <<EOF > start.sh
#!/bin/bash
cd "\$(dirname "\$0")"
source venv/bin/activate
mkdir -p logs
touch logs/run.log logs/error.log
echo "[ \$(date) ] ▶️ Запуск \$BOT_NAME..." >> logs/run.log
exec python $BOT_NAME.py >> logs/run.log 2>> logs/error.log
EOF
chmod +x start.sh

echo "🧹 Завершаем старые screen-сессии: $BOT_NAME" | tee -a "$INSTALL_LOG"
screen -ls | grep "\.${BOT_NAME}" | awk '{print $1}' | while read -r session_id; do
  screen -S "$session_id" -X quit
done

echo "📺 Запуск новой screen-сессии..." | tee -a "$INSTALL_LOG"
screen -dmS "$BOT_NAME" "$BOT_DIR/start.sh"

sleep 1
if screen -list | grep -q "\.${BOT_NAME}"; then
  echo "✅ Бот $BOT_NAME запущен в screen-сессии" | tee -a "$INSTALL_LOG"
else
  echo "❌ Ошибка запуска screen-сессии" | tee -a "$INSTALL_LOG"
fi

echo "ℹ️ Подключиться: screen -r $BOT_NAME" | tee -a "$INSTALL_LOG"
