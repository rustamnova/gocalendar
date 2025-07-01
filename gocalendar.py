import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from openai import OpenAI
import asyncio

# === Настройка логов ===
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/worklog.txt", mode="a", encoding="utf-8"),
        logging.FileHandler("logs/errors.txt", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ],
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# === Загрузка .env ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")
SERVICE_ACCOUNT_FILE = "credentials.json"
ALLOWED_BOTS = set(map(int, os.getenv("USER_IDS", "").split(",")))

# === Проверка credentials.json ===
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    raise FileNotFoundError("❌ Не найден файл credentials.json")

# === Статус переменных ===
print("BOT_TOKEN:", "OK" if BOT_TOKEN else "❌ MISSING")
print("OPENAI_API_KEY:", "OK" if OPENAI_API_KEY else "❌ MISSING")
print("CALENDAR_ID:", CALENDAR_ID)
print("credentials.json exists:", os.path.exists(SERVICE_ACCOUNT_FILE))

# === Инициализация бота и OpenAI ===
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)
client = OpenAI(api_key=OPENAI_API_KEY)

# === Авторизация Google Calendar ===
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/calendar"])
calendar_service = build('calendar', 'v3', credentials=creds)

def ask_gpt_for_date(text):
    prompt = (
        "Проанализируй текст. Найди дату и время начала мероприятия в тексте поста и страницы:\n"
        f"{text}\n\n"
        "Если указано несколько дат, выбери первую.\n"
        "Если год не указан, используй 2025.\n"
        "Если время не указано — используй 12:00.\n"
        "Ответ верни строго в формате: ГГГГ-ММ-ДД ЧЧ:ММ."
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    gpt_reply = response.choices[0].message.content.strip().rstrip(" .")
    try:
        return datetime.strptime(gpt_reply, "%Y-%m-%d %H:%M")
    except Exception as e:
        raise ValueError(f"Не удалось разобрать ответ GPT: {gpt_reply}") from e

def extract_urls(text: str) -> list[str]:
    return re.findall(r'(https?://\S+)', text)

def extract_urls_from_message(message: Message) -> list[str]:
    urls = extract_urls(message.text or message.caption or "")
    entities = message.entities or message.caption_entities or []
    for entity in entities:
        if entity.type == "text_link":
            urls.append(entity.url)
    return urls

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
        logging.warning(f"Ошибка при извлечении даты: {e}")
    return None

def event_already_exists(description: str) -> bool:
    try:
        now = datetime.utcnow().isoformat() + "Z"
        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=20,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        for event in events:
            if event.get("description", "").strip() == description.strip():
                return True
    except Exception as e:
        logging.error(f"Ошибка при проверке на дубликат: {e}")
    return False

def create_calendar_event(summary, description, start_dt):
    if event_already_exists(description):
        logging.info("⏭️ Событие уже существует, пропускаем.")
        return
    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Europe/Moscow'},
        'end': {'dateTime': (start_dt + timedelta(hours=1)).isoformat(), 'timeZone': 'Europe/Moscow'},
    }
    try:
        calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        logging.info(f"✅ Событие добавлено: {summary} — {start_dt}")
    except Exception as e:
        logging.error(f"❌ Ошибка добавления события: {e}")

@router.message()
async def handle_message(message: Message):
    user_id = message.from_user.id if message.from_user else None

    if message.from_user and message.from_user.is_bot:
        if user_id not in ALLOWED_BOTS:
            logging.info(f"⛔ Игнорируем сообщение от чужого бота: {user_id}")
            return
        logging.info(f"✅ Принято сообщение от разрешённого бота: {user_id}")

    text = message.text or message.caption or ""
    urls = extract_urls_from_message(message)
    url = urls[0] if urls else None

    logging.info(f"Обработка сообщения. Ссылка: {url if url else '[без ссылки]'}")
    dt = extract_date_from_page_or_message(text, url)

    if dt:
        try:
            summary = (text or url)[:30] + "..."
            description = text
            if url and url not in text:
                description = f"🖼 Ссылка: {url}\n\n{text}"
            create_calendar_event(summary, description, dt)
            await message.reply(f"Добавлено в календарь: {dt.strftime('%d.%m.%Y %H:%M')}")
        except Exception as e:
            logging.warning(f"Не удалось создать событие: {e}")
    else:
        logging.info("📭 Дата не найдена")

async def main():
    logging.info("🚀 Бот запущен")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
