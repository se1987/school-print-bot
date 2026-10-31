"""
line_client.py のテスト
- split_text: LINE の文字数上限（UTF-16 単位）で行の切れ目に分割する
- _text_messages: Quick Reply は最後のメッセージにだけ付く
"""

import asyncio

import line_client
from line_client import (
    LINE_MESSAGES_PER_REQUEST,
    LINE_TEXT_MAX_UNITS,
    _build_quick_reply,
    _reply,
    _text_messages,
    split_text,
    utf16_len,
)


class TestUtf16Len:
    def test_ascii_and_kana(self):
        assert utf16_len("abc") == 3
        assert utf16_len("あいう") == 3

    def test_emoji_counts_as_two(self):
        # 📅 はサロゲートペアなので LINE は 2 文字と数える
        assert utf16_len("📅") == 2


class TestSplitText:
    def test_short_text_is_one_chunk(self):
        assert split_text("短い\nメッセージ") == ["短い\nメッセージ"]

    def test_splits_at_line_boundaries_within_limit(self):
        lines = [f"📅 予定{i:02d} の説明文です" for i in range(400)]
        text = "\n".join(lines)
        chunks = split_text(text)
        assert len(chunks) > 1
        assert all(utf16_len(c) <= LINE_TEXT_MAX_UNITS for c in chunks)
        # 行は壊れず、つなぎ直すと元に戻る
        assert "\n".join(chunks) == text

    def test_custom_limit(self):
        chunks = split_text("aaa\nbbb\nccc", limit=7)
        assert chunks == ["aaa\nbbb", "ccc"]

    def test_single_long_line_is_hard_split(self):
        chunks = split_text("あ" * 25, limit=10)
        assert chunks == ["あ" * 10, "あ" * 10, "あ" * 5]

    def test_emoji_heavy_line_respects_utf16_limit(self):
        chunks = split_text("📅" * 10, limit=6)  # 1絵文字 = 2単位 → 3個ずつ
        assert chunks == ["📅📅📅"] * 3 + ["📅"]


class TestTextMessages:
    def test_quick_reply_only_on_last_message(self):
        qr = _build_quick_reply([("登録", "action=cal_register&print_id=1")])
        text = "\n".join(["📅 予定の説明文です"] * 600)
        messages = _text_messages(text, quick_reply=qr)
        assert len(messages) > 1
        assert all(m.quick_reply is None for m in messages[:-1])
        assert messages[-1].quick_reply == qr

    def test_short_text_single_message_with_quick_reply(self):
        qr = _build_quick_reply([("登録", "x")])
        [message] = _text_messages("短い", quick_reply=qr)
        assert message.text == "短い"
        assert message.quick_reply == qr


class _FakeApi:
    def __init__(self):
        self.requests = []

    async def reply_message(self, request):
        self.requests.append(request)


class TestReplyOverflow:
    def test_keeps_quick_reply_when_truncating_to_five(self, monkeypatch):
        api = _FakeApi()
        monkeypatch.setattr(line_client, "_get_line_api", lambda: api)
        qr = _build_quick_reply([("登録", "x")])
        # 6件分の本文（各塊が上限ぎりぎり）に Quick Reply を付ける
        text = "\n".join(["あ" * (LINE_TEXT_MAX_UNITS - 1)] * 6)
        messages = _text_messages(text, quick_reply=qr)
        assert len(messages) == 6

        asyncio.run(_reply("token", messages))

        [request] = api.requests
        sent = request.messages
        assert len(sent) == LINE_MESSAGES_PER_REQUEST
        assert all(m.quick_reply is None for m in sent[:-1])
        assert sent[-1].quick_reply == qr
        assert sent[-1].text == messages[4].text
