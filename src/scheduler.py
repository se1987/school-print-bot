"""
リマインドスケジューラー
毎朝7時（JST）に翌日の予定を、子どもの学年に合わせてLINEで通知する
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db

scheduler = AsyncIOScheduler()


async def send_daily_reminders():
    """翌日が期限のタスクを、各ユーザーの子どもの学年に合わせて通知"""
    from line_handler import _push_text

    print("🔔 リマインドチェック開始...")

    tasks = db.get_tasks_for_reminder(days_before=1)
    if not tasks:
        print("  → リマインド対象なし")
        return

    # ユーザーごとにグループ化
    user_tasks: dict[str, list] = {}
    for task in tasks:
        uid = task["user_id"]
        if uid not in user_tasks:
            user_tasks[uid] = []
        user_tasks[uid].append(task)

    for user_id, task_list in user_tasks.items():
        children = db.get_children(user_id)

        if children:
            # 子ども登録済み → 学年に合わせたパーソナライズ通知
            message = _build_personalized_reminder(task_list, children)
        else:
            # 子ども未登録 → 全タスクをそのまま通知
            message = _build_generic_reminder(task_list)

        try:
            await _push_text(user_id, message)
            for task in task_list:
                db.mark_task_reminded(task["id"])
            print(f"  ✅ {user_id} に通知完了")
        except Exception as e:
            print(f"  ❌ {user_id} への通知失敗: {e}")


def _build_personalized_reminder(tasks: list[dict], children: list[dict]) -> str:
    """子どもの学年に合わせたリマインドメッセージを構築"""
    lines = ["🔔 明日の予定リマインド\n"]

    for child in children:
        child_name = child["name"]
        child_grade = child["grade"]

        relevant_tasks = [
            t for t in tasks if db.is_task_relevant_to_child(t, child_grade)
        ]

        if not relevant_tasks:
            continue

        lines.append(f"👤 {child_name}（{child_grade}）")
        lines.append("─────────────")

        for task in relevant_tasks:
            emoji = "📅" if task["task_type"] == "event" else "✏️"
            lines.append(f"  {emoji} {task['title']}")

            # その子専用の下校時刻を表示
            dismissal = db.get_dismissal_time_for_child(task, child_grade)
            if dismissal:
                lines.append(f"     ⏰ {child_name}の下校: {dismissal}")

            desc = task.get("description", "")
            if desc:
                lines.append(f"     {desc}")

        lines.append("")

    if len(lines) <= 1:
        # 該当する子がいなかった場合
        return _build_generic_reminder(tasks)

    lines.append("📋 準備を忘れずに！")
    return "\n".join(lines)


def _build_generic_reminder(tasks: list[dict]) -> str:
    """子ども未登録時の汎用リマインドメッセージ"""
    lines = ["🔔 明日の予定・タスクのリマインド\n"]

    for task in tasks:
        emoji = "📅" if task["task_type"] == "event" else "✏️"
        lines.append(f"{emoji} {task['title']}")

        # 下校時刻が学年別にある場合はすべて表示
        times = task.get("dismissal_times", [])
        if times:
            for dt in times:
                lines.append(f"   ⏰ {dt['grades']}: {dt['time']}")

        desc = task.get("description", "")
        if desc:
            lines.append(f"   {desc}")
        lines.append("")

    lines.append(f"📋 合計 {len(tasks)} 件です。準備を忘れずに！")
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
