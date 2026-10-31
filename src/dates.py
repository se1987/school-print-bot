"""
日付ユーティリティ

Gemini が返す YYYY-MM-DD の文字列を、保護者が読みやすい「11/5(水)」形式に整えたり、
曜日を求めたりする。ホストのタイムゾーンに依存しないよう、「今日」は JST で扱う。
"""

from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# date.weekday() の 0（月曜）〜6（日曜）に対応する日本語の曜日
WEEKDAYS_JA = "月火水木金土日"


def today_jst() -> date:
    """JST ベースの今日の日付を返す"""
    return datetime.now(JST).date()


def parse_iso_date(iso: str | None) -> date | None:
    """YYYY-MM-DD 形式の文字列を date にする。不正なら None"""
    if not isinstance(iso, str):
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None


def weekday_ja(iso: str | None) -> str | None:
    """"2026-11-05" → "水"。日付として読めなければ None"""
    d = parse_iso_date(iso)
    return WEEKDAYS_JA[d.weekday()] if d else None


def format_date_ja(iso: str | None, *, today: date | None = None) -> str:
    """"2026-11-05" → "11/5(水)"。年が今年と違うときだけ "2027/4/8(木)" のように年も付ける。

    日付として読めない文字列はそのまま返す（表示が欠けるよりは生の値が見えたほうがよい）。
    """
    d = parse_iso_date(iso)
    if d is None:
        return iso or ""
    today = today or today_jst()
    wd = WEEKDAYS_JA[d.weekday()]
    if d.year != today.year:
        return f"{d.year}/{d.month}/{d.day}({wd})"
    return f"{d.month}/{d.day}({wd})"
