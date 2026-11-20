import hashlib
import json
import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from constants import END_DATE, GOOGLE_CALENDAR, START_DATE


BASE_DIR = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/calendar"]
SOURCE_MARKER = "ruz_hack"
GOOGLE_API_NUM_RETRIES = 3


class GoogleCalendarConfigError(RuntimeError):
    pass


def _execute(request):
    """Execute a Google API request with retries for transient failures."""
    return request.execute(num_retries=GOOGLE_API_NUM_RETRIES)


def _lesson_key(lesson):
    identity = {
        "room_id": str(lesson["room_id"]),
        "date": lesson["date"],
        "start": lesson["start"],
        "end": lesson["end"],
        "subject": lesson["subject"],
    }
    encoded = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _teacher_name(teacher):
    if not teacher:
        return None
    parts = [
        teacher.get("first_name"),
        teacher.get("middle_name"),
        teacher.get("last_name"),
    ]
    return " ".join(part for part in parts if part)


def _event_body(lesson, room_name, timezone):
    teacher = _teacher_name(lesson.get("teacher"))
    groups = ", ".join(
        group.get("name", str(group.get("id", "")))
        for group in (lesson.get("groups") or [])
        if group.get("name") or group.get("id") is not None
    )
    description = ["Расписание RUZ СПбПУ"]
    if teacher:
        description.append(f"Преподаватель: {teacher}")
    if groups:
        description.append(f"Группы: {groups}")

    lesson_key = _lesson_key(lesson)
    body = {
        "summary": lesson["subject"],
        "location": room_name,
        "description": "\n".join(description),
        "start": {
            "dateTime": f'{lesson["date"]}T{lesson["start"]}:00',
            "timeZone": timezone,
        },
        "end": {
            "dateTime": f'{lesson["date"]}T{lesson["end"]}:00',
            "timeZone": timezone,
        },
        "extendedProperties": {
            "private": {
                "ruzSource": SOURCE_MARKER,
                "ruzRoomId": str(lesson["room_id"]),
                "ruzLessonKey": lesson_key,
            }
        },
    }
    fingerprint_data = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    body["extendedProperties"]["private"]["ruzFingerprint"] = hashlib.sha256(
        fingerprint_data
    ).hexdigest()
    return body


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


def _semester_bounds(timezone):
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise GoogleCalendarConfigError(
            f"Unknown Google Calendar timezone: {timezone!r}"
        ) from error

    start = datetime.combine(START_DATE.date(), time.min, tzinfo=zone)
    end = datetime.combine(END_DATE.date() + timedelta(days=1), time.min, tzinfo=zone)
    return start.isoformat(), end.isoformat()


def _list_events(service, calendar_id, timezone, today):
    time_min, time_max = _audit_bounds(timezone, today)
    events = []
    page_token = None
    while True:
        response = _execute(
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                showDeleted=False,
                pageToken=page_token,
            )
        )
        events.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return events


def _list_managed_events(service, calendar_id, room_id, timezone):
    time_min, time_max = _semester_bounds(timezone)
    events = []
    page_token = None
    while True:
        response = _execute(
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                showDeleted=False,
                privateExtendedProperty=f"ruzSource={SOURCE_MARKER}",
                pageToken=page_token,
            )
        )
        for event in response.get("items", []):
            private = event.get("extendedProperties", {}).get("private", {})
            if private.get("ruzRoomId") == str(room_id):
                events.append(event)
        page_token = response.get("nextPageToken")
        if not page_token:
            return events


def sync_synchronized_calendar(
    room_id,
    room_name,
    lessons,
    service=None,
    config=None,
):
    """Make managed events in the synchronized calendar match the RUZ schedule."""
    config = GOOGLE_CALENDAR if config is None else config
    if not config.get("enabled", False):
        return {"created": 0, "updated": 0, "deleted": 0, "disabled": True}

    calendars = config.get("synchronized_calendars", {})
    calendar_id = calendars.get(room_id) or calendars.get(str(room_id))
    if not calendar_id:
        raise GoogleCalendarConfigError(
            f"Synchronized calendar id is not configured for room {room_id}"
        )

    timezone = config["timezone"]
    service = service or _build_service(config["credentials_file"])
    desired = {
        _lesson_key(lesson): _event_body(lesson, room_name, timezone)
        for lesson in lessons
        if str(lesson.get("room_id")) == str(room_id)
    }
    existing = {}
    duplicate_ids = []
    for event in _list_managed_events(
        service, calendar_id, room_id, timezone
    ):
        private = event.get("extendedProperties", {}).get("private", {})
        key = private.get("ruzLessonKey")
        if not key or key in existing:
            duplicate_ids.append(event["id"])
        else:
            existing[key] = event

    stats = {"created": 0, "updated": 0, "deleted": 0, "disabled": False}
    for event_id in duplicate_ids:
        _execute(service.events().delete(calendarId=calendar_id, eventId=event_id))
        stats["deleted"] += 1

    for key, body in desired.items():
        event = existing.pop(key, None)
        if event is None:
            _execute(service.events().insert(calendarId=calendar_id, body=body))
            stats["created"] += 1
            continue

        current_private = event.get("extendedProperties", {}).get("private", {})
        wanted_private = body["extendedProperties"]["private"]
        if current_private.get("ruzFingerprint") != wanted_private["ruzFingerprint"]:
            _execute(
                service.events().update(
                    calendarId=calendar_id,
                    eventId=event["id"],
                    body=body,
                )
            )
            stats["updated"] += 1

    for event in existing.values():
        _execute(
            service.events().delete(
                calendarId=calendar_id, eventId=event["id"]
            )
        )
        stats["deleted"] += 1

    logging.info(
        "Synchronized Google Calendar updated for room %s: "
        "created=%s updated=%s deleted=%s",
        room_id,
        stats["created"],
        stats["updated"],
        stats["deleted"],
    )
    return stats


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
