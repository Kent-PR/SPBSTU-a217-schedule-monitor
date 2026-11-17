import requests
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timedelta

from storage import load_current_schedule, save_current_schedule, save_changes, load_snapshot_schedule,\
    save_snapshot_schedule, load_failed_messages, save_failed_messages, load_calendar_missing,\
    save_calendar_missing
from telegram_notifier import (
    prepare_retry_parts,
    send_telegram,
    send_telegram_detailed,
)
from formatter import format_changes, format_conflicts, format_missing_calendar_dates
from conflict_checker import find_conflicts
from constants import BUILDING_ID, ROOMS, START_DATE, END_DATE
from normalization import lesson_key, normalize_lesson, normalize_text
from google_calendar import find_missing_lessons

BASE_DIR = Path(__file__).resolve().parent

# ================= SETUP =================

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ================ LOGGING =================

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = "schedule_service.log"
DISABLE_FILE_LOGGING_ENV = "SCHEDULE_MONITOR_DISABLE_FILE_LOGGING"

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def configure_file_logging():
    if os.environ.get(DISABLE_FILE_LOGGING_ENV) == "1":
        return

    LOG_DIR.mkdir(exist_ok=True)
    log_path = (LOG_DIR / LOG_FILE).resolve()
    if any(
        isinstance(existing, RotatingFileHandler)
        and Path(existing.baseFilename).resolve() == log_path
        for existing in logger.handlers
    ):
        return

    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5Mb
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)


configure_file_logging()


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}
API_TIMEOUT = (5, 20)  # connect timeout, read timeout

# =============================================


def get_api_url(room_id):
    return f"https://ruz.spbstu.ru/api/v1/ruz/buildings/{BUILDING_ID}/rooms/{room_id}/scheduler"


class ScheduleDataError(ValueError):
    pass


def validate_week_data(data):
    if not isinstance(data, dict):
        raise ScheduleDataError("response root must be an object")

    days = data.get("days")
    if not isinstance(days, list):
        raise ScheduleDataError("response field 'days' must be a list")

    for day_index, day in enumerate(days):
        if not isinstance(day, dict):
            raise ScheduleDataError(f"days[{day_index}] must be an object")

        date = day.get("date")
        if not isinstance(date, str):
            raise ScheduleDataError(f"days[{day_index}].date must be a string")
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError as error:
            raise ScheduleDataError(
                f"days[{day_index}].date has invalid format: {date!r}"
            ) from error

        lessons = day.get("lessons")
        if not isinstance(lessons, list):
            raise ScheduleDataError(f"days[{day_index}].lessons must be a list")

        for lesson_index, lesson in enumerate(lessons):
            path = f"days[{day_index}].lessons[{lesson_index}]"
            if not isinstance(lesson, dict):
                raise ScheduleDataError(f"{path} must be an object")

            for field in ("time_start", "time_end", "subject"):
                if (
                    not isinstance(lesson.get(field), str)
                    or not normalize_text(lesson[field])
                ):
                    raise ScheduleDataError(f"{path}.{field} must be a non-empty string")

            for field in ("time_start", "time_end"):
                try:
                    datetime.strptime(normalize_text(lesson[field]), "%H:%M")
                except ValueError as error:
                    raise ScheduleDataError(
                        f"{path}.{field} has invalid format: {lesson[field]!r}"
                    ) from error

            for field in ("teachers", "groups"):
                value = lesson.get(field)
                if value is not None and not isinstance(value, list):
                    raise ScheduleDataError(f"{path}.{field} must be a list or null")

            for teacher_index, teacher in enumerate(lesson.get("teachers") or []):
                if not isinstance(teacher, dict):
                    raise ScheduleDataError(
                        f"{path}.teachers[{teacher_index}] must be an object"
                    )

            for group_index, group in enumerate(lesson.get("groups") or []):
                if not isinstance(group, dict) or "id" not in group:
                    raise ScheduleDataError(
                        f"{path}.groups[{group_index}] must contain an id"
                    )

    return data


def fetch_week(room_id, date):
    url = get_api_url(room_id)
    params = {"date": date.strftime("%Y-%m-%d")}
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        status = error.response.status_code if error.response is not None else None
        request_url = error.request.url if error.request is not None else url
        logging.error(
            "RUZ API request failed: type=%s status=%s url=%s error=%s",
            type(error).__name__,
            status if status is not None else "n/a",
            request_url,
            error,
        )
        raise

    try:
        data = response.json()
    except ValueError as error:
        logging.error(
            "RUZ API returned invalid JSON: type=%s status=%s url=%s error=%s",
            type(error).__name__,
            response.status_code,
            response.url,
            error,
        )
        raise

    try:
        return validate_week_data(data)
    except ScheduleDataError as error:
        logging.error(
            "RUZ API returned invalid schedule data: status=%s url=%s error=%s",
            response.status_code,
            response.url,
            error,
        )
        raise


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

    for raw_lesson in lessons:
        lesson = normalize_lesson(raw_lesson)
        key = lesson_key(lesson)

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
    old_keys = {lesson_key(item) for item in old}
    new_keys = {lesson_key(item) for item in new}

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys

    added = [item for item in new if lesson_key(item) in added_keys]
    removed = [item for item in old if lesson_key(item) in removed_keys]

    return added, removed


