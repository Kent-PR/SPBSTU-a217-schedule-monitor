import time
import logging
from datetime import datetime
from main import run_check
from constants import SUMMARY_TIMES, CHECK_INTERVAL


def is_summary_time():
    now = datetime.now()
    for hour, minute in SUMMARY_TIMES:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        diff = abs((now - target).total_seconds())
        if diff <= CHECK_INTERVAL / 2:
            return True
    return False


def run_scheduler(running_flag):
    logging.info("Scheduler started")
    summary_done = set()

    while running_flag():
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%Y-%m-%d")

        key = f"{date_str}_{time_str}"

        if is_summary_time() and key not in summary_done:
            logging.info(f"Summary check triggered at {time_str}")
            run_check(is_summary=True)
            summary_done.add(key)
        else:
            run_check(is_summary=False)

        # чистим старые ключи чтобы set не рос бесконечно
        summary_done = {k for k in summary_done if k.startswith(date_str)}

        for _ in range(CHECK_INTERVAL):
            if not running_flag():
                break
            time.sleep(1)
