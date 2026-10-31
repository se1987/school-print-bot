"""
LINE Messaging API クライアント
reply / push / コンテンツ取得を集約するラッパーモジュール
"""

import logging
import os

import aiohttp
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    QuickReply,
    QuickReplyItem,
    PostbackAction,
)

logger = logging.getLogger(__name__)

# コンテンツ取得のタイムアウト（秒）
CONTENT_DOWNLOAD_TIMEOUT = 30

# LINE のテキストメッセージは 5,000 文字（UTF-16 単位）まで。絵文字は 2 単位なので余裕を見る
LINE_TEXT_MAX_UNITS = 4800
# 1 回の reply / push で送れるメッセージ数
LINE_MESSAGES_PER_REQUEST = 5

# AsyncApiClient はイベントループが必要なため、遅延初期化する
_line_api: AsyncMessagingApi | None = None


def _get_line_api() -> AsyncMessagingApi:
    """LINE APIクライアントを遅延初期化して返す"""
    global _line_api
    if _line_api is None:
        token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        if not token:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN environment variable is required")
        config = Configuration(access_token=token)
        async_api_client = AsyncApiClient(config)
        _line_api = AsyncMessagingApi(async_api_client)
    return _line_api


async def reply_text(reply_token: str, text: str) -> None:
    """LINEにリプライメッセージを送信（長文は分割して複数メッセージにする）"""
    await _reply(reply_token, _text_messages(text))


async def push_text(user_id: str, text: str) -> None:
    """LINEにプッシュメッセージを送信（長文は分割して複数メッセージにする）"""
    await _push(user_id, _text_messages(text))


async def push_text_with_quick_reply(
    user_id: str, text: str, items: list[tuple[str, str]]
) -> None:
    """Quick Reply ボタン付きのプッシュメッセージを送信（ボタンは最後のメッセージに付く）

    Args:
        items: (ラベル, postbackデータ) のタプル一覧
    """
    await _push(user_id, _text_messages(text, quick_reply=_build_quick_reply(items)))


async def reply_text_with_quick_reply(
    reply_token: str, text: str, items: list[tuple[str, str]]
) -> None:
    """Quick Reply ボタン付きのリプライメッセージを送信（ボタンは最後のメッセージに付く）

    Args:
        items: (ラベル, postbackデータ) のタプル一覧
    """
    await _reply(reply_token, _text_messages(text, quick_reply=_build_quick_reply(items)))


async def _reply(reply_token: str, messages: list[TextMessage]) -> None:
    # reply token は1回しか使えないので、1リクエストに収まる分だけ送る。
    # 現状 reply で送るのは一覧・ヘルプ等で上限（5件 × 4,800 単位）に届くことはないが、
    # 万一超えたときも Quick Reply のボタンだけは残った最後のメッセージに付け替えて失わない
    if len(messages) > LINE_MESSAGES_PER_REQUEST:
        logger.warning(
            "[LINE] Reply が %d 件に分割され上限を超えたため、先頭 %d 件のみ送信します",
            len(messages), LINE_MESSAGES_PER_REQUEST,
        )
        quick_reply = messages[-1].quick_reply
        messages = messages[:LINE_MESSAGES_PER_REQUEST]
        if quick_reply is not None:
            messages[-1] = TextMessage(text=messages[-1].text, quick_reply=quick_reply)
    api = _get_line_api()
    try:
        await api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=messages))
    except Exception as e:
        logger.error("[LINE] Reply失敗: %s", e)
        raise


async def _push(user_id: str, messages: list[TextMessage]) -> None:
    api = _get_line_api()
    try:
        # push は複数回送れるので、5件ずつに分けて全部届ける
        for start in range(0, len(messages), LINE_MESSAGES_PER_REQUEST):
            batch = messages[start:start + LINE_MESSAGES_PER_REQUEST]
            await api.push_message(PushMessageRequest(to=user_id, messages=batch))
    except Exception as e:
        logger.error("[LINE] Push失敗: %s", e)
        raise


def _text_messages(text: str, quick_reply: QuickReply | None = None) -> list[TextMessage]:
    """本文を LINE の上限に収まるよう分割し、Quick Reply は最後のメッセージに付ける"""
    chunks = split_text(text)
    messages = [TextMessage(text=chunk) for chunk in chunks[:-1]]
    messages.append(TextMessage(text=chunks[-1], quick_reply=quick_reply))
    return messages


def utf16_len(text: str) -> int:
    """LINE が数える文字数（UTF-16 の単位数）。絵文字や一部の漢字は 2 と数える"""
    return len(text.encode("utf-16-le")) // 2


def split_text(text: str, limit: int = LINE_TEXT_MAX_UNITS) -> list[str]:
    """上限を超える本文を、行の切れ目で複数の塊に分ける。必ず1つ以上の塊を返す

    1行だけで上限を超える場合は、その行を文字単位で切る。
    """
    if utf16_len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        for piece in _split_long_line(line, limit):
            candidate = piece if not current else f"{current}\n{piece}"
            if utf16_len(candidate) <= limit:
                current = candidate
            else:
                chunks.append(current)
                current = piece
    chunks.append(current)
    return chunks


def _split_long_line(line: str, limit: int) -> list[str]:
    if utf16_len(line) <= limit:
        return [line]
    pieces: list[str] = []
    current = ""
    for ch in line:
        if utf16_len(current + ch) > limit:
            pieces.append(current)
            current = ch
        else:
            current += ch
    pieces.append(current)
    return pieces


def _build_quick_reply(items: list[tuple[str, str]]) -> QuickReply:
    return QuickReply(
        items=[
            QuickReplyItem(action=PostbackAction(label=label, data=data, display_text=label))
            for label, data in items
        ]
    )


async def download_content(message_id: str) -> bytes:
    """LINEサーバーからメッセージコンテンツ（画像/PDF）をダウンロード"""
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN environment variable is required")
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {token}"}
    timeout = aiohttp.ClientTimeout(total=CONTENT_DOWNLOAD_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise Exception(f"LINEコンテンツ取得失敗: status={resp.status}")
            return await resp.read()
