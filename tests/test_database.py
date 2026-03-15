"""
database.py のテスト
- 学年マッチングのピュア関数
- 子ども CRUD
"""

from database import (
    _extract_grade_number,
    _grade_in_range,
    is_task_relevant_to_child,
    get_dismissal_time_for_child,
    add_child,
    get_children,
    delete_child,
    update_child_grade,
    get_all_children,
)


class TestExtractGradeNumber:
    def test_elementary(self):
        assert _extract_grade_number("3年") == 3

    def test_middle_school(self):
        assert _extract_grade_number("中学2年") == 2

    def test_high_school(self):
        assert _extract_grade_number("高校1年") == 1

    def test_short_prefix(self):
        assert _extract_grade_number("中1年") == 1

    def test_all_grades_returns_none(self):
        assert _extract_grade_number("全学年") is None


class TestGradeInRange:
    def test_lower_bound(self):
        assert _grade_in_range(1, "1〜4年") is True

    def test_upper_bound(self):
        assert _grade_in_range(4, "1〜4年") is True

    def test_mid_range(self):
        assert _grade_in_range(2, "1〜4年") is True

    def test_out_of_range_high(self):
        assert _grade_in_range(5, "1〜4年") is False

    def test_out_of_range_low(self):
        assert _grade_in_range(0, "1〜4年") is False

    def test_fullwidth_tilde(self):
        assert _grade_in_range(2, "1～4年") is True  # ～ (U+FF5E)

    def test_hyphen_separator(self):
        assert _grade_in_range(2, "1-4年") is True


class TestIsTaskRelevantToChild:
    def test_all_grades(self):
        task = {"target_grades": ["全学年"]}
        assert is_task_relevant_to_child(task, "3年") is True

    def test_matching_grade(self):
        task = {"target_grades": ["3年", "4年"]}
        assert is_task_relevant_to_child(task, "3年") is True

    def test_non_matching_grade(self):
        task = {"target_grades": ["3年", "4年"]}
        assert is_task_relevant_to_child(task, "5年") is False

    def test_range_match(self):
        task = {"target_grades": ["1〜4年"]}
        assert is_task_relevant_to_child(task, "2年") is True
        assert is_task_relevant_to_child(task, "5年") is False

    def test_middle_school_exact(self):
        task = {"target_grades": ["中学1年"]}
        assert is_task_relevant_to_child(task, "中学1年") is True
        assert is_task_relevant_to_child(task, "中学2年") is False

    def test_empty_targets_defaults_to_relevant(self):
        task = {"target_grades": []}
        assert is_task_relevant_to_child(task, "1年") is True


class TestGetDismissalTimeForChild:
    def test_range_match(self):
        task = {
            "dismissal_times": [
                {"grades": "1〜4年", "time": "13:00"},
                {"grades": "5年", "time": "13:30"},
            ]
        }
        assert get_dismissal_time_for_child(task, "2年") == "13:00"
        assert get_dismissal_time_for_child(task, "5年") == "13:30"

    def test_no_dismissal_times(self):
        task = {"dismissal_times": []}
        assert get_dismissal_time_for_child(task, "1年") is None

    def test_all_grades_keyword(self):
        task = {
            "dismissal_times": [
                {"grades": "全学年", "time": "14:00"},
            ]
        }
        assert get_dismissal_time_for_child(task, "3年") == "14:00"


class TestChildCRUD:
    def test_add_and_get(self, setup_db):
        add_child("user1", "たろう", "1年")
        children = get_children("user1")
        assert len(children) == 1
        assert children[0]["name"] == "たろう"
        assert children[0]["grade"] == "1年"

    def test_multiple_children(self, setup_db):
        add_child("user1", "たろう", "1年")
        add_child("user1", "はなこ", "中学2年")
        assert len(get_children("user1")) == 2

    def test_user_isolation(self, setup_db):
        add_child("user1", "たろう", "1年")
        add_child("user2", "はなこ", "2年")
        assert len(get_children("user1")) == 1
        assert len(get_children("user2")) == 1

    def test_update_grade(self, setup_db):
        child_id = add_child("user1", "たろう", "1年")
        update_child_grade(child_id, "2年")
        assert get_children("user1")[0]["grade"] == "2年"

    def test_delete_child(self, setup_db):
        child_id = add_child("user1", "たろう", "1年")
        delete_child(child_id)
        assert get_children("user1") == []

    def test_get_all_children_across_users(self, setup_db):
        add_child("user1", "たろう", "1年")
        add_child("user2", "はなこ", "2年")
        all_children = get_all_children()
        assert len(all_children) == 2
        user_ids = {c["user_id"] for c in all_children}
        assert user_ids == {"user1", "user2"}
