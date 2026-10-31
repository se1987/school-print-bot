"""
読み取り結果の整合チェック

Gemini の読み取りは表形式のプリント（学年だより等）で日付が1日ずれることがある。
機械的に検出できるずれを ⚠️ の文言にして返し、保護者がプリントと見比べる手がかりにする。
DB や外部 API には依存しない純粋関数のみ。
"""

from datetime import date, timedelta

from dates import WEEKDAYS_JA, format_date_ja, parse_iso_date, today_jst

# 曜日不一致のとき、正しい日付の候補を探す範囲（前後の日数）。3なら他の6曜日をちょうど1回ずつ含む
WEEKDAY_FIX_SEARCH_DAYS = 3
# 今日からこれ以上離れた日付は「年の読み間違い」を疑う
PAST_LIMIT_DAYS = 60
FUTURE_LIMIT_DAYS = 400


def check_tasks(tasks: list[dict], *, today: date | None = None) -> list[list[str]]:
    """各タスクの警告文のリストを、tasks と同じ順番で返す（警告がなければ空リスト）"""
    today = today or today_jst()
    warnings: list[list[str]] = [[] for _ in tasks]

    for i, task in enumerate(tasks):
        due = parse_iso_date(task.get("due_date"))
        if due is None:
            continue
        msg = _weekday_mismatch(task, due, today)
        if msg:
            warnings[i].append(msg)
        msg = _year_far_off(due, today)
        if msg:
            warnings[i].append(msg)

    for i, j in _consecutive_pairs(tasks):
        a = format_date_ja(tasks[i]["due_date"], today=today)
        b = format_date_ja(tasks[j]["due_date"], today=today)
        msg = f"⚠️ 同じ予定が {a} と {b} の両方にあります。片方は読み間違いかもしれません"
        warnings[i].append(msg)
        warnings[j].append(msg)

    return warnings


def _weekday_mismatch(task: dict, due: date, today: date) -> str | None:
    """プリントに書かれた曜日と due_date の曜日が食い違っていれば警告する"""
    printed = task.get("weekday_on_print")
    # None や空文字は「曜日の記載なし」。"" in "月火…" は True になるので長さも見る
    if not (isinstance(printed, str) and len(printed) == 1 and printed in WEEKDAYS_JA):
        return None
    actual = WEEKDAYS_JA[due.weekday()]
    if printed == actual:
        return None

    msg = f"⚠️ 曜日が合いません: プリントは({printed})、{format_date_ja(due.isoformat(), today=today)}は({actual})"
    # 7日周期なので、前後3日以内にはプリントの曜日と一致する日がちょうど1つある
    delta = (WEEKDAYS_JA.index(printed) - due.weekday()) % 7
    if delta > WEEKDAY_FIX_SEARCH_DAYS:
        delta -= 7
    candidate = due + timedelta(days=delta)
    msg += f"。{format_date_ja(candidate.isoformat(), today=today)} の可能性があります"
    return msg


def _year_far_off(due: date, today: date) -> str | None:
    """今日から離れすぎた日付は、年の推定ミス（令和の換算や年度またぎ）を疑う"""
    delta = (due - today).days
    if delta < -PAST_LIMIT_DAYS or delta > FUTURE_LIMIT_DAYS:
        shown = f"{due.year}/{due.month}/{due.day}"
        return f"⚠️ 日付が今日から離れています（{shown}）。年の読み取りをご確認ください"
    return None


def _normalize_title(title: str | None) -> str:
    return "".join((title or "").split()).casefold()


def _consecutive_pairs(tasks: list[dict]) -> list[tuple[int, int]]:
    """同じタイトルで日付が1日違いのタスクの組（インデックス）を返す"""
    pairs: list[tuple[int, int]] = []
    for i in range(len(tasks)):
        due_i = parse_iso_date(tasks[i].get("due_date"))
        if due_i is None:
            continue
        title_i = _normalize_title(tasks[i].get("title"))
        if not title_i:
            continue
        for j in range(i + 1, len(tasks)):
            due_j = parse_iso_date(tasks[j].get("due_date"))
            if due_j is None or _normalize_title(tasks[j].get("title")) != title_i:
                continue
            if abs((due_i - due_j).days) == 1:
                pairs.append((i, j))
    return pairs
