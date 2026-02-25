import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from openai import OpenAI
import asyncio

# === Подготовка логов ===
import sys as _sys
from logging.handlers import RotatingFileHandler

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGS_DIR = os.path.join(_BASE_DIR, "logs")
os.makedirs(_LOGS_DIR, exist_ok=True)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# worklog.txt — рабочие процессы (INFO+), ротация 10 МБ × 5
_worklog_handler = RotatingFileHandler(
    os.path.join(_LOGS_DIR, "worklog.txt"), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_worklog_handler.setLevel(logging.INFO)
_worklog_handler.setFormatter(_fmt)

# errors.txt — только ошибки (ERROR+), ротация 5 МБ × 3
_error_handler = RotatingFileHandler(
    os.path.join(_LOGS_DIR, "errors.txt"), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_error_handler.setLevel(logging.ERROR)
_error_handler.setFormatter(_fmt)

_console_handler = logging.StreamHandler(_sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_worklog_handler, _error_handler, _console_handler])


def log_install(msg: str):
    with open(os.path.join(_LOGS_DIR, "install.txt"), "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

# === Переменные окружения ===
load_dotenv(override=True)
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")
SERVICE_ACCOUNT_FILE = "credentials.json"
USER_IDS = list(map(int, os.getenv("USER_IDS", "").split(",")))

# === Проверка обязательных файлов ===
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    raise FileNotFoundError("❌ Не найден файл credentials.json в корне проекта")

# === Инициализация сервисов ===
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)
client = OpenAI(api_key=OPENAI_API_KEY)

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/calendar"])
calendar_service = build('calendar', 'v3', credentials=creds)

# === Вспомогательные функции ===
import random
from datetime import datetime, time

def ask_gpt_for_date(text):
    current_year = datetime.now().year
    prompt = (
        "Проанализируй текст. Найди дату начала мероприятия в тексте поста и страницы:\n"
        f"{text}\n\n"
        f"Если указано несколько дат, выбери первую.\n"
        f"Если год не указан, используй {current_year}.\n"
        "Игнорируй время — верни только дату.\n"
        "Ответ верни строго в формате: ГГГГ-ММ-ДД"
    )

    preferred_models = ["gpt-5.2", "gpt-5.1", "gpt-4.1", "gpt-4o", "gpt-3.5-turbo"]

    for model_name in preferred_models:
        try:
            logging.info(f"🔍 Пробуем модель: {model_name}")
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )

            gpt_reply = response.choices[0].message.content.strip().rstrip(" .")
            date_part = datetime.strptime(gpt_reply, "%Y-%m-%d").date()

            # 🎲 Случайное время от 03:00 до 23:00
            hour = random.randint(3, 23)
            minute = random.choice([0, 15, 30, 45])
            random_time = time(hour=hour, minute=minute)

            final_dt = datetime.combine(date_part, random_time)
            logging.info(f"📅 Распознана дата: {final_dt}")
            return final_dt

        except Exception as e:
            logging.warning(f"⚠️ Ошибка с моделью {model_name}: {e}")
            continue

    logging.error("❌ Не удалось распознать дату ни с одной моделью GPT.")
    return None


def extract_urls(text: str) -> list[str]:
    return re.findall(r'(https?://\S+)', text)

def extract_urls_from_message(message: Message) -> list[str]:
    urls = extract_urls(message.text or message.caption or "")
    entities = message.entities or message.caption_entities or []
    for entity in entities:
        if entity.type == "text_link":
            urls.append(entity.url)
    return list(set(urls))

def expand_links_in_text(text: str, entities) -> str:
    """Вставляет URL прямо после текста каждой гиперссылки (text_link entity).
    Telegram offsets работают в UTF-16 code units, поэтому используем encode('utf-16-le')."""
    link_entities = [e for e in (entities or []) if e.type == "text_link"]
    if not link_entities:
        return text

    encoded = text.encode("utf-16-le")
    parts = []
    prev = 0  # позиция в байтах UTF-16-LE

    for entity in sorted(link_entities, key=lambda e: e.offset):
        start = entity.offset * 2
        end = (entity.offset + entity.length) * 2
        parts.append(encoded[prev:start].decode("utf-16-le"))
        parts.append(encoded[start:end].decode("utf-16-le"))
        parts.append(f": {entity.url}")
        prev = end

    parts.append(encoded[prev:].decode("utf-16-le"))
    return "".join(parts)

