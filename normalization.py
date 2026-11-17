import unicodedata


def normalize_text(value):
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return " ".join(text.split())


def text_key(value):
    return normalize_text(value).casefold()


def subject_key(value):
    return text_key(value)


def lesson_key(lesson):
    return (
        lesson["room_id"],
        normalize_text(lesson["date"]),
        normalize_text(lesson["start"]),
        normalize_text(lesson["end"]),
        subject_key(lesson["subject"]),
    )


def normalize_lesson(lesson):
    normalized = lesson.copy()

    for field in ("date", "start", "end", "subject"):
        normalized[field] = normalize_text(lesson.get(field))

    teacher = lesson.get("teacher")
    if isinstance(teacher, dict):
        normalized["teacher"] = teacher.copy()
        for field in ("first_name", "middle_name", "last_name"):
            value = normalize_text(teacher.get(field))
            normalized["teacher"][field] = value or None

    groups = []
    for group in lesson.get("groups") or []:
        normalized_group = group.copy()
        if "name" in normalized_group:
            normalized_group["name"] = normalize_text(normalized_group["name"])
        groups.append(normalized_group)
    normalized["groups"] = groups

    return normalized
