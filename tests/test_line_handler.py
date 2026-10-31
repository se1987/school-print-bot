"""
line_handler.py のテスト
- 子ども登録コマンドの正規表現パース（表記ゆらぎ対応）
- 検索キーワード長の制限（validate_keyword）
"""

import re
from datetime import date

import pytest

# line_handler から検証関数と定数を取得（conftest で env 設定済み）
from line_handler import MAX_KEYWORD_LENGTH, validate_keyword

# line_handler.py と同じパターン
_CHILD_VARIANTS = r"(?:子ども|子供|こども)"
CHILD_REGISTER_PATTERN = re.compile(rf"{_CHILD_VARIANTS}登録\s+(.+?)\s+(\S+年)")
CHILD_DELETE_PATTERN = re.compile(rf"{_CHILD_VARIANTS}削除\s+(.+)")

CHILD_LIST_KEYWORDS = {"子ども一覧", "子ども", "子供一覧", "子供", "こども一覧", "こども"}
CHILD_REGISTER_KEYWORDS = {"子ども登録", "子供登録", "こども登録"}


class TestChildRegisterPattern:
    def test_elementary(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 たろう 1年")
        assert m is not None
        assert m.group(1) == "たろう"
        assert m.group(2) == "1年"

    def test_middle_school(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 はなこ 中学1年")
        assert m is not None
        assert m.group(1) == "はなこ"
        assert m.group(2) == "中学1年"

    def test_high_school(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 じろう 高校2年")
        assert m is not None
        assert m.group(2) == "高校2年"

    def test_short_prefix_middle(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 さくら 中2年")
        assert m is not None
        assert m.group(2) == "中2年"

    def test_short_prefix_high(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 たろう 高1年")
        assert m is not None
        assert m.group(2) == "高1年"

    def test_no_match_without_grade(self):
        assert CHILD_REGISTER_PATTERN.match("子ども登録 たろう") is None

    def test_no_match_unrelated_command(self):
        assert CHILD_REGISTER_PATTERN.match("子ども一覧") is None

    def test_no_match_grade_only(self):
        assert CHILD_REGISTER_PATTERN.match("子ども登録 1年") is None


class TestChildVariantKanji:
    """「子供」表記でのコマンド"""
    def test_register_kanji(self):
        m = CHILD_REGISTER_PATTERN.match("子供登録 たろう 1年")
        assert m is not None
        assert m.group(1) == "たろう"
        assert m.group(2) == "1年"

    def test_register_hiragana(self):
        m = CHILD_REGISTER_PATTERN.match("こども登録 はなこ 3年")
        assert m is not None
        assert m.group(1) == "はなこ"
        assert m.group(2) == "3年"

    def test_delete_kanji(self):
        m = CHILD_DELETE_PATTERN.match("子供削除 たろう")
        assert m is not None
        assert m.group(1) == "たろう"

    def test_delete_hiragana(self):
        m = CHILD_DELETE_PATTERN.match("こども削除 はなこ")
        assert m is not None
        assert m.group(1) == "はなこ"

    def test_list_keywords(self):
        assert "子供一覧" in CHILD_LIST_KEYWORDS
        assert "こども一覧" in CHILD_LIST_KEYWORDS
        assert "子供" in CHILD_LIST_KEYWORDS
        assert "こども" in CHILD_LIST_KEYWORDS

    def test_register_keywords(self):
        assert "子供登録" in CHILD_REGISTER_KEYWORDS
        assert "こども登録" in CHILD_REGISTER_KEYWORDS


class TestKeywordLength:
    def test_within_limit(self):
        """MAX_KEYWORD_LENGTH ちょうどは validate_keyword で許可される"""
        validate_keyword("a" * MAX_KEYWORD_LENGTH)

    def test_exceeds_limit_raises(self):
        """MAX_KEYWORD_LENGTH + 1 は validate_keyword が ValueError を送出する"""
        with pytest.raises(ValueError):
            validate_keyword("a" * (MAX_KEYWORD_LENGTH + 1))


class TestFormatAnalysisResult:
    """解析結果の返信に、曜日・原文・⚠️警告が入ること（子ども未登録なので DB 不要）"""

    def _result(self, tasks):
        return {"grade": "1年", "summary": "学年だより", "tasks": tasks, "notes": []}

    def test_shows_weekday_and_source_text(self, monkeypatch):
        import dates
        import line_handler

        monkeypatch.setattr(dates, "today_jst", lambda: date(2026, 10, 31))
        task = {
            "title": "親子ふれあい活動",
            "due_date": "2026-11-05",
            "task_type": "event",
            "source_text": "5日(木) 親子ふれあい活動",
        }
        text = line_handler._format_analysis_result(self._result([task]), children=[])
        assert "親子ふれあい活動 (11/5(木))" in text
        assert "📝 原文:「5日(木) 親子ふれあい活動」" in text
        assert "⚠️" not in text

    def test_shows_warnings_and_footer_count(self, monkeypatch):
        import dates
        import line_handler

        monkeypatch.setattr(dates, "today_jst", lambda: date(2026, 10, 31))
        task = {"title": "親子ふれあい活動", "due_date": "2026-11-05", "task_type": "event"}
        warnings_by_id = {id(task): ["⚠️ 曜日が合いません: テスト"]}
        text = line_handler._format_analysis_result(
            self._result([task]), children=[], warnings_by_id=warnings_by_id
        )
        assert "     ⚠️ 曜日が合いません: テスト" in text
        assert "⚠️ 気になる点が1件あります" in text
        # 未登録（cal_count=0）なら Google カレンダー側での修正は案内しない
        assert "ご確認ください" in text
        assert "Googleカレンダー側で直してください" not in text

    def test_footer_reports_dropped_tasks(self):
        import line_handler

        result = {"grade": None, "summary": "s", "tasks": [], "notes": [], "dropped_task_count": 2}
        text = line_handler._format_analysis_result(result, children=[])
        assert "⚠️ 2件は内容を読み取れなかったため保存していません" in text

        result["dropped_task_count"] = 0
        assert "読み取れなかった" not in line_handler._format_analysis_result(result, children=[])

    def test_footer_guides_to_calendar_only_when_registered(self, monkeypatch):
        import dates
        import line_handler

        monkeypatch.setattr(dates, "today_jst", lambda: date(2026, 10, 31))
        task = {"title": "親子ふれあい活動", "due_date": "2026-11-05", "task_type": "event"}
        warnings_by_id = {id(task): ["⚠️ テスト"]}
        registered = line_handler._format_analysis_result(
            self._result([task]), children=[], cal_count=1, warnings_by_id=warnings_by_id
        )
        assert "Googleカレンダー側で直してください" in registered

        pending = line_handler._format_analysis_result(
            self._result([task]), children=[], pending_confirm=True, warnings_by_id=warnings_by_id
        )
        assert "下のボタンで登録するか決めてください" in pending
        assert "Googleカレンダー側で直してください" not in pending

    def test_todo_deadline_uses_weekday_format(self, monkeypatch):
        import dates
        import line_handler

        monkeypatch.setattr(dates, "today_jst", lambda: date(2026, 10, 31))
        task = {"title": "上履きを持たせる", "due_date": "2026-11-06", "task_type": "task"}
        text = line_handler._format_analysis_result(self._result([task]), children=[])
        assert "上履きを持たせる（〜11/6(金)）" in text
