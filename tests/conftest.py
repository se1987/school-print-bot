import os
import sys

# src/ モジュールのインポートより先にフェイク環境変数を設定
os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-tests")
os.environ.setdefault("LINE_CHANNEL_ACCESS_TOKEN", "fake-token-for-tests")
os.environ.setdefault("LINE_CHANNEL_SECRET", "fake-secret-for-tests")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import database


@pytest.fixture
def setup_db(tmp_path, monkeypatch):
    """テスト用の一時DBを作成し、終了後に自動削除する"""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    database.init_db()
