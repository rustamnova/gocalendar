import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone, date as date_type
from urllib.parse import quote_plus
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from openai import OpenAI
import asyncio
import random
from datetime import time

# === Подготовка логов ===
import sys as _sys
from logging.handlers import RotatingFileHandler

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGS_DIR = os.path.join(_BASE_DIR, "logs")
os.makedirs(_LOGS_DIR, exist_ok=True)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

_worklog_handler = RotatingFileHandler(
    os.path.join(_LOGS_DIR, "worklog.txt"), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_worklog_handler.setLevel(logging.INFO)
_worklog_handler.setFormatter(_fmt)

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

# === Постоянная кнопка внизу чата ===
MENU_BTN_TEXT = "📅 Главное меню"

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MENU_BTN_TEXT)]],
        resize_keyboard=True,
        is_persistent=True,
    )

# === Константы ===
MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн",
                "июл", "авг", "сен", "окт", "ноя", "дек"]
MONTHS_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
             "июля", "августа", "сентября", "октября", "ноября", "декабря"]
DAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

# === Простая клавиатура навигации (без списка событий — для /start и on_startup) ===
def nav_keyboard(current_date: date_type) -> InlineKeyboardMarkup:
    today = datetime.now().date()
    prev_date = current_date - timedelta(days=1)
    next_date = current_date + timedelta(days=1)

    if current_date == today:
        center_label = f"Сегодня, {today.day} {MONTHS_SHORT[today.month - 1]}"
    else:
        center_label = f"{current_date.day} {MONTHS_SHORT[current_date.month - 1]}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀", callback_data=f"events_nav:{prev_date}"),
            InlineKeyboardButton(text=center_label, callback_data="events_today"),
            InlineKeyboardButton(text="▶", callback_data=f"events_nav:{next_date}"),
        ],
        [
            InlineKeyboardButton(text="🗓 Выбрать дату", callback_data="events_choose"),
        ],
    ])

# === Google Calendar: запрос событий ===
def get_events_for_date(target_date: date_type) -> list[dict]:
    try:
        tz = timezone(timedelta(hours=3))  # Europe/Moscow UTC+3
        day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=tz)
        day_end = day_start + timedelta(days=1)

        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except Exception as e:
        logging.error(f"❌ Ошибка при получении событий: {e}")
        return []

# === Форматирование событий ===
def event_button_label(event: dict) -> str:
    """Название кнопки: summary или первая строка description."""
    title = event.get('summary', '').strip()
    if title:
        return title[:60]
    description = event.get('description', '')
    first_line = description.strip().split('\n')[0][:60]
    return first_line or 'Без названия'

def format_event_detail(event: dict) -> str:
    """Полный текст мероприятия для отдельного сообщения."""
    title = event.get('summary', '').strip()
    description = event.get('description', '').strip()
    start = event.get('start', {})

    lines = []
    if title:
        lines.append(f"<b>{title}</b>")
    if 'dateTime' in start:
        dt = datetime.fromisoformat(start['dateTime'])
        lines.append(f"📅 {dt.strftime('%d.%m.%Y %H:%M')}")
    elif 'date' in start:
        lines.append(f"📅 {start['date']}")
    if description:
        lines.append("")
        lines.append(description)

    text = "\n".join(lines)
    # Telegram limit 4096 chars
    if len(text) > 4000:
        text = text[:4000] + "\n…"
    return text

def format_events_header(events: list[dict], target_date: date_type) -> str:
    weekday = DAYS_RU[target_date.weekday()]
    month = MONTHS_RU[target_date.month - 1]
    date_str = f"{target_date.day} {month} {target_date.year} ({weekday})"
    if not events:
        return f"📭 На <b>{date_str}</b> мероприятий нет."
    count = len(events)
    return f"📅 <b>Мероприятия на {date_str}</b> — {count} шт.\nНажми на название чтобы открыть подробности:"

