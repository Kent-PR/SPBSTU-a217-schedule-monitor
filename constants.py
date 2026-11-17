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

    outage_alert_threshold = config.get("outage_alert_threshold", 3)
    if (
        isinstance(outage_alert_threshold, bool)
        or not isinstance(outage_alert_threshold, int)
        or outage_alert_threshold <= 0
    ):
        raise RuntimeError("'outage_alert_threshold' must be a positive integer")

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

    google_calendar = config.get("google_calendar", {})
    if not isinstance(google_calendar, dict):
        raise RuntimeError("'google_calendar' must be an object")

    enabled = google_calendar.get("enabled", False)
    if not isinstance(enabled, bool):
        raise RuntimeError("'google_calendar.enabled' must be a boolean")

    raw_calendars = google_calendar.get("calendars", {})
    if not isinstance(raw_calendars, dict):
        raise RuntimeError("'google_calendar.calendars' must be an object")

    calendars = {}
    for raw_room_id, calendar_id in raw_calendars.items():
        try:
            room_id = int(raw_room_id)
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                f"Invalid room id in 'google_calendar.calendars': {raw_room_id!r}"
            ) from error
        if room_id not in rooms:
            raise RuntimeError(
                f"Unknown room id in 'google_calendar.calendars': {room_id}"
            )
        if not isinstance(calendar_id, str):
            raise RuntimeError(
                f"Calendar id for room {room_id} must be a string"
            )
        calendars[room_id] = calendar_id.strip()

    if enabled:
        missing_calendars = [room_id for room_id in rooms if not calendars.get(room_id)]
        if missing_calendars:
            missing = ", ".join(str(room_id) for room_id in missing_calendars)
            raise RuntimeError(
                "Google Calendar is enabled, but calendar ids are missing for "
                f"rooms: {missing}"
            )

    credentials_file = google_calendar.get(
        "credentials_file", "google_service_account.json"
    )
    timezone = google_calendar.get("timezone", "Europe/Moscow")
    for field_name, value in (
        ("credentials_file", credentials_file),
        ("timezone", timezone),
    ):
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(
                f"'google_calendar.{field_name}' must be a non-empty string"
            )

    google_calendar_config = {
        "enabled": enabled,
        "calendars": calendars,
        "credentials_file": credentials_file.strip(),
        "timezone": timezone.strip(),
    }

    return (
        building_id,
        rooms,
        start_date,
        end_date,
        check_interval,
        outage_alert_threshold,
        summary_times,
        google_calendar_config,
    )


(
    BUILDING_ID,
    ROOMS,
    START_DATE,
    END_DATE,
    CHECK_INTERVAL,
    OUTAGE_ALERT_THRESHOLD,
    SUMMARY_TIMES,
    GOOGLE_CALENDAR,
) = _load_config()
