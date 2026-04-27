"""
LINEリッチメニュー登録スクリプト（ワンショット）

何をするか:
  1. PILで2x3レイアウトのメニュー画像を生成
  2. LINE Messaging APIでリッチメニューを作成・画像アップロード
  3. 全ユーザーのデフォルトメニューに設定

使い方:
  python scripts/setup_richmenu.py

事前準備:
  - .envにLINE_CHANNEL_ACCESS_TOKENが設定されていること
  - Pillow（requirements.txt に含まれる）

メニュー内容を変更したい場合は BUTTONS を編集して再実行してください。
同名の旧メニューは自動で削除されます。
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessageAction,
    MessagingApi,
    RichMenuArea,
    RichMenuBounds,
    RichMenuRequest,
    RichMenuSize,
)

load_dotenv()

# === メニュー定義 ===

WIDTH, HEIGHT = 2500, 843  # LINE推奨の小サイズ
ROWS, COLS = 2, 3

# (タイトル, サブテキスト, 送信メッセージ, 背景色)
BUTTONS = [
    ("タスク一覧", "未対応の予定を表示", "タスク一覧", (255, 233, 200)),
    ("子ども一覧", "登録済みの子を確認", "子ども一覧", (210, 235, 255)),
    ("カレンダー設定", "登録モードを切替", "カレンダー設定", (220, 240, 220)),
    ("通知テスト", "リマインドを即時送信", "通知テスト", (255, 220, 230)),
    ("全タスク", "期限切れも含めて表示", "全タスク", (235, 225, 250)),
    ("ヘルプ", "使い方を表示", "ヘルプ", (240, 240, 240)),
]

MENU_NAME = "school-print-bot-main"
CHAT_BAR_TEXT = "メニュー"
IMAGE_PATH = Path(__file__).parent / "richmenu.png"

# 日本語フォント候補（OS別、見つかった最初のものを使用）
JP_FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Osaka.ttf",
    # Linux (Noto / IPA / VL)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/vlgothic/VL-Gothic-Regular.ttf",
    # Windows
    "C:\\Windows\\Fonts\\YuGothB.ttc",
    "C:\\Windows\\Fonts\\YuGothM.ttc",
    "C:\\Windows\\Fonts\\meiryo.ttc",
    "C:\\Windows\\Fonts\\msgothic.ttc",
]


def find_jp_font(size: int) -> ImageFont.FreeTypeFont:
    for path in JP_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    print("❌ 日本語フォントが見つかりません。OSにフォントをインストールしてください。")
    sys.exit(1)


def _cell_geometry(index: int) -> tuple[int, int, int, int]:
    """セル(x, y, w, h) を返す。最終列・最終行は端まで引き伸ばす"""
    col = index % COLS
    row = index // COLS
    cell_w = WIDTH // COLS
    cell_h = HEIGHT // ROWS
    x = col * cell_w
    y = row * cell_h
    w = WIDTH - x if col == COLS - 1 else cell_w
    h = HEIGHT - y if row == ROWS - 1 else cell_h
    return x, y, w, h


def generate_image() -> Path:
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    title_font = find_jp_font(96)
    sub_font = find_jp_font(48)
    title_color = (40, 50, 70)
    sub_color = (100, 110, 130)
    border_color = (220, 225, 235)

    for i, (title, sub, _, bg) in enumerate(BUTTONS):
        x, y, w, h = _cell_geometry(i)
        # 背景塗り
        draw.rectangle([x, y, x + w, y + h], fill=bg)
        # 区切り線
        draw.rectangle([x, y, x + w, y + h], outline=border_color, width=4)

        # タイトル中央揃え（やや上寄り）
        bbox = draw.textbbox((0, 0), title, font=title_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        cx = x + w // 2
        cy = y + h // 2
        draw.text((cx - tw // 2, cy - th - 10), title, fill=title_color, font=title_font)

        # サブテキスト
        bbox = draw.textbbox((0, 0), sub, font=sub_font)
        sw = bbox[2] - bbox[0]
        draw.text((cx - sw // 2, cy + 30), sub, fill=sub_color, font=sub_font)

    img.save(IMAGE_PATH, "PNG")
    print(f"✅ メニュー画像を生成: {IMAGE_PATH}")
    return IMAGE_PATH


def build_areas() -> list[RichMenuArea]:
    areas = []
    for i, (_, _, msg, _) in enumerate(BUTTONS):
        x, y, w, h = _cell_geometry(i)
        areas.append(
            RichMenuArea(
                bounds=RichMenuBounds(x=x, y=y, width=w, height=h),
                action=MessageAction(label=msg[:20], text=msg),
            )
        )
    return areas


def cleanup_existing(api: MessagingApi) -> None:
    """同名の既存メニューを削除（重複防止）"""
    res = api.get_rich_menu_list()
    for menu in res.richmenus:
        if menu.name == MENU_NAME:
            print(f"🗑  既存メニューを削除: {menu.rich_menu_id}")
            api.delete_rich_menu(menu.rich_menu_id)


def upload_rich_menu_image(rich_menu_id: str, image_path: Path, token: str) -> None:
    """画像アップロードはSDK(v3.14.3)のバイナリ送信が一部環境で不具合のため、
    urllibで直接 LINE Data API に POST する"""
    url = f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content"
    with open(image_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/png",
            "Content-Length": str(len(data)),
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"画像アップロード失敗: status={resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"画像アップロード失敗: {e.code} {e.reason} / {body}") from e


def main() -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        print("❌ LINE_CHANNEL_ACCESS_TOKEN が未設定です（.env を確認してください）")
        sys.exit(1)

    image_path = generate_image()

    config = Configuration(access_token=token)
    with ApiClient(config) as client:
        api = MessagingApi(client)

        cleanup_existing(api)

        request = RichMenuRequest(
            size=RichMenuSize(width=WIDTH, height=HEIGHT),
            selected=True,
            name=MENU_NAME,
            chatBarText=CHAT_BAR_TEXT,
            areas=build_areas(),
        )
        result = api.create_rich_menu(request)
        rich_menu_id = result.rich_menu_id
        print(f"✅ リッチメニュー作成: {rich_menu_id}")

        upload_rich_menu_image(rich_menu_id, image_path, token)
        print("✅ 画像アップロード完了")

        api.set_default_rich_menu(rich_menu_id)
        print("✅ デフォルトメニューに設定")
        print()
        print("🎉 完了！LINEのトークを再度開くと下部にメニューが表示されます")
        print("   （表示されない場合はトークを一度閉じて開き直してください）")


if __name__ == "__main__":
    main()
