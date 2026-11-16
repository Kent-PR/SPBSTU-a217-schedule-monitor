import sys
from types import ModuleType

import pytest


# Tests never use real Telegram credentials.
credentials = ModuleType("tg_credentials")
credentials.TG_TOKEN = "test-token"
credentials.TG_CHAT_ID = "test-chat"
credentials.TG_PROXY = "http://127.0.0.1:10808"
sys.modules["tg_credentials"] = credentials


@pytest.fixture
def lesson():
    def factory(**overrides):
        item = {
            "room_id": 1948,
            "date": "2026-11-18",
            "start": "10:00",
            "end": "11:40",
            "subject": "Высшая математика",
            "teacher": {
                "first_name": "Иван",
                "middle_name": "Иванович",
                "last_name": "Иванов",
            },
            "groups": [{"id": 1, "name": "Группа 1"}],
        }
        item.update(overrides)
        return item

    return factory

