# 📚 学校プリント管理Bot

LINEにプリントを送ると、AIがタスクを自動抽出 → カレンダー登録 → リマインド通知

## 🏗️ アーキテクチャ

```text
マチコミ → [スクショ/PDF] → LINE Bot → FastAPI → Gemini API（解析）
                                          ↓
                                     SQLite（保存）
                                       ↓         ↓
                              LINE通知        Google Calendar
                            （リマインド）    → TimeTree連携
```

## ✨ 主な機能

- **AI解析**: プリントのPDF/画像からタスク・予定を自動抽出
- **学年別下校時刻**: 同じ日でも学年ごとに異なる下校時刻を正確に把握
- **子ども登録**: 兄弟の学年を登録すると、その子に関係ある情報だけを通知
- **リマインド**: 毎朝7時にLINEで翌日の予定を自動通知
- **自動進級**: 毎年4月1日に学年を自動更新（卒業学年は手動更新を通知）
- **全文検索**: 過去のプリントをキーワードで検索
- **Googleカレンダー連携**: プリント解析後に自動でカレンダーへ登録（オプション）

## 📱 使い方

| 操作 | 説明 |
| --- | --- |
| 📸 画像/PDF送信 | プリントを解析してタスク抽出 |
| 🔍 キーワード送信 | 過去のプリントを検索 |
| 📋 「タスク一覧」 | 未対応タスクを表示 |
| 👶 「子ども登録 たろう 1年」 | 子どもの学年を登録（中学1年・高校2年なども可） |
| 👨‍👩‍👧‍👦 「子ども一覧」 | 登録済みの子どもを確認 |
| ❓ 「ヘルプ」 | 使い方を表示 |

### 子ども登録の効果

登録前（学校だよりの卒業式の日）:

```text
📅 卒業証書授与式 (2026-03-17)
   ⏰ 1〜4年: 13:00
   ⏰ 5年: 13:30
```

登録後（「子ども登録 たろう 1年」の場合）:

```text
📅 卒業証書授与式 (2026-03-17)
   ⏰ たろう: 13:00
```

リマインドも同様に、たろうに関係ある予定だけが届きます。

## 🚀 セットアップ

### 必要なアカウント（すべて無料）

1. **LINE Developers** → Messaging APIチャネル作成
2. **Google AI Studio** → Gemini APIキー取得
3. **Railway** → ホスティング

### 手順

```bash
# 1. リポジトリをクローン
git clone <your-repo-url>
cd school-print-bot

# 2. 仮想環境＆パッケージ
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. 環境変数
cp .env.example .env
# .env を編集して各APIキーを設定

# 4. 起動
python src/main.py
```

### Docker で起動する場合

```bash
# .env を用意（DB_PATH を Docker 用に設定）
cp .env.example .env
# .env を編集して各APIキーを設定、DB_PATH=/app/data/school_prints.db に変更

# 起動
docker compose up -d

# ログ確認
docker compose logs -f

# 停止
docker compose down
```

> SQLite のデータは `./data/` にボリュームマウントされるため、コンテナを再起動してもデータは保持されます。

### Railway デプロイ

1. GitHubにpush
2. Railway → New Project → Deploy from GitHub
3. Variables に `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `GEMINI_API_KEY` を設定（`PORT` は Railway が自動注入）
4. Generate Domain → URLを取得
5. LINE Developers → Webhook URL に `https://your-app.up.railway.app/callback` を設定

### Google Calendar連携（オプション）

プリント解析時に自動でGoogleカレンダーへ予定を登録します。

#### 初回セットアップ

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
1. **Google Calendar API** を有効化
1. **OAuth 2.0 クライアントID** を作成（アプリケーション種別: デスクトップアプリ）
1. クライアントシークレットJSONをダウンロードし `scripts/credentials.json` として保存
1. 認証スクリプトを実行:

```bash
python scripts/authorize_google.py
```

1. 出力されたJSONを環境変数に設定:

```bash
# .env または Railway Variables
GOOGLE_CALENDAR_CREDENTIALS_JSON='{"token": "...", "refresh_token": "...", ...}'
```

> `GOOGLE_CALENDAR_CREDENTIALS_JSON` が未設定の場合、カレンダー連携はスキップされます。他の機能は正常に動作します。

#### TimeTree連携

Googleカレンダー → iPhoneの設定 → カレンダー → アカウント → Googleアカウントを追加するだけで自動同期され、TimeTreeにもインポートできます。

## 📁 ファイル構成

```text
school-print-bot/
├── src/
│   ├── main.py             # FastAPI エントリーポイント
│   ├── line_handler.py     # LINE Webhook + 子ども管理 + フォーマット
│   ├── gemini_client.py    # Gemini API（学年別下校時刻対応プロンプト）
│   ├── database.py         # SQLite + 学年マッチングロジック
│   └── scheduler.py        # パーソナライズ対応リマインドスケジューラー
├── docs/                   # 備忘録・設計資料（React コンポーネント）
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

## 🔜 今後の追加予定

- [ ] Google カレンダー連携（ボタンタップで登録）
- [ ] Rich Menu（メニューボタン）
- [ ] 個人懇談の地区別リマインド
