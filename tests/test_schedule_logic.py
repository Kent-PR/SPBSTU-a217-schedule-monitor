from main import compare_schedules, merge_lessons


def test_merge_same_lesson_with_different_groups(lesson):
    first = lesson(groups=[{"id": 1, "name": "Группа 1"}])
    second = lesson(groups=[{"id": 2, "name": "Группа 2"}])

    merged = merge_lessons([first, second])

    assert len(merged) == 1
    assert {group["id"] for group in merged[0]["groups"]} == {1, 2}


def test_merge_does_not_duplicate_groups(lesson):
    merged = merge_lessons([lesson(), lesson()])

    assert len(merged) == 1
    assert len(merged[0]["groups"]) == 1


def test_merge_ignores_teacher_difference(lesson):
    another_teacher = {
        "first_name": "Пётр",
        "middle_name": "Петрович",
        "last_name": "Петров",
    }

    assert len(merge_lessons([lesson(), lesson(teacher=another_teacher)])) == 1


def test_merge_keeps_different_subjects_and_times(lesson):
    lessons = [
        lesson(),
        lesson(subject="Физика"),
        lesson(start="12:00", end="13:40"),
    ]

    assert len(merge_lessons(lessons)) == 3


def test_compare_detects_added_and_removed_lessons(lesson):
    old = [lesson(subject="Старая пара")]
    new = [lesson(subject="Новая пара")]

    added, removed = compare_schedules(old, new)

    assert added == new
    assert removed == old


def test_compare_ignores_teacher_and_group_changes(lesson):
    old = [lesson()]
    new = [
        lesson(
            teacher={"last_name": "Петров"},
            groups=[{"id": 99, "name": "Другая группа"}],
        )
    ]

    assert compare_schedules(old, new) == ([], [])


def test_compare_ignores_order(lesson):
    first = lesson(subject="Математика")
    second = lesson(subject="Физика", start="12:00", end="13:40")

    assert compare_schedules([first, second], [second, first]) == ([], [])


def test_compare_treats_time_change_as_remove_and_add(lesson):
    old = [lesson()]
    new = [lesson(start="10:10")]

    assert compare_schedules(old, new) == (new, old)

