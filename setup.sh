#!/bin/bash

echo "🚀 Начинаем установку бота GoCalendar..."

# === Переменные ===
GIT_TOKEN="GIT_TOKEN_REMOVED_2"
GIT_USER="rustamnova"
GIT_REPO="gocalendar"
CLONE_URL="https://${GIT_TOKEN}@github.com/${GIT_USER}/${GIT_REPO}.git"
PROJECT_DIR="$HOME/$GIT_REPO"

# === Установка Python 3.10 и системных библиотек ===
echo "📦 Устанавливаем зависимости и Python 3.10..."
apt update
apt install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.10 python3.10-venv python3.10-dev screen git build-essential libffi-dev libssl-dev python-is-python3

# === Удаление старой версии ===
echo "🧹 Удаляем старую версию..."
rm -rf "$PROJECT_DIR"

# === Клонирование проекта ===
echo "📥 Клонируем проект с GitHub..."
git clone "$CLONE_URL" "$PROJECT_DIR"
if [ $? -ne 0 ]; then
  echo "❌ Ошибка клонирования. Проверь токен и доступ."
  exit 1
fi
cd "$PROJECT_DIR" || exit 1

# === Виртуальное окружение ===
echo "🐍 Создаём виртуальное окружение на Python 3.10..."
python3.10 -m venv venv
source venv/bin/activate

# === Установка зависимостей ===
echo "📚 Устанавливаем зависимости..."
pip install --upgrade pip

while IFS= read -r dep || [[ -n "$dep" ]]; do
  if [[ -n "$dep" ]]; then
    echo "➡ pip install $dep"
    pip install "$dep" || echo "⚠️ Ошибка при установке $dep — пропускаем"
  fi
done < requirements.txt

# === Проверка на наличие основного скрипта ===
if [ ! -f "gocalendar.py" ]; then
  echo "❌ Файл gocalendar.py не найден в $PROJECT_DIR"
  exit 1
fi

# === Скрипт запуска бота ===
cat <<'EOS' > start.sh
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
touch log.txt
python gocalendar.py >> log.txt 2>&1
EOS

chmod +x start.sh

# === Завершение старых screen-сессий ===
echo "🧹 Завершаем старые screen-сессии 'gocalendar'..."
screen -ls | grep '\.gocalendar' | awk '{print $1}' | xargs -r -n 1 -I{} screen -S {} -X quit

# === Запуск нового screen ===
echo "📺 Запускаем бота в новой screen-сессии..."
screen -dmS gocalendar "$PROJECT_DIR/start.sh"

echo "✅ Бот запущен! Чтобы подключиться: screen -r gocalendar"
