import requests
import logging
import time
from dataclasses import dataclass
from html import escape
from private_config.tg_credentials import TG_TOKEN, TG_CHAT_ID, TG_PROXY

TOKEN = TG_TOKEN
CHAT_ID = TG_CHAT_ID

PROXIES = {
    "http": TG_PROXY,
    "https": TG_PROXY,
}

API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
MAX_MESSAGE_LENGTH = 4000
RETRY_QUEUE_PART_LENGTH = MAX_MESSAGE_LENGTH - 200


@dataclass(frozen=True)
class TelegramSendResult:
    status: bool | None
    remaining_parts: tuple[str, ...]


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


def _safe_error(error):
    return str(error).replace(TOKEN, "***")


def _send_chunk(text: str, retries, delay):
    payload = {
        "chat_id": CHAT_ID,
        "text": escape(text, quote=False),
        "parse_mode": "HTML"
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                API_URL,
                json=payload,
                timeout=10,
                proxies=PROXIES,
            )
            response.raise_for_status()
            logging.info("Telegram notification sent successfully via proxy")
            return True
        except requests.RequestException as e:
            if e.response is not None and e.response.status_code == 400:
                logging.error(
                    "Telegram rejected the message with HTTP 400 via proxy; "
                    "the request will not be retried"
                )
                return None

            logging.warning(
                "Telegram proxy attempt %s/%s failed: %s",
                attempt,
                retries,
                _safe_error(e),
            )
            if attempt < retries:
                time.sleep(delay)

    logging.warning("Telegram proxy failed, trying direct connection")
    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Telegram notification sent successfully directly")
        return True
    except requests.RequestException as e:
        if e.response is not None and e.response.status_code == 400:
            logging.error(
                "Telegram rejected the message with HTTP 400 directly; "
                "the request will not be retried"
            )
            return None

        logging.error(
            "Telegram notification failed directly too: %s",
            _safe_error(e),
        )
        return False


def send_telegram_detailed(text: str, retries=3, delay=30):
    chunks = split_message(text)

    for index, chunk in enumerate(chunks, start=1):
        result = _send_chunk(chunk, retries, delay)
        if result is not True:
            logging.error(
                "Telegram notification part %s/%s failed",
                index,
                len(chunks),
            )
            return TelegramSendResult(result, tuple(chunks[index - 1:]))

    return TelegramSendResult(True, ())


def send_telegram(text: str, retries=3, delay=30):
    return send_telegram_detailed(text, retries, delay).status


def prepare_retry_parts(parts):
    retry_parts = []
    for part in parts:
        retry_parts.extend(split_message(part, RETRY_QUEUE_PART_LENGTH))

    return retry_parts