def extract_date_from_page_or_message(text, url=None):
    try:
        page_text = ""
        if url:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text(" ", strip=True)
        combined_text = (text + "\n" + page_text).strip()
        return ask_gpt_for_date(combined_text[:3500])
    except Exception as e:
        logging.warning(f"⚠️ Ошибка при извлечении даты: {e}")
        return None

def event_already_exists(description: str) -> bool:
    try:
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat()

        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=30,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        for event in events_result.get('items', []):
            if event.get("description", "").strip() == description.strip():
                return True
    except Exception as e:
        logging.error(f"❌ Ошибка проверки дубликатов: {e}")
    return False

def create_calendar_event(summary, description, start_dt):
    if event_already_exists(description):
        logging.info("⏭️ Событие уже существует — пропускаем.")
        return
    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Europe/Moscow'},
        'end': {'dateTime': (start_dt + timedelta(hours=1)).isoformat(), 'timeZone': 'Europe/Moscow'},
    }
    try:
        calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        logging.info(f"✅ Добавлено событие: {summary} — {start_dt}")
    except Exception as e:
        logging.error(f"❌ Ошибка при добавлении события: {e}")

# === Команда /start ===
@router.message(CommandStart())
async def cmd_start(message: Message):
    sender_id = message.from_user.id if message.from_user else None
    if sender_id not in USER_IDS:
        logging.warning("⛔ Неавторизованный /start от %s", sender_id)
        return
    await message.answer(
        "👋 Привет! Я GoCalendar — автоматически добавляю события в Google Календарь.\n\n"
        "Что умею:\n"
        "• Принять ссылку на анонс или текст с датой\n"
        "• Распознать дату и название мероприятия\n"
        "• Добавить событие в Google Календарь\n\n"
        "Просто пришли ссылку или текст мероприятия 📅"
    )


# === Обработка сообщений ===
@router.message()
async def handle_message(message: Message):
    sender_id = message.from_user.id if message.from_user else None
    is_bot = message.from_user.is_bot if message.from_user else False

    logging.info(f"📩 Получено сообщение от {'бота' if is_bot else 'пользователя'} {sender_id}")

    if sender_id not in USER_IDS:
        logging.warning("⛔ Неавторизованный пользователь. Игнорируем.")
        return

    text = message.text or message.caption or ""
    urls = extract_urls_from_message(message)
    url = urls[0] if urls else None

    logging.info(f"🔍 Начинаем анализ текста. URL: {url or '–'}")

    status = await message.answer("🔍 Определяю дату мероприятия...")

    dt = extract_date_from_page_or_message(text, url)
    if dt:
        try:
            await status.edit_text("📅 Добавляю событие в Google Календарь...")
            summary = (text or url)[:30] + "..."
            entities = message.entities or message.caption_entities or []
            description = expand_links_in_text(text, entities)
            create_calendar_event(summary, description, dt)
            await status.edit_text(f"✅ Добавлено в календарь: {dt.strftime('%d.%m.%Y %H:%M')}")
        except Exception as e:
            logging.error(f"❌ Ошибка при создании события: {e}")
            await status.edit_text("❌ Ошибка при добавлении в календарь.")
    else:
        await status.edit_text("📭 Не удалось определить дату мероприятия.")
        logging.info("📭 Дата не найдена в сообщении.")

# === Запуск бота ===
async def on_startup():
    for uid in USER_IDS:
        try:
            await bot.send_message(uid, "✅ GoCalendar запущен! Пришли анонс или ссылку — добавлю в Google Календарь 📅")
        except Exception:
            pass


async def main():
    log_install(f"=== Запуск Gocalendar === (Python {_sys.version.split()[0]})")
    logging.info("🚀 Gocalendar бот запущен")
    try:
        await dp.start_polling(bot, allowed_updates=["message"], on_startup=on_startup)
    finally:
        log_install("=== Остановка Gocalendar ===")

if __name__ == '__main__':
    asyncio.run(main())
