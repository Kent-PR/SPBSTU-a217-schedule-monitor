from datetime import date
from unittest.mock import Mock

import main


def test_instant_check_does_not_replace_nonempty_snapshot_with_empty(
    monkeypatch, lesson
):
    save_snapshot = Mock()
    save_changes = Mock()
    send = Mock()
    monkeypatch.setattr(main, "fetch_full_schedule", Mock(return_value=[]))
    monkeypatch.setattr(main, "load_snapshot_schedule", Mock(return_value=[lesson()]))
    monkeypatch.setattr(main, "save_snapshot_schedule", save_snapshot)
    monkeypatch.setattr(main, "save_changes", save_changes)
    monkeypatch.setattr(main, "send_or_queue", send)

    main.instant_check(1948, "Room", date(2026, 11, 16))

    save_snapshot.assert_not_called()
    save_changes.assert_not_called()
    send.assert_not_called()


def test_summary_check_preserves_both_baselines_on_empty_response(
    monkeypatch, lesson
):
    save_current = Mock()
    save_snapshot = Mock()
    send = Mock()
    monkeypatch.setattr(main, "fetch_full_schedule", Mock(return_value=[]))
    monkeypatch.setattr(main, "load_current_schedule", Mock(return_value=[lesson()]))
    monkeypatch.setattr(main, "save_current_schedule", save_current)
    monkeypatch.setattr(main, "save_snapshot_schedule", save_snapshot)
    monkeypatch.setattr(main, "send_or_queue", send)

    main.summary_check(1948, "Room", date(2026, 11, 16))

    save_current.assert_not_called()
    save_snapshot.assert_not_called()
    send.assert_not_called()


def test_failure_of_first_room_does_not_skip_second_room(monkeypatch):
    fetch = Mock(side_effect=[RuntimeError("API failed"), []])
    monkeypatch.setattr(main, "fetch_full_schedule", fetch)
    monkeypatch.setattr(main, "load_snapshot_schedule", Mock(return_value=[]))
    monkeypatch.setattr(main, "retry_failed_messages", Mock())

    main.run_check()

    assert fetch.call_count == 2

