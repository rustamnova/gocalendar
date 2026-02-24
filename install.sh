#!/bin/bash

WORKDIR="/root/.bots"
mkdir -p "$WORKDIR"

# === Шаг 1: Получение .env ===
echo "📥 Вставьте .env файл (BOT_TOKEN, GITHUB_TOKEN, REPO_URL, ...), затем нажмите Ctrl+D:"
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

echo "🌐 Клонируем репозиторий $REPO_URL → $BOT_DIR"
rm -rf "$BOT_DIR"
git clone https://$GITHUB_TOKEN@github.com/$REPO.git "$BOT_DIR" || {
  echo "❌ Ошибка клонирования"
  exit 1
}

# === Инициализация директории логов ===
mkdir -p "$BOT_DIR/logs"
INSTALL_LOG="$BOT_DIR/logs/install.txt"
touch "$INSTALL_LOG"

# Все дальнейшие echo пишутся и в консоль, и в install.txt
exec > >(tee -a "$INSTALL_LOG") 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 Установка бота $BOT_NAME начата"

# === Копирование .env ===
cp "$ENV_TEMP" "$BOT_DIR/.env"
rm "$ENV_TEMP"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ .env скопирован"

# === Переход в директорию и проверка основного .py файла ===
cd "$BOT_DIR" || exit 1
if [ ! -f "$BOT_NAME.py" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Не найден файл $BOT_NAME.py"
  exit 1
fi

# === Установка системных пакетов ===
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 📦 Установка системных зависимостей..."
apt update -qq
apt install -y python3.12 python3.12-venv python3.12-dev git screen ffmpeg build-essential
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Системные пакеты установлены"

# === Виртуальное окружение ===
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🐍 Настройка Python-окружения..."
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt || true
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Python-окружение готово"

# === Генерация скриптов ===
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚙️ Генерация скриптов..."

cat > start.sh << 'STARTEOF'
#!/bin/bash
cd "$(dirname "$0")"
BOT_NAME=$(basename "$(pwd)")
source venv/bin/activate
mkdir -p logs
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ▶️ Запуск $BOT_NAME..." >> logs/worklog.txt
python $BOT_NAME.py 2>> logs/errors.txt
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⏹ $BOT_NAME остановлен (exit $?)" >> logs/worklog.txt
STARTEOF

cat > stop.sh << 'STOPEOF'
#!/bin/bash
cd "$(dirname "$0")"
BOT_NAME=$(basename "$(pwd)")
SESSION_NAME="$BOT_NAME"
if screen -list | grep -q "\.${SESSION_NAME}"; then
  echo "🛑 Остановка screen-сессии $SESSION_NAME..."
  screen -S "$SESSION_NAME" -X quit
  echo "✅ $BOT_NAME остановлен."
else
  echo "⚠️ screen-сессия $SESSION_NAME не найдена."
fi
STOPEOF

cat > restart.sh << 'RESTARTEOF'
#!/bin/bash
cd "$(dirname "$0")"
BOT_NAME=$(basename "$(pwd)")
SESSION_NAME="$BOT_NAME"
if screen -list | grep -q "\.${SESSION_NAME}"; then
  echo "🛑 Остановка screen-сессии $SESSION_NAME..."
  screen -S "$SESSION_NAME" -X quit
fi
echo "🔄 Перезапуск $BOT_NAME..."
screen -dmS "$SESSION_NAME" ./start.sh
echo "✅ $BOT_NAME перезапущен в screen: $SESSION_NAME"
RESTARTEOF

chmod +x start.sh stop.sh restart.sh
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Скрипты созданы"

# === Завершение старых screen-сессий ===
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🧹 Завершаем старые screen-сессии: $BOT_NAME"
screen -ls | grep "\.${BOT_NAME}" | awk '{print $1}' | while read -r session_id; do
  screen -S "$session_id" -X quit
done

# === Запуск новой screen-сессии ===
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 📺 Запуск новой screen-сессии..."
screen -dmS "$BOT_NAME" "$BOT_DIR/start.sh"

sleep 1
if screen -list | grep -q "\.${BOT_NAME}"; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Бот $BOT_NAME запущен в screen-сессии"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Ошибка запуска screen-сессии"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🏁 Установка завершена. Логи: $BOT_DIR/logs/"
echo "ℹ️  Подключиться: screen -r $BOT_NAME"
