"""
学校プリント管理Bot - メインエントリーポイント

FastAPI + LINE Messaging API + Gemini API
プリントのPDF/画像からタスクを自動抽出し、カレンダー登録・リマインドを行う
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException

from linebot.v3.webhook import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent

import database as db
import line_handler
from scheduler import start_scheduler

# 環境変数読み込み（.envファイル）
load_dotenv()


# ============================================================
# アプリケーション起動・終了処理
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時・終了時の処理"""
    # --- 起動時 ---
    db.init_db()
    start_scheduler()
    print("🚀 学校プリント管理Bot 起動完了！")
    yield
    # --- 終了時 ---
    print("👋 Bot を停止します")


app = FastAPI(
    title="学校プリント管理Bot",
    description="LINEにプリントを送ると、AIがタスクを抽出してくれるBot",
    version="0.1.0",
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
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
