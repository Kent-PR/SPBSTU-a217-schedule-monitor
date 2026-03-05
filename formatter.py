from datetime import datetime

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def format_date(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = WEEKDAYS_RU[dt.weekday()]
    return f"{dt.strftime('%d.%m.%Y')} ({day_name})"


def format_changes(room_name, added, removed):
    """
    Generates a text message about changes for a single classroom.
    Returns a string or None if there are no changes.
    """
    if not added and not removed:
        return None # Don't send anything if there are no changes.

    lines = [f"⚠ Изменения в {room_name}"]

    if added:
        lines.append("➕ Добавлено:")
        for item in added:
            lines.append(f"  {format_date(item['date'])}\n    {item['start']} {item['subject']}")

    if removed:
        lines.append("➖ Удалено:")
        for item in removed:
            lines.append(f"  {format_date(item['date'])}\n    {item['start']} {item['subject']}")

    return "\n".join(lines)