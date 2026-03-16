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
)

logger = logging.getLogger(__name__)

config = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
async_api_client = AsyncApiClient(config)
line_api = AsyncMessagingApi(async_api_client)

# コンテンツ取得のタイムアウト（秒）
CONTENT_DOWNLOAD_TIMEOUT = 30


async def reply_text(reply_token: str, text: str):
    """LINEにリプライメッセージを送信"""
    try:
        await line_api.reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
        )
    except Exception as e:
        logger.error("[LINE] Reply失敗: %s", e)


async def push_text(user_id: str, text: str):
    """LINEにプッシュメッセージを送信"""
    try:
        await line_api.push_message(
            PushMessageRequest(to=user_id, messages=[TextMessage(text=text)])
        )
    except Exception as e:
        logger.error("[LINE] Push失敗 (user=%s): %s", user_id, e)


async def download_content(message_id: str) -> bytes:
    """LINEサーバーからメッセージコンテンツ（画像/PDF）をダウンロード"""
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')}"}
    timeout = aiohttp.ClientTimeout(total=CONTENT_DOWNLOAD_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise Exception(f"LINEコンテンツ取得失敗: status={resp.status}")
            return await resp.read()
