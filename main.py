import requests
import json
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timedelta
from telegram_notifier import send_telegram

BASE_DIR = Path(__file__).resolve().parent

# ================= SETUP =================

BUILDING_ID = 69
ROOMS = {
    1948: "Room A.2.17(Stationary)",
    1949: "Room А.2.17(Mobile)"
}

START_DATE = datetime(2026, 2, 1)
END_DATE = datetime(2026, 8, 30)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ================ LOGGING =================

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = "schedule_service.log"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    LOG_DIR / "schedule_service.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)

handler.setFormatter(formatter)
logger.addHandler(handler)


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

# =============================================


def get_api_url(room_id):
    return f"https://ruz.spbstu.ru/api/v1/ruz/buildings/{BUILDING_ID}/rooms/{room_id}/scheduler"


def fetch_week(room_id, date):
    url = get_api_url(room_id)
    params = {"date": date.strftime("%Y-%m-%d")}
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()


def fetch_full_schedule(room_id):
    current = START_DATE
    lessons = []

    while current <= END_DATE:
        data = fetch_week(room_id, current)

        for day in data.get("days", []):
            for lesson in day.get("lessons", []):
                lessons.append({
                    "room_id": room_id,
                    "date": day["date"],
                    "start": lesson.get("time_start"),
                    "end": lesson.get("time_end"),
                    "subject": lesson.get("subject"),
                    "teacher": lesson.get("teacher"),
                    "groups": lesson.get("groups")
                })

        current += timedelta(days=7)

    return sorted(lessons, key=lambda x: (x["date"], x["start"]))


def get_file_path(room_id):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    return os.path.join(DATA_DIR, f"{room_id}.json")


def load_old_schedule(room_id):
    path = get_file_path(room_id)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_schedule(room_id, data):
    path = get_file_path(room_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def compare_schedules(old, new):
    old_set = {json.dumps(i, sort_keys=True) for i in old}
    new_set = {json.dumps(i, sort_keys=True) for i in new}

    added = new_set - old_set
    removed = old_set - new_set

    return [json.loads(x) for x in added], [json.loads(x) for x in removed]


def format_changes(room_name, added, removed):
    """
    Generates a text message about changes for a single classroom.
    Returns a string or None if there are no changes.
    """
    if not added and not removed:
        return None  # ничего не отправляем, если изменений нет

    lines = [f"⚠ Изменения в {room_name}"]

    if added:
        lines.append("➕ Добавлено:")
        for item in added:
            lines.append(f"  {item['date']} {item['start']} {item['subject']}")

    if removed:
        lines.append("➖ Удалено:")
        for item in removed:
            lines.append(f"  {item['date']} {item['start']} {item['subject']}")

    return "\n".join(lines)


def run_check():
    messages = []

    logging.info("Schedule check started")

    for room_id, room_name in ROOMS.items():
        logging.info(f"{room_name} check")

        try:
            new_schedule = fetch_full_schedule(room_id)
        except Exception:
            logging.error(f"{room_name}: failed to fetch schedule")
            continue

        old_schedule = load_old_schedule(room_id)
        added, removed = compare_schedules(old_schedule, new_schedule)

        if added or removed:
            logging.info(f"{room_name}: changes detected")
            msg = format_changes(room_name, added, removed)
            if msg:
                messages.append(msg)
        else:
            logging.info(f"{room_name}: no changes detected")

        save_schedule(room_id, new_schedule)

    logging.info("Schedule check ended")

    # If there are any changes, send one message to Telegram
    if messages:
        full_text = "\n\n".join(messages)
        with open("changes.log", "a", encoding="utf-8") as f:
            f.write(full_text + "\n\n")
        send_telegram(full_text)


def main():
    run_check()



if __name__ == "__main__":
    main()