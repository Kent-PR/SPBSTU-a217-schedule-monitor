import logging
from unittest.mock import Mock

import google_calendar


class FakeRequest:
    def __init__(self, response=None):
        self.response = response or {}

    def execute(self):
        return self.response


class FakeEvents:
    def __init__(self, pages=None):
        self.pages = list(pages or [{"items": []}, {"items": []}])
        self.list_calls = []
        self.inserted = []
        self.updated = []
        self.deleted = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return FakeRequest(self.pages.pop(0))

    def insert(self, **kwargs):
        self.inserted.append(kwargs)
        return FakeRequest()

    def update(self, **kwargs):
        self.updated.append(kwargs)
        return FakeRequest()

    def delete(self, **kwargs):
        self.deleted.append(kwargs)
        return FakeRequest()


class FakeService:
    def __init__(self, pages=None):
        self.events_api = FakeEvents(pages)

    def events(self):
        return self.events_api


def enabled_config():
    return {
        "enabled": True,
        "synchronized_calendars": {
            1948: "sync-1948@example.com",
            1949: "sync-1949@example.com",
        },
        "production_calendars": {
            1948: "prod-1948@example.com",
            1949: "prod-1949@example.com",
        },
        "credentials_file": "unused-in-tests.json",
        "timezone": "UTC",
    }


def calendar_event(
    start="2026-11-18T10:00:00Z",
    end="2026-11-18T11:40:00Z",
    summary="Mathematics",
):
    return {
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "summary": summary,
    }


def expected_missing():
    return {
        "room_id": 1948,
        "date": "2026-11-18",
        "start": "10:00",
        "end": "11:40",
        "subject": "Mathematics",
    }


def managed_event(lesson, room_name="Room A.2.17", event_id="event-1"):
    event = google_calendar._event_body(lesson, room_name, "UTC")
    event["id"] = event_id
    return event


def test_disabled_sync_does_not_build_google_service(monkeypatch, lesson):
    build = Mock()
    monkeypatch.setattr(google_calendar, "_build_service", build)

    stats = google_calendar.sync_synchronized_calendar(
        1948, "Room", [lesson()], config={"enabled": False}
    )

    assert stats["disabled"] is True
    build.assert_not_called()


def test_sync_creates_missing_lesson(monkeypatch, lesson):
    service = FakeService()
    monkeypatch.setattr(
        google_calendar, "_list_managed_events", Mock(return_value=[])
    )

    stats = google_calendar.sync_synchronized_calendar(
        1948,
        "Room A.2.17",
        [lesson()],
        service=service,
        config=enabled_config(),
    )

    assert stats == {"created": 1, "updated": 0, "deleted": 0, "disabled": False}
    inserted = service.events_api.inserted[0]
    assert inserted["calendarId"] == "sync-1948@example.com"
    assert inserted["body"]["extendedProperties"]["private"]["ruzSource"] == "ruz_hack"


def test_sync_keeps_unchanged_managed_event(monkeypatch, lesson):
    service = FakeService()
    existing = managed_event(lesson())
    monkeypatch.setattr(
        google_calendar, "_list_managed_events", Mock(return_value=[existing])
    )

    stats = google_calendar.sync_synchronized_calendar(
        1948,
        "Room A.2.17",
        [lesson()],
        service=service,
        config=enabled_config(),
    )

    assert stats == {"created": 0, "updated": 0, "deleted": 0, "disabled": False}


def test_sync_updates_changed_managed_event(monkeypatch, lesson):
    service = FakeService()
    existing = managed_event(lesson())
    existing["extendedProperties"]["private"]["ruzFingerprint"] = "old"
    monkeypatch.setattr(
        google_calendar, "_list_managed_events", Mock(return_value=[existing])
    )

    stats = google_calendar.sync_synchronized_calendar(
        1948,
        "Room A.2.17",
        [lesson()],
        service=service,
        config=enabled_config(),
    )

    assert stats["updated"] == 1
    assert service.events_api.updated[0]["eventId"] == "event-1"


def test_sync_deletes_managed_event_removed_from_ruz(monkeypatch, lesson):
    service = FakeService()
    existing = managed_event(lesson())
    monkeypatch.setattr(
        google_calendar, "_list_managed_events", Mock(return_value=[existing])
    )

    stats = google_calendar.sync_synchronized_calendar(
        1948,
        "Room A.2.17",
        [],
        service=service,
        config=enabled_config(),
    )

    assert stats["deleted"] == 1
    assert service.events_api.deleted[0]["eventId"] == "event-1"


