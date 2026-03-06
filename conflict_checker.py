from datetime import datetime


def parse_time(t):
    return datetime.strptime(t, "%H:%M")


def has_overlap(start1, end1, start2, end2):
    return parse_time(start1) < parse_time(end2) and parse_time(start2) < parse_time(end1)


def find_conflicts(lessons):
    conflicts = []

    for i, a in enumerate(lessons):
        for b in lessons[i + 1:]:
            if a["room_id"] != b["room_id"]:
                continue
            if a["date"] != b["date"]:
                continue
            if a["subject"] == b["subject"]:
                continue
            if has_overlap(a["start"], a["end"], b["start"], b["end"]):
                conflicts.append((a, b))

    return conflicts
