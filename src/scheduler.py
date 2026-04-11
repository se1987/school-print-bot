"""
リマインドスケジューラー
毎朝7時（JST）に当日・翌日の予定を、子どもの学年に合わせてLINEで通知する
"""

import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

JST = timezone(timedelta(hours=9))
_WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]


def _jst_today() -> date:
    """JSTベースの今日の日付を返す"""
    return datetime.now(JST).date()


def _format_date_label(d: date) -> str:
    """'4月11日（土）' 形式で日付をフォーマット"""
    return f"{d.month}月{d.day}日（{_WEEKDAYS_JA[d.weekday()]}）"


async def send_reminder_for_user(user_id: str) -> bool:
    """指定ユーザー向けに当日・翌日のリマインドを1通だけ送る（通知テスト用）。送信したら True、対象がなければ False。"""
    from line_client import push_text

    today_tasks = db.get_tasks_for_reminder(days_before=0)
    tomorrow_tasks = db.get_tasks_for_reminder(days_before=1)
    today_list = [t for t in today_tasks if t["user_id"] == user_id]
    tomorrow_list = [t for t in tomorrow_tasks if t["user_id"] == user_id]

    if not today_list and not tomorrow_list:
        return False

    children = db.get_children(user_id)
    if children:
        message = _build_personalized_reminder(today_list, tomorrow_list, children)
    else:
        message = _build_generic_reminder(today_list, tomorrow_list)

    try:
        await push_text(user_id, message)
    except Exception as e:
        logger.error("[Scheduler] %s への通知失敗: %s", user_id, e)
        return False

    for task in today_list + tomorrow_list:
        db.mark_task_reminded(task["id"])
    return True


async def send_daily_reminders():
    """当日＋翌日が期限のタスクを、各ユーザーの子どもの学年に合わせて通知"""
    from line_client import push_text

    logger.info("[Scheduler] リマインドチェック開始")

    # 当日(days_before=0)と翌日(days_before=1)のタスクを両方取得
    today_tasks = db.get_tasks_for_reminder(days_before=0)
    tomorrow_tasks = db.get_tasks_for_reminder(days_before=1)

    if not today_tasks and not tomorrow_tasks:
        logger.info("[Scheduler] リマインド対象なし")
        return

    # ユーザーごとにグループ化
    user_today: dict[str, list] = {}
    for task in today_tasks:
        user_today.setdefault(task["user_id"], []).append(task)

    user_tomorrow: dict[str, list] = {}
    for task in tomorrow_tasks:
        user_tomorrow.setdefault(task["user_id"], []).append(task)

    all_user_ids = set(user_today.keys()) | set(user_tomorrow.keys())

    for user_id in all_user_ids:
        today_list = user_today.get(user_id, [])
        tomorrow_list = user_tomorrow.get(user_id, [])
        children = db.get_children(user_id)

        if children:
            message = _build_personalized_reminder(today_list, tomorrow_list, children)
        else:
            message = _build_generic_reminder(today_list, tomorrow_list)

        try:
            await push_text(user_id, message)
            for task in today_list + tomorrow_list:
                db.mark_task_reminded(task["id"])
            logger.info("[Scheduler] %s に通知完了", user_id)
        except Exception as e:
            logger.error("[Scheduler] %s への通知失敗: %s", user_id, e)


def _build_task_section(tasks: list[dict], children: list[dict] | None, label: str) -> tuple[list[str], int]:
    """タスクリストを子ども別にフォーマットするヘルパー。戻り値は (行リスト, 表示したタスク数)。"""
    lines = []
    displayed_ids: set[int] = set()
    if not tasks:
        return lines, 0

    lines.append(f"\n{label}")
    lines.append("━━━━━━━━━━━━━━━━━")

    if children:
        for child in children:
            relevant = [t for t in tasks if db.is_task_relevant_to_child(t, child["grade"])]
            if not relevant:
                continue
            lines.append(f"  👤 {child['name']}（{child['grade']}）")
            for task in relevant:
                displayed_ids.add(task["id"])
                emoji = "📅" if task["task_type"] == "event" else "✏️"
                lines.append(f"    {emoji} {task['title']}")
                dismissal = db.get_dismissal_time_for_child(task, child["grade"])
                if dismissal:
                    lines.append(f"       ⏰ 下校: {dismissal}")
                desc = task.get("description", "")
                if desc:
                    lines.append(f"       {desc}")
            lines.append("")
        displayed_count = len(displayed_ids)
    else:
        for task in tasks:
            displayed_ids.add(task["id"])
            emoji = "📅" if task["task_type"] == "event" else "✏️"
            lines.append(f"  {emoji} {task['title']}")
            times = task.get("dismissal_times", [])
            for dt in times:
                lines.append(f"     ⏰ {dt['grades']}: {dt['time']}")
            desc = task.get("description", "")
            if desc:
                lines.append(f"     {desc}")
        lines.append("")
        displayed_count = len(tasks)

    return lines, displayed_count