def events_keyboard_with_list(events: list[dict], target_date: date_type) -> InlineKeyboardMarkup:
    today = datetime.now().date()
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    if target_date == today:
        center_label = f"Сегодня, {today.day} {MONTHS_SHORT[today.month - 1]}"
    else:
        center_label = f"{target_date.day} {MONTHS_SHORT[target_date.month - 1]}"

    rows = []
    for event in events:
        label = event_button_label(event)
        event_id = event.get('id', '')
        rows.append([InlineKeyboardButton(text=label, callback_data=f"ev:{event_id}")])

    rows.append([
        InlineKeyboardButton(text="◀", callback_data=f"events_nav:{prev_date}"),
        InlineKeyboardButton(text=center_label, callback_data="events_today"),
        InlineKeyboardButton(text="▶", callback_data=f"events_nav:{next_date}"),
    ])
    rows.append([
        InlineKeyboardButton(text="🗓 Выбрать дату", callback_data="events_choose"),
        InlineKeyboardButton(text="📋 Все подробности", callback_data=f"ev_all:{target_date}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_event_by_id(event_id: str) -> dict | None:
    try:
        return calendar_service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
    except Exception as e:
        logging.error(f"❌ Ошибка получения события {event_id}: {e}")
        return None

# === Показ событий за дату ===
async def show_events(target: date_type, edit_message: Message):
    events = get_events_for_date(target)
    text = format_events_header(events, target)
    keyboard = events_keyboard_with_list(events, target)
    await edit_message.edit_text(text, reply_markup=keyboard)

# === GPT: определение даты ===
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
            )
            gpt_reply = response.choices[0].message.content.strip().rstrip(" .")
            date_part = datetime.strptime(gpt_reply, "%Y-%m-%d").date()

            hour = random.randint(3, 23)
            minute = random.choice([0, 15, 30, 45])
            final_dt = datetime.combine(date_part, time(hour=hour, minute=minute))
            logging.info(f"📅 Распознана дата: {final_dt}")
            return final_dt
        except Exception as e:
            logging.warning(f"⚠️ Ошибка с моделью {model_name}: {e}")
            continue

    logging.error("❌ Не удалось распознать дату ни с одной моделью GPT.")
    return None


def is_telegram_story_url(url: str) -> bool:
    """Проверяет, является ли URL ссылкой на Telegram-статус (story)."""
    return bool(re.search(r't\.me/[^/]+/s/\d+', url))

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
    link_entities = [e for e in (entities or []) if e.type == "text_link"]
    if not link_entities:
        return text

    encoded = text.encode("utf-16-le")
    parts = []
    prev = 0

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

# === /start ===
@router.message(CommandStart())
async def cmd_start(message: Message):
    sender_id = message.from_user.id if message.from_user else None
    if sender_id not in USER_IDS:
        logging.warning("⛔ Неавторизованный /start от %s", sender_id)
        return
    today = datetime.now().date()
    await message.answer(MENU_BTN_TEXT, reply_markup=main_menu_keyboard())
    await message.answer(
        "👋 Привет! Я GoCalendar — автоматически добавляю события в Google Календарь.\n\n"
        "Что умею:\n"
        "• Принять ссылку на анонс или текст с датой\n"
        "• Распознать дату и название мероприятия\n"
        "• Добавить событие в Google Календарь\n\n"
        "Просто пришли ссылку или текст мероприятия 📅\n\n"
        "Или посмотри мероприятия по дате:",
        reply_markup=nav_keyboard(today)
    )

# === /events ===
@router.message(Command("events"))
async def cmd_events(message: Message):
    sender_id = message.from_user.id if message.from_user else None
    if sender_id not in USER_IDS:
        return
    today = datetime.now().date()
    await message.answer("📅 Выбери дату:", reply_markup=nav_keyboard(today))

# === Кнопка центр (Сегодня) ===
@router.callback_query(F.data == "events_today")
async def cb_events_today(callback: CallbackQuery):
    if callback.from_user.id not in USER_IDS:
        await callback.answer()
        return
    today = datetime.now().date()
    logging.info(f"📊 Просмотр дат: {callback.from_user.id} → {today}")
    await show_events(today, callback.message)
    await callback.answer()

# === Кнопки ◀ / ▶ (навигация по дням) ===
@router.callback_query(F.data.startswith("events_nav:"))
async def cb_events_nav(callback: CallbackQuery):
    if callback.from_user.id not in USER_IDS:
        await callback.answer()
        return
    date_str = callback.data.split(":", 1)[1]
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        await callback.answer("Некорректная дата")
        return
    logging.info(f"📊 Просмотр дат: {callback.from_user.id} → {target}")
    await show_events(target, callback.message)
    await callback.answer()

# === Кнопка «Выбрать дату» — открыть календарь ===
@router.callback_query(F.data == "events_choose")
async def cb_events_choose(callback: CallbackQuery):
    if callback.from_user.id not in USER_IDS:
        await callback.answer()
        return
    now = datetime.now()
    calendar_markup = await SimpleCalendar().start_calendar(year=now.year, month=now.month)
    await callback.message.edit_text("🗓 Выбери дату:", reply_markup=calendar_markup)
    await callback.answer()

# === Выбор даты в inline-календаре ===
@router.callback_query(SimpleCalendarCallback.filter())
async def cb_calendar_selected(callback: CallbackQuery, callback_data: SimpleCalendarCallback):
    if callback.from_user.id not in USER_IDS:
        await callback.answer()
        return
    selected, selected_date = await SimpleCalendar().process_selection(callback, callback_data)
    if selected:
        logging.info(f"📊 Просмотр дат: {callback.from_user.id} → {selected_date.date()}")
        await show_events(selected_date.date(), callback.message)
    await callback.answer()

# === Нажатие на кнопку мероприятия — показать полный текст ===
@router.callback_query(F.data.startswith("ev:"))
async def cb_event_detail(callback: CallbackQuery):
    if callback.from_user.id not in USER_IDS:
        await callback.answer()
        return
    event_id = callback.data[3:]
    event = get_event_by_id(event_id)
    if not event:
        await callback.answer("Мероприятие не найдено", show_alert=True)
        return
    text = format_event_detail(event)
    await callback.message.answer(text)
    await callback.answer()

# === Кнопка «Все подробности» — прислать каждое мероприятие отдельным постом ===
@router.callback_query(F.data.startswith("ev_all:"))
async def cb_event_all(callback: CallbackQuery):
    if callback.from_user.id not in USER_IDS:
        await callback.answer()
        return
    date_str = callback.data[7:]
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        await callback.answer("Некорректная дата", show_alert=True)
        return

    events = get_events_for_date(target)
    if not events:
        await callback.answer("На эту дату мероприятий нет", show_alert=True)
        return

    await callback.answer(f"Отправляю {len(events)} мероприятий…")
    for event in events:
        text = format_event_detail(event)
        await callback.message.answer(text)

# === Нажатие постоянной кнопки «Главное меню» ===
@router.message(F.text == MENU_BTN_TEXT)
async def cmd_menu_button(message: Message):
    sender_id = message.from_user.id if message.from_user else None
    if sender_id not in USER_IDS:
        return
    today = datetime.now().date()
    await message.answer(
        "📅 Главное меню — выбери дату или пришли мероприятие:",
        reply_markup=nav_keyboard(today)
    )

# === Обработка входящих сообщений (добавление мероприятий) ===
@router.message()
async def handle_message(message: Message):
    sender_id = message.from_user.id if message.from_user else None
    is_bot = message.from_user.is_bot if message.from_user else False

    logging.info(f"📩 Получено сообщение от {'бота' if is_bot else 'пользователя'} {sender_id}")

    if sender_id not in USER_IDS:
        logging.warning("⛔ Неавторизованный пользователь. Игнорируем.")
        return

    # Telegram-статусы (stories): бот не может прочитать текст статуса напрямую
    if message.story is not None:
        logging.info("📖 Получен Telegram-статус (story) — текст недоступен через Bot API")
        await message.answer(
            "📖 Это Telegram-статус — бот не может прочитать его текст напрямую.\n\n"
            "Скопируй текст статуса и пришли его сюда — добавлю мероприятие в календарь 📅"
        )
        return

    text = message.text or message.caption or ""
    urls = extract_urls_from_message(message)
    url = urls[0] if urls else None

    # Нет ни текста, ни ссылки — нечего анализировать
    if not text and not url:
        await message.answer(
            "📭 Пришли текст анонса или ссылку на мероприятие — добавлю в Google Календарь 📅"
        )
        return

    # Ссылка на Telegram-статус (story): страница не отдаёт текст
    if url and is_telegram_story_url(url):
        # Удаляем ссылку из текста, смотрим есть ли что-то ещё
        text_without_url = text.replace(url, "").strip()
        if text_without_url:
            # Есть текст помимо ссылки — используем его, URL не фетчим
            logging.info(f"📖 Telegram story URL + текст — используем текст без фетча")
            url = None
            text = text_without_url
        else:
            # Только ссылка — текст статуса недоступен через Bot API
            logging.info(f"📖 Telegram story URL без текста — просим скопировать")
            await message.answer(
                "📖 Ссылка на Telegram-статус — бот не может прочитать его содержимое автоматически.\n\n"
                "Скопируй текст статуса и пришли его сюда (можно вместе со ссылкой) — добавлю в календарь 📅"
            )
            return

    logging.info(f"🔍 Начинаем анализ текста. URL: {url or '–'}")

    status = await message.answer("🔍 Определяю дату мероприятия...")

    dt = extract_date_from_page_or_message(text, url)
    if dt:
        try:
            await status.edit_text("📅 Добавляю событие в Google Календарь...")
            summary_source = text or url or ""
            summary = (summary_source[:60] + "...") if len(summary_source) > 60 else summary_source
            entities = message.entities or message.caption_entities or []
            description = expand_links_in_text(text, entities)
            create_calendar_event(summary, description, dt)
            event_date = dt.date()
            events = get_events_for_date(event_date)
            header = f"✅ Добавлено в календарь: {dt.strftime('%d.%m.%Y')}\n\n" + format_events_header(events, event_date)
            await status.edit_text(header, reply_markup=events_keyboard_with_list(events, event_date))
        except Exception as e:
            logging.error(f"❌ Ошибка при создании события: {e}")
            await status.edit_text("❌ Ошибка при добавлении в календарь.")
    else:
        await status.edit_text("📭 Не удалось определить дату мероприятия.")
        logging.info("📭 Дата не найдена в сообщении.")

# === Запуск ===
async def on_startup():
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="events", description="Мероприятия по дате"),
    ])
    today = datetime.now().date()
    for uid in USER_IDS:
        try:
            await bot.send_message(
                uid,
                "✅ GoCalendar запущен! Пришли анонс или ссылку — добавлю в Google Календарь 📅\n\n"
                "Или посмотри мероприятия по дате:",
                reply_markup=main_menu_keyboard()
            )
        except Exception:
            pass


async def main():
    log_install(f"=== Запуск Gocalendar === (Python {_sys.version.split()[0]})")
    logging.info("🚀 Gocalendar бот запущен")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"], on_startup=on_startup)
    finally:
        log_install("=== Остановка Gocalendar ===")

if __name__ == '__main__':
    asyncio.run(main())
