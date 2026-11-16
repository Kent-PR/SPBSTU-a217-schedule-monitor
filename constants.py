import json
from datetime import datetime
from pathlib import Path


WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "schedule_config.json"


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError as error:
        raise RuntimeError(f"Configuration file not found: {CONFIG_PATH}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Invalid JSON in {CONFIG_PATH}: line {error.lineno}, column {error.colno}"
        ) from error

    if not isinstance(config, dict):
        raise RuntimeError("Schedule configuration root must be an object")

    building_id = config.get("building_id")
    if isinstance(building_id, bool) or not isinstance(building_id, int) or building_id <= 0:
        raise RuntimeError("'building_id' must be a positive integer")

    raw_rooms = config.get("rooms")
    if not isinstance(raw_rooms, dict) or not raw_rooms:
        raise RuntimeError("'rooms' must be a non-empty object")

    rooms = {}
    for raw_room_id, room_name in raw_rooms.items():
        try:
            room_id = int(raw_room_id)
        except (TypeError, ValueError) as error:
            raise RuntimeError(f"Invalid room id: {raw_room_id!r}") from error
        if room_id <= 0 or not isinstance(room_name, str) or not room_name.strip():
            raise RuntimeError(f"Invalid room configuration for id {raw_room_id!r}")
        rooms[room_id] = room_name.strip()

    semester = config.get("semester")
    if not isinstance(semester, dict):
        raise RuntimeError("'semester' must be an object")
    try:
        start_date = datetime.strptime(semester["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(semester["end_date"], "%Y-%m-%d")
    except KeyError as error:
        raise RuntimeError(f"Missing semester setting: {error.args[0]}") from error
    except (TypeError, ValueError) as error:
        raise RuntimeError("Semester dates must use YYYY-MM-DD format") from error
    if start_date > end_date:
        raise RuntimeError("Semester start_date must not be after end_date")

    check_interval = config.get("check_interval_seconds")
    if isinstance(check_interval, bool) or not isinstance(check_interval, int) or check_interval <= 0:
        raise RuntimeError("'check_interval_seconds' must be a positive integer")

    raw_summary_times = config.get("summary_times")
    if not isinstance(raw_summary_times, list):
        raise RuntimeError("'summary_times' must be a list of HH:MM strings")

    summary_times = []
    for value in raw_summary_times:
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except (TypeError, ValueError) as error:
            raise RuntimeError(f"Invalid summary time: {value!r}; expected HH:MM") from error
        time_tuple = (parsed.hour, parsed.minute)
        if time_tuple not in summary_times:
            summary_times.append(time_tuple)

    return building_id, rooms, start_date, end_date, check_interval, summary_times


(
    BUILDING_ID,
    ROOMS,
    START_DATE,
    END_DATE,
    CHECK_INTERVAL,
    SUMMARY_TIMES,
) = _load_config()
