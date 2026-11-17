from conflict_checker import find_conflicts
from main import compare_schedules, merge_lessons
from normalization import normalize_lesson, normalize_text, subject_key


def test_normalize_text_collapses_whitespace_and_unicode():
    assert normalize_text("  Высшая\u00a0  математика\t") == "Высшая математика"
    assert normalize_text("Ａｕｄｉｔｏｒｉｕｍ") == "Auditorium"


def test_subject_key_is_case_insensitive():
    assert subject_key("Высшая математика") == subject_key(" ВЫСШАЯ   МАТЕМАТИКА ")


def test_normalize_lesson_cleans_display_fields(lesson):
    item = lesson(
        subject="  Высшая   математика ",
        teacher={
            "first_name": " Иван ",
            "middle_name": "  Иванович  ",
            "last_name": "Иванов ",
        },
        groups=[{"id": 1, "name": "  Группа   1 "}],
    )

    normalized = normalize_lesson(item)

    assert normalized["subject"] == "Высшая математика"
    assert normalized["teacher"]["first_name"] == "Иван"
    assert normalized["teacher"]["middle_name"] == "Иванович"
    assert normalized["teacher"]["last_name"] == "Иванов"
    assert normalized["groups"][0]["name"] == "Группа 1"


def test_merge_treats_whitespace_and_case_variants_as_one_lesson(lesson):
    merged = merge_lessons(
        [
            lesson(subject="Высшая математика", groups=[{"id": 1}]),
            lesson(subject="  ВЫСШАЯ   МАТЕМАТИКА ", groups=[{"id": 2}]),
        ]
    )

    assert len(merged) == 1
    assert merged[0]["subject"] == "Высшая математика"
    assert {group["id"] for group in merged[0]["groups"]} == {1, 2}


def test_compare_ignores_cosmetic_subject_changes(lesson):
    old = [lesson(subject="Проектная деятельность")]
    new = [lesson(subject="  ПРОЕКТНАЯ\u00a0 ДЕЯТЕЛЬНОСТЬ ")]

    assert compare_schedules(old, new) == ([], [])


def test_cosmetic_subject_variants_are_not_conflict(lesson):
    first = lesson(subject="Высшая математика", start="10:00", end="11:40")
    second = lesson(
        subject=" ВЫСШАЯ   МАТЕМАТИКА ",
        start="11:00",
        end="12:40",
    )

    assert find_conflicts([first, second]) == []
