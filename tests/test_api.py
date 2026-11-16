from datetime import datetime
from unittest.mock import Mock

import pytest
import requests

import main


def valid_week():
    return {
        "days": [
            {
                "date": "2026-11-18",
                "lessons": [
                    {
                        "time_start": "10:00",
                        "time_end": "11:40",
                        "subject": "Математика",
                        "teachers": [],
                        "groups": [{"id": 1}],
                    }
                ],
            }
        ]
    }


def test_fetch_week_uses_timeout_and_returns_valid_data(monkeypatch):
    response = Mock(status_code=200, url="https://ruz.test/week")
    response.raise_for_status.return_value = None
    response.json.return_value = valid_week()
    get = Mock(return_value=response)
    monkeypatch.setattr(main.requests, "get", get)

    assert main.fetch_week(1948, datetime(2026, 11, 16)) == valid_week()
    assert get.call_args.kwargs["timeout"] == (5, 20)


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        {"days": "invalid"},
        {"days": [{"date": "18.11.2026", "lessons": []}]},
        {"days": [{"date": "2026-11-18", "lessons": "invalid"}]},
        {
            "days": [
                {
                    "date": "2026-11-18",
                    "lessons": [
                        {
                            "time_start": "25:00",
                            "time_end": "11:40",
                            "subject": "Математика",
                        }
                    ],
                }
            ]
        },
    ],
)
def test_invalid_api_structures_are_rejected(data):
    with pytest.raises(main.ScheduleDataError):
        main.validate_week_data(data)


def test_http_error_is_logged_and_raised(monkeypatch, caplog):
    request = requests.Request("GET", "https://ruz.spbstu.ru/test").prepare()
    response = requests.Response()
    response.status_code = 503
    response.request = request
    error = requests.HTTPError("503 Server Error", request=request, response=response)
    monkeypatch.setattr(main.requests, "get", Mock(side_effect=error))

    with pytest.raises(requests.HTTPError):
        main.fetch_week(1948, datetime(2026, 11, 16))

    assert "status=503" in caplog.text
    assert "https://ruz.spbstu.ru/test" in caplog.text


def test_timeout_is_logged_and_raised(monkeypatch, caplog):
    request = requests.Request("GET", "https://ruz.spbstu.ru/test").prepare()
    error = requests.ConnectTimeout("timed out", request=request)
    monkeypatch.setattr(main.requests, "get", Mock(side_effect=error))

    with pytest.raises(requests.ConnectTimeout):
        main.fetch_week(1948, datetime(2026, 11, 16))

    assert "ConnectTimeout" in caplog.text


def test_invalid_json_is_logged_and_raised(monkeypatch, caplog):
    response = Mock(status_code=200, url="https://ruz.test/week")
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("invalid JSON")
    monkeypatch.setattr(main.requests, "get", Mock(return_value=response))

    with pytest.raises(ValueError):
        main.fetch_week(1948, datetime(2026, 11, 16))

    assert "invalid JSON" in caplog.text

