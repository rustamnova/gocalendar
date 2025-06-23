#!/bin/bash

echo "🚀 Установка Telegram-бота с нуля..."

WORKDIR="/root/.bots"
mkdir -p "$WORKDIR"

# === Шаг 1: Получение .env ===
echo "📥 Вставьте .env файл (GITHUB_TOKEN, BOT_TOKEN, OPENAI_API_KEY, REPO_URL), затем нажмите Ctrl+D:"
ENV_TEMP=$(mktemp)
cat > "$ENV_TEMP"
source "$ENV_TEMP"

# === Проверка переменных ===
if [[ -z "$GITHUB_TOKEN" || -z "$BOT_TOKEN" || -z "$OPENAI_API_KEY" || -z "$REPO_URL" ]]; then
  echo "❌ Один из обязательных параметров в .env не задан"
  exit 1
fi

# === Определение BOT_NAME и путей ===
REPO=$(echo "$REPO_URL" | sed -E 's|https://github.com/||;s|\.git$||')
BOT_NAME=$(basename "$REPO")
BOT_DIR="$WORKDIR/$BOT_NAME"

echo "🌐 Клонируем $REPO_URL в $BOT_DIR"
rm -rf "$BOT_DIR"
git clone https://$GITHUB_TOKEN@github.com/$REPO.git "$BOT_DIR" || {
  echo "❌ Ошибка клонирования"
  exit 1
}

# === Копируем .env в папку бота ===
cp "$ENV_TEMP" "$BOT_DIR/.env"
rm "$ENV_TEMP"

# === Проверка наличия основного Python-файла ===
cd "$BOT_DIR" || exit 1
if [ ! -f "$BOT_NAME.py" ]; then
  echo "❌ Не найден основной Python-файл: $BOT_NAME.py"
  exit 1
fi

# === Шаг 4: Установка системных зависимостей ===
echo "📦 Установка зависимостей..."
apt update
apt install -y python3.12 python3.12-venv python3.12-dev git screen ffmpeg build-essential

# === Шаг 5: Настройка Python-окружения ===
echo "🐍 Создание виртуального окружения..."
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# === Шаг 6: Создание start.sh ===
echo "⚙️ Создание start.sh..."
cat <<EOF > start.sh
#!/bin/bash
cd "\$(dirname "\$0")"
source venv/bin/activate
touch log.txt error.log
echo "[\$(date)] Запуск $BOT_NAME..." >> log.txt
python $BOT_NAME.py >> log.txt 2>> error.log
EOF

chmod +x start.sh

# === Шаг 7: Завершение старых screen-сессий ===
echo "🧹 Завершаем старые screen-сессии с именем $BOT_NAME..."
screen -ls | grep "\.${BOT_NAME}" | awk '{print $1}' | while read -r session_id; do
  screen -S "$session_id" -X quit
done

# === Шаг 8: Запуск новой screen-сессии ===
echo "📺 Запускаем screen: $BOT_NAME"
screen -dmS "$BOT_NAME" bash "$BOT_DIR/start.sh"

sleep 1
if screen -list | grep -q "\.${BOT_NAME}"; then
  echo "✅ screen-сессия '$BOT_NAME' успешно создана"
else
  echo "❌ Ошибка запуска screen-сессии '$BOT_NAME'"
fi

echo "✅ Бот $BOT_NAME установлен и запущен!"
echo "ℹ️ Подключиться: screen -r $BOT_NAME"
