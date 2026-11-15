# 運用メモ（operations.md）

本番運用（Cloud Run + PostgreSQL、または Railway）で踏んだ「消えやすい設定」の記録。
再デプロイ・環境再構築で同じ罠を踏み直さないための、未来の自分向けメモ。
コードは Git が覚えているが、コンソール上の設定は誰も覚えていないので、ここに残す。

## 1. データの永続化

コンテナのファイルシステムは揮発性で、再デプロイ（Cloud Run ではスリープ復帰のたび）に消える。
データは必ずコンテナの外に置く。置き場所は構成によって違う。

### Cloud Run 構成: PostgreSQL（`DATABASE_URL`）

- 確認: 起動ログに「データベース初期化完了（PostgreSQL）」と出ているか。「（SQLite）」と出ていたら `DATABASE_URL` が渡っておらず、**揮発性のファイルに書いている**（次のスリープで消える）
- Supabase を使う場合:
  - 接続文字列は「Transaction pooler」（ポート 6543）のものを使う。Direct connection は IPv6 のみで Cloud Run から届かない
  - 無料プランは 1 週間ほど利用が無いとプロジェクトが一時停止する。毎朝のリマインドが DB を読むので通常は止まらないが、Cloud Scheduler を止めると一緒に止まりうる
  - 他のアプリと同じプロジェクトに同居させる場合は、専用スキーマ + 専用ロールに分ける（§5.1 の SQL）。`DB_SCHEMA` を付け忘れると既定スキーマ（public）にテーブルを作ろうとする

### Railway 構成: Volume 上の SQLite（`DB_PATH`）

- 症状: 再デプロイのたびに SQLite のデータ（解析済みプリント・タスク・子ども登録）が消える
- 対処: DB ファイルの置き場所（`DB_PATH` のディレクトリ）に Volume をマウントする
- 確認: redeploy 後に DB の中身が残っているか（**設定の有無ではなく、データの実在を確認する**）
- 注意: Volume はマウントパス配下しか守らない。`DB_PATH` とマウントパスがズレていると、Volume が存在していても揮発性側に書き続ける（一度これで再消失した）

## 2. Google OAuth の公開（本番化）

- 症状: 約7日で認証が切れ、カレンダー登録が止まる
- 原因: 同意画面が「テスト」だとリフレッシュトークンが7日で失効する
- 対処: 同意画面を「公開（本番）」に変更済み
- 確認: 8日以上経過後もカレンダー登録が動くか
- 再認証手順: `python scripts/authorize_google.py` → 出力 JSON を本番環境の `GOOGLE_CALENDAR_CREDENTIALS_JSON` に再設定（Cloud Run: Secret Manager に新しいバージョンを追加して再デプロイ / Railway: Variables）
- 補足: 月1運用ではトークンが「使うたびに必ず失効している」形で現れる（7日 < 利用間隔のため）。エラーはログ上「PDF 処理エラー」の名前で出ることがあった（`RefreshError` の突き抜け。コード側は捕捉して縮退運転するよう修正済み）

## 3. Gemini API の課金設定

- 症状/懸念: 無料枠のレート制限に加え、入力データが製品改善に利用されうる規約上の扱い
- 対処: 課金を有効化し有料ティアで運用中（有料ティアではプロンプト・応答が製品改善に使われない）
- 確認: 課金アカウントが紐づいているか（AI Studio / GCP の Billing ページ）
- 補足: 規約・無料枠の条件は変わりやすいので、参照時は公式ドキュメント（利用規約 / Pricing / Data governance）の最新版を確認する

## 4. 秘密情報のローテーション手順（漏えい疑い時）

ホスティング側のセキュリティインシデント（例: 2026-10 の Railway の環境変数まわりの侵害公表）のように、
自分に非がなくても秘密情報を作り直す場面は起こりうる。慌てないよう「どの変数を・どの順で・どこで作り直すか」を残しておく。
作業はほぼコンソール操作で、コードは変わらない。

