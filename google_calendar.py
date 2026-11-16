import hashlib
import json
import logging
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from constants import END_DATE, GOOGLE_CALENDAR, START_DATE


BASE_DIR = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/calendar"]
SOURCE_MARKER = "ruz_hack"


class GoogleCalendarConfigError(RuntimeError):
    pass


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


def _calendar_bounds(timezone):
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise GoogleCalendarConfigError(
            f"Unknown Google Calendar timezone: {timezone!r}"
        ) from error

    start = datetime.combine(START_DATE.date(), time.min, tzinfo=zone)
    end = datetime.combine(END_DATE.date() + timedelta(days=1), time.min, tzinfo=zone)
    return start.isoformat(), end.isoformat()


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


def _list_managed_events(service, calendar_id, room_id, timezone):
    time_min, time_max = _calendar_bounds(timezone)
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
                privateExtendedProperty=f"ruzSource={SOURCE_MARKER}",
                pageToken=page_token,
            )
            .execute()
        )
        for event in response.get("items", []):
            private = event.get("extendedProperties", {}).get("private", {})
            if private.get("ruzRoomId") == str(room_id):
                events.append(event)
        page_token = response.get("nextPageToken")
        if not page_token:
            return events


def sync_schedule(room_id, room_name, lessons, service=None, config=None):
    """Make managed Google events for one room exactly match the RUZ schedule."""
    config = GOOGLE_CALENDAR if config is None else config
    if not config.get("enabled", False):
        return {"created": 0, "updated": 0, "deleted": 0, "disabled": True}

    calendars = config.get("calendars", {})
    calendar_id = calendars.get(room_id) or calendars.get(str(room_id))
    if not calendar_id:
        raise GoogleCalendarConfigError(
            f"Google calendar id is not configured for room {room_id}"
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
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        stats["deleted"] += 1

    for key, body in desired.items():
        event = existing.pop(key, None)
        if event is None:
            service.events().insert(calendarId=calendar_id, body=body).execute()
            stats["created"] += 1
            continue

        current_private = event.get("extendedProperties", {}).get("private", {})
        wanted_private = body["extendedProperties"]["private"]
        if current_private.get("ruzFingerprint") != wanted_private["ruzFingerprint"]:
            service.events().update(
                calendarId=calendar_id, eventId=event["id"], body=body
            ).execute()
            stats["updated"] += 1

    for event in existing.values():
        service.events().delete(
            calendarId=calendar_id, eventId=event["id"]
        ).execute()
        stats["deleted"] += 1

    logging.info(
        "Google Calendar synchronized for room %s: created=%s updated=%s deleted=%s",
        room_id,
        stats["created"],
        stats["updated"],
        stats["deleted"],
    )
    return stats