def is_safe_schedule_update(previous, new, room_id, source_name):
    if previous and not new:
        logging.error(
            "%s for room %s was not updated: API returned an empty schedule "
            "while the saved schedule contains %s lessons",
            source_name,
            room_id,
            len(previous),
        )
        return False

    return True


def run_check(is_summary=False):
    today = datetime.now().date()
    retry_failed_messages()

    logging.info("=" * 50)
    logging.info("Schedule check started")

    for room_id, room_name in ROOMS.items():
        try:
            new_schedule = fetch_full_schedule(room_id)
        except Exception:
            logging.exception("%s: failed to fetch schedule", room_name)
            continue

        instant_check(room_id, room_name, today, new_schedule)
        if is_summary:
            summary_check(room_id, room_name, today, new_schedule)

    logging.info("Schedule check ended")


def instant_check(room_id, room_name, today, new_schedule=None):
    logging.info(f"{room_name} instant check")

    if new_schedule is None:
        try:
            new_schedule = fetch_full_schedule(room_id)
        except Exception:
            logging.exception("%s: failed to fetch schedule", room_name)
            return

    snapshot = load_snapshot_schedule(room_id)
    if not is_safe_schedule_update(snapshot, new_schedule, room_id, "Snapshot"):
        return

    audit_google_calendar(room_id, room_name, new_schedule, today)

    added, removed = compare_schedules(snapshot, new_schedule)

    added = [i for i in added if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]
    removed = [i for i in removed if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]

    if added or removed:
        logging.warning(f"\t⚠ Changes detected⚠")
        save_snapshot_schedule(room_id, new_schedule)
        save_changes(room_id, today.strftime("%Y-%m-%d"), added, removed)
        msg = format_changes(room_name, added, removed)
        if msg:
            send_or_queue(msg)
    else:
        logging.info(f"\tNo changes detected")


def audit_google_calendar(room_id, room_name, schedule, today):
    try:
        missing = find_missing_lessons(room_id, schedule, today=today)
    except Exception:
        logging.exception("%s: Google Calendar audit failed", room_name)
        return

    previous = load_calendar_missing(room_id)
    previous_dates = {
        item["date"] if isinstance(item, dict) else str(item)
        for item in previous
    }
    missing_dates = sorted({item["date"] for item in missing})
    if previous_dates == set(missing_dates):
        return

    if missing:
        message = format_missing_calendar_dates(room_name, missing)
        if message:
            send_or_queue(message)

    save_calendar_missing(room_id, missing_dates)


def send_or_queue(message):
    result = send_telegram_detailed(message)
    if result.status is False:
        queue = load_failed_messages()
        queue.extend(prepare_retry_parts(result.remaining_parts))
        save_failed_messages(queue)
    return result.status


def retry_failed_messages():
    queue = load_failed_messages()
    if not queue:
        return

    still_failed = []
    pending_parts = prepare_retry_parts(
        message for message in queue if isinstance(message, str)
    )
    for msg in pending_parts:
        stamped_msg = msg + f"\n\nОтправлено с задержкой: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        if send_telegram(stamped_msg) is False:
            still_failed.append(msg)

    save_failed_messages(still_failed)


def summary_check(room_id, room_name, today, new_schedule=None):
    logging.info(f"{room_name} summary check")

    if new_schedule is None:
        try:
            new_schedule = fetch_full_schedule(room_id)
        except Exception:
            logging.exception("%s: failed to fetch schedule", room_name)
            return

    current = load_current_schedule(room_id)
    if not is_safe_schedule_update(current, new_schedule, room_id, "Current schedule"):
        return

    added, removed = compare_schedules(current, new_schedule)

    added = [i for i in added if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]
    removed = [i for i in removed if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]

    if added or removed:
        logging.warning(f"\t⚠ Changes detected⚠")
        msg = format_changes(room_name, added, removed)
        if msg:
            send_or_queue(msg)
    else:
        logging.info(f"\tNo changes detected")

    future_schedule = [i for i in new_schedule if datetime.strptime(i["date"], "%Y-%m-%d").date() >= today]
    conflicts = find_conflicts(future_schedule)
    if conflicts:
        logging.warning(f"\t⚠ Conflicts found: {len(conflicts)}")
        conflict_msg = format_conflicts(room_name, conflicts)
        if conflict_msg:
            send_or_queue(conflict_msg)
    else:
        logging.info(f"\tNo conflicts detected")

    save_current_schedule(room_id, new_schedule)
    save_snapshot_schedule(room_id, new_schedule)


def main():
    run_check()


if __name__ == "__main__":
    main()
