"""
dates.py のテスト
- weekday_ja: YYYY-MM-DD → 日本語の曜日
- format_date_ja: 保護者向けの「11/5(水)」表記（年が違うときだけ年を付ける）
"""

from datetime import date

import pytest

from dates import format_date_ja, parse_iso_date, weekday_ja

TODAY = date(2026, 10, 31)


class TestParseIsoDate:
    def test_valid(self):
        assert parse_iso_date("2026-11-05") == date(2026, 11, 5)

    @pytest.mark.parametrize("value", [None, "", "11月5日", "2026/11/05", "2026-13-01", 20261105])
    def test_invalid_returns_none(self, value):
        assert parse_iso_date(value) is None


class TestWeekdayJa:
    def test_thursday(self):
        assert weekday_ja("2026-11-05") == "木"

    def test_sunday(self):
        assert weekday_ja("2026-11-01") == "日"

    def test_invalid_returns_none(self):
        assert weekday_ja("不明") is None
        assert weekday_ja(None) is None


class TestFormatDateJa:
    def test_same_year_omits_year(self):
        assert format_date_ja("2026-11-05", today=TODAY) == "11/5(木)"

    def test_other_year_includes_year(self):
        assert format_date_ja("2027-04-08", today=TODAY) == "2027/4/8(木)"

    def test_invalid_returns_raw(self):
        assert format_date_ja("春休み中", today=TODAY) == "春休み中"

    def test_none_returns_empty(self):
        assert format_date_ja(None, today=TODAY) == ""
