"""
データベース操作モジュール
SQLiteを使って、プリント情報・抽出タスク・子ども情報を管理する
"""

import os
import sqlite3
import json
import re
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(os.getenv("DB_PATH", "school_prints.db"))


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS prints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                grade TEXT,
                original_text TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                print_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date DATE,
                task_type TEXT DEFAULT 'task',
                target_grades TEXT DEFAULT '["全学年"]',
                dismissal_times TEXT DEFAULT '[]',
                is_registered_to_calendar INTEGER DEFAULT 0,
                calendar_event_id TEXT,
                is_reminded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (print_id) REFERENCES prints(id)
            );
            CREATE TABLE IF NOT EXISTS children (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                grade TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                calendar_mode TEXT NOT NULL DEFAULT 'auto',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_prints_user ON prints(user_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
            CREATE INDEX IF NOT EXISTS idx_children_user ON children(user_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_print ON tasks(print_id);
        """)
        # 既存DBにカラムを追加（マイグレーション）
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN calendar_event_id TEXT")
        except sqlite3.OperationalError:
            pass  # カラム既存ならスキップ
    print("✅ データベース初期化完了")


@contextmanager
def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# === 子ども管理 ===

def add_child(user_id: str, name: str, grade: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO children (user_id, name, grade) VALUES (?, ?, ?)",
            (user_id, name, grade),
        )
        return cursor.lastrowid


def get_all_children() -> list[dict]:
    """全ユーザーの子ども一覧を返す（進級処理用）"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, user_id, name, grade FROM children ORDER BY user_id"
        ).fetchall()
        return [dict(row) for row in rows]


def get_children(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, grade FROM children WHERE user_id = ? ORDER BY grade",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def update_child_grade(child_id: int, new_grade: str):
    with get_connection() as conn:
        conn.execute("UPDATE children SET grade = ? WHERE id = ?", (new_grade, child_id))


def delete_child(child_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM children WHERE id = ?", (child_id,))


# === プリント関連 ===

def save_print(user_id: str, original_text: str, summary: str, grade: str = None, image_url: str = None) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO prints (user_id, grade, original_text, summary) VALUES (?, ?, ?, ?)",
            (user_id, grade, original_text, summary),
        )
        return cursor.lastrowid


def search_prints(user_id: str, keyword: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, grade, summary, original_text, created_at
               FROM prints WHERE user_id = ? AND (original_text LIKE ? OR summary LIKE ?)
               ORDER BY created_at DESC LIMIT 10""",
            (user_id, f"%{keyword}%", f"%{keyword}%"),
        ).fetchall()
        return [dict(row) for row in rows]


# === タスク関連 ===

def save_tasks(print_id: int, user_id: str, tasks: list[dict]) -> list[int]:
    task_ids = []
    with get_connection() as conn:
        for task in tasks:
            target_grades = json.dumps(task.get("target_grades", ["全学年"]), ensure_ascii=False)
            dismissal_times = json.dumps(task.get("dismissal_times", []), ensure_ascii=False)
            cursor = conn.execute(
                """INSERT INTO tasks
                   (print_id, user_id, title, description, due_date, task_type, target_grades, dismissal_times)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (print_id, user_id, task.get("title", ""), task.get("description", ""),
                 task.get("due_date"), task.get("task_type", "task"), target_grades, dismissal_times),
            )
            task_ids.append(cursor.lastrowid)
    return task_ids


def _deserialize_task(row) -> dict:
    d = dict(row)
    d["target_grades"] = json.loads(d.get("target_grades") or '["全学年"]')
    d["dismissal_times"] = json.loads(d.get("dismissal_times") or "[]")
    return d


def get_pending_tasks(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, title, description, due_date, task_type, target_grades, dismissal_times
               FROM tasks
               WHERE user_id = ? AND due_date >= date('now', '+9 hours')
               ORDER BY due_date ASC""",
            (user_id,),
        ).fetchall()
        return [_deserialize_task(row) for row in rows]


def get_all_tasks(user_id: str) -> list[dict]:
    """期限切れを含む全タスクを返す"""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, title, description, due_date, task_type, target_grades, dismissal_times
               FROM tasks
               WHERE user_id = ?
               ORDER BY due_date DESC""",
            (user_id,),
        ).fetchall()
        return [_deserialize_task(row) for row in rows]


def find_duplicate_task(user_id: str, title: str, due_date: str | None) -> dict | None:
    """同一ユーザー・タイトル・日付の既存タスクを検索（重複検出用）"""
    if not due_date:
        return None
    with get_connection() as conn:
        row = conn.execute(
            """SELECT id, title, due_date, is_registered_to_calendar, calendar_event_id
               FROM tasks
               WHERE user_id = ? AND title = ? AND due_date = ?
               LIMIT 1""",
            (user_id, title, due_date),
        ).fetchone()
        return dict(row) if row else None


def mark_task_registered(task_id: int, calendar_event_id: str | None = None):
    with get_connection() as conn:
        conn.execute(
            "UPDATE tasks SET is_registered_to_calendar = 1, calendar_event_id = ? WHERE id = ?",
            (calendar_event_id, task_id),
        )


def get_unregistered_tasks_for_print(print_id: int, user_id: str) -> list[dict]:
    """指定プリントのうちカレンダー未登録のタスクを返す（保留モードの確認用）"""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, title, description, due_date, task_type, target_grades, dismissal_times
               FROM tasks
               WHERE print_id = ? AND user_id = ? AND is_registered_to_calendar = 0""",
            (print_id, user_id),
        ).fetchall()
        return [_deserialize_task(row) for row in rows]


# === ユーザー設定 ===

VALID_CALENDAR_MODES = ("auto", "off", "ask")


def get_calendar_mode(user_id: str) -> str:
    """カレンダー登録モード: 'auto'（自動）, 'off'（無効）, 'ask'（保留・都度確認）"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT calendar_mode FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["calendar_mode"] if row else "auto"


def set_calendar_mode(user_id: str, mode: str) -> None:
    if mode not in VALID_CALENDAR_MODES:
        raise ValueError(f"invalid calendar_mode: {mode}")
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO user_settings (user_id, calendar_mode)
               VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 calendar_mode = excluded.calendar_mode,
                 updated_at = CURRENT_TIMESTAMP""",
            (user_id, mode),
        )


def get_tasks_for_reminder(days_before: int = 1) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT t.id, t.user_id, t.title, t.description, t.due_date,
                      t.task_type, t.target_grades, t.dismissal_times
               FROM tasks t
               WHERE t.due_date = date('now', '+9 hours', '+' || ? || ' days') AND t.is_reminded = 0
               ORDER BY t.due_date ASC""",
            (days_before,),
        ).fetchall()
        return [_deserialize_task(row) for row in rows]


def mark_task_reminded(task_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE tasks SET is_reminded = 1 WHERE id = ?", (task_id,))


# === 学年マッチングヘルパー ===

def _extract_grade_number(grade: str) -> int | None:
    match = re.search(r"(\d+)", grade)
    return int(match.group(1)) if match else None


def _grade_in_range(grade_num: int, range_str: str) -> bool:
    """'1〜4年' のようなレンジに含まれるか判定"""
    for sep in ("〜", "～", "-", "−"):
        if sep in range_str:
            parts = range_str.replace("年", "").split(sep)
            try:
                return int(parts[0]) <= grade_num <= int(parts[1])
            except (ValueError, IndexError):
                pass
    return False


def is_task_relevant_to_child(task: dict, child_grade: str) -> bool:
    """タスクがその学年の子に関連するか"""
    targets = task.get("target_grades", [])
    if not targets or "全学年" in targets:
        return True
    grade_num = _extract_grade_number(child_grade)
    if grade_num is None:
        return True
    for tg in targets:
        if child_grade == tg or child_grade in tg:
            return True
        if _grade_in_range(grade_num, tg):
            return True
    return False


def get_dismissal_time_for_child(task: dict, child_grade: str) -> str | None:
    """特定の学年の子の下校時刻を取得"""
    times = task.get("dismissal_times", [])
    if not times:
        return None
    grade_num = _extract_grade_number(child_grade)
    if grade_num is None:
        return " / ".join(f"{d['grades']} {d['time']}" for d in times)
    for dt in times:
        gs = dt.get("grades", "")
        ts = dt.get("time", "")
        if child_grade in gs or "全学年" in gs:
            return ts
        if grade_num and _grade_in_range(grade_num, gs):
            return ts
    # マッチしなかった場合は全部返す
    return " / ".join(f"{d['grades']} {d['time']}" for d in times)