**このリポジトリは公開されている。** ここに書いてよいのは手順だけで、アカウント名・ワークスペース名・キーの一部・
通知メールの文面・「いつ何が漏れた可能性があるか」といった個別事情は書かない（攻撃者への手がかりになる）。

### 対象の変数と漏れた場合の影響

| 変数 | 漏れた場合にできること | 優先度 |
|---|---|---|
| `GEMINI_API_KEY` | こちらの課金で Gemini を使われる | 高（AI キーは攻撃者の主目的） |
| `LINE_CHANNEL_ACCESS_TOKEN` | Bot として利用者の LINE に任意のメッセージを送れる | 高 |
| `LINE_CHANNEL_SECRET` | 偽の Webhook を `/callback` に送って Bot を操作できる | 中 |
| `GOOGLE_CALENDAR_CREDENTIALS_JSON` | refresh_token と client_secret を含む。カレンダーの予定を読み書きできる（スコープは `calendar.events` のみ） | 中 |
| `DATABASE_URL`（Cloud Run 構成） | DB のパスワードを含む。プリントの内容・子どもの名前と学年・LINE ユーザー ID を読み書きできる | 高 |
| `CRON_SECRET`（Cloud Run 構成） | `/cron/*` を叩いてリマインドを前倒しで送らせることができる（送信済みは再送されず、進級は 4 月に年 1 回だけ） | 低 |

`GOOGLE_CALENDAR_ID` / `DB_PATH` / `DB_SCHEMA` / `SCHEDULER_MODE` / `PORT` は秘密ではないので対象外。
Railway 構成の SQLite の中身は環境変数ではなく Volume 上にあるため、環境変数の漏えいとは別の話。

### 手順（この順番で）

0. **通知メールの真偽を確認する**: メール内のリンクは踏まず、ブラウザから直接ホスティング側（Google Cloud / Railway）にログインしてお知らせ・公式ブログで同じ内容を確認する
1. **Gemini**: Google AI Studio で新しいキーを発行 → 古いキーを削除。AI Studio の使用量と GCP Billing に見覚えのない利用がないか確認する
2. **LINE**: LINE Developers コンソール → 該当チャネル
   - 「Messaging API 設定」でチャネルアクセストークンを再発行
   - 「チャネル基本設定」でチャネルシークレットを再発行
   - 再発行した瞬間に古い値は無効になり、手順 5 まで Bot は停止する（家族向けなので短時間の停止は許容）
3. **Google OAuth**:
   - Google アカウント → セキュリティ → 「サードパーティのアプリとサービス」から本アプリのアクセスを削除（盗まれた refresh_token が即座に無効になる）
   - GCP Console → 認証情報 → OAuth クライアントで「シークレットをリセット」→ 新しい `credentials.json` を `scripts/` に置く
   - `python scripts/authorize_google.py` を実行 → 出力 JSON を控える
   - Google カレンダーに見覚えのない予定の追加・削除がないか確認する
4. **DB と cron（Cloud Run 構成のみ）**:
   - DB ロールのパスワードを変更（`ALTER ROLE school_print_bot PASSWORD '...'`）→ 新しい `DATABASE_URL` を控える
   - `openssl rand -hex 32` で新しい `CRON_SECRET` を作る
5. **ホスティング側に投入**:
   - Cloud Run: Secret Manager の各シークレットに新しいバージョンを追加 → 古いバージョンを無効化・破棄（無料枠は有効なバージョン 6 個まで）→ 再デプロイ → Cloud Scheduler の 2 ジョブの `X-Cron-Secret` ヘッダーも更新
   - Railway: Variables の 4 変数を新しい値に差し替え → Redeploy
6. **動作確認**: LINE で `通知テスト` → リマインダーが返る / 画像を 1 枚送信 → Gemini 解析とカレンダー登録が通る
7. **アカウント周辺**: ホスティング側アカウントのパスワード変更と 2 段階認証。GitHub の Settings → Security log / Applications に見覚えのないアクセス・連携がないか確認（GitHub 連携でデプロイしている場合）

