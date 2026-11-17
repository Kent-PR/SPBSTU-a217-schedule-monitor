from unittest.mock import Mock

import google_calendar


class FakeRequest:
    def __init__(self, response=None):
        self.response = response or {}

    def execute(self):
        return self.response


class FakeEvents:
    def __init__(self, pages=None):
        self.pages = list(pages or [{"items": []}])
        self.list_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return FakeRequest(self.pages.pop(0))


class FakeService:
    def __init__(self, pages=None):
        self.events_api = FakeEvents(pages)

    def events(self):
        return self.events_api


def enabled_config():
    return {
        "enabled": True,
        "calendars": {
            1948: "calendar-1948@example.com",
            1949: "calendar-1949@example.com",
        },
        "credentials_file": "unused-in-tests.json",
        "timezone": "UTC",
    }


def calendar_event(start="2026-11-18T10:00:00Z", end="2026-11-18T11:40:00Z"):
    return {
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }


def test_disabled_audit_does_not_build_google_service(monkeypatch, lesson):
    build = Mock()
    monkeypatch.setattr(google_calendar, "_build_service", build)
    missing = google_calendar.find_missing_lessons(
        1948, [lesson()], config={"enabled": False}
    )
    assert missing == []
    build.assert_not_called()


def test_audit_reports_missing_lesson(lesson):
    service = FakeService()
    missing = google_calendar.find_missing_lessons(
        1948,
        [lesson()],
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )
    assert missing == [lesson()]
    assert service.events_api.list_calls[0]["calendarId"] == "calendar-1948@example.com"


def test_audit_accepts_matching_time_slot(lesson):
    service = FakeService([{"items": [calendar_event()]}])
    missing = google_calendar.find_missing_lessons(
        1948,
        [lesson()],
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )
    assert missing == []


def test_audit_converts_event_offset_to_configured_timezone(lesson):
    service = FakeService(
        [{"items": [calendar_event("2026-11-18T13:00:00+03:00", "2026-11-18T14:40:00+03:00")]}]
    )
    missing = google_calendar.find_missing_lessons(
        1948,
        [lesson()],
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )
    assert missing == []


def test_audit_ignores_past_lessons(lesson):
    service = FakeService()
    missing = google_calendar.find_missing_lessons(
        1948,
        [lesson(date="2026-11-15")],
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )
    assert missing == []


def test_audit_only_uses_lessons_for_requested_room(lesson):
    service = FakeService()
    missing = google_calendar.find_missing_lessons(
        1948,
        [lesson(room_id=1949)],
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )
    assert missing == []


def test_each_room_uses_its_own_calendar(lesson):
    service = FakeService()
    google_calendar.find_missing_lessons(
        1949,
        [lesson(room_id=1949)],
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )
    assert service.events_api.list_calls[0]["calendarId"] == "calendar-1949@example.com"


def test_enabled_audit_requires_calendar_for_room(lesson):
    config = enabled_config()
    config["calendars"].pop(1948)

    try:
        google_calendar.find_missing_lessons(1948, [lesson()], config=config)
    except google_calendar.GoogleCalendarConfigError as error:
        assert "room 1948" in str(error)
    else:
        raise AssertionError("Missing room calendar must be rejected")
