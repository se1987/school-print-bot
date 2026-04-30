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
    """LINEにリプライメッセージを送信"""
    api = _get_line_api()
    try:
        await api.reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
        )
    except Exception as e:
        logger.error("[LINE] Reply失敗: %s", e)
        raise


async def push_text(user_id: str, text: str) -> None:
    """LINEにプッシュメッセージを送信"""
    api = _get_line_api()
    try:
        await api.push_message(
            PushMessageRequest(to=user_id, messages=[TextMessage(text=text)])
        )
    except Exception as e:
        logger.error("[LINE] Push失敗: %s", e)
        raise


async def push_text_with_quick_reply(
    user_id: str, text: str, items: list[tuple[str, str]]
) -> None:
    """Quick Reply ボタン付きのプッシュメッセージを送信

    Args:
        items: (ラベル, postbackデータ) のタプル一覧
    """
    api = _get_line_api()
    quick_reply = _build_quick_reply(items)
    try:
        await api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text, quick_reply=quick_reply)],
            )
        )
    except Exception as e:
        logger.error("[LINE] Push(QuickReply)失敗: %s", e)
        raise


async def reply_text_with_quick_reply(
    reply_token: str, text: str, items: list[tuple[str, str]]
) -> None:
    """Quick Reply ボタン付きのリプライメッセージを送信

    Args:
        items: (ラベル, postbackデータ) のタプル一覧
    """
    api = _get_line_api()
    quick_reply = _build_quick_reply(items)
    try:
        await api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text, quick_reply=quick_reply)],
            )
        )
    except Exception as e:
        logger.error("[LINE] Reply(QuickReply)失敗: %s", e)
        raise


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
