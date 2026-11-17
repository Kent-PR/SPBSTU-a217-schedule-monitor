from datetime import date
from unittest.mock import Mock

import main


def test_calendar_audit_notifies_and_saves_new_missing_lessons(monkeypatch, lesson):
    missing = [lesson()]
    send = Mock(return_value=True)
    save = Mock()
    monkeypatch.setattr(main, "find_missing_lessons", Mock(return_value=missing))
    monkeypatch.setattr(main, "load_calendar_missing", Mock(return_value=[]))
    monkeypatch.setattr(main, "save_calendar_missing", save)
    monkeypatch.setattr(main, "send_or_queue", send)

    main.audit_google_calendar(1948, "Room A.2.17", missing, date(2026, 11, 16))

    assert "Не внесено в прод-календарь" in send.call_args.args[0]
    assert "18.11.2026" in send.call_args.args[0]
    assert "10:00" not in send.call_args.args[0]
    assert "Высшая математика" not in send.call_args.args[0]
    save.assert_called_once_with(1948, ["2026-11-18"])


def test_calendar_audit_does_not_repeat_unchanged_alert(monkeypatch, lesson):
    missing = [
        lesson(),
        lesson(start="12:00", end="13:40", subject="Физика"),
    ]
    send = Mock()
    monkeypatch.setattr(main, "find_missing_lessons", Mock(return_value=missing))
    monkeypatch.setattr(main, "load_calendar_missing", Mock(return_value=["2026-11-18"]))
    monkeypatch.setattr(main, "save_calendar_missing", Mock())
    monkeypatch.setattr(main, "send_or_queue", send)

    main.audit_google_calendar(1948, "Room A.2.17", missing, date(2026, 11, 16))

    send.assert_not_called()


def test_calendar_audit_clears_saved_state_when_calendar_is_complete(
    monkeypatch, lesson
):
    save = Mock()
    monkeypatch.setattr(main, "find_missing_lessons", Mock(return_value=[]))
    monkeypatch.setattr(main, "load_calendar_missing", Mock(return_value=[lesson()]))
    monkeypatch.setattr(main, "save_calendar_missing", save)
    monkeypatch.setattr(main, "send_or_queue", Mock())

    main.audit_google_calendar(1948, "Room A.2.17", [], date(2026, 11, 16))

    save.assert_called_once_with(1948, [])
