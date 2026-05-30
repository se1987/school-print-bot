"""
学校プリント管理Bot - メインエントリーポイント

FastAPI + LINE Messaging API + Gemini API
プリントのPDF/画像からタスクを自動抽出し、カレンダー登録・リマインドを行う
"""

import asyncio
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

# バックグラウンドタスクの参照を保持する（保持しないとGCで途中破棄される恐れがある）
_background_tasks: set[asyncio.Task] = set()


# ============================================================
# エンドポイント
# ============================================================

@app.get("/")
async def root():
    """ヘルスチェック用"""
    return {"status": "ok", "message": "学校プリント管理Bot is running!"}


async def _process_event(event):
    """1イベントを処理する。バックグラウンドタスクとして実行され、例外はログのみ"""
    try:
        if isinstance(event, MessageEvent):
            await line_handler.handle_message(event)
        elif isinstance(event, PostbackEvent):
            await line_handler.handle_postback(event)
    except Exception:
        logger.exception("[Callback] イベント処理中に未捕捉の例外が発生しました")


@app.post("/callback")
async def callback(request: Request):
    """
    LINE Webhook エンドポイント
    LINEからのイベント（メッセージ等）を受け取って処理する

    Gemini解析などの重い処理はバックグラウンドで実行し、LINEには即座に
    200を返す。これをしないと応答がLINEのタイムアウトを超え、接続が切られて
    499（Client Closed Request）が記録される＋Webhookが再送されてしまう。
    """
    # リクエストの署名検証
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 重い処理を待たずにバックグラウンドへ流し、即座に200を返す
    for event in events:
        task = asyncio.create_task(_process_event(event))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

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
