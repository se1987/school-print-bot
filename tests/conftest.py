import os
import sys
import uuid

# src/ モジュールのインポートより先にフェイク環境変数を設定
os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-tests")
os.environ.setdefault("LINE_CHANNEL_ACCESS_TOKEN", "fake-token-for-tests")
os.environ.setdefault("LINE_CHANNEL_SECRET", "fake-secret-for-tests")
# 開発者の .env に本番用の設定があってもテストが引きずられないようにする
os.environ["DATABASE_URL"] = ""
os.environ["DB_SCHEMA"] = ""
os.environ["SCHEDULER_MODE"] = "internal"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import database

# 設定すると、DB を使うテストを PostgreSQL に対しても実行する（CI ではサービスコンテナを指す）
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")


@pytest.fixture(params=["sqlite", "postgres"])
def setup_db(request, tmp_path, monkeypatch):
    """テスト用の空DBを用意する。SQLite は一時ファイル、PostgreSQL はテストごとの使い捨てスキーマ"""
    if request.param == "sqlite":
        monkeypatch.setattr(database, "DATABASE_URL", "")
        monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
        database.init_db()
        yield
        return

    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL が未設定のため PostgreSQL のテストをスキップ")
    import psycopg

    schema = f"test_{uuid.uuid4().hex}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    monkeypatch.setattr(database, "DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(database, "DB_SCHEMA", schema)
    database.init_db()
    yield
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
