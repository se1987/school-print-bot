"""
line_handler.py のテスト
- 子ども登録コマンドの正規表現パース
"""

import re

# line_handler.py と同じパターン
CHILD_REGISTER_PATTERN = re.compile(r"子ども登録\s+(.+?)\s+(\S+年)")


class TestChildRegisterPattern:
    def test_elementary(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 たろう 1年")
        assert m is not None
        assert m.group(1) == "たろう"
        assert m.group(2) == "1年"

    def test_middle_school(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 はなこ 中学1年")
        assert m is not None
        assert m.group(1) == "はなこ"
        assert m.group(2) == "中学1年"

    def test_high_school(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 じろう 高校2年")
        assert m is not None
        assert m.group(2) == "高校2年"

    def test_short_prefix_middle(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 さくら 中2年")
        assert m is not None
        assert m.group(2) == "中2年"

    def test_short_prefix_high(self):
        m = CHILD_REGISTER_PATTERN.match("子ども登録 たろう 高1年")
        assert m is not None
        assert m.group(2) == "高1年"

    def test_no_match_without_grade(self):
        assert CHILD_REGISTER_PATTERN.match("子ども登録 たろう") is None

    def test_no_match_unrelated_command(self):
        assert CHILD_REGISTER_PATTERN.match("子ども一覧") is None

    def test_no_match_grade_only(self):
        assert CHILD_REGISTER_PATTERN.match("子ども登録 1年") is None
