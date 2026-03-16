"""
LINE Bot Webhook ハンドラー
ユーザーからのメッセージを処理し、適切な応答を返す
"""

import logging
import re

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    FileMessageContent,
)

import database as db
import gemini_client
import google_calendar
from line_client import reply_text, push_text, download_content

logger = logging.getLogger(__name__)

# 検索キーワードの最大長
MAX_KEYWORD_LENGTH = 200


def validate_keyword(keyword: str) -> None:
    """検索キーワードの長さを検証する。超過時は ValueError を送出する。"""
    if len(keyword) > MAX_KEYWORD_LENGTH:
        raise ValueError(f"検索キーワードが長すぎます（{MAX_KEYWORD_LENGTH}文字以内にしてください）")


# ============================================================
# メッセージ振り分け
# ============================================================

async def handle_message(event: MessageEvent):
    if isinstance(event.message, ImageMessageContent):
        await handle_image(event)
    elif isinstance(event.message, FileMessageContent):
        await handle_file(event)
    elif isinstance(event.message, TextMessageContent):
        await handle_text(event)


# ============================================================
# 画像・PDF解析
# ============================================================

async def handle_image(event: MessageEvent):
    user_id = event.source.user_id
    message_id = event.message.id

    await reply_text(event.reply_token, "📄 プリントを解析中です...\nしばらくお待ちください。")

    try:
        image_bytes = await download_content(message_id)
        result = await gemini_client.analyze_image(image_bytes, "image/jpeg")
        await _save_and_reply(user_id, result)
    except Exception as e:
        logger.error("[Handler] 画像処理エラー: %s", e)
        await push_text(user_id, "⚠️ 解析中にエラーが発生しました。\nもう一度送信してみてください。")


async def handle_file(event: MessageEvent):
    user_id = event.source.user_id
    message_id = event.message.id
    file_name = event.message.file_name or ""

    if not file_name.lower().endswith(".pdf"):
        await reply_text(event.reply_token, "📎 PDFファイルを送ってください。\n（画像やスクリーンショットでもOKです！）")
        return

    await reply_text(event.reply_token, "📄 PDFを解析中です...\nしばらくお待ちください。")

    try:
        pdf_bytes = await download_content(message_id)
        result = await gemini_client.analyze_pdf(pdf_bytes)
        await _save_and_reply(user_id, result)
    except Exception as e:
        logger.error("[Handler] PDF処理エラー: %s", e)
        await push_text(user_id, "⚠️ 解析中にエラーが発生しました。\nもう一度送信してみてください。")


async def _save_and_reply(user_id: str, result: dict):
    """解析結果を保存してLINEに返信する共通処理"""
    print_id = db.save_print(
        user_id=user_id,
        original_text=result.get("summary", ""),
        summary=result.get("summary", ""),
        grade=result.get("grade"),
    )
    tasks = result.get("tasks", [])
    cal_count = 0
    if tasks:
        task_ids = db.save_tasks(print_id, user_id, tasks)
        if google_calendar.is_calendar_enabled():
            for task_id, task in zip(task_ids, tasks):
                event_id = google_calendar.register_task_to_calendar(task)
                if event_id:
                    db.mark_task_registered(task_id)
                    cal_count += 1

    children = db.get_children(user_id)
    response_text = _format_analysis_result(result, children, cal_count)
    await push_text(user_id, response_text)


# ============================================================
# テキストコマンド処理
# ============================================================

# 「子ども」「子供」「こども」の表記ゆらぎに対応
_CHILD_VARIANTS = r"(?:子ども|子供|こども)"

_CHILD_REGISTER_RE = re.compile(rf"{_CHILD_VARIANTS}登録\s+(.+?)\s+(\S+年)")
_CHILD_DELETE_RE = re.compile(rf"{_CHILD_VARIANTS}削除\s+(.+)")
_CHILD_LIST_KEYWORDS = {"子ども一覧", "子ども", "子供一覧", "子供", "こども一覧", "こども"}
_CHILD_REGISTER_KEYWORDS = {"子ども登録", "子供登録", "こども登録"}


async def handle_text(event: MessageEvent):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 子ども登録コマンド
    child_match = _CHILD_REGISTER_RE.match(text)
    if child_match:
        await _register_child(event, user_id, child_match.group(1), child_match.group(2))
        return

    if text in _CHILD_REGISTER_KEYWORDS:
        await reply_text(
            event.reply_token,
            "👶 子どもを登録するには、以下の形式で送信してください:\n\n"
            "  子ども登録 たろう 1年\n"
            "  子ども登録 はなこ 4年\n"
            "  子ども登録 じろう 中学1年\n\n"
            "登録すると、学年に合った下校時刻やタスクだけを\n"
            "リマインドでお届けします！"
        )
        return

    if text in _CHILD_LIST_KEYWORDS:
        await _show_children(event, user_id)
        return

    child_del = _CHILD_DELETE_RE.match(text)
    if child_del:
        await _delete_child(event, user_id, child_del.group(1))
        return

    if text in ("タスク一覧", "タスク"):
        await _show_pending_tasks(event, user_id)
        return

    if text in ("全タスク", "タスク履歴"):
        await _show_all_tasks(event, user_id)
        return

    if text == "通知テスト":
        await _test_reminder(event, user_id)
        return

    if text in ("ヘルプ", "使い方"):
        await _show_help(event)
        return

    # それ以外 → キーワード検索
    await _search_prints(event, user_id, text)


