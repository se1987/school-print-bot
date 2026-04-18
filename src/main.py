"""
学校プリント管理Bot - メインエントリーポイント

FastAPI + LINE Messaging API + Gemini API
プリントのPDF/画像からタスクを自動抽出し、カレンダー登録・リマインドを行う
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# 環境変数読み込み（.envファイル）
load_dotenv()

# --- ログ設定 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ============================================================
# 起動時の設定バリデーション
# ============================================================

REQUIRED_ENV_VARS = [
    "LINE_CHANNEL_SECRET",
    "LINE_CHANNEL_ACCESS_TOKEN",
    "GEMINI_API_KEY",
]

OPTIONAL_ENV_VARS = [
    "GOOGLE_CALENDAR_CREDENTIALS_JSON",
    "GOOGLE_CALENDAR_ID",
    "DB_PATH",
]


def validate_env():
    """必須環境変数の存在チェック。不足時はエラー終了"""
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        logger.critical("必須環境変数が未設定です: %s", ", ".join(missing))
        sys.exit(1)

    for v in OPTIONAL_ENV_VARS:
        if os.getenv(v):
            logger.info("  ✓ %s: 設定済み", v)
        else:
            logger.info("  - %s: 未設定（オプション）", v)


validate_env()

# --- 以下、環境変数が確定してからインポート ---
from fastapi import FastAPI, Request, HTTPException  # noqa: E402

from linebot.v3.webhook import WebhookParser  # noqa: E402
from linebot.v3.exceptions import InvalidSignatureError  # noqa: E402
from linebot.v3.webhooks import MessageEvent, PostbackEvent  # noqa: E402

import database as db  # noqa: E402
import line_handler  # noqa: E402
from scheduler import start_scheduler  # noqa: E402


# ============================================================
# アプリケーション起動・終了処理
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時・終了時の処理"""
    # --- 起動時 ---
    db.init_db()
    start_scheduler()
    logger.info("学校プリント管理Bot 起動完了")
    yield
    # --- 終了時 ---
    logger.info("Bot を停止します")


app = FastAPI(
    title="学校プリント管理Bot",
    description="LINEにプリントを送ると、AIがタスクを抽出してくれるBot",
    version="0.2.0",
    lifespan=lifespan,
)

# LINE Webhook パーサー
parser = WebhookParser(os.getenv("LINE_CHANNEL_SECRET"))


# ============================================================
# エンドポイント
# ============================================================

@app.get("/")
async def root():
    """ヘルスチェック用"""
    return {"status": "ok", "message": "学校プリント管理Bot is running!"}


@app.post("/callback")
async def callback(request: Request):
    """
    LINE Webhook エンドポイント
    LINEからのイベント（メッセージ等）を受け取って処理する
    """
    # リクエストの署名検証
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # イベント処理（非同期）
    for event in events:
        if isinstance(event, MessageEvent):
            await line_handler.handle_message(event)
        elif isinstance(event, PostbackEvent):
            await line_handler.handle_postback(event)

    return {"status": "ok"}


@app.get("/health")
async def health():
    """Railway のヘルスチェック用"""
    return {"status": "healthy"}


# ============================================================
# ローカル実行用
# ============================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, app_dir="src")
