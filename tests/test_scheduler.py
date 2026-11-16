from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

import scheduler


class FakeClock:
    def __init__(self, start):
        self.start = start
        self.seconds = 0.0

    def now(self):
        return self.start + timedelta(seconds=self.seconds)

    def monotonic(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds

    def advance(self, seconds):
        self.seconds += seconds


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 11, 16, 9, 59, 59), None),
        (datetime(2026, 11, 16, 10, 0, 0), "2026-11-16_10:00"),
        (datetime(2026, 11, 16, 10, 9, 59), "2026-11-16_10:00"),
        (datetime(2026, 11, 16, 10, 10, 0), None),
        (datetime(2026, 11, 16, 17, 5, 0), "2026-11-16_17:00"),
        (datetime(2026, 11, 16, 18, 0, 0), None),
    ],
)
def test_due_summary_slot_window(now, expected):
    assert scheduler.get_due_summary_slot(now) == expected


def test_completed_summary_slot_is_not_returned_again():
    completed = {"2026-11-16_10:00"}

    assert (
        scheduler.get_due_summary_slot(
            datetime(2026, 11, 16, 10, 5), completed
        )
        is None
    )


def test_checks_keep_start_to_start_interval(monkeypatch):
    clock = FakeClock(datetime(2026, 11, 16, 8, 0))
    starts = []

    def check(is_summary):
        starts.append(clock.seconds)
        clock.advance(120)

    monkeypatch.setattr(scheduler, "run_check", check)

    scheduler.run_scheduler(
        lambda: len(starts) < 3,
        now_fn=clock.now,
        monotonic_fn=clock.monotonic,
        sleep_fn=clock.sleep,
    )

    assert starts == [0, 600, 1200]


def test_summary_runs_once_for_planned_slot(monkeypatch):
    clock = FakeClock(datetime(2026, 11, 16, 10, 0))
    calls = []

    def check(is_summary):
        calls.append(is_summary)

    monkeypatch.setattr(scheduler, "run_check", check)

    scheduler.run_scheduler(
        lambda: len(calls) < 2,
        now_fn=clock.now,
        monotonic_fn=clock.monotonic,
        sleep_fn=clock.sleep,
    )

    assert calls == [True, False]


def test_missed_old_summary_is_not_backfilled(monkeypatch):
    clock = FakeClock(datetime(2026, 11, 16, 12, 0))
    calls = []
    monkeypatch.setattr(
        scheduler,
        "run_check",
        lambda is_summary: calls.append(is_summary),
    )

    scheduler.run_scheduler(
        lambda: len(calls) < 1,
        now_fn=clock.now,
        monotonic_fn=clock.monotonic,
        sleep_fn=clock.sleep,
    )

    assert calls == [False]


def test_unhandled_check_error_does_not_stop_scheduler(monkeypatch):
    clock = FakeClock(datetime(2026, 11, 16, 8, 0))
    attempts = []

    def check(is_summary):
        attempts.append(clock.seconds)
        if len(attempts) == 1:
            raise RuntimeError("temporary failure")

    monkeypatch.setattr(scheduler, "run_check", check)

    scheduler.run_scheduler(
        lambda: len(attempts) < 2,
        now_fn=clock.now,
        monotonic_fn=clock.monotonic,
        sleep_fn=clock.sleep,
    )

    assert attempts == [0, 600]


def test_wait_stops_responsively():
    clock = FakeClock(datetime(2026, 11, 16, 8, 0))
    running = Mock(side_effect=[True, False])

    completed = scheduler.wait_until(
        600,
        running,
        clock.monotonic,
        clock.sleep,
    )

    assert completed is False
    assert clock.seconds == 1
