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

# === Загрузка переменных окружения ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")
SERVICE_ACCOUNT_FILE = "credentials.json"

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

# Преобразуем \n в реальные переводы строк
creds_data["private_key"] = creds_data["private_key"].replace("\\n", "\n")

if not os.path.exists(SERVICE_ACCOUNT_FILE):
    with open(SERVICE_ACCOUNT_FILE, "w") as f:
        json.dump(creds_data, f)
    print("✅ credentials.json создан из встроенных данных")

# Продолжай с остальной логикой бота...
