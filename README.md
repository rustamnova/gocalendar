# GoCalendar Bot

Telegram-бот для автоматического добавления городских мероприятий в Google Calendar.  
Администратор отправляет ссылку или текст анонса — бот определяет дату и добавляет событие.

> **Примечание:** Этот репозиторий содержит admin-версию бота. Публичная версия с поддержкой пользователей, реферальной программой и статистикой — [CalendarGo](https://github.com/rustamnova/calendargo).

---

## Возможности

- **Умное распознавание дат** — несколько стратегий:
  1. JSON-LD Schema.org (`Event`, `MusicEvent`, `TheaterEvent` и др.)
  2. HTML мета-теги (`event:start_date`, `article:published_time`)
  3. Регулярные выражения (`DD.MM.YYYY`, `DD.MM`, `DD месяц [YYYY]`)
  4. GPT (gpt-4.1 / gpt-4o / gpt-3.5-turbo) с подсказками из regex
- **Шаг подтверждения** — перед добавлением показывает найденную дату, позволяет изменить
- **Просмотр событий по датам** — навигация ◀/▶, inline-выбор из календаря
- **Управление событиями** — перенос на другую дату, удаление с подтверждением
- **Защита от дублей** — проверяет description перед добавлением
- **Telegram Stories** — корректно обрабатывает ссылки на статусы (просит скопировать текст)
- **Доступ по списку** — только авторизованные `USER_IDS` могут управлять ботом

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| Telegram Bot | [aiogram 3](https://docs.aiogram.dev/) |
| Google Calendar | Google Calendar API v3 (Service Account) |
| Парсинг страниц | requests + BeautifulSoup4 |
| Распознавание дат | OpenAI API (gpt-4.1 / gpt-4o / gpt-3.5-turbo) |
| Inline-календарь | [aiogram-calendar](https://github.com/KeyZenD/aiogram_calendar) |

---

## Установка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/rustamnova/gocalendar.git
cd gocalendar
```

### 2. Создать виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Настроить переменные окружения

```bash
cp .env.example .env
nano .env
```

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | Токен бота от [@BotFather](https://t.me/BotFather) |
| `OPENAI_API_KEY` | API-ключ OpenAI для распознавания дат |
| `CALENDAR_ID` | ID Google Calendar (`primary` или `...@group.calendar.google.com`) |
| `USER_IDS` | Telegram ID авторизованных пользователей через запятую |

### 4. Настроить Google Calendar (Service Account)

1. Создать проект в [Google Cloud Console](https://console.cloud.google.com/)
2. Включить **Google Calendar API**
3. Создать Service Account → скачать JSON-ключ → сохранить как `credentials.json` в корне проекта
4. В настройках Google Calendar → поделиться с email сервисного аккаунта (роль: редактор)

### 5. Запустить

```bash
python gocalendar.py
```

Или через screen для фонового запуска:

```bash
screen -dmS gocalendar bash -c 'venv/bin/python gocalendar.py'
```

---

## Использование

После запуска бот доступен только для `USER_IDS` из `.env`.

**Добавить мероприятие:**  
Отправь ссылку на анонс или текст с датой. Бот покажет найденную дату — подтверди или скорректируй.

**Посмотреть мероприятия:**  
Команда `/events` или кнопка меню — навигация по датам.

**Управление событием:**  
Нажми на название мероприятия → кнопки «Перенести» / «Удалить».

---

## Структура проекта

```
gocalendar/
├── gocalendar.py       # Основной файл бота
├── daily_report.py     # Скрипт ежедневного отчёта (cron)
├── requirements.txt    # Зависимости Python
├── install.sh          # Скрипт установки
├── start.sh / stop.sh  # Управление процессом
├── .env.example        # Шаблон переменных окружения
├── credentials.json    # Service Account ключ (НЕ коммитить!)
└── logs/               # Логи (НЕ коммитить!)
```

---

## Лицензия

MIT
