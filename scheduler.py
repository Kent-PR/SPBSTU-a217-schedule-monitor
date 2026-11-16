import time
import logging
from datetime import datetime
from main import run_check
from constants import SUMMARY_TIMES, CHECK_INTERVAL


def get_due_summary_slot(now, completed_slots=None):
    completed_slots = completed_slots or set()

    for hour, minute in SUMMARY_TIMES:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        seconds_after_target = (now - target).total_seconds()
        slot_key = target.strftime("%Y-%m-%d_%H:%M")

        if (
            0 <= seconds_after_target < CHECK_INTERVAL
            and slot_key not in completed_slots
        ):
            return slot_key

    return None


def is_summary_time(now=None):
    return get_due_summary_slot(now or datetime.now()) is not None


def wait_until(deadline, running_flag, monotonic_fn, sleep_fn):
    while running_flag():
        remaining = deadline - monotonic_fn()
        if remaining <= 0:
            return True
        sleep_fn(min(1, remaining))

    return False


def run_scheduler(
    running_flag,
    now_fn=None,
    monotonic_fn=None,
    sleep_fn=None,
):
    now_fn = now_fn or datetime.now
    monotonic_fn = monotonic_fn or time.monotonic
    sleep_fn = sleep_fn or time.sleep

    logging.info("Scheduler started")
    summary_done = set()
    next_check = monotonic_fn()

    while running_flag():
        cycle_started = monotonic_fn()
        now = now_fn()
        date_str = now.strftime("%Y-%m-%d")
        summary_done = {key for key in summary_done if key.startswith(date_str)}
        summary_slot = get_due_summary_slot(now, summary_done)

        try:
            if summary_slot:
                logging.info("Summary check triggered for %s", summary_slot)
            run_check(is_summary=summary_slot is not None)
        except Exception:
            logging.exception("Unhandled error in scheduler check")
        else:
            if summary_slot:
                summary_done.add(summary_slot)

        next_check = max(next_check + CHECK_INTERVAL, cycle_started + CHECK_INTERVAL)
        if not wait_until(next_check, running_flag, monotonic_fn, sleep_fn):
            break