### 注意

- 順番の意図: 課金被害が出る Gemini を最初に止める。LINE と Google は「古い値の無効化」と「新しい値の投入」が同時にできないので、停止時間を短くするため手順 1〜4 で新しい値を揃えてから手順 5 でまとめて投入する
- Google OAuth は手順 3 の 1 つ目（アクセス削除）だけでも refresh_token は無効になるが、client_secret も JSON に含まれているのでリセットまでやる
- ローテーション後に `RefreshError` が出る場合は、古い JSON が本番環境に残っている（差し替え漏れ）か、同意画面が「テスト」に戻っている（§2 参照）のどちらか

## 5. Cloud Run 構成のセットアップ（Railway からの移行）

無料枠で動かすための構成。常時起動の Railway と違い「普段は寝ていて、呼ばれたら起きる」ので、
データ（→ PostgreSQL）と目覚まし（→ Cloud Scheduler）をコンテナの外に出している。

```
LINE ──────────────── Webhook ──▶ Cloud Run ──▶ PostgreSQL（Supabase など）
Cloud Scheduler ── 7:00 /cron/* ──▶ （普段は 0 台）
```

`<...>` は自分の値に置き換える。リージョンは東京（`asia-northeast1`）の例。
無料枠の条件は変わるので、作業前に各サービスの料金ページを確認し、**予算アラート（例: 月 100 円）を必ず設定する**。

### 5.1 PostgreSQL を用意する

既存の Supabase プロジェクトに同居させる場合、SQL Editor で専用のスキーマとロールを作る（他のアプリのテーブルと権限を分ける）。

```sql
CREATE SCHEMA school_print_bot;
CREATE ROLE school_print_bot LOGIN PASSWORD '<強いパスワード>';
GRANT USAGE, CREATE ON SCHEMA school_print_bot TO school_print_bot;
```

- `DATABASE_URL`: ダッシュボードの Connect →「Transaction pooler」の文字列をコピーし、ユーザー名を `school_print_bot.<プロジェクトref>`、パスワードを上で決めたものに置き換える
- `DB_SCHEMA`: `school_print_bot`
- テーブルはアプリの初回起動時に自動で作られる

### 5.2 秘密情報を Secret Manager に入れる

```bash
gcloud config set project <プロジェクトID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com

# 値は対話入力する（コマンド履歴に残さない）。6 個とも同じ要領で作る
for name in LINE_CHANNEL_SECRET LINE_CHANNEL_ACCESS_TOKEN GEMINI_API_KEY \
            GOOGLE_CALENDAR_CREDENTIALS_JSON DATABASE_URL CRON_SECRET; do
  read -rsp "$name: " value && echo
  printf '%s' "$value" | gcloud secrets create "$name" --data-file=-
done
```

- `CRON_SECRET` は `openssl rand -hex 32` で作った値を入れる
- 無料枠は「有効なシークレットバージョン 6 個」まで。ちょうど 6 個なので、更新時は古いバージョンを破棄する
- Cloud Run の実行サービスアカウントに「Secret Manager のシークレット アクセサー」ロールが必要（初回デプロイ時に gcloud が付与を提案する）

### 5.3 デプロイする

```bash
gcloud run deploy school-print-bot --source . --region asia-northeast1 \
  --allow-unauthenticated --no-cpu-throttling \
  --min-instances 0 --max-instances 1 --cpu 1 --memory 512Mi \
  --set-env-vars SCHEDULER_MODE=external,DB_SCHEMA=school_print_bot,GOOGLE_CALENDAR_ID=primary \
  --set-secrets LINE_CHANNEL_SECRET=LINE_CHANNEL_SECRET:latest,LINE_CHANNEL_ACCESS_TOKEN=LINE_CHANNEL_ACCESS_TOKEN:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,GOOGLE_CALENDAR_CREDENTIALS_JSON=GOOGLE_CALENDAR_CREDENTIALS_JSON:latest,DATABASE_URL=DATABASE_URL:latest,CRON_SECRET=CRON_SECRET:latest
```

