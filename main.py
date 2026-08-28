import requests
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timedelta

from storage import load_current_schedule, save_current_schedule, save_changes, load_snapshot_schedule,\
    save_snapshot_schedule, load_failed_messages, save_failed_messages
from telegram_notifier import send_telegram
from formatter import format_changes, format_conflicts
from conflict_checker import find_conflicts

BASE_DIR = Path(__file__).resolve().parent

# ================= SETUP =================

BUILDING_ID = 69
ROOMS = {
    1948: "Room A.2.17(Stationary)",
    1949: "Room А.2.17(Mobile)"
}

START_DATE = datetime(2026, 9, 1)
END_DATE = datetime(2027, 1, 31)

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
    maxBytes=5 * 1024 * 1024,  # 5Mb
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
                teachers = lesson.get("teachers", [])
                if teachers:
                    t = teachers[0]
                    teacher = {
                        "first_name": t.get("first_name"),
                        "middle_name": t.get("middle_name"),
                        "last_name": t.get("last_name")
                    }
                else:
                    teacher = None

                lessons.append({
                    "room_id": room_id,
                    "date": day["date"],
                    "start": lesson.get("time_start"),
                    "end": lesson.get("time_end"),
                    "subject": lesson.get("subject"),
                    "teacher": teacher,
                    "groups": lesson.get("groups")
                })

        current += timedelta(days=7)

    return sorted(merge_lessons(lessons), key=lambda x: (x["date"], x["start"]))


def merge_lessons(lessons):
    merged = {}

    for lesson in lessons:
        key = (
            lesson["room_id"],
            lesson["date"],
            lesson["start"],
            lesson["end"],
            lesson["subject"]
        )

        if key not in merged:
            merged[key] = lesson.copy()
            merged[key]["groups"] = lesson["groups"] or []
        else:
            existing_ids = {g["id"] for g in merged[key]["groups"]}
            for group in (lesson["groups"] or []):
                if group["id"] not in existing_ids:
                    merged[key]["groups"].append(group)

    return list(merged.values())


def compare_schedules(old, new):
    def key(lesson):
        return (
            lesson["room_id"],
            lesson["date"],
            lesson["start"],
            lesson["end"],
            lesson["subject"]
        )

    old_keys = {key(i) for i in old}
    new_keys = {key(i) for i in new}

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys

    added = [i for i in new if key(i) in added_keys]
    removed = [i for i in old if key(i) in removed_keys]

    return added, removed


def run_check(is_summary=False):
    today = datetime.now().date()
    retry_failed_messages()

    logging.info("=" * 50)
    logging.info("Schedule check started")

    for room_id, room_name in ROOMS.items():
        instant_check(room_id, room_name, today)
        if is_summary:
            summary_check(room_id, room_name, today)

    logging.info("Schedule check ended")


def instant_check(room_id, room_name, today):
    logging.info(f"{room_name} instant check")

    try:
        new_schedule = fetch_full_schedule(room_id)
    except Exception:
        logging.error(f"{room_name}: failed to fetch schedule")
        return

    snapshot = load_snapshot_schedule(room_id)
    added, removed = compare_schedules(snapshot, new_schedule)

    added = [i for i in added if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]
    removed = [i for i in removed if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]

    if added or removed:
        logging.warning(f"\t⚠ Changes detected⚠")
        save_snapshot_schedule(room_id, new_schedule)
        save_changes(room_id, today.strftime("%Y-%m-%d"), added, removed)
        msg = format_changes(room_name, added, removed)
        if msg:
            if not send_telegram(msg):
                queue = load_failed_messages()
                queue.append(msg)
                save_failed_messages(queue)
    else:
        logging.info(f"\tNo changes detected")


def retry_failed_messages():
    queue = load_failed_messages()
    if not queue:
        return

    still_failed = []
    for msg in queue:
        stamped_msg = msg + f"\n\nОтправлено с задержкой: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        if not send_telegram(stamped_msg):
            still_failed.append(msg)

    save_failed_messages(still_failed)


def summary_check(room_id, room_name, today):
    logging.info(f"{room_name} summary check")

    try:
        new_schedule = fetch_full_schedule(room_id)
    except Exception:
        logging.error(f"{room_name}: failed to fetch schedule")
        return

    current = load_current_schedule(room_id)
    added, removed = compare_schedules(current, new_schedule)

    added = [i for i in added if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]
    removed = [i for i in removed if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]

    if added or removed:
        logging.warning(f"\t⚠ Changes detected⚠")
        msg = format_changes(room_name, added, removed)
        if msg:
            if not send_telegram(msg):
                queue = load_failed_messages()
                queue.append(msg)
                save_failed_messages(queue)
    else:
        logging.info(f"\tNo changes detected")

    future_schedule = [i for i in new_schedule if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]
    conflicts = find_conflicts(future_schedule)
    if conflicts:
        logging.warning(f"\t⚠ Conflicts found: {len(conflicts)}")
        conflict_msg = format_conflicts(room_name, conflicts)
        if conflict_msg:
            send_telegram(conflict_msg)
    else:
        logging.info(f"\tNo conflicts detected")

    save_current_schedule(room_id, new_schedule)
    save_snapshot_schedule(room_id, new_schedule)


def main():
    run_check()


if __name__ == "__main__":
    main()
