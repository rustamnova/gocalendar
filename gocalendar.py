import logging
import re
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# --- CONFIG ---
BOT_TOKEN = "BOT_TOKEN_REMOVED"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = "credentials.json"
CALENDAR_ID = "primary"  # или ID конкретного календаря

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

import json

with open("credentials.json", "w") as f:
    json.dump(creds_data, f)

# --- INIT ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# --- Google Calendar client ---
creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
calendar_service = build('calendar', 'v3', credentials=creds)


# --- Utils ---
def extract_urls(text):
    return re.findall(r'(https?://\S+)', text)


def extract_date_from_page(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        text = soup.get_text(" ", strip=True)
        match = re.search(r'(\d{1,2} [а-яА-Яa-zA-Z]+ \d{4}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})', text)
        if match:
            return match.group(1)
    except Exception as e:
        logging.warning(f"Ошибка парсинга {url}: {e}")
    return None


def create_calendar_event(summary, description, start_dt):
    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Europe/Moscow'},
        'end': {'dateTime': (start_dt + timedelta(hours=1)).isoformat(), 'timeZone': 'Europe/Moscow'},
    }
    calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()


# --- Handlers ---
@dp.message_handler()
async def handle_message(message: Message):
    urls = extract_urls(message.text)
    if not urls:
        return

    for url in urls:
        logging.info(f"Обработка ссылки: {url}")
        date_str = extract_date_from_page(url)
        if date_str:
            try:
                dt = parse_date(date_str)
                create_calendar_event("Мероприятие из чата", url, dt)
                await message.reply(f"Добавлено в календарь: {dt.strftime('%d.%m.%Y')}")
            except Exception as e:
                logging.warning(f"Не удалось создать событие: {e}")


# --- Date Parsing ---
def parse_date(date_str):
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    raise ValueError(f"Неизвестный формат даты: {date_str}")


# --- Start bot ---
if __name__ == '__main__':
    print("Бот запущен")
    executor.start_polling(dp, skip_updates=True)
