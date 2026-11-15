"""
main.py のテスト
- 外部 cron 用エンドポイント（/cron/*）の認証と、モードによる有効・無効
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

import dates
import main
import scheduler


@pytest.fixture
def client(monkeypatch):
    """lifespan（DB初期化・スケジューラー起動）を動かさずにエンドポイントだけ叩く"""
    calls = []

    async def fake_reminders():
        calls.append("reminder")

    async def fake_advance():
        calls.append("advance")
        return True

    monkeypatch.setattr(scheduler, "send_daily_reminders", fake_reminders)
    monkeypatch.setattr(scheduler, "advance_grades_april", fake_advance)
    c = TestClient(main.app)
    c.calls = calls
    return c


def _external(monkeypatch, secret="s3cret"):
    monkeypatch.setenv("SCHEDULER_MODE", "external")
    monkeypatch.setenv("CRON_SECRET", secret)


class TestCronEndpoints:
    def test_runs_job_with_valid_secret(self, client, monkeypatch):
        _external(monkeypatch)
        res = client.post("/cron/daily-reminder", headers={"X-Cron-Secret": "s3cret"})
        assert res.status_code == 200
        assert client.calls == ["reminder"]

    def test_advance_grades_reports_execution(self, client, monkeypatch):
        _external(monkeypatch)
        monkeypatch.setattr(dates, "today_jst", lambda: date(2027, 4, 1))
        res = client.post("/cron/advance-grades", headers={"X-Cron-Secret": "s3cret"})
        assert res.json() == {"status": "ok", "executed": True}

    def test_advance_grades_skipped_outside_april(self, client, monkeypatch):
        """管理画面からの手動実行（動作確認）で進級してしまわない"""
        _external(monkeypatch)
        monkeypatch.setattr(dates, "today_jst", lambda: date(2026, 11, 15))
        res = client.post("/cron/advance-grades", headers={"X-Cron-Secret": "s3cret"})
        assert res.json() == {"status": "skipped", "executed": False}
        assert client.calls == []

    @pytest.mark.parametrize("headers", [{}, {"X-Cron-Secret": "wrong"}, {"Authorization": "Bearer s3cret"}])
    def test_rejects_missing_or_wrong_secret(self, client, monkeypatch, headers):
        _external(monkeypatch)
        res = client.post("/cron/daily-reminder", headers=headers)
        assert res.status_code == 401
        assert client.calls == []

    def test_disabled_in_internal_mode(self, client, monkeypatch):
        """プロセス内スケジューラーと二重に動かないよう、internal では 404"""
        monkeypatch.setenv("SCHEDULER_MODE", "internal")
        monkeypatch.setenv("CRON_SECRET", "s3cret")
        res = client.post("/cron/daily-reminder", headers={"X-Cron-Secret": "s3cret"})
        assert res.status_code == 404
        assert client.calls == []


class TestValidateEnv:
    def test_external_mode_requires_cron_secret(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_MODE", "external")
        monkeypatch.delenv("CRON_SECRET", raising=False)
        with pytest.raises(SystemExit):
            main.validate_env()

    def test_unknown_mode_is_rejected(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_MODE", "cloud")
        with pytest.raises(SystemExit):
            main.validate_env()
