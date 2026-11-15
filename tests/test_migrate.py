"""scripts/migrate_sqlite_to_postgres.py のテスト（PostgreSQL が必要）"""

import importlib.util
import os

import pytest

import database

_spec = importlib.util.spec_from_file_location(
    "migrate_sqlite_to_postgres",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "migrate_sqlite_to_postgres.py"),
)
migrate_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate_mod)


@pytest.fixture
def sqlite_file(tmp_path, monkeypatch):
    """移行元になる SQLite を作る"""
    path = tmp_path / "source.db"
    with monkeypatch.context() as m:
        m.setattr(database, "DATABASE_URL", "")
        m.setattr(database, "DB_PATH", path)
        database.init_db()
        database.add_child("U1", "たろう", "1年")
        print_id = database.save_print("U1", "遠足のお知らせ", "遠足")
        database.save_tasks(print_id, "U1", [
            {"title": "遠足", "due_date": "2026-11-05", "target_grades": ["1〜4年"],
             "dismissal_times": [{"grades": "1〜4年", "time": "13:00"}]},
        ])
        database.set_calendar_mode("U1", "ask")
    return str(path)


@pytest.mark.parametrize("setup_db", ["postgres"], indirect=True)
class TestMigrate:
    def test_copies_rows_and_continues_numbering(self, sqlite_file, setup_db):
        counts = migrate_mod.migrate(sqlite_file)
        assert counts == {"prints": 1, "tasks": 1, "children": 1, "user_settings": 1, "app_state": 0}

        assert database.get_children("U1")[0]["name"] == "たろう"
        assert database.get_calendar_mode("U1") == "ask"
        task = database.get_all_tasks("U1")[0]
        assert task["target_grades"] == ["1〜4年"]
        assert task["dismissal_times"] == [{"grades": "1〜4年", "time": "13:00"}]
        assert database.search_prints("U1", "遠足")[0]["created_at"][:2] == "20"

        # 引き継いだ id と衝突せずに新規登録できる
        assert database.add_child("U1", "はなこ", "3年") == 2
        assert database.save_print("U1", "x", "y") == 2

    def test_refuses_non_empty_destination(self, sqlite_file, setup_db):
        migrate_mod.migrate(sqlite_file)
        with pytest.raises(SystemExit):
            migrate_mod.migrate(sqlite_file)
        assert len(database.get_children("U1")) == 1
