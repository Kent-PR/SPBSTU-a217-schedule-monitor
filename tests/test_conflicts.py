from conflict_checker import find_conflicts, has_overlap
from formatter import format_conflicts, format_teacher


def test_different_overlapping_subjects_are_conflict(lesson):
    first = lesson(subject="Математика", start="10:00", end="11:40")
    second = lesson(subject="Физика", start="11:00", end="12:40")

    assert find_conflicts([first, second]) == [(first, second)]


def test_touching_time_boundaries_are_not_overlap():
    assert not has_overlap("10:00", "11:40", "11:40", "13:20")


def test_same_subject_is_not_conflict(lesson):
    first = lesson(start="10:00", end="11:40")
    second = lesson(start="11:00", end="12:40")

    assert find_conflicts([first, second]) == []


def test_different_rooms_or_dates_are_not_conflict(lesson):
    first = lesson(subject="Математика")
    another_room = lesson(subject="Физика", room_id=1949)
    another_date = lesson(subject="Химия", date="2026-11-19")

    assert find_conflicts([first, another_room, another_date]) == []


def test_conflict_message_contains_both_lessons(lesson):
    first = lesson(subject="Математика", start="10:00", end="11:40")
    second = lesson(
        subject="Проектная деятельность",
        start="11:00",
        end="12:40",
        teacher=None,
    )

    message = format_conflicts("Room A.2.17", [(first, second)])

    assert "18.11.2026 (Ср)" in message
    assert "10:00 – 11:40" in message
    assert "11:00 – 12:40" in message
    assert "Математика" in message
    assert "Проектная деятельность" in message
    assert "Иванов И. И." in message
    assert "пересекается с" in message


def test_teacher_formatting_without_teacher():
    assert format_teacher(None) == "—"

