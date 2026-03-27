#!/usr/bin/env python3
"""
daily_report.py — ежедневная аналитика GoCalendar бота.
Запускается cron-ом в 09:00 каждый день.
"""
import os
import re
import asyncio
from datetime import datetime, timedelta, timezone, date as date_type
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
USER_IDS = list(map(int, os.getenv("USER_IDS", "").split(",")))
CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_FILE = os.path.join(_BASE_DIR, "credentials.json")
LOGS_DIR = os.path.join(_BASE_DIR, "logs")

creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/calendar"]
)
calendar_service = build("calendar", "v3", credentials=creds)

MONTHS_RU = [
    "января","февраля","марта","апреля","мая","июня",
    "июля","августа","сентября","октября","ноября","декабря"
]
DAYS_SHORT = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]


def parse_logs_for_date(target: date_type) -> dict:
    """Парсим worklog.txt за указанную дату."""
    date_str = target.strftime("%Y-%m-%d")
    stats = {
        "messages": 0,
        "events_added": 0,
        "failed_dates": 0,
        "calendar_views": 0,
        "users": set(),
    }

    log_path = os.path.join(LOGS_DIR, "worklog.txt")
    if not os.path.exists(log_path):
        return stats

    seen = set()  # дедупликация одинаковых строк
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith(date_str):
                continue
            line = line.rstrip("\n")
            if line in seen:
                continue
            seen.add(line)

            if "📩 Получено сообщение от пользователя" in line:
                stats["messages"] += 1
                m = re.search(r"пользователя (\d+)", line)
                if m:
                    stats["users"].add(m.group(1))
            elif "✅ Добавлено событие:" in line:
                stats["events_added"] += 1
            elif "📭 Дата не найдена" in line or "Не удалось распознать дату" in line:
                stats["failed_dates"] += 1
            elif "📊 Просмотр дат:" in line:
                stats["calendar_views"] += 1

    return stats


def get_calendar_stats() -> dict:
    """Статистика из Google Calendar."""
    tz = timezone(timedelta(hours=3))
    now = datetime.now(tz)
    yesterday = now - timedelta(days=1)

    stats = {
        "events_today": 0,
        "upcoming_7d": 0,
        "upcoming_30d": 0,
        "added_yesterday": 0,
    }

    try:
        # Мероприятия сегодня
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        r = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=today_start.isoformat(),
            timeMax=today_end.isoformat(),
            singleEvents=True,
        ).execute()
        stats["events_today"] = len(r.get("items", []))

        # Ближайшие 7 дней
        r7 = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=(now + timedelta(days=7)).isoformat(),
            singleEvents=True,
            maxResults=200,
        ).execute()
        stats["upcoming_7d"] = len(r7.get("items", []))

        # Ближайшие 30 дней
        r30 = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=(now + timedelta(days=30)).isoformat(),
            singleEvents=True,
            maxResults=500,
        ).execute()
        stats["upcoming_30d"] = len(r30.get("items", []))

        # Добавлено вчера (по полю created)
        yest_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yest_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
        r_new = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            updatedMin=yest_start.isoformat(),
            singleEvents=True,
            maxResults=200,
        ).execute()
        for ev in r_new.get("items", []):
            created_str = ev.get("created", "")
            if created_str:
                # Google возвращает created в UTC, приводим к дате
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                created_local = created_dt.astimezone(tz).date()
                if created_local == yesterday.date():
                    stats["added_yesterday"] += 1

    except Exception as e:
        print(f"❌ Calendar API error: {e}")

    return stats


def build_report(log_stats: dict, cal_stats: dict, report_date: date_type) -> str:
    date_str = f"{report_date.day} {MONTHS_RU[report_date.month - 1]} ({DAYS_SHORT[report_date.weekday()]})"

    success_rate = ""
    total_attempts = log_stats["events_added"] + log_stats["failed_dates"]
    if total_attempts > 0:
        pct = int(log_stats["events_added"] / total_attempts * 100)
        success_rate = f" ({pct}% успех)"

    lines = [
        f"📊 <b>Отчёт GoCalendar за {date_str}</b>",
        "",
        "👥 <b>Активность пользователей:</b>",
        f"  • Сообщений получено: <b>{log_stats['messages']}</b>",
        f"  • Уникальных пользователей: <b>{len(log_stats['users'])}</b>",
        f"  • Просмотров дат в боте: <b>{log_stats['calendar_views']}</b>",
        "",
        "🗓 <b>Добавление событий:</b>",
        f"  • Успешно добавлено: <b>{log_stats['events_added']}</b>{success_rate}",
        f"  • Не удалось распознать дату: <b>{log_stats['failed_dates']}</b>",
        "",
        "📆 <b>Состояние календаря:</b>",
        f"  • Мероприятий сегодня: <b>{cal_stats['events_today']}</b>",
        f"  • Следующие 7 дней: <b>{cal_stats['upcoming_7d']}</b>",
        f"  • Следующие 30 дней: <b>{cal_stats['upcoming_30d']}</b>",
    ]

    if log_stats["users"]:
        lines.append("")
        lines.append(f"👤 Активные пользователи: {', '.join(sorted(log_stats['users']))}")

    if log_stats["messages"] == 0 and log_stats["calendar_views"] == 0:
        lines.append("")
        lines.append("💤 Вчера активности не было.")

    return "\n".join(lines)


async def send_report():
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    yesterday = (datetime.now() - timedelta(days=1)).date()
    log_stats = parse_logs_for_date(yesterday)
    cal_stats = get_calendar_stats()
    report = build_report(log_stats, cal_stats, yesterday)

    print(report)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    for uid in USER_IDS:
        try:
            await bot.send_message(uid, report)
            print(f"✅ Отчёт отправлен → {uid}")
        except Exception as e:
            print(f"❌ Ошибка отправки → {uid}: {e}")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(send_report())
