from unittest.mock import Mock

import google_calendar


class FakeRequest:
    def execute(self):
        return {}


class FakeEvents:
    def __init__(self):
        self.inserted = []
        self.updated = []
        self.deleted = []

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
    def __init__(self):
        self.events_api = FakeEvents()

    def events(self):
        return self.events_api


def enabled_config():
    return {
        "enabled": True,
        "calendar_id": "calendar@example.com",
        "credentials_file": "unused-in-tests.json",
        "timezone": "Europe/Moscow",
    }


def event_for(lesson, room_name="Room A.2.17", event_id="event-1"):
    body = google_calendar._event_body(lesson, room_name, "Europe/Moscow")
    body["id"] = event_id
    return body


def test_disabled_sync_does_not_build_google_service(monkeypatch, lesson):
    build = Mock()
    monkeypatch.setattr(google_calendar, "_build_service", build)
    stats = google_calendar.sync_schedule(
        1948, "Room", [lesson()], config={"enabled": False}
    )
    assert stats["disabled"] is True
    build.assert_not_called()


def test_sync_creates_missing_lesson(monkeypatch, lesson):
    service = FakeService()
    monkeypatch.setattr(google_calendar, "_list_managed_events", Mock(return_value=[]))
    stats = google_calendar.sync_schedule(
        1948, "Room A.2.17", [lesson()], service=service, config=enabled_config()
    )
    assert stats == {"created": 1, "updated": 0, "deleted": 0, "disabled": False}
    body = service.events_api.inserted[0]["body"]
    assert body["summary"] == "Высшая математика"
    assert body["start"]["timeZone"] == "Europe/Moscow"
    assert body["extendedProperties"]["private"]["ruzSource"] == "ruz_hack"


def test_sync_keeps_unchanged_event(monkeypatch, lesson):
    service = FakeService()
    existing = event_for(lesson())
    monkeypatch.setattr(
        google_calendar, "_list_managed_events", Mock(return_value=[existing])
    )
    stats = google_calendar.sync_schedule(
        1948, "Room A.2.17", [lesson()], service=service, config=enabled_config()
    )
    assert stats == {"created": 0, "updated": 0, "deleted": 0, "disabled": False}


def test_sync_updates_changed_details(monkeypatch, lesson):
    service = FakeService()
    current = lesson()
    existing = event_for(current)
    existing["extendedProperties"]["private"]["ruzFingerprint"] = "old"
    monkeypatch.setattr(
        google_calendar, "_list_managed_events", Mock(return_value=[existing])
    )
    stats = google_calendar.sync_schedule(
        1948, "Room A.2.17", [current], service=service, config=enabled_config()
    )
    assert stats["updated"] == 1
    assert service.events_api.updated[0]["eventId"] == "event-1"


def test_sync_deletes_event_removed_from_ruz(monkeypatch, lesson):
    service = FakeService()
    existing = event_for(lesson())
    monkeypatch.setattr(
        google_calendar, "_list_managed_events", Mock(return_value=[existing])
    )
    stats = google_calendar.sync_schedule(
        1948, "Room A.2.17", [], service=service, config=enabled_config()
    )
    assert stats["deleted"] == 1
    assert service.events_api.deleted[0]["eventId"] == "event-1"


def test_sync_only_uses_lessons_for_requested_room(monkeypatch, lesson):
    service = FakeService()
    monkeypatch.setattr(google_calendar, "_list_managed_events", Mock(return_value=[]))
    google_calendar.sync_schedule(
        1948,
        "Room A.2.17",
        [lesson(room_id=1949)],
        service=service,
        config=enabled_config(),
    )
    assert service.events_api.inserted == []
