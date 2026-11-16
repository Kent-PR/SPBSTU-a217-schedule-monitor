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
MAX_MESSAGE_LENGTH = 4000


def split_message(text: str, max_length=MAX_MESSAGE_LENGTH):
    """Split text into Telegram-safe chunks, preferring line boundaries."""
    if max_length <= 0:
        raise ValueError("max_length must be positive")

    chunks = []
    remaining = text

    while len(remaining) > max_length:
        newline_at = remaining.rfind("\n", 0, max_length)
        if newline_at < 0:
            split_at = max_length
        else:
            split_at = newline_at + 1

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]

    chunks.append(remaining)
    return chunks


def _send_chunk(text: str, retries, delay):
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


def send_telegram(text: str, retries=3, delay=30):
    chunks = split_message(text)

    for index, chunk in enumerate(chunks, start=1):
        if not _send_chunk(chunk, retries, delay):
            logging.error(
                "Telegram notification part %s/%s failed",
                index,
                len(chunks),
            )
            return False

    return True
