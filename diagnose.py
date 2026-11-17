import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


os.environ.setdefault("SCHEDULE_MONITOR_DISABLE_FILE_LOGGING", "1")

BASE_DIR = Path(__file__).resolve().parent
SERVICE_NAME = "ScheduleMonitorService"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


def check_configuration():
    try:
        from constants import (
            CHECK_INTERVAL,
            GOOGLE_CALENDAR,
            OUTAGE_ALERT_THRESHOLD,
            ROOMS,
        )
    except Exception as error:
        return CheckResult("Configuration", "FAIL", str(error))

    calendar_status = "enabled" if GOOGLE_CALENDAR.get("enabled") else "disabled"
    return CheckResult(
        "Configuration",
        "OK",
        f"rooms={len(ROOMS)}, interval={CHECK_INTERVAL}s, "
        f"outage_threshold={OUTAGE_ALERT_THRESHOLD}, calendar={calendar_status}",
    )


def check_json_files(base_dir=BASE_DIR):
    paths = []
    for directory_name in ("data", "messages_queue"):
        directory = Path(base_dir) / directory_name
        if directory.exists():
            paths.extend(directory.rglob("*.json"))

    if not paths:
        return [CheckResult("Local JSON", "WARN", "no runtime JSON files found")]

    results = []
    invalid = []
    for path in sorted(paths):
        try:
            with open(path, "r", encoding="utf-8") as file:
                json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            invalid.append(f"{path.relative_to(base_dir)}: {error}")

    if invalid:
        results.extend(CheckResult("Local JSON", "FAIL", detail) for detail in invalid)
    else:
        results.append(
            CheckResult("Local JSON", "OK", f"valid files={len(paths)}")
        )
    return results


def check_ruz():
    try:
        from constants import ROOMS
        from main import fetch_week
    except Exception as error:
        return [CheckResult("RUZ API", "FAIL", f"initialization failed: {error}")]

    results = []
    today = date.today()
    for room_id, room_name in ROOMS.items():
        try:
            week = fetch_week(room_id, today)
            days = week.get("days", [])
            lessons = sum(len(day.get("lessons", [])) for day in days)
            results.append(
                CheckResult(
                    f"RUZ {room_name}",
                    "OK",
                    f"room_id={room_id}, days={len(days)}, lessons={lessons}",
                )
            )
        except Exception as error:
            results.append(CheckResult(f"RUZ {room_name}", "FAIL", str(error)))
    return results


def check_telegram():
    try:
        import requests
        from telegram_notifier import CHAT_ID, PROXIES, TOKEN
    except Exception as error:
        return CheckResult("Telegram", "FAIL", f"initialization failed: {error}")

    url = f"https://api.telegram.org/bot{TOKEN}/getChat"
    failures = []
    attempts = (("proxy", PROXIES), ("direct", None))
    for connection_name, proxies in attempts:
        try:
            response = requests.get(
                url,
                params={"chat_id": CHAT_ID},
                timeout=10,
                proxies=proxies,
            )
            response.raise_for_status()
            status = "OK" if connection_name == "proxy" else "WARN"
            detail = f"getChat succeeded via {connection_name} connection"
            if failures:
                detail += f"; proxy error: {failures[0]}"
            return CheckResult("Telegram", status, detail)
        except requests.RequestException as error:
            safe_error = str(error).replace(TOKEN, "***")
            failures.append(f"{connection_name}: {safe_error}")

    return CheckResult("Telegram", "FAIL", "; ".join(failures))


def check_google_calendar():
    try:
        from constants import GOOGLE_CALENDAR, ROOMS
        from google_calendar import _build_service
    except Exception as error:
        return [
            CheckResult(
                "Google Calendar", "FAIL", f"initialization failed: {error}"
            )
        ]

    if not GOOGLE_CALENDAR.get("enabled"):
        return [CheckResult("Google Calendar", "WARN", "integration is disabled")]

    try:
        service = _build_service(GOOGLE_CALENDAR["credentials_file"])
    except Exception as error:
        return [CheckResult("Google Calendar", "FAIL", str(error))]

    results = []
    for room_id, room_name in ROOMS.items():
        calendar_id = GOOGLE_CALENDAR["calendars"].get(room_id)
        try:
            metadata = service.calendars().get(calendarId=calendar_id).execute()
            summary = metadata.get("summary") or "unnamed calendar"
            results.append(
                CheckResult(
                    f"Calendar {room_name}",
                    "OK",
                    f"read access confirmed: {summary}",
                )
            )
        except Exception as error:
            results.append(
                CheckResult(f"Calendar {room_name}", "FAIL", str(error))
            )
    return results


def check_windows_service():
    try:
        completed = subprocess.run(
            ["sc", "query", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return CheckResult("Windows service", "WARN", str(error))

    output = " ".join(completed.stdout.split())
    if completed.returncode != 0:
        detail = " ".join(completed.stderr.split()) or output or "query failed"
        return CheckResult("Windows service", "WARN", detail)
    if "RUNNING" in output:
        return CheckResult("Windows service", "OK", f"{SERVICE_NAME} is running")
    if "STOPPED" in output:
        return CheckResult("Windows service", "WARN", f"{SERVICE_NAME} is stopped")
    return CheckResult("Windows service", "WARN", output or "unknown state")


def run_diagnostics():
    results = [check_configuration()]
    results.extend(check_json_files())
    results.extend(check_ruz())
    results.append(check_telegram())
    results.extend(check_google_calendar())
    results.append(check_windows_service())
    return results


def main():
    if hasattr(sys.stdout, "reconfigure") and not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"Schedule Monitor diagnostics — {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("-" * 72)
    results = run_diagnostics()
    for result in results:
        print(f"[{result.status:<4}] {result.name}: {result.detail}")

    failures = sum(result.status == "FAIL" for result in results)
    warnings = sum(result.status == "WARN" for result in results)
    print("-" * 72)
    print(f"Result: failures={failures}, warnings={warnings}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
