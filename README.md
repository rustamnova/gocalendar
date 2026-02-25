# GoCalendar — бот для Google Календаря

Telegram-бот, который автоматически добавляет события в Google Calendar. Получает текст или ссылку на анонс мероприятия, извлекает дату и название через GPT и создаёт событие через Google Calendar API.

## Возможности

- Распознавание даты и названия мероприятия из текста (GPT)
- Скрапинг анонсов по ссылке (afisha.ru, timepad, VK и др.)
- Добавление событий в Google Calendar через Service Account
- Проверка дублей перед добавлением
- Поддержка пересланных сообщений и прямых ссылок

## Установка

```bash
git clone https://github.com/rustamnova/gocalendar.git /root/.bots/gocalendar
cd /root/.bots/gocalendar
bash install.sh
```

Поместите `credentials.json` (Service Account Google) в папку бота.

## Переменные окружения (`.env`)

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен Telegram-бота |
| `OPENAI_API_KEY` | API-ключ OpenAI (GPT для распознавания дат) |
| `CALENDAR_ID` | ID календаря (по умолчанию: `primary`) |

## Управление

```bash
bash start.sh      # Запуск
bash stop.sh       # Остановка
bash restart.sh    # Перезапуск
screen -r gocalendar  # Подключиться к сессии
```

## Использование

Отправьте боту текст анонса мероприятия или ссылку на страницу события — бот извлечёт дату и название и добавит событие в Google Calendar.

## Команды бота

| Команда | Действие |
|---|---|
| `/start` | Справка |

## Логи

```
logs/
├── worklog.txt   # Рабочий лог (INFO+)
├── errors.txt    # Ошибки (ERROR+)
└── install.txt   # Запуски и остановки
```
