"""
Google Calendar連携モジュール
タスク・予定をGoogleカレンダーに登録する

セットアップ手順:
  1. scripts/authorize_google.py を実行してOAuth認証
  2. 出力されたJSONをGOOGLE_CALENDAR_CREDENTIALS_JSON環境変数に設定
"""

import json
import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def is_calendar_enabled() -> bool:
    """Google Calendar連携が設定されているか確認"""
    return bool(os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON"))


def _get_credentials() -> Credentials | None:
    """環境変数からOAuth認証情報を取得・リフレッシュ"""
    creds_json = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON")
    if not creds_json:
        return None

    info = json.loads(creds_json)
    creds = Credentials(
        token=info.get("token"),
        refresh_token=info.get("refresh_token"),
        token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=info.get("client_id"),
        client_secret=info.get("client_secret"),
        scopes=info.get("scopes", SCOPES),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return creds


def _build_service():
    """Calendar APIサービスを構築"""
    creds = _get_credentials()
    if creds is None:
        return None
    return build("calendar", "v3", credentials=creds)


def register_task_to_calendar(task: dict) -> str | None:
    """
    タスクをGoogleカレンダーに登録する

    Args:
        task: タスク辞書（title, description, due_date, task_type を含む）

    Returns:
        カレンダーイベントID（成功時）、None（失敗・スキップ時）
    """
    due_date = task.get("due_date")
    if not due_date:
        return None

    service = _build_service()
    if service is None:
        return None

    title = task.get("title", "学校タスク")
    description_parts = []

    desc = task.get("description", "")
    if desc:
        description_parts.append(desc)

    target_grades = task.get("target_grades", [])
    if target_grades and target_grades != ["全学年"]:
        description_parts.append(f"対象: {', '.join(target_grades)}")

    dismissal_times = task.get("dismissal_times", [])
    if dismissal_times:
        times_str = " / ".join(f"{d['grades']} {d['time']}" for d in dismissal_times)
        description_parts.append(f"下校時刻: {times_str}")

    event = {
        "summary": title,
        "description": "\n".join(description_parts),
        "start": {"date": due_date},
        "end": {"date": due_date},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 24 * 60},  # 前日
            ],
        },
    }

    try:
        result = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        logger.info("[Calendar] イベント登録成功: %s (%s)", title, due_date)
        return result.get("id")
    except HttpError as e:
        logger.error("[Calendar] イベント登録エラー: %s", e)
        return None
