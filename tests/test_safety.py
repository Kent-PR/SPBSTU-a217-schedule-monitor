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
    monkeypatch.setattr(main, "record_fetch_failure", Mock())
    monkeypatch.setattr(main, "record_fetch_success", Mock())
    monkeypatch.setattr(main, "sync_synchronized_calendar", Mock())
    monkeypatch.setattr(main, "audit_google_calendar", Mock())

    main.run_check()

    assert fetch.call_count == 2


def test_summary_run_fetches_each_room_only_once(monkeypatch):
    schedule = []
    fetch = Mock(return_value=schedule)
    instant = Mock()
    summary = Mock()
    monkeypatch.setattr(main, "ROOMS", {1948: "Room A.2.17"})
    monkeypatch.setattr(main, "fetch_full_schedule", fetch)
    monkeypatch.setattr(main, "instant_check", instant)
    monkeypatch.setattr(main, "summary_check", summary)
    monkeypatch.setattr(main, "retry_failed_messages", Mock())
    monkeypatch.setattr(main, "record_fetch_success", Mock())

    main.run_check(is_summary=True)

    fetch.assert_called_once_with(1948)
    instant.assert_called_once()
    summary.assert_called_once()
    assert instant.call_args.args[3] is schedule
    assert summary.call_args.args[3] is schedule


def test_outage_alert_once_and_recovery_after_success(monkeypatch):
    state = {}
    fetch = Mock(side_effect=RuntimeError("API failed"))
    send = Mock(return_value=True)

    def save_state(room_id, new_state):
        assert room_id == 1948
        state.clear()
        state.update(new_state)

    monkeypatch.setattr(main, "ROOMS", {1948: "Room A.2.17"})
    monkeypatch.setattr(main, "OUTAGE_ALERT_THRESHOLD", 3)
    monkeypatch.setattr(main, "fetch_full_schedule", fetch)
    monkeypatch.setattr(main, "load_availability_state", lambda room_id: dict(state))
    monkeypatch.setattr(main, "save_availability_state", save_state)
    monkeypatch.setattr(main, "send_or_queue", send)
    monkeypatch.setattr(main, "retry_failed_messages", Mock())
    monkeypatch.setattr(main, "instant_check", Mock())

    for _ in range(4):
        main.run_check()

    assert send.call_count == 1
    assert "3" in send.call_args.args[0]
    assert state == {"consecutive_failures": 4, "outage_notified": True}

    fetch.side_effect = None
    fetch.return_value = []
    main.run_check()

    assert send.call_count == 2
    assert "восстановлен" in send.call_args.args[0]
    assert "4" in send.call_args.args[0]
    assert state == {}

