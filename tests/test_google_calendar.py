"""
google_calendar.py のテスト
- is_calendar_enabled: 環境変数による有効/無効判定
- register_task_to_calendar: タスク登録ロジック（モック）
"""

import json
from unittest.mock import MagicMock, patch

import pytest

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
        mock_list_exec = MagicMock()
        mock_list_exec.execute.return_value = {"items": []}
        mock_events = MagicMock()
        mock_events.insert.return_value = mock_exec
        mock_events.list.return_value = mock_list_exec
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
        mock_list_exec = MagicMock()
        mock_list_exec.execute.return_value = {"items": []}
        mock_events = MagicMock()
        mock_events.insert.return_value = mock_exec
        mock_events.list.return_value = mock_list_exec
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

        mock_list_exec = MagicMock()
        mock_list_exec.execute.return_value = {"items": []}

        mock_events = MagicMock()
        mock_events.insert.side_effect = lambda calendarId, body: (
            captured.update(body) or mock_exec
        )
        mock_events.list.return_value = mock_list_exec

        mock_service = MagicMock()
        mock_service.events.return_value = mock_events

        with patch("google_calendar._build_service", return_value=mock_service):
            google_calendar.register_task_to_calendar(self._make_task())

        assert "下校時刻" in captured.get("description", "")

    def test_skips_insert_when_duplicate_exists(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"token": "x"}')

        mock_list_exec = MagicMock()
        mock_list_exec.execute.return_value = {
            "items": [{"summary": "運動会", "id": "existing_evt"}]
        }
        mock_events = MagicMock()
        mock_events.list.return_value = mock_list_exec

        mock_service = MagicMock()
        mock_service.events.return_value = mock_events

        with patch("google_calendar._build_service", return_value=mock_service):
            result = google_calendar.register_task_to_calendar(self._make_task())

        assert result == "existing_evt"
        mock_events.insert.assert_not_called()

    def test_inserts_when_no_duplicate(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"token": "x"}')

        mock_list_exec = MagicMock()
        mock_list_exec.execute.return_value = {"items": []}

        mock_insert_exec = MagicMock()
        mock_insert_exec.execute.return_value = {"id": "new_evt"}

        mock_events = MagicMock()
        mock_events.list.return_value = mock_list_exec
        mock_events.insert.return_value = mock_insert_exec

        mock_service = MagicMock()
        mock_service.events.return_value = mock_events

        with patch("google_calendar._build_service", return_value=mock_service):
            result = google_calendar.register_task_to_calendar(self._make_task())

        assert result == "new_evt"
        mock_events.insert.assert_called_once()

    def test_all_day_event_end_is_next_day(self, monkeypatch):
        """終日イベントの end.date は排他的なので翌日を指定する"""
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"token": "x"}')

        captured = {}
        mock_exec = MagicMock()
        mock_exec.execute.return_value = {"id": "evt"}
        mock_list_exec = MagicMock()
        mock_list_exec.execute.return_value = {"items": []}
        mock_events = MagicMock()
        mock_events.insert.side_effect = lambda calendarId, body: (
            captured.update(body) or mock_exec
        )
        mock_events.list.return_value = mock_list_exec
        mock_service = MagicMock()
        mock_service.events.return_value = mock_events

        with patch("google_calendar._build_service", return_value=mock_service):
            google_calendar.register_task_to_calendar(self._make_task(due_date="2026-05-31"))

        assert captured["start"] == {"date": "2026-05-31"}
        assert captured["end"] == {"date": "2026-06-01"}

    @pytest.mark.parametrize("due_date", ["5月10日", 20260510, "9999-12-31"])
    def test_returns_none_on_invalid_due_date(self, monkeypatch, due_date):
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"token": "x"}')

        with patch("google_calendar._build_service") as mock_build:
            result = google_calendar.register_task_to_calendar(self._make_task(due_date=due_date))

        assert result is None
        mock_build.assert_not_called()

    def test_returns_none_on_refresh_error_during_api_call(self, monkeypatch):
        """API呼び出し中の401→リフレッシュ失敗（invalid_grant）でも例外を外に出さない"""
        from google.auth.exceptions import RefreshError

        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"token": "x"}')

        mock_list_exec = MagicMock()
        mock_list_exec.execute.side_effect = RefreshError("invalid_grant")
        mock_events = MagicMock()
        mock_events.list.return_value = mock_list_exec
        mock_service = MagicMock()
        mock_service.events.return_value = mock_events

        with patch("google_calendar._build_service", return_value=mock_service):
            result = google_calendar.register_task_to_calendar(self._make_task())

        assert result is None
        mock_events.insert.assert_not_called()


class TestDeleteCalendarEvent:
    def _service(self, side_effect=None):
        service = MagicMock()
        service.events.return_value.delete.return_value.execute.side_effect = side_effect
        return service

    def test_deletes_event(self):
        service = self._service()
        with patch("google_calendar._build_service", return_value=service):
            assert google_calendar.delete_calendar_event("evt1") is True
        service.events.return_value.delete.assert_called_once_with(
            calendarId=google_calendar.CALENDAR_ID, eventId="evt1"
        )

    @pytest.mark.parametrize("status", [404, 410])
    def test_already_gone_counts_as_deleted(self, status):
        from googleapiclient.errors import HttpError

        err = HttpError(resp=MagicMock(status=status), content=b"gone")
        with patch("google_calendar._build_service", return_value=self._service(err)):
            assert google_calendar.delete_calendar_event("evt1") is True

    def test_other_http_error_returns_false(self):
        from googleapiclient.errors import HttpError

        err = HttpError(resp=MagicMock(status=500), content=b"boom")
        with patch("google_calendar._build_service", return_value=self._service(err)):
            assert google_calendar.delete_calendar_event("evt1") is False

    def test_refresh_error_returns_false(self):
        from google.auth.exceptions import RefreshError

        with patch("google_calendar._build_service", return_value=self._service(RefreshError("invalid_grant"))):
            assert google_calendar.delete_calendar_event("evt1") is False

    def test_no_service_returns_false(self):
        with patch("google_calendar._build_service", return_value=None):
            assert google_calendar.delete_calendar_event("evt1") is False

    def test_empty_event_id_is_noop(self):
        with patch("google_calendar._build_service") as build:
            assert google_calendar.delete_calendar_event("") is True
        build.assert_not_called()

    def test_transport_error_returns_false(self):
        with patch("google_calendar._build_service", return_value=self._service(TimeoutError("timed out"))):
            assert google_calendar.delete_calendar_event("evt1") is False

    def test_service_build_error_returns_false(self):
        with patch("google_calendar._build_service", side_effect=OSError("network down")):
            assert google_calendar.delete_calendar_event("evt1") is False
