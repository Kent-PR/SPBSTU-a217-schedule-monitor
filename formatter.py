from datetime import datetime
from constants import WEEKDAYS_RU


def format_date(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = WEEKDAYS_RU[dt.weekday()]
    return f"{dt.strftime('%d.%m.%Y')} ({day_name})"


def truncate(text, max_len=40):
    if not text:
        return "—"
    return text if len(text) <= max_len else text[:max_len].rstrip() + "..."


def format_teacher(teacher):
    if not teacher:
        return "—"
    if not isinstance(teacher, dict):
        return str(teacher)

    last_name = teacher.get("last_name") or ""
    initials = " ".join(
        f"{name[0]}."
        for name in (teacher.get("first_name"), teacher.get("middle_name"))
        if name
    )
    return " ".join(part for part in (last_name, initials) if part) or "—"


def format_changes(room_name, added, removed):
    """
    Generates a text message about changes for a single classroom.
    Returns a string or None if there are no changes.
    """
    if not added and not removed:
        return None # Don't send anything if there are no changes.

    lines = [f"⚠ Изменения в {room_name}"]

    if added:
        lines.append("")
        lines.append("➕ Добавлено")
        for item in added:
            lines.append(f"📅 {format_date(item['date'])}")
            lines.append(f"🕐 {item['start']} – {item['end']}")
            lines.append(f"📖 {truncate(item['subject'])}")
            lines.append("")

    if removed:
        lines.append("➖ Удалено")
        for item in removed:
            lines.append(f"📅 {format_date(item['date'])}")
            lines.append(f"🕐 {item['start']} – {item['end']}")
            lines.append(f"📖 {truncate(item['subject'])}")
            lines.append("")

    return "\n".join(lines)


def format_conflicts(room_name, conflicts):
    if not conflicts:
        return None

    lines = [f"⚠️ Конфликты в {room_name}"]

    for a, b in conflicts:
        lines.extend([
            "",
            f"📅 {format_date(a['date'])}",
            "",
            f"🕐 {a['start']} – {a['end']}",
            f"📖 {truncate(a['subject'], max_len=80)}",
            f"👤 {format_teacher(a.get('teacher'))}",
            "",
            "↕ пересекается с",
            "",
            f"🕐 {b['start']} – {b['end']}",
            f"📖 {truncate(b['subject'], max_len=80)}",
            f"👤 {format_teacher(b.get('teacher'))}",
        ])

    return "\n".join(lines)