def _build_personalized_reminder(today_tasks: list[dict], tomorrow_tasks: list[dict], children: list[dict]) -> str:
    """子どもの学年に合わせたリマインドメッセージを構築"""
    lines = ["🔔 おはようございます！"]

    today = _jst_today()
    tomorrow = today + timedelta(days=1)
    today_label = f"📌 今日の予定・タスク {_format_date_label(today)}"
    tomorrow_label = f"📅 明日の予定・タスク {_format_date_label(tomorrow)}"

    today_section, today_count = _build_task_section(today_tasks, children, today_label)
    tomorrow_section, tomorrow_count = _build_task_section(tomorrow_tasks, children, tomorrow_label)
    total_displayed = today_count + tomorrow_count

    if total_displayed == 0:
        return _build_generic_reminder(today_tasks, tomorrow_tasks)

    lines.extend(today_section)
    lines.extend(tomorrow_section)

    lines.append(f"📋 合計 {total_displayed} 件です。準備を忘れずに！")
    return "\n".join(lines)


def _build_generic_reminder(today_tasks: list[dict], tomorrow_tasks: list[dict]) -> str:
    """子ども未登録時の汎用リマインドメッセージ"""
    lines = ["🔔 おはようございます！"]

    today = _jst_today()
    tomorrow = today + timedelta(days=1)
    today_label = f"📌 今日の予定・タスク {_format_date_label(today)}"
    tomorrow_label = f"📅 明日の予定・タスク {_format_date_label(tomorrow)}"

    today_section, today_count = _build_task_section(today_tasks, None, today_label)
    tomorrow_section, tomorrow_count = _build_task_section(tomorrow_tasks, None, tomorrow_label)
    lines.extend(today_section)
    lines.extend(tomorrow_section)

    total_displayed = today_count + tomorrow_count
    lines.append(f"📋 合計 {total_displayed} 件です。準備を忘れずに！")
    lines.append("\n💡 「子ども登録」と送信すると、学年に合った通知になります")
    return "\n".join(lines)


def _advance_grade(grade: str) -> tuple[str, bool]:
    """
    学年を1つ進める
    Returns: (new_grade, is_graduated)
    卒業学年（小6・中学3年・高校3年）の場合は is_graduated=True を返す
    """
    import re
    match = re.match(r"(中学|高校|中|高)?(\d+)年", grade)
    if not match:
        return grade, False
    prefix = match.group(1) or ""
    num = int(match.group(2))
    if (prefix == "" and num >= 6) or (prefix in ("中学", "中") and num >= 3) or (prefix in ("高校", "高") and num >= 3):
        return grade, True
    return f"{prefix}{num + 1}年", False


async def advance_grades_april():
    """4月1日 9時 JST に全員の学年を1つ進める"""
    from line_client import push_text
    logger.info("[Scheduler] 学年自動進級処理開始")
    children = db.get_all_children()
    for child in children:
        new_grade, graduated = _advance_grade(child["grade"])
        try:
            if graduated:
                await push_text(
                    child["user_id"],
                    f"🎓 {child['name']}さん（{child['grade']}）は卒業学年です。\n"
                    "進学先の学年に更新するか、削除してください。\n\n"
                    f"例: 子ども登録 {child['name']} 中学1年\n"
                    f"削除: 子ども削除 {child['name']}"
                )
            else:
                db.update_child_grade(child["id"], new_grade)
                await push_text(
                    child["user_id"],
                    f"🎒 新学年おめでとうございます！\n"
                    f"{child['name']}さんの学年を {child['grade']} → {new_grade} に更新しました。"
                )
        except Exception as e:
            logger.error("[Scheduler] %s への進級通知失敗: %s", child["user_id"], e)
    logger.info("[Scheduler] %d 件の学年を処理しました", len(children))


def start_scheduler():
    # 毎朝7時 JST = UTC 22:00（前日）
    scheduler.add_job(
        send_daily_reminders,
        CronTrigger(hour=22, minute=0),
        id="daily_reminder",
        replace_existing=True,
    )
    # 4月1日 9時 JST = UTC 0時（4月1日）
    scheduler.add_job(
        advance_grades_april,
        CronTrigger(month=4, day=1, hour=0, minute=0),
        id="advance_grades",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[Scheduler] リマインドスケジューラー起動（毎朝7時 JST）")
