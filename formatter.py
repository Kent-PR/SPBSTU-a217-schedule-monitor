from datetime import datetime

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def format_date(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = WEEKDAYS_RU[dt.weekday()]
    return f"{dt.strftime('%d.%m.%Y')} ({day_name})"


def truncate(text, max_len=40):
    if not text:
        return "—"
    return text if len(text) <= max_len else text[:max_len].rstrip() + "..."


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
        lines.append("")
        lines.append(f"📅 {a['date']}")
        lines.append(f"🕐 {a['start']}")

    return "\n".join(lines)