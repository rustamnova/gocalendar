#!/bin/bash

echo "🚀 Начинаем установку бота GoCalendar..."

# === Переменные ===
GIT_TOKEN="GIT_TOKEN_REMOVED_2"
GIT_USER="rustamnova"
GIT_REPO="gocalendar"
CLONE_URL="https://${GIT_TOKEN}@github.com/${GIT_USER}/${GIT_REPO}.git"
PROJECT_DIR="$HOME/$GIT_REPO"

# === 0. Установка screen и python-is-python3 (если не установлены) ===
echo "📦 Устанавливаем необходимые утилиты..."
apt update
apt install -y screen python-is-python3 build-essential python3-dev libffi-dev libssl-dev git

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

cd "$PROJECT_DIR" || exit 1

# === 3. Виртуальное окружение ===
echo "🐍 Создаем виртуальное окружение..."
python3 -m venv venv
source venv/bin/activate

# === 4. Установка Python-зависимостей ===
echo "📚 Устанавливаем зависимости..."
pip install --upgrade pip

while IFS= read -r dep || [[ -n "$dep" ]]; do
  if [[ -n "$dep" ]]; then
    echo "➡ pip install $dep"
    pip install "$dep" || echo "⚠️ Ошибка при установке $dep — пропускаем"
  fi
done < requirements.txt

# === 5. Проверка на наличие скрипта бота ===
if [ ! -f "$PROJECT_DIR/gocalendar.py" ]; then
  echo "❌ Файл gocalendar.py не найден в $PROJECT_DIR"
  exit 1
fi

# === 6. Скрипт запуска бота ===
cat <<'EOS' > start.sh
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python gocalendar.py >> log.txt 2>&1
EOS

chmod +x start.sh

# === 7. Завершение и удаление старых screen-сессий с тем же именем ===
echo "🧹 Завершаем старые screen-сессии 'gocalendar'..."
screen -ls | grep '\.gocalendar' | awk '{print $1}' | xargs -r -n 1 screen -S {} -X quit

# === 8. Запуск в screen ===
echo "📺 Запускаем бота в screen-сессии..."
screen -dmS gocalendar "$PROJECT_DIR/start.sh"

echo "✅ Бот запущен в screen. Чтобы войти: screen -r gocalendar"
