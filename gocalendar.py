import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
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

# === Подготовка логов ===
os.makedirs("logs", exist_ok=True)
for log_name in ["worklog.txt", "errors.txt"]:
    log_path = os.path.join("logs", log_name)
    if os.path.exists(log_path):
        os.remove(log_path)

# === Настройка логирования ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/worklog.txt", mode="w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
error_handler = logging.FileHandler("logs/errors.txt", mode="w", encoding="utf-8")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.getLogger().addHandler(error_handler)

# === Переменные окружения ===
load_dotenv()
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
    return datetime.strptime(gpt_reply, "%Y-%m-%d %H:%M")

def extract_urls(text: str) -> list[str]:
    return re.findall(r'(https?://\S+)', text)

def extract_urls_from_message(message: Message) -> list[str]:
    urls = extract_urls(message.text or message.caption or "")
    entities = message.entities or message.caption_entities or []
    for entity in entities:
        if entity.type == "text_link":
            urls.append(entity.url)
    return list(set(urls))

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
        now = datetime.utcnow().isoformat() + "Z"
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

    dt = extract_date_from_page_or_message(text, url)
    if dt:
        try:
            summary = (text or url)[:30] + "..."
            poster_link = next((u for u in urls if "ibb.co" in u or "imgbb" in u), None)
            yandex_link = next((u for u in urls if "yandex.ru/search" in u), None)
            other_links = [u for u in urls if u not in (poster_link, yandex_link)]

            link_block = ""
            if poster_link:
                link_block += f"\n\n🖼 Ссылка на афишу:\n{poster_link}"
            if yandex_link:
                link_block += f"\n\n🔎 Искать в Яндексе:\n{yandex_link}"
            if other_links:
                link_block += "\n\n🔗 Другие ссылки:\n" + "\n".join(other_links)

            description = text + link_block
            create_calendar_event(summary, description, dt)
            await message.reply(f"📅 Добавлено в календарь: {dt.strftime('%d.%m.%Y %H:%M')}")
        except Exception as e:
            logging.error(f"❌ Ошибка при создании события: {e}")
    else:
        logging.info("📭 Дата не найдена в сообщении.")

# === Запуск бота ===
async def main():
    logging.info("🚀 Gocalendar бот запущен")
    await dp.start_polling(bot, allowed_updates=["message"])

if __name__ == '__main__':
    asyncio.run(main())
