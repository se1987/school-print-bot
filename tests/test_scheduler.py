"""
scheduler.py のテスト
- _advance_grade: 学年自動進級ロジック
"""

from scheduler import _advance_grade


class TestAdvanceGrade:
    # 小学校
    def test_elementary_normal(self):
        assert _advance_grade("1年") == ("2年", False)
        assert _advance_grade("2年") == ("3年", False)
        assert _advance_grade("5年") == ("6年", False)

    def test_elementary_graduation(self):
        grade, graduated = _advance_grade("6年")
        assert graduated is True
        assert grade == "6年"  # 更新しない

    # 中学校（中学◯年）
    def test_middle_school_normal(self):
        assert _advance_grade("中学1年") == ("中学2年", False)
        assert _advance_grade("中学2年") == ("中学3年", False)

    def test_middle_school_graduation(self):
        _, graduated = _advance_grade("中学3年")
        assert graduated is True

    # 高校（高校◯年）
    def test_high_school_normal(self):
        assert _advance_grade("高校1年") == ("高校2年", False)
        assert _advance_grade("高校2年") == ("高校3年", False)

    def test_high_school_graduation(self):
        _, graduated = _advance_grade("高校3年")
        assert graduated is True

    # 省略形（中◯年 / 高◯年）
    def test_short_prefix_middle_normal(self):
        assert _advance_grade("中1年") == ("中2年", False)
        assert _advance_grade("中2年") == ("中3年", False)

    def test_short_prefix_middle_graduation(self):
        _, graduated = _advance_grade("中3年")
        assert graduated is True

    def test_short_prefix_high_normal(self):
        assert _advance_grade("高1年") == ("高2年", False)

    def test_short_prefix_high_graduation(self):
        _, graduated = _advance_grade("高3年")
        assert graduated is True

    # 不明な形式はそのまま返す
    def test_unknown_format(self):
        grade, graduated = _advance_grade("不明")
        assert grade == "不明"
        assert graduated is False
