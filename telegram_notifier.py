import requests
import logging
import time


def send_telegram(text: str, retries=3, delay=30):
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    logging.info(f"[DEV] Telegram message:\n{text}")
