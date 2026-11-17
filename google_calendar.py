import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from constants import END_DATE, GOOGLE_CALENDAR, START_DATE


BASE_DIR = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class GoogleCalendarConfigError(RuntimeError):
    pass


def _build_service(credentials_file):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as error:
        raise GoogleCalendarConfigError(
            "Google Calendar dependencies are missing; run pip install -r requirements.txt"
        ) from error

    credentials_path = Path(credentials_file)
    if not credentials_path.is_absolute():
        credentials_path = BASE_DIR / credentials_path
    if not credentials_path.is_file():
        raise GoogleCalendarConfigError(
            f"Google service-account credentials not found: {credentials_path}"
        )

    credentials = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _audit_bounds(timezone, today):
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise GoogleCalendarConfigError(
            f"Unknown Google Calendar timezone: {timezone!r}"
        ) from error

    first_day = max(today, START_DATE.date())
    start = datetime.combine(first_day, time.min, tzinfo=zone)
    end = datetime.combine(END_DATE.date() + timedelta(days=1), time.min, tzinfo=zone)
    return start.isoformat(), end.isoformat()


def _list_events(service, calendar_id, timezone, today):
    time_min, time_max = _audit_bounds(timezone, today)
    events = []
    page_token = None
    while True:
        response = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                showDeleted=False,
                pageToken=page_token,
            )
            .execute()
        )
        events.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return events


def _parse_datetime(value, zone):
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(zone)


def _event_interval(event, timezone):
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise GoogleCalendarConfigError(
            f"Unknown Google Calendar timezone: {timezone!r}"
        ) from error
    start = _parse_datetime(event.get("start", {}).get("dateTime"), zone)
    end = _parse_datetime(event.get("end", {}).get("dateTime"), zone)
    if start is None or end is None:
        return None
    return start.date().isoformat(), start.strftime("%H:%M"), end.strftime("%H:%M")


def find_missing_lessons(
    room_id,
    lessons,
    service=None,
    config=None,
    today=None,
):
    """Return future RUZ lessons with no exact time slot in the room calendar."""
    config = GOOGLE_CALENDAR if config is None else config
    if not config.get("enabled", False):
        return []

    today = today or date.today()
    calendars = config.get("calendars", {})
    calendar_id = calendars.get(room_id) or calendars.get(str(room_id))
    if not calendar_id:
        raise GoogleCalendarConfigError(
            f"Google calendar id is not configured for room {room_id}"
        )
    timezone = config["timezone"]
    service = service or _build_service(config["credentials_file"])
    events = _list_events(service, calendar_id, timezone, today)
    occupied_intervals = {
        interval
        for event in events
        if (interval := _event_interval(event, timezone)) is not None
    }

    missing = []
    for lesson in lessons:
        if str(lesson.get("room_id")) != str(room_id):
            continue
        lesson_date = datetime.strptime(lesson["date"], "%Y-%m-%d").date()
        if lesson_date < today or lesson_date > END_DATE.date():
            continue
        interval = (lesson["date"], lesson["start"], lesson["end"])
        if interval not in occupied_intervals:
            missing.append(lesson)

    missing.sort(key=lambda lesson: (lesson["date"], lesson["start"], lesson["end"]))
    logging.info(
        "Google Calendar audit for room %s: calendar_events=%s missing_lessons=%s",
        room_id,
        len(events),
        len(missing),
    )
    return missing
