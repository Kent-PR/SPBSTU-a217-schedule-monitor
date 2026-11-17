import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import main


def test_tests_disable_production_file_handler():
    assert os.environ[main.DISABLE_FILE_LOGGING_ENV] == "1"

    production_log = (main.LOG_DIR / main.LOG_FILE).resolve()
    active_log_files = {
        Path(handler.baseFilename).resolve()
        for handler in logging.getLogger().handlers
        if isinstance(handler, RotatingFileHandler)
    }

    assert production_log not in active_log_files


def test_caplog_still_receives_application_messages(caplog):
    with caplog.at_level(logging.ERROR):
        logging.error("synthetic test error")

    assert "synthetic test error" in caplog.text
