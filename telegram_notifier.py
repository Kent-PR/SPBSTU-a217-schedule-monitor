import requests
import logging
import time

from tg_credentials import TG_TOKEN, TG_CHAT_ID

API_URL = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"


def send_telegram(text: str, retries=3, delay=30):
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            response.raise_for_status()
            logging.info("Telegram notification sent successfully")
            return
        except requests.RequestException as e:
            logging.warning(f"Telegram attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay)

    logging.error("Telegram notification failed after all retries")