# ============================================================
# 子ども管理コマンド
# ============================================================

async def _register_child(event, user_id, name, grade):
    db.add_child(user_id, name, grade)
    children = db.get_children(user_id)
    names = "、".join(f"{c['name']}（{c['grade']}）" for c in children)
    await reply_text(
        event.reply_token,
        f"✅ {name}（{grade}）を登録しました！\n\n"
        f"👨‍👩‍👧‍👦 登録済み: {names}\n\n"
        "これでリマインドやプリント解析が\n"
        "学年に合わせた内容になります 🎉"
    )


async def _show_children(event, user_id):
    children = db.get_children(user_id)
    if not children:
        await reply_text(
            event.reply_token,
            "👶 まだ子どもが登録されていません。\n\n"
            "「子ども登録 名前 ◯年」で登録できます\n"
            "例: 子ども登録 たろう 1年"
        )
        return

    lines = ["👨‍👩‍👧‍👦 登録済みの子ども\n"]
    for c in children:
        lines.append(f"  🎒 {c['name']}（{c['grade']}）")
    lines.append("\n💡 削除: 「子ども削除 名前」")
    lines.append("💡 進級は毎年4月1日に自動で行われます")
    await reply_text(event.reply_token, "\n".join(lines))


async def _delete_child(event, user_id, name):
    children = db.get_children(user_id)
    target = next((c for c in children if c["name"] == name.strip()), None)
    if not target:
        await reply_text(event.reply_token, f"⚠️ 「{name}」は見つかりませんでした。")
        return
    db.delete_child(target["id"])
    await reply_text(event.reply_token, f"✅ {name}（{target['grade']}）を削除しました。")


# ============================================================
# タスク表示・検索
# ============================================================

async def _show_pending_tasks(event, user_id):
    tasks = db.get_pending_tasks(user_id)
    if not tasks:
        await reply_text(event.reply_token, "✅ 現在、未対応のタスクはありません！")
        return

    children = db.get_children(user_id)

    if children:
        # 子どもごとに関連タスクをフィルタして表示
        lines = ["📋 未対応のタスク一覧\n"]
        for child in children:
            relevant = [t for t in tasks if db.is_task_relevant_to_child(t, child["grade"])]
            if not relevant:
                continue
            lines.append(f"👤 {child['name']}（{child['grade']}）")
            for task in relevant:
                emoji = "📅" if task["task_type"] == "event" else "✏️"
                due = task["due_date"] or "日付未定"
                lines.append(f"  {emoji} {task['title']}（{due}）")
                dismissal = db.get_dismissal_time_for_child(task, child["grade"])
                if dismissal:
                    lines.append(f"     ⏰ 下校: {dismissal}")
            lines.append("")
    else:
        lines = ["📋 未対応のタスク一覧\n"]
        for task in tasks:
            emoji = "📅" if task["task_type"] == "event" else "✏️"
            due = task["due_date"] or "日付未定"
            lines.append(f"{emoji} {task['title']}（{due}）")
            times = task.get("dismissal_times", [])
            for dt in times:
                lines.append(f"   ⏰ {dt['grades']}: {dt['time']}")
            lines.append("")
        lines.append("💡 「子ども登録」で学年に合わせた表示になります")

    await reply_text(event.reply_token, "\n".join(lines))


async def _show_all_tasks(event, user_id):
    """期限切れを含む全タスクを表示"""
    tasks = db.get_all_tasks(user_id)
    if not tasks:
        await reply_text(event.reply_token, "📋 タスクはまだ登録されていません。\nプリントの画像やPDFを送ってください！")
        return

    from datetime import date
    today = date.today().isoformat()

    lines = ["📋 全タスク一覧\n"]
    for task in tasks:
        emoji = "📅" if task["task_type"] == "event" else "✏️"
        due = task["due_date"] or "日付未定"
        expired = " ⚠️期限切れ" if task["due_date"] and task["due_date"] < today else ""
        lines.append(f"{emoji} {task['title']}（{due}）{expired}")
    lines.append(f"\n合計 {len(tasks)} 件")
    await reply_text(event.reply_token, "\n".join(lines))


async def _test_reminder(event, user_id):
    """通知テスト: リクエストしたユーザー向けにリマインドを1通だけ即時送信"""
    from scheduler import send_reminder_for_user
    await reply_text(event.reply_token, "🔔 通知テストを実行中...")
    sent = await send_reminder_for_user(user_id)
    if sent:
        await push_text(user_id, "✅ 通知テスト完了\n対象のタスク・予定を送信しました。")
    else:
        await push_text(user_id, "✅ 通知テスト完了\n当日・翌日が期限のタスクはありませんでした。")


