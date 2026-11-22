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


class TestTaskDelete:
    """予定削除コマンド: 番号の読み取り・確認ボタン・削除（DB とカレンダーはモック）"""

    def _event(self):
        from types import SimpleNamespace
        return SimpleNamespace(reply_token="tok")

    def _capture(self, monkeypatch):
        import line_handler
        sent = []

        async def fake_reply(token, text):
            sent.append(("reply", text, None))

        async def fake_reply_qr(token, text, items):
            sent.append(("reply_qr", text, items))

        async def fake_push(user_id, text):
            sent.append(("push", text, None))

        monkeypatch.setattr(line_handler, "reply_text", fake_reply)
        monkeypatch.setattr(line_handler, "push_text", fake_push)
        monkeypatch.setattr(line_handler, "reply_text_with_quick_reply", fake_reply_qr)
        return sent

    def test_parse_task_ids_accepts_various_forms(self):
        from line_handler import _parse_task_ids
        assert _parse_task_ids("12 15") == [12, 15]
        assert _parse_task_ids("#12、#15,12") == [12, 15]
        assert _parse_task_ids("１２　１５") == [12, 15]  # 全角
        assert _parse_task_ids("") == []
        assert _parse_task_ids("0 abc") == []

    def test_command_pattern(self):
        from line_handler import _TASK_DELETE_RE
        assert _TASK_DELETE_RE.match("予定削除 12 15").group(1) == "12 15"
        assert _TASK_DELETE_RE.match("タスク削除12").group(1) == "12"
        assert _TASK_DELETE_RE.match("予定削除").group(1) == ""
        assert _TASK_DELETE_RE.match("子ども削除 たろう") is None

    def test_confirm_shows_targets_and_buttons(self, monkeypatch):
        import asyncio
        import line_handler
        sent = self._capture(monkeypatch)
        tasks = [
            {"id": 12, "title": "作品展の搬入", "due_date": "2026-12-03", "task_type": "event",
             "calendar_event_id": "evt"},
        ]
        monkeypatch.setattr(line_handler.db, "get_tasks_by_ids", lambda uid, ids: tasks)
        asyncio.run(line_handler._confirm_delete_tasks(self._event(), "U1", "12 99"))
        [(kind, text, items)] = sent
        assert kind == "reply_qr"
        assert "#12 作品展の搬入" in text
        assert "カレンダーからも削除" in text
        assert "見つからなかった番号: #99" in text
        assert items[0] == ("削除する", "action=task_delete&ids=12")
        assert items[1][1] == "action=task_delete_cancel"

    def test_confirm_without_numbers_shows_usage(self, monkeypatch):
        import asyncio
        import line_handler
        sent = self._capture(monkeypatch)
        asyncio.run(line_handler._confirm_delete_tasks(self._event(), "U1", ""))
        assert sent[0][0] == "reply" and "例: 予定削除 12" in sent[0][1]

    def test_confirm_rejects_too_many(self, monkeypatch):
        import asyncio
        import line_handler
        sent = self._capture(monkeypatch)
        many = " ".join(str(i) for i in range(1, line_handler.MAX_DELETE_TASKS + 2))
        asyncio.run(line_handler._confirm_delete_tasks(self._event(), "U1", many))
        assert "までです" in sent[0][1]

    def test_postback_data_fits_line_limit(self):
        import line_handler
        ids = ",".join(str(100000 + i) for i in range(line_handler.MAX_DELETE_TASKS))
        assert len(f"action=task_delete&ids={ids}") <= 300

    def test_delete_removes_tasks_and_calendar_events(self, monkeypatch):
        import asyncio
        import line_handler
        sent = self._capture(monkeypatch)
        tasks = [
            {"id": 1, "title": "A", "due_date": "2026-11-05", "task_type": "event", "calendar_event_id": "e1"},
            {"id": 2, "title": "B", "due_date": "2026-11-06", "task_type": "event", "calendar_event_id": "e2"},
            {"id": 3, "title": "C", "due_date": None, "task_type": "task", "calendar_event_id": None},
        ]
        deleted_events, deleted_ids = [], []
        monkeypatch.setattr(line_handler.db, "get_tasks_by_ids", lambda uid, ids: tasks)
        monkeypatch.setattr(
            line_handler.db, "delete_tasks",
            lambda uid, ids: deleted_ids.extend(ids) or len(ids),
        )

        def fake_delete_event(event_id):
            deleted_events.append(event_id)
            return event_id != "e2"  # e2 だけカレンダー削除に失敗

        monkeypatch.setattr(line_handler.google_calendar, "delete_calendar_event", fake_delete_event)
        monkeypatch.setattr(line_handler.db, "is_calendar_event_shared", lambda eid, ids: False)
        asyncio.run(line_handler._delete_tasks(self._event(), "U1", [1, 2, 3]))
        assert deleted_events == ["e1", "e2"]
        assert deleted_ids == [1, 2, 3]
        # カレンダー削除がある時は、先に開始を返信し、結果は push で送る
        assert sent[0] == ("reply", "🗑️ 3件の予定を削除中...", None)
        assert sent[1][0] == "push"
        text = sent[1][1]
        assert "3件の予定を削除しました" in text
        assert "Googleカレンダーからは削除できませんでした" in text and "#2 B" in text

    def test_delete_when_nothing_found(self, monkeypatch):
        import asyncio
        import line_handler
        sent = self._capture(monkeypatch)
        monkeypatch.setattr(line_handler.db, "get_tasks_by_ids", lambda uid, ids: [])
        asyncio.run(line_handler._delete_tasks(self._event(), "U1", [5]))
        assert "削除する予定はありませんでした" in sent[0][1]

    def test_delete_keeps_calendar_event_shared_with_others(self, monkeypatch):
        import asyncio
        import line_handler
        sent = self._capture(monkeypatch)
        tasks = [
            {"id": 1, "title": "A", "due_date": "2026-11-05", "task_type": "event", "calendar_event_id": "shared"},
            {"id": 2, "title": "B", "due_date": "2026-11-06", "task_type": "event", "calendar_event_id": "mine"},
            {"id": 3, "title": "B'", "due_date": "2026-11-06", "task_type": "event", "calendar_event_id": "mine"},
        ]
        deleted_events = []
        monkeypatch.setattr(line_handler.db, "get_tasks_by_ids", lambda uid, ids: tasks)
        monkeypatch.setattr(line_handler.db, "delete_tasks", lambda uid, ids: len(ids))
        monkeypatch.setattr(line_handler.db, "is_calendar_event_shared", lambda eid, ids: eid == "shared")
        monkeypatch.setattr(
            line_handler.google_calendar, "delete_calendar_event",
            lambda eid: deleted_events.append(eid) or True,
        )
        asyncio.run(line_handler._delete_tasks(self._event(), "U1", [1, 2, 3]))
        # 他のタスクが参照するイベントは消さず、同じイベントは1回だけ消す
        assert deleted_events == ["mine"]
        assert sent[-1][0] == "push" and "3件の予定を削除しました" in sent[-1][1]

    def test_delete_without_calendar_replies_once(self, monkeypatch):
        import asyncio
        import line_handler
        sent = self._capture(monkeypatch)
        tasks = [{"id": 3, "title": "C", "due_date": None, "task_type": "task", "calendar_event_id": None}]
        monkeypatch.setattr(line_handler.db, "get_tasks_by_ids", lambda uid, ids: tasks)
        monkeypatch.setattr(line_handler.db, "delete_tasks", lambda uid, ids: len(ids))
        asyncio.run(line_handler._delete_tasks(self._event(), "U1", [3]))
        # カレンダーに無い予定だけなら、push を使わず返信1回で済ませる
        assert [k for k, _, _ in sent] == ["reply"]
        assert "1件の予定を削除しました" in sent[0][1]

    def test_calendar_register_refetches_after_reply(self, monkeypatch):
        import asyncio
        import line_handler
        sent = self._capture(monkeypatch)
        fetched = [
            [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}],  # 返信前
            [{"id": 2, "title": "B"}],  # 返信中に #1 が削除された
        ]
        registered = []
        monkeypatch.setattr(line_handler.google_calendar, "is_calendar_enabled", lambda: True)
        monkeypatch.setattr(line_handler.db, "get_unregistered_tasks_for_print", lambda pid, uid: fetched.pop(0))
        monkeypatch.setattr(
            line_handler.google_calendar, "register_task_to_calendar",
            lambda task: registered.append(task["id"]) or f"evt{task['id']}",
        )
        monkeypatch.setattr(line_handler.db, "mark_task_registered", lambda tid, eid: None)
        asyncio.run(line_handler._handle_calendar_decision(self._event(), "U1", "cal_register", 7))
        # 削除済みの #1 は登録しない
        assert registered == [2]
        assert sent[-1] == ("push", "✅ 1件をGoogleカレンダーに登録しました", None)