def test_sync_never_writes_to_production_calendar(monkeypatch, lesson):
    service = FakeService()
    monkeypatch.setattr(
        google_calendar, "_list_managed_events", Mock(return_value=[])
    )

    google_calendar.sync_synchronized_calendar(
        1949,
        "Room A.2.17 Mobile",
        [lesson(room_id=1949)],
        service=service,
        config=enabled_config(),
    )

    assert service.events_api.inserted[0]["calendarId"] == "sync-1949@example.com"
    assert all(
        call["calendarId"] != "prod-1949@example.com"
        for call in service.events_api.inserted
        + service.events_api.updated
        + service.events_api.deleted
    )


def test_disabled_audit_does_not_build_google_service(monkeypatch):
    build = Mock()
    monkeypatch.setattr(google_calendar, "_build_service", build)

    missing = google_calendar.find_missing_prod_events(
        1948, config={"enabled": False}
    )

    assert missing == []
    build.assert_not_called()


def test_audit_reports_event_present_only_in_synchronized_calendar():
    service = FakeService([{"items": [calendar_event()]}, {"items": []}])

    missing = google_calendar.find_missing_prod_events(
        1948,
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )

    assert missing == [expected_missing()]
    assert service.events_api.list_calls[0]["calendarId"] == "sync-1948@example.com"
    assert service.events_api.list_calls[1]["calendarId"] == "prod-1948@example.com"


def test_audit_accepts_matching_production_time_slot():
    event = calendar_event()
    service = FakeService([{"items": [event]}, {"items": [event]}])

    missing = google_calendar.find_missing_prod_events(
        1948,
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )

    assert missing == []


def test_audit_converts_both_calendars_to_configured_timezone():
    synchronized = calendar_event(
        "2026-11-18T13:00:00+03:00", "2026-11-18T14:40:00+03:00"
    )
    production = calendar_event()
    service = FakeService(
        [{"items": [synchronized]}, {"items": [production]}]
    )

    missing = google_calendar.find_missing_prod_events(
        1948,
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )

    assert missing == []


def test_audit_ignores_past_synchronized_events():
    past = calendar_event(
        "2026-11-15T10:00:00Z", "2026-11-15T11:40:00Z"
    )
    service = FakeService([{"items": [past]}, {"items": []}])

    missing = google_calendar.find_missing_prod_events(
        1948,
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )

    assert missing == []


def test_duplicate_synchronized_slots_are_one_missing_lesson():
    event = calendar_event()
    service = FakeService([{"items": [event, event]}, {"items": []}])

    missing = google_calendar.find_missing_prod_events(
        1948,
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )

    assert missing == [expected_missing()]


def test_each_room_uses_its_own_calendar_pair():
    service = FakeService()

    google_calendar.find_missing_prod_events(
        1949,
        service=service,
        config=enabled_config(),
        today=google_calendar.date(2026, 11, 16),
    )

    assert service.events_api.list_calls[0]["calendarId"] == "sync-1949@example.com"
    assert service.events_api.list_calls[1]["calendarId"] == "prod-1949@example.com"


def test_enabled_audit_requires_both_calendars_for_room():
    config = enabled_config()
    config["synchronized_calendars"].pop(1948)

    try:
        google_calendar.find_missing_prod_events(1948, config=config)
    except google_calendar.GoogleCalendarConfigError as error:
        assert "room 1948" in str(error)
    else:
        raise AssertionError("Missing synchronized calendar must be rejected")


def test_ruz_synchronized_mismatch_is_logged(caplog, lesson):
    synchronized = calendar_event()
    production = calendar_event()
    ruz_lesson = lesson(start="12:00", end="13:40")
    service = FakeService(
        [{"items": [synchronized]}, {"items": [production]}]
    )

    with caplog.at_level(logging.WARNING):
        google_calendar.find_missing_prod_events(
            1948,
            [ruz_lesson],
            service=service,
            config=enabled_config(),
            today=google_calendar.date(2026, 11, 16),
        )

    message = caplog.messages[-1]
    assert "missing_in_synchronized=1 [2026-11-18 12:00-13:40]" in message
    assert "extra_in_synchronized=1 [2026-11-18 10:00-11:40]" in message
