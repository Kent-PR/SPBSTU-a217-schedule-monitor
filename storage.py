import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from constants import WEEKDAYS_RU

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

MESSAGES_DIR = BASE_DIR / "messages_queue"
MESSAGES_DIR.mkdir(exist_ok=True)


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(data, temp_file, ensure_ascii=False, indent=4)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, path)
    except Exception:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


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
    atomic_write_json(path, data)


def save_changes(room_id, date, added, removed):
    time_str = datetime.now().strftime("%H_%M_%S")
    path = get_changes_path(room_id, date, time_str)
    atomic_write_json(path, {"added": added, "removed": removed})


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
    atomic_write_json(path, data)


def get_calendar_missing_path(room_id):
    return get_room_dir(room_id) / f"{room_id}_calendar_missing.json"


def load_calendar_missing(room_id):
    path = get_calendar_missing_path(room_id)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_calendar_missing(room_id, data):
    path = get_calendar_missing_path(room_id)
    atomic_write_json(path, data)


def get_availability_state_path(room_id):
    return get_room_dir(room_id) / f"{room_id}_availability_state.json"


def load_availability_state(room_id):
    path = get_availability_state_path(room_id)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_availability_state(room_id, data):
    path = get_availability_state_path(room_id)
    atomic_write_json(path, data)


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
    atomic_write_json(path, messages)
