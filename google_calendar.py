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


def _format_intervals(intervals, limit=20):
    ordered = sorted(intervals)
    visible = ordered[:limit]
    text = ", ".join(
        f"{event_date} {start}-{end}" for event_date, start, end in visible
    )
    if len(ordered) > limit:
        text += f", ... +{len(ordered) - limit} more"
    return text or "none"


def _log_ruz_synchronized_mismatch(room_id, lessons, synchronized_intervals, today):
    if lessons is None:
        return

    ruz_intervals = {
        (lesson["date"], lesson["start"], lesson["end"])
        for lesson in lessons
        if str(lesson.get("room_id")) == str(room_id)
        and today <= datetime.strptime(lesson["date"], "%Y-%m-%d").date()
        <= END_DATE.date()
    }
    missing_in_synchronized = ruz_intervals - synchronized_intervals
    extra_in_synchronized = synchronized_intervals - ruz_intervals
    if not missing_in_synchronized and not extra_in_synchronized:
        return

    logging.warning(
        "RUZ/synchronized calendar mismatch for room %s: "
        "missing_in_synchronized=%s [%s]; extra_in_synchronized=%s [%s]",
        room_id,
        len(missing_in_synchronized),
        _format_intervals(missing_in_synchronized),
        len(extra_in_synchronized),
        _format_intervals(extra_in_synchronized),
    )


def find_missing_prod_events(
    room_id,
    ruz_lessons=None,
    service=None,
    config=None,
    today=None,
):
    """Return synchronized calendar slots missing from the production calendar."""
    config = GOOGLE_CALENDAR if config is None else config
    if not config.get("enabled", False):
        return []

    today = today or date.today()
    synchronized_calendars = config.get("synchronized_calendars", {})
    production_calendars = config.get("production_calendars", {})
    synchronized_id = synchronized_calendars.get(room_id) or synchronized_calendars.get(
        str(room_id)
    )
    production_id = production_calendars.get(room_id) or production_calendars.get(
        str(room_id)
    )
    if not synchronized_id or not production_id:
        raise GoogleCalendarConfigError(
            f"Both synchronized and production calendar ids are required for room {room_id}"
        )

    timezone = config["timezone"]
    service = service or _build_service(config["credentials_file"])
    synchronized_events = _list_events(service, synchronized_id, timezone, today)
    production_events = _list_events(service, production_id, timezone, today)
    production_intervals = {
        interval
        for event in production_events
        if (interval := _event_interval(event, timezone)) is not None
    }

    missing = []
    seen_intervals = set()
    for event in synchronized_events:
        interval = _event_interval(event, timezone)
        if interval is None or interval in seen_intervals:
            continue
        event_date = datetime.strptime(interval[0], "%Y-%m-%d").date()
        if event_date < today or event_date > END_DATE.date():
            continue
        seen_intervals.add(interval)
        if interval not in production_intervals:
            missing.append(
                {
                    "room_id": room_id,
                    "date": interval[0],
                    "start": interval[1],
                    "end": interval[2],
                    "subject": event.get("summary") or "—",
                }
            )

    _log_ruz_synchronized_mismatch(
        room_id, ruz_lessons, seen_intervals, today
    )
    missing.sort(key=lambda item: (item["date"], item["start"], item["end"]))
    logging.info(
        "Google Calendar audit for room %s: synchronized_events=%s "
        "production_events=%s missing_events=%s",
        room_id,
        len(synchronized_events),
        len(production_events),
        len(missing),
    )
    return missing
