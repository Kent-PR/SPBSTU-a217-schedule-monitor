import json
from pathlib import Path
from datetime import datetime
from constants import WEEKDAYS_RU

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

MESSAGES_DIR = BASE_DIR / "messages_queue"
MESSAGES_DIR.mkdir(exist_ok=True)


def get_room_dir(room_id):
    path = DATA_DIR / str(room_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_current_schedule_path(room_id):
    return get_room_dir(room_id) / f"{room_id}_current_schedule.json"


def get_day_dir(room_id, date):
    dt = datetime.strptime(date, "%Y-%m-%d")
    day_name = WEEKDAYS_RU[dt.weekday()]
    day_folder = f"{dt.strftime('%d')}_{day_name}"
    path = get_room_dir(room_id) / str(dt.year) / f"{dt.month:02d}" / day_folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_changes_path(room_id, date, time):
    changes_dir = get_day_dir(room_id, date) / "changes"
    changes_dir.mkdir(exist_ok=True)
    return changes_dir / f"{room_id}_{time}.json"


def load_current_schedule(room_id):
    path = get_current_schedule_path(room_id)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_current_schedule(room_id, data):
    path = get_current_schedule_path(room_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def save_changes(room_id, date, added, removed):
    time_str = datetime.now().strftime("%H_%M_%S")
    path = get_changes_path(room_id, date, time_str)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"added": added, "removed": removed}, f, ensure_ascii=False, indent=4)


def get_snapshot_schedule_path(room_id):
    return get_room_dir(room_id) / f"{room_id}_snapshot_schedule.json"


def load_snapshot_schedule(room_id):
    path = get_snapshot_schedule_path(room_id)
    if not path.exists():
        data = load_current_schedule(room_id)
        save_snapshot_schedule(room_id, data)
        return data
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot_schedule(room_id, data):
    path = get_snapshot_schedule_path(room_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_failed_messages_path():
    return MESSAGES_DIR / "failed_messages.json"

def load_failed_messages():
    path = get_failed_messages_path()
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_failed_messages(messages):
    path = get_failed_messages_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)
