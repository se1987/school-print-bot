"""
google_calendar.py のテスト
- is_calendar_enabled: 環境変数による有効/無効判定
- register_task_to_calendar: タスク登録ロジック（モック）
"""

import json
from unittest.mock import MagicMock, patch

import google_calendar


class TestIsCalendarEnabled:
    def test_disabled_when_no_env(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", raising=False)
        assert google_calendar.is_calendar_enabled() is False

    def test_enabled_when_env_set(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"token": "x"}')
        assert google_calendar.is_calendar_enabled() is True


class TestRegisterTaskToCalendar:
    def _make_task(self, due_date="2026-05-10", title="運動会", description="雨天中止あり"):
        return {
            "title": title,
            "description": description,
            "due_date": due_date,
            "task_type": "event",
            "target_grades": ["全学年"],
            "dismissal_times": [{"grades": "1〜4年", "time": "13:00"}],
        }

    def test_returns_none_when_no_due_date(self):
        task = self._make_task(due_date=None)
        assert google_calendar.register_task_to_calendar(task) is None

    def test_returns_none_when_calendar_disabled(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", raising=False)
        assert google_calendar.register_task_to_calendar(self._make_task()) is None

    def test_returns_event_id_on_success(self, monkeypatch):
        monkeypatch.setenv(
            "GOOGLE_CALENDAR_CREDENTIALS_JSON",
            json.dumps({
                "token": "tok",
                "refresh_token": "ref",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "cid",
                "client_secret": "csec",
                "scopes": ["https://www.googleapis.com/auth/calendar.events"],
            }),
        )

        mock_exec = MagicMock()
        mock_exec.execute.return_value = {"id": "evt123"}
        mock_events = MagicMock()
        mock_events.insert.return_value = mock_exec
        mock_service = MagicMock()
        mock_service.events.return_value = mock_events

        with patch("google_calendar._build_service", return_value=mock_service):
            result = google_calendar.register_task_to_calendar(self._make_task())

        assert result == "evt123"

    def test_returns_none_on_http_error(self, monkeypatch):
        from googleapiclient.errors import HttpError

        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"token": "x"}')

        mock_exec = MagicMock()
        mock_exec.execute.side_effect = HttpError(
            resp=MagicMock(status=403), content=b"Forbidden"
        )
        mock_events = MagicMock()
        mock_events.insert.return_value = mock_exec
        mock_service = MagicMock()
        mock_service.events.return_value = mock_events

        with patch("google_calendar._build_service", return_value=mock_service):
            result = google_calendar.register_task_to_calendar(self._make_task())

        assert result is None

    def test_event_includes_dismissal_times_in_description(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"token": "x"}')

        captured = {}

        mock_exec = MagicMock()
        mock_exec.execute.return_value = {"id": "evt456"}

        mock_events = MagicMock()
        mock_events.insert.side_effect = lambda calendarId, body: (
            captured.update(body) or mock_exec
        )

        mock_service = MagicMock()
        mock_service.events.return_value = mock_events

        with patch("google_calendar._build_service", return_value=mock_service):
            google_calendar.register_task_to_calendar(self._make_task())

        assert "下校時刻" in captured.get("description", "")
