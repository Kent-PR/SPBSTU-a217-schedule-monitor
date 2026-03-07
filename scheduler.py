import time
import logging
from datetime import datetime
from main import run_check

SUMMARY_TIMES = ["10:00", "17:00"]
CHECK_INTERVAL = 600  # 10 минут


def is_summary_time():
    now = datetime.now().strftime("%H:%M")
    return now in SUMMARY_TIMES


def run_scheduler():
    logging.info("Scheduler started")
    summary_done = set()

    while True:
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

        time.sleep(CHECK_INTERVAL)