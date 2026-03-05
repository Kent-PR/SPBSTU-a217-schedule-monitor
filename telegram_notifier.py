import requests
import logging

from tg_credentials import TG_TOKEN, TG_CHAT_ID

API_URL = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"


def send_telegram(text: str):
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Telegram notification sent successfully")
    except requests.RequestException as e:
        logging.error(f"Telegram notification failed: {e}")