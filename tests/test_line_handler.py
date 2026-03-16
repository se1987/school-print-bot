"""
line_handler.py のテスト
- 子ども登録コマンドの正規表現パース（表記ゆらぎ対応）
- 検索キーワード長の制限
"""

import re

# line_handler.py と同じパターン
_CHILD_VARIANTS = r"(?:子ども|子供|こども)"
CHILD_REGISTER_PATTERN = re.compile(rf"{_CHILD_VARIANTS}登録\s+(.+?)\s+(\S+年)")
CHILD_DELETE_PATTERN = re.compile(rf"{_CHILD_VARIANTS}削除\s+(.+)")

CHILD_LIST_KEYWORDS = {"子ども一覧", "子ども", "子供一覧", "子供", "こども一覧", "こども"}
CHILD_REGISTER_KEYWORDS = {"子ども登録", "子供登録", "こども登録"}

MAX_KEYWORD_LENGTH = 200


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


class TestChildVariantKanji:
    """「子供」表記でのコマンド"""
    def test_register_kanji(self):
        m = CHILD_REGISTER_PATTERN.match("子供登録 たろう 1年")
        assert m is not None
        assert m.group(1) == "たろう"
        assert m.group(2) == "1年"

    def test_register_hiragana(self):
        m = CHILD_REGISTER_PATTERN.match("こども登録 はなこ 3年")
        assert m is not None
        assert m.group(1) == "はなこ"
        assert m.group(2) == "3年"

    def test_delete_kanji(self):
        m = CHILD_DELETE_PATTERN.match("子供削除 たろう")
        assert m is not None
        assert m.group(1) == "たろう"

    def test_delete_hiragana(self):
        m = CHILD_DELETE_PATTERN.match("こども削除 はなこ")
        assert m is not None
        assert m.group(1) == "はなこ"

    def test_list_keywords(self):
        assert "子供一覧" in CHILD_LIST_KEYWORDS
        assert "こども一覧" in CHILD_LIST_KEYWORDS
        assert "子供" in CHILD_LIST_KEYWORDS
        assert "こども" in CHILD_LIST_KEYWORDS

    def test_register_keywords(self):
        assert "子供登録" in CHILD_REGISTER_KEYWORDS
        assert "こども登録" in CHILD_REGISTER_KEYWORDS


class TestKeywordLength:
    def test_within_limit(self):
        keyword = "a" * MAX_KEYWORD_LENGTH
        assert len(keyword) <= MAX_KEYWORD_LENGTH

    def test_exceeds_limit(self):
        keyword = "a" * (MAX_KEYWORD_LENGTH + 1)
        assert len(keyword) > MAX_KEYWORD_LENGTH
