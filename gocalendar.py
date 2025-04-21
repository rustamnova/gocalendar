import logging
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.utils.markdown import hbold
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram import Bot, Dispatcher
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import asyncio
from dateutil import parser
import openai

# --- CONFIG ---
BOT_TOKEN = "BOT_TOKEN_REMOVED"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = "credentials.json"
CALENDAR_ID = "CALENDAR_ID_REMOVED@group.calendar.google.com"
openai.api_key = "OPENAI_KEY_REMOVED"

# --- SAVE CREDS TO FILE ---
creds_data = {
    "type": "service_account",
    "project_id": "REMOVED",
    "private_key_id": "REMOVED",
    "private_key": "PRIVATE_KEY_REMOVED",
    "client_email": "REMOVED@REMOVED.iam.gserviceaccount.com",
    "client_id": "REMOVED",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "REMOVED",
    "universe_domain": "googleapis.com"
}

# --- INIT ---
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
calendar_service = build('calendar', 'v3', credentials=creds)

# --- GPT-based date extraction ---
from openai import OpenAI
client = OpenAI(api_key=openai.api_key)

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


# --- Utils ---
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

def create_calendar_event(summary, description, start_dt):
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

# --- Handler ---
@router.message()
async def handle_message(message: Message):
    text = message.text or message.caption or ""
    urls = extract_urls_from_message(message)

    for url in urls if urls else [None]:
        logging.info(f"Обработка ссылки: {url if url else '[без ссылки]'}")
        dt = extract_date_from_page_or_message(text, url)
        if dt:
            try:
                summary = (url or text)[:30] + "..."  # первые 30 символов в заголовок
                description = url or text
                create_calendar_event(summary, description, dt)
                await message.reply(f"Добавлено в календарь: {dt.strftime('%d.%m.%Y %H:%M')}")
            except Exception as e:
                logging.warning(f"Не удалось создать событие: {e}")


# --- Main ---
async def main():
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
