"""
SQLite のデータを PostgreSQL にコピーする移行スクリプト（SQLite → PostgreSQL の引っ越し用）

使い方:
    DATABASE_URL='postgresql://...' [DB_SCHEMA=school_print_bot] \\
        python scripts/migrate_sqlite_to_postgres.py path/to/school_prints.db

- コピー先のテーブルは src/database.py の init_db() で作成する
- コピー先にすでにデータがある場合は何もせず終了する（二重取り込み防止）
- id はそのまま引き継ぎ、最後に採番を最大値の次へ進める
- 全体が1トランザクションなので、途中で失敗したら何も書き込まれない
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import database as db  # noqa: E402

# 外部キーの都合で prints を tasks より先にコピーする
TABLES = {
    "prints": ["id", "user_id", "grade", "original_text", "summary", "created_at"],
    "tasks": [
        "id", "print_id", "user_id", "title", "description", "due_date", "task_type",
        "target_grades", "dismissal_times", "is_registered_to_calendar",
        "calendar_event_id", "is_reminded", "created_at",
    ],
    "children": ["id", "user_id", "name", "grade", "created_at"],
    "user_settings": ["user_id", "calendar_mode", "updated_at"],
    "app_state": ["key", "value"],
}
IDENTITY_TABLES = ("prints", "tasks", "children")


def migrate(sqlite_path: str) -> dict[str, int]:
    if not db.is_postgres():
        raise SystemExit("DATABASE_URL が未設定です（コピー先の PostgreSQL を指定してください）")
    if not os.path.exists(sqlite_path):
        raise SystemExit(f"SQLite ファイルが見つかりません: {sqlite_path}")

    db.init_db()
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    existing = {r["name"] for r in src.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    counts: dict[str, int] = {}

    with db.get_connection() as conn:
        for table in TABLES:
            if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise SystemExit(f"コピー先の {table} にすでにデータがあるため中止しました")

        print_ids = set()
        for table, columns in TABLES.items():
            counts[table] = 0
            if table not in existing:
                continue  # 古い SQLite には無いテーブル（app_state など）
            src_columns = {r["name"] for r in src.execute(f"PRAGMA table_info({table})")}
            cols = [c for c in columns if c in src_columns]
            placeholders = ", ".join("?" for _ in cols)
            for row in src.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY 1"):
                if table == "prints":
                    print_ids.add(row["id"])
                if table == "tasks" and row["print_id"] not in print_ids:
                    # SQLite は外部キーを強制しないので、親のいないタスクが残っていることがある
                    print(f"  ! tasks.id={row['id']} は親の prints が無いためスキップ")
                    continue
                conn.execute(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
                    tuple(row[c] for c in cols),
                )
                counts[table] += 1

        for table in IDENTITY_TABLES:
            conn.execute(
                f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                                  (SELECT COALESCE(MAX(id), 0) + 1 FROM {table}), false)"""
            )
    src.close()
    return counts


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    for name, n in migrate(sys.argv[1]).items():
        print(f"  {name}: {n} 行")
    print("✅ 移行完了")
