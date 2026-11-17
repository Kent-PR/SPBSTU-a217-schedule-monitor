import json

import requests

import diagnose


class FakeResponse:
    def __init__(self, error=None):
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


def test_json_check_accepts_valid_runtime_files(tmp_path):
    data_dir = tmp_path / "data" / "1948"
    data_dir.mkdir(parents=True)
    (data_dir / "schedule.json").write_text(
        json.dumps({"lessons": []}), encoding="utf-8"
    )

    results = diagnose.check_json_files(tmp_path)

    assert results == [diagnose.CheckResult("Local JSON", "OK", "valid files=1")]


def test_json_check_reports_invalid_file(tmp_path):
    queue_dir = tmp_path / "messages_queue"
    queue_dir.mkdir()
    (queue_dir / "failed_messages.json").write_text("[broken", encoding="utf-8")

    results = diagnose.check_json_files(tmp_path)

    assert len(results) == 1
    assert results[0].status == "FAIL"
    assert "failed_messages.json" in results[0].detail


def test_telegram_check_falls_back_to_direct_connection(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs["proxies"])
        if kwargs["proxies"] is not None:
            return FakeResponse(requests.ConnectionError("proxy unavailable"))
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    result = diagnose.check_telegram()

    assert result.status == "WARN"
    assert "direct" in result.detail
    assert len(calls) == 2


def test_main_returns_failure_exit_code(monkeypatch):
    monkeypatch.setattr(
        diagnose,
        "run_diagnostics",
        lambda: [diagnose.CheckResult("RUZ", "FAIL", "unavailable")],
    )

    assert diagnose.main() == 1
