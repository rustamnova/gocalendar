#!/bin/bash

# === Настройки ===
BOT_NAME="gocalendar"
BOT_DIR="/root/.bots/$BOT_NAME"
SESSION_NAME="$BOT_NAME"
LOG_FILE="/root/.masterbot_logs/install_${BOT_NAME}.log"
SCRIPTS_DIR="/root/.masterbot_scripts"

# === Логирование установки ===
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "🚀 Установка $BOT_NAME..."

# === Подготовка директорий ===
mkdir -p "$BOT_DIR"

# === Ввод .env ===
ENV_PATH="$BOT_DIR/.env"
echo "📥 Вставьте .env (GITHUB_TOKEN, BOT_TOKEN, OPENAI_API_KEY), затем нажмите Ctrl+D:"
cat > "$ENV_PATH"
echo "✅ .env сохранён в: $ENV_PATH"

# === Проверка дублей токена ===
INSTALL_TOKEN=$(grep BOT_TOKEN= "$ENV_PATH" | cut -d= -f2)
DUPLICATES=$(grep -hR BOT_TOKEN= /root/.bots/*/.env | grep "$INSTALL_TOKEN" | wc -l)
if [[ "$DUPLICATES" -gt 1 ]]; then
  echo "❌ Этот BOT_TOKEN уже используется другим ботом!"
  grep -hR BOT_TOKEN= /root/.bots/*/.env | grep "$INSTALL_TOKEN"
  exit 1
fi

# === Проверка GitHub-доступа ===
source "$ENV_PATH"
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "❌ GITHUB_TOKEN не задан!"
  exit 1
fi

echo "🔐 Проверка доступа к GitHub..."
git ls-remote https://rustamnova:$GITHUB_TOKEN@github.com/rustamnova/$BOT_NAME.git &>/dev/null
if [ $? -ne 0 ]; then
  echo "❌ GitHub-доступ не получен. Проверь токен или репозиторий."
  exit 1
fi

# === Установка зависимостей ===
echo "📦 Установка системных пакетов..."
apt update
apt install -y software-properties-common git screen python-is-python3
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.12 python3.12-venv python3.12-dev libffi-dev libssl-dev ffmpeg build-essential

# === Клонирование ===
echo "🌐 Клонируем $BOT_NAME..."
rm -rf "$BOT_DIR"
git clone https://rustamnova:$GITHUB_TOKEN@github.com/rustamnova/$BOT_NAME.git "$BOT_DIR" || {
  echo "❌ Ошибка клонирования"
  exit 1
}

# === Восстановление .env ===
echo "🔄 Восстанавливаем .env..."
echo "$(<$ENV_PATH)" > "$BOT_DIR/.env"

# === Python-окружение (без вложенной venv/venv) ===
cd "$BOT_DIR" || exit 1
echo "🐍 Установка Python-зависимостей..."
python3.12 -m venv ./venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# === Копирование скриптов (если есть) ===
echo "📁 Копируем скрипты..."
mkdir -p "$SCRIPTS_DIR"
if [ -d "Scripts" ]; then
  cp Scripts/*.sh "$SCRIPTS_DIR"
  chmod +x "$SCRIPTS_DIR"/*.sh
fi

# === start.sh ===
echo "⚙️ Создаём start.sh..."
cat <<EOF > start.sh
#!/bin/bash
cd "\$(dirname "\$0")"
source venv/bin/activate
STDOUT_LOG="log.txt"
STDERR_LOG="error.log"
touch \$STDOUT_LOG \$STDERR_LOG
echo "[\$(date)] Запуск $BOT_NAME..." >> \$STDOUT_LOG
python gocalendar.py >> \$STDOUT_LOG 2>> \$STDERR_LOG
EOF

chmod +x start.sh

# === screen перезапуск ===
if screen -list | grep -q "\\.${SESSION_NAME}"; then
  echo "🧹 Завершаем старую screen-сессию..."
  screen -S "$SESSION_NAME" -X quit
fi

echo "📺 Запускаем $BOT_NAME в screen: $SESSION_NAME"
screen -dmS "$SESSION_NAME" "$BOT_DIR/start.sh"

# === Финал ===
echo "✅ $BOT_NAME установлен и запущен!"
echo "📄 Лог установки: $LOG_FILE"
echo "📁 stdout: $BOT_DIR/log.txt"
echo "🚨 stderr: $BOT_DIR/error.log"
echo "📂 screen -r $SESSION_NAME"

# tail логов
echo "📤 Последние строки stdout:"
tail -n 50 "$BOT_DIR/log.txt"
if [ -s "$BOT_DIR/error.log" ]; then
  echo "🚨 Обнаружены ошибки:"
  tail -n 10 "$BOT_DIR/error.log"
else
  echo "✅ Ошибок не обнаружено в error.log"
fi