async def _search_prints(event, user_id, keyword):
    try:
        validate_keyword(keyword)
    except ValueError as e:
        await reply_text(event.reply_token, f"⚠️ {e}")
        return

    results = db.search_prints(user_id, keyword)
    if not results:
        await reply_text(
            event.reply_token,
            f"🔍 「{keyword}」に一致するプリントは見つかりませんでした。\n\n"
            "💡 ヒント:\n"
            "・画像やPDFを送ると登録できます\n"
            "・「タスク一覧」で未対応タスクを確認\n"
            "・「ヘルプ」で使い方を表示",
        )
        return

    lines = [f"🔍 「{keyword}」の検索結果: {len(results)}件\n"]
    for r in results:
        date_str = r["created_at"][:10] if r["created_at"] else "不明"
        grade = f"[{r['grade']}] " if r.get("grade") else ""
        summary = r["summary"][:60] if r["summary"] else "要約なし"
        lines.append(f"📄 {grade}{summary}")
        lines.append(f"   ({date_str}登録)")
        lines.append("")

    await reply_text(event.reply_token, "\n".join(lines))


async def _show_help(event):
    await reply_text(
        event.reply_token,
        "📚 学校プリント管理Bot\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "📸 画像/PDFを送信\n"
        "→ プリントを解析してタスク抽出\n\n"
        "🔍 キーワードを送信\n"
        "→ 過去のプリントを検索\n\n"
        "📋 「タスク一覧」\n"
        "→ 未対応タスクを表示\n\n"
        "📋 「全タスク」\n"
        "→ 期限切れ含む全タスクを表示\n\n"
        "🔔 「通知テスト」\n"
        "→ リマインド通知を即時実行\n\n"
        "👶 「子ども登録 名前 ◯年」\n"
        "→ 学年別の下校時刻を通知\n"
        "  例: 子ども登録 たろう 1年\n"
        "  例: 子ども登録 じろう 中学1年\n\n"
        "👨‍👩‍👧‍👦 「子ども一覧」\n"
        "→ 登録済みの子どもを確認\n\n"
        "❓ 「ヘルプ」\n"
        "→ この使い方を表示\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "💡 スクショでもPDFでもOK！\n"
        "🔔 毎朝7時に当日・翌日のリマインドをお届け"
    )


# ============================================================
# 解析結果フォーマット（学年パーソナライズ対応）
# ============================================================

def _format_analysis_result(result: dict, children: list[dict], cal_count: int = 0) -> str:
    """解析結果をLINEメッセージ用にフォーマット"""
    lines = []

    if "error" in result:
        return f"⚠️ 解析中にエラーが発生しました:\n{result['error']}"

    grade = result.get("grade")
    if grade:
        lines.append(f"🏫 {grade}")

    summary = result.get("summary", "")
    if summary:
        lines.append(f"📄 {summary}")

    tasks = result.get("tasks", [])
    events = [t for t in tasks if t.get("task_type") == "event"]
    todo_tasks = [t for t in tasks if t.get("task_type") != "event"]

    # --- 予定 ---
    if events:
        lines.append("\n📅 予定・行事")
        lines.append("━━━━━━━━━━━━━━━━━")
        for task in events:
            due = task.get("due_date", "")
            date_str = f" ({due})" if due else ""
            lines.append(f"  📅 {task.get('title', '不明')}{date_str}")

            desc = task.get("description", "")
            if desc:
                lines.append(f"     {desc}")

            # 下校時刻の表示
            times = task.get("dismissal_times", [])
            if times:
                if children:
                    # 子どもが登録済み → その子専用の下校時刻
                    for child in children:
                        dismissal = db.get_dismissal_time_for_child(task, child["grade"])
                        if dismissal:
                            lines.append(f"     ⏰ {child['name']}: {dismissal}")
                else:
                    # 子ども未登録 → 全学年分を表示
                    for dt in times:
                        lines.append(f"     ⏰ {dt['grades']}: {dt['time']}")

    # --- タスク ---
    if todo_tasks:
        lines.append("\n✏️ やることリスト")
        lines.append("━━━━━━━━━━━━━━━━━")
        for task in todo_tasks:
            due = task.get("due_date")
            deadline = f"（〜{due}）" if due else ""
            lines.append(f"  ✏️ {task.get('title', '不明')}{deadline}")
            desc = task.get("description", "")
            if desc:
                lines.append(f"     {desc}")

    # --- 補足情報 ---
    notes = result.get("notes", [])
    if notes:
        lines.append("\n💡 補足情報")
        for note in notes:
            lines.append(f"  ・{note}")

    # --- フッター ---
    if tasks:
        lines.append(f"\n━━━━━━━━━━━━━━━━━")
        lines.append(f"✅ {len(tasks)}件の予定・タスクを保存しました")
        if cal_count > 0:
            lines.append(f"📅 {cal_count}件をGoogleカレンダーに登録しました")
            lines.append(
                "🌳 TimeTreeでも確認できます\n"
                "   設定方法: https://support.timetreeapp.com/hc/ja/articles/360000629341"
            )

    if not children:
        lines.append("\n💡 「子ども登録 名前 ◯年」で\n   学年に合った下校時刻を表示できます")

    return "\n".join(lines)
