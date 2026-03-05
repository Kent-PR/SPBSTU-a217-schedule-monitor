import time
import logging
from main import run_check

logging.basicConfig(
    filename="logs/schedule_service.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.info("Service runner started")

while True:
    try:
        run_check()
    except Exception:
        logging.exception("Error in service loop")

    time.sleep(600)  # 10 минут