消えると困るオプション（コンソールで編集したときに外れやすい）:

- `--no-cpu-throttling`（インスタンスベースの課金）: Webhook は LINE に 200 を返してから解析するので、既定の「リクエスト中だけ CPU を割り当てる」設定だと**返信が来ない／極端に遅くなる**。その代わりインスタンスが起きている間（最後のリクエストのあとしばらく）は課金対象になるので、無料枠の消費は Cloud Run の指標で時々確認する
- `--max-instances 1`: 課金の上限を抑える
- `--allow-unauthenticated`: LINE と Cloud Scheduler が外から呼べるようにする。認証は `/callback` は LINE 署名、`/cron/*` は `X-Cron-Secret` で行っている
- `:latest` で渡したシークレットは**デプロイ時点の値で固定される**。シークレットを更新したら再デプロイが必要

確認: `https://<Cloud Run の URL>/health` が `{"status": "healthy"}` を返し、ログに「データベース初期化完了（PostgreSQL）」と出ること。

### 5.4 Cloud Scheduler に目覚ましを登録する

```bash
URL=https://<Cloud Run の URL>
read -rsp "CRON_SECRET: " CRON_SECRET && echo

gcloud scheduler jobs create http school-print-bot-daily-reminder --location asia-northeast1 \
  --schedule "0 7 * * *" --time-zone "Asia/Tokyo" --http-method POST \
  --uri "$URL/cron/daily-reminder" --headers "X-Cron-Secret=$CRON_SECRET" --attempt-deadline 180s

gcloud scheduler jobs create http school-print-bot-advance-grades --location asia-northeast1 \
  --schedule "0 9 1 4 *" --time-zone "Asia/Tokyo" --http-method POST \
  --uri "$URL/cron/advance-grades" --headers "X-Cron-Secret=$CRON_SECRET" --attempt-deadline 180s
```

- タイムゾーンを `Asia/Tokyo` にし忘れると UTC の 7:00（日本の 16:00）に届く
- 確認: コンソールで daily-reminder を「強制実行」→ 結果が成功になり、対象タスクがあれば LINE に届く。advance-grades は 4 月以外に強制実行しても進級しない（`"status": "skipped"` が返る）
- 無料枠はジョブ 3 個まで。一時停止中のジョブも数に入る

### 5.5 Railway から切り替える

1. **データを移す（任意）**: Railway の Volume から `school_prints.db` を取り出し、手元で実行する

   ```bash
   DATABASE_URL='<接続文字列>' DB_SCHEMA=school_print_bot \
     python scripts/migrate_sqlite_to_postgres.py school_prints.db
   ```

   コピー先が空のときだけ動く。子ども登録だけなら LINE から `子ども登録` をやり直すほうが早い
2. **Webhook を切り替える**: LINE Developers → Messaging API 設定 → Webhook URL を `https://<Cloud Run の URL>/callback` に変更 →「検証」
3. **動作確認**: LINE で `通知テスト` を送る → 画像を 1 枚送信（§4 の動作確認と同じ）
4. **Railway 側のリマインドを止める**: 両方が動いている間は**朝のリマインドが二重に届く**（DB が別なので互いの送信済みを知らない）。切り替えた日のうちに Railway のサービスを停止する
5. **戻したくなったら**: Railway のサービスを再開し、Webhook URL を戻し、Cloud Scheduler の 2 ジョブを一時停止する。切り替え後に Cloud Run 側で増えたデータは Railway 側には無い点に注意
6. しばらく安定して動いたら、Railway のサービスと環境変数を削除し、プランを解約する（サービスを止めただけでは月額は止まらない）

## 付記: LINE Webhook の 499

設定ではなくコード側の教訓だが、関連するので1行だけ。
Webhook が Gemini 解析の完了を待ってから 200 を返すと、LINE のタイムアウトで接続が切られ 499 になる（PDF は解析が重く発生しやすい）。即時 200 応答＋バックグラウンド処理化で修正済み。
