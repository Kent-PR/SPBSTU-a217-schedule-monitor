import requests
import os

from tg_credentials import TG_TOKEN, TG_CHAT_ID

API_URL = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"


def send_telegram(text: str):
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"  # можно убрать, если не нужен форматированный текст
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print("Ошибка отправки в Telegram:", e)