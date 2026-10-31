"""
verification.py のテスト
- 曜日不一致（プリントの曜日と due_date の曜日が違う）
- 同じ予定が連日（1日違いで同タイトル）
- 年の推定ミス（今日から離れすぎた日付）
"""

from datetime import date

from verification import check_tasks

# 2026-10-31 は土曜。2026-11-04 は水曜、11-05 は木曜、11-06 は金曜
TODAY = date(2026, 10, 31)


def _task(title="親子ふれあい活動", due="2026-11-05", weekday=None):
    return {"title": title, "due_date": due, "weekday_on_print": weekday}


class TestWeekdayMismatch:
    def test_no_warning_when_weekday_matches(self):
        assert check_tasks([_task(weekday="木")], today=TODAY) == [[]]

    def test_no_warning_when_weekday_unknown(self):
        assert check_tasks([_task(weekday=None)], today=TODAY) == [[]]

    def test_warns_and_suggests_nearby_date(self):
        [warnings] = check_tasks([_task(weekday="金")], today=TODAY)
        assert len(warnings) == 1
        assert "曜日が合いません" in warnings[0]
        assert "プリントは(金)" in warnings[0]
        assert "11/5(木)は(木)" in warnings[0]
        assert "11/6(金) の可能性" in warnings[0]

    def test_suggestion_goes_backwards_too(self):
        # 11/5(木) に対してプリントが(水)なら 11/4
        [warnings] = check_tasks([_task(weekday="水")], today=TODAY)
        assert "11/4(水) の可能性" in warnings[0]

    def test_suggestion_picks_nearest_within_three_days(self):
        # 11/5(木) に対して(日)は +3日（11/8）が候補。-4日（11/1）ではない
        [warnings] = check_tasks([_task(weekday="日")], today=TODAY)
        assert "11/8(日) の可能性" in warnings[0]


class TestConsecutiveDuplicate:
    def test_warns_both_tasks(self):
        tasks = [_task(due="2026-11-05"), _task(due="2026-11-06")]
        warnings = check_tasks(tasks, today=TODAY)
        assert len(warnings[0]) == 1 and len(warnings[1]) == 1
        assert "同じ予定が 11/5(木) と 11/6(金) の両方" in warnings[0][0]
        assert warnings[0] == warnings[1]

    def test_ignores_title_spacing_and_case(self):
        tasks = [_task(title="親子 ふれあい活動", due="2026-11-05"), _task(title="親子ふれあい活動", due="2026-11-06")]
        warnings = check_tasks(tasks, today=TODAY)
        assert warnings[0] and warnings[1]

    def test_no_warning_for_different_titles(self):
        tasks = [_task(title="入学式", due="2026-11-05"), _task(title="始業式", due="2026-11-06")]
        assert check_tasks(tasks, today=TODAY) == [[], []]

    def test_no_warning_when_two_days_apart(self):
        tasks = [_task(due="2026-11-05"), _task(due="2026-11-07")]
        assert check_tasks(tasks, today=TODAY) == [[], []]

    def test_same_day_is_not_flagged_here(self):
        # 同日の完全重複は DB 側の find_duplicate_task が扱うので対象外
        tasks = [_task(due="2026-11-05"), _task(due="2026-11-05")]
        assert check_tasks(tasks, today=TODAY) == [[], []]


class TestYearFarOff:
    def test_warns_when_too_far_in_past(self):
        [warnings] = check_tasks([_task(due="2025-11-05")], today=TODAY)
        assert "日付が今日から離れています（2025/11/5）" in warnings[0]

    def test_warns_when_too_far_in_future(self):
        [warnings] = check_tasks([_task(due="2028-04-08")], today=TODAY)
        assert "日付が今日から離れています" in warnings[0]

    def test_next_school_year_is_fine(self):
        # 翌年度の4月（約5か月先）は正常
        assert check_tasks([_task(due="2027-04-08")], today=TODAY) == [[]]

    def test_recent_past_is_fine(self):
        assert check_tasks([_task(due="2026-10-01")], today=TODAY) == [[]]


class TestEdgeCases:
    def test_empty(self):
        assert check_tasks([], today=TODAY) == []

    def test_missing_or_invalid_due_date(self):
        tasks = [_task(due=None, weekday="木"), _task(due="春休み中", weekday="木")]
        assert check_tasks(tasks, today=TODAY) == [[], []]

    def test_multiple_warnings_on_one_task(self):
        # 曜日不一致 + 連日重複 の両方が付く
        tasks = [_task(due="2026-11-05", weekday="金"), _task(due="2026-11-06", weekday="金")]
        warnings = check_tasks(tasks, today=TODAY)
        assert len(warnings[0]) == 2
        assert len(warnings[1]) == 1  # 11/6 は金曜なので曜日は一致

    def test_empty_or_non_string_weekday_is_ignored(self):
        tasks = [_task(weekday=""), _task(weekday=3), _task(weekday="木曜日")]
        assert check_tasks(tasks, today=TODAY) == [[], [], []]
