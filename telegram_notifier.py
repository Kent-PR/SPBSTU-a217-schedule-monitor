import requests
import logging
import time
from tg_credentials import TG_TOKEN, TG_CHAT_ID, TG_PROXY
from storage import load_failed_messages, save_failed_messages

TOKEN = TG_TOKEN
CHAT_ID = TG_CHAT_ID

PROXIES = {
    "http": TG_PROXY,
    "https": TG_PROXY,
}

API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"


def send_telegram(text: str, retries=3, delay=30):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            response.raise_for_status()
            logging.info("Telegram notification sent successfully")
            return True
        except requests.RequestException as e:
            logging.warning(f"Telegram attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay)

    logging.warning("Direct connection failed, trying via proxy")
    try:
        response = requests.post(API_URL, json=payload, timeout=10, proxies=PROXIES)
        response.raise_for_status()
        logging.info("Telegram notification sent successfully via proxy")
        return True
    except requests.RequestException as e:
        logging.error(f"Telegram notification failed via proxy too: {e}")
        return False
