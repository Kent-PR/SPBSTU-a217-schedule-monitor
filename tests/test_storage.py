import json
from unittest.mock import Mock

import pytest

import storage


def test_atomic_write_replaces_complete_json(tmp_path):
    target = tmp_path / "schedule.json"
    target.write_text('{"old": true}', encoding="utf-8")

    storage.atomic_write_json(target, {"new": "data"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"new": "data"}
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_failed_write_preserves_previous_file_and_removes_temporary(
    tmp_path, monkeypatch
):
    target = tmp_path / "schedule.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def broken_dump(data, file, **kwargs):
        file.write('{"partial":')
        raise OSError("disk failure")

    monkeypatch.setattr(storage.json, "dump", broken_dump)

    with pytest.raises(OSError, match="disk failure"):
        storage.atomic_write_json(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
    assert list(tmp_path.iterdir()) == [target]


def test_replace_failure_preserves_previous_file_and_removes_temporary(
    tmp_path, monkeypatch
):
    target = tmp_path / "schedule.json"
    target.write_text('{"old": true}', encoding="utf-8")
    monkeypatch.setattr(storage.os, "replace", Mock(side_effect=OSError("locked")))

    with pytest.raises(OSError, match="locked"):
        storage.atomic_write_json(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
    assert list(tmp_path.iterdir()) == [target]


def test_all_storage_saves_use_atomic_writer(tmp_path, monkeypatch):
    atomic = Mock()
    monkeypatch.setattr(storage, "atomic_write_json", atomic)
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(storage, "MESSAGES_DIR", tmp_path / "messages")

    storage.save_current_schedule(1948, ["current"])
    storage.save_snapshot_schedule(1948, ["snapshot"])
    storage.save_changes(1948, "2026-11-17", ["added"], ["removed"])
    storage.save_calendar_missing(1948, ["2026-11-18"])
    storage.save_failed_messages(["message"])

    assert atomic.call_count == 5
