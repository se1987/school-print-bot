"""
リマインドスケジューラー
毎朝7時（JST）に翌日の予定を、子どもの学年に合わせてLINEで通知する
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db

scheduler = AsyncIOScheduler()


async def send_daily_reminders():
    """当日＋翌日が期限のタスクを、各ユーザーの子どもの学年に合わせて通知"""
    from line_handler import _push_text

    print("🔔 リマインドチェック開始...")

    # 当日(days_before=0)と翌日(days_before=1)のタスクを両方取得
    today_tasks = db.get_tasks_for_reminder(days_before=0)
    tomorrow_tasks = db.get_tasks_for_reminder(days_before=1)

    if not today_tasks and not tomorrow_tasks:
        print("  → リマインド対象なし")
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
            await _push_text(user_id, message)
            for task in today_list + tomorrow_list:
                db.mark_task_reminded(task["id"])
            print(f"  ✅ {user_id} に通知完了")
        except Exception as e:
            print(f"  ❌ {user_id} への通知失敗: {e}")


def _build_task_section(tasks: list[dict], children: list[dict] | None, label: str) -> list[str]:
    """タスクリストを子ども別にフォーマットするヘルパー"""
    lines = []
    if not tasks:
        return lines

    lines.append(f"\n{label}")
    lines.append("━━━━━━━━━━━━━━━━━")

    if children:
        for child in children:
            relevant = [t for t in tasks if db.is_task_relevant_to_child(t, child["grade"])]
            if not relevant:
                continue
            lines.append(f"  👤 {child['name']}（{child['grade']}）")
            for task in relevant:
                emoji = "📅" if task["task_type"] == "event" else "✏️"
                lines.append(f"    {emoji} {task['title']}")
                dismissal = db.get_dismissal_time_for_child(task, child["grade"])
                if dismissal:
                    lines.append(f"       ⏰ 下校: {dismissal}")
                desc = task.get("description", "")
                if desc:
                    lines.append(f"       {desc}")
            lines.append("")
    else:
        for task in tasks:
            emoji = "📅" if task["task_type"] == "event" else "✏️"
            lines.append(f"  {emoji} {task['title']}")
            times = task.get("dismissal_times", [])
            for dt in times:
                lines.append(f"     ⏰ {dt['grades']}: {dt['time']}")
            desc = task.get("description", "")
            if desc:
                lines.append(f"     {desc}")
        lines.append("")

    return lines


def _build_personalized_reminder(today_tasks: list[dict], tomorrow_tasks: list[dict], children: list[dict]) -> str:
    """子どもの学年に合わせたリマインドメッセージを構築"""
    lines = ["🔔 おはようございます！"]

    today_section = _build_task_section(today_tasks, children, "📌 今日の予定・タスク")
    tomorrow_section = _build_task_section(tomorrow_tasks, children, "📅 明日の予定・タスク")

    if not today_section and not tomorrow_section:
        return _build_generic_reminder(today_tasks, tomorrow_tasks)

    lines.extend(today_section)
    lines.extend(tomorrow_section)

    total = len(today_tasks) + len(tomorrow_tasks)
    lines.append(f"📋 合計 {total} 件です。準備を忘れずに！")
    return "\n".join(lines)


def _build_generic_reminder(today_tasks: list[dict], tomorrow_tasks: list[dict]) -> str:
    """子ども未登録時の汎用リマインドメッセージ"""
    lines = ["🔔 おはようございます！"]

    lines.extend(_build_task_section(today_tasks, None, "📌 今日の予定・タスク"))
    lines.extend(_build_task_section(tomorrow_tasks, None, "📅 明日の予定・タスク"))

    total = len(today_tasks) + len(tomorrow_tasks)
    lines.append(f"📋 合計 {total} 件です。準備を忘れずに！")
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
    from line_handler import _push_text
    print("🎓 学年自動進級処理開始...")
    children = db.get_all_children()
    for child in children:
        new_grade, graduated = _advance_grade(child["grade"])
        try:
            if graduated:
                await _push_text(
                    child["user_id"],
                    f"🎓 {child['name']}さん（{child['grade']}）は卒業学年です。\n"
                    "進学先の学年に更新するか、削除してください。\n\n"
                    f"例: 子ども登録 {child['name']} 中学1年\n"
                    f"削除: 子ども削除 {child['name']}"
                )
            else:
                db.update_child_grade(child["id"], new_grade)
                await _push_text(
                    child["user_id"],
                    f"🎒 新学年おめでとうございます！\n"
                    f"{child['name']}さんの学年を {child['grade']} → {new_grade} に更新しました。"
                )
        except Exception as e:
            print(f"  ❌ {child['user_id']} への進級通知失敗: {e}")
    print(f"  ✅ {len(children)} 件の学年を処理しました")


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
    print("⏰ リマインドスケジューラー起動（毎朝7時 JST）")
