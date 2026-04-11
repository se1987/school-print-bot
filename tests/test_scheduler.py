"""
scheduler.py のテスト
- _advance_grade: 学年自動進級ロジック
- _build_task_section / _build_personalized_reminder / _build_generic_reminder: リマインドメッセージ構築
"""

from datetime import timedelta

from scheduler import (
    _advance_grade,
    _build_generic_reminder,
    _build_personalized_reminder,
    _build_task_section,
    _format_date_label,
    _jst_today,
)


class TestAdvanceGrade:
    # 小学校
    def test_elementary_normal(self):
        assert _advance_grade("1年") == ("2年", False)
        assert _advance_grade("2年") == ("3年", False)
        assert _advance_grade("5年") == ("6年", False)

    def test_elementary_graduation(self):
        grade, graduated = _advance_grade("6年")
        assert graduated is True
        assert grade == "6年"  # 更新しない

    # 中学校（中学◯年）
    def test_middle_school_normal(self):
        assert _advance_grade("中学1年") == ("中学2年", False)
        assert _advance_grade("中学2年") == ("中学3年", False)

    def test_middle_school_graduation(self):
        _, graduated = _advance_grade("中学3年")
        assert graduated is True

    # 高校（高校◯年）
    def test_high_school_normal(self):
        assert _advance_grade("高校1年") == ("高校2年", False)
        assert _advance_grade("高校2年") == ("高校3年", False)

    def test_high_school_graduation(self):
        _, graduated = _advance_grade("高校3年")
        assert graduated is True

    # 省略形（中◯年 / 高◯年）
    def test_short_prefix_middle_normal(self):
        assert _advance_grade("中1年") == ("中2年", False)
        assert _advance_grade("中2年") == ("中3年", False)

    def test_short_prefix_middle_graduation(self):
        _, graduated = _advance_grade("中3年")
        assert graduated is True

    def test_short_prefix_high_normal(self):
        assert _advance_grade("高1年") == ("高2年", False)

    def test_short_prefix_high_graduation(self):
        _, graduated = _advance_grade("高3年")
        assert graduated is True

    # 不明な形式はそのまま返す
    def test_unknown_format(self):
        grade, graduated = _advance_grade("不明")
        assert grade == "不明"
        assert graduated is False


class TestBuildTaskSection:
    def _make_task(self, title="テスト", task_type="event", due_date="2026-03-17"):
        return {
            "id": 1, "title": title, "task_type": task_type, "due_date": due_date,
            "description": "", "target_grades": ["全学年"], "dismissal_times": [],
            "user_id": "U001",
        }

    def test_empty_tasks_returns_empty(self):
        lines, count = _build_task_section([], None, "📌 今日")
        assert lines == []
        assert count == 0

    def test_section_with_tasks_no_children(self):
        tasks = [self._make_task(title="参観日")]
        lines, count = _build_task_section(tasks, None, "📌 今日の予定")
        text = "\n".join(lines)
        assert "今日の予定" in text
        assert "参観日" in text
        assert count == 1

    def test_section_with_children(self):
        tasks = [self._make_task(title="遠足")]
        children = [{"name": "たろう", "grade": "1年"}]
        lines, count = _build_task_section(tasks, children, "📅 明日の予定")
        text = "\n".join(lines)
        assert "たろう" in text
        assert "遠足" in text
        assert count == 1


class TestBuildReminder:
    def _make_task(self, title="テスト", due_date="2026-03-17"):
        return {
            "id": 1, "title": title, "task_type": "event", "due_date": due_date,
            "description": "", "target_grades": ["全学年"], "dismissal_times": [],
            "user_id": "U001",
        }

    def test_personalized_today_and_tomorrow(self):
        children = [{"name": "たろう", "grade": "1年"}]
        msg = _build_personalized_reminder(
            [self._make_task(title="今日のイベント")],
            [self._make_task(title="明日のイベント")],
            children,
        )
        assert "今日" in msg
        assert "明日" in msg
        assert "おはようございます" in msg

    def test_personalized_today_only(self):
        children = [{"name": "はな", "grade": "3年"}]
        msg = _build_personalized_reminder(
            [self._make_task(title="体育")], [], children,
        )
        assert "今日" in msg
        assert "体育" in msg

    def test_generic_reminder(self):
        msg = _build_generic_reminder(
            [self._make_task(title="持ち物確認")],
            [self._make_task(title="遠足")],
        )
        assert "今日" in msg
        assert "明日" in msg
        assert "子ども登録" in msg

    def test_generic_empty(self):
        msg = _build_generic_reminder([], [])
        assert "合計 0 件" in msg

    def test_personalized_includes_today_and_tomorrow_dates(self):
        today = _jst_today()
        tomorrow = today + timedelta(days=1)
        children = [{"name": "たろう", "grade": "1年"}]
        msg = _build_personalized_reminder(
            [self._make_task(title="今日のイベント")],
            [self._make_task(title="明日のイベント")],
            children,
        )
        assert _format_date_label(today) in msg
        assert _format_date_label(tomorrow) in msg

    def test_generic_includes_today_and_tomorrow_dates(self):
        today = _jst_today()
        tomorrow = today + timedelta(days=1)
        msg = _build_generic_reminder(
            [self._make_task(title="持ち物確認")],
            [self._make_task(title="遠足")],
        )
        assert _format_date_label(today) in msg
        assert _format_date_label(tomorrow) in msg


class TestFormatDateLabel:
    def test_weekday_japanese(self):
        from datetime import date
        # 2026-04-11 は土曜日
        assert _format_date_label(date(2026, 4, 11)) == "4月11日（土）"
        # 2026-04-12 は日曜日
        assert _format_date_label(date(2026, 4, 12)) == "4月12日（日）"
        # 2026-01-01 は木曜日
        assert _format_date_label(date(2026, 1, 1)) == "1月1日（木）"
