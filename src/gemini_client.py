"""
Gemini API クライアント
PDF/画像からテキスト抽出＋タスク・日付を構造化データとして返す
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime

from google import genai
from google.genai import errors, types

from dates import JST, WEEKDAYS_JA

logger = logging.getLogger(__name__)

# Gemini クライアント初期化
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 使用するモデル（無料枠あり・高速）
MODEL_NAME = "gemini-2.5-flash"

# タスク抽出用のシステムプロンプト
SYSTEM_PROMPT = """あなたは学校から配布されるプリントを解析する、保護者向けアシスタントです。

画像またはPDFが送られてきたら、以下を行ってください。

## 出力形式
以下のJSON形式 **のみ** を出力してください。JSON以外のテキストは一切出力しないでください。

```json
{{
  "grade": "プリントに記載の学年（例: '1年', '4年'）。学校だより等で全学年共通の場合は'全学年'",
  "summary": "プリントの内容を保護者向けに2〜3行で要約",
  "tasks": [
    {{
      "title": "タスクや予定の名前（短く・分かりやすく）",
      "description": "詳細な説明",
      "due_date": "YYYY-MM-DD形式の日付（不明な場合はnull）",
      "task_type": "event または task",
      "target_grades": ["対象学年のリスト。例: ['1年','2年','3年','4年','5年'] 。全学年なら['全学年']"],
      "dismissal_times": [
        {{"grades": "対象学年（例: '1〜4年'）", "time": "下校時刻（例: '13:00'）"}}
      ],
      "source_text": "日付と行事名の根拠になった、プリント上の原文の短い引用（例: '5日(水) 親子ふれあい活動'）。表なら「日」列と行事名のセルをそのまま。見つからなければnull",
      "weekday_on_print": "プリントにその予定の曜日が書かれていればその1文字（'月'〜'日'）。書かれていなければnull"
    }}
  ],
  "notes": ["タスクではないが保護者に有用な補足情報"]
}}
```

## 抽出ルール

### 予定（task_type: "event"）
- **下校時刻が通常と異なる日は最優先で抽出してください**
  - titleに下校時刻の変更があることを示す（例: "卒業式（学年別下校）"）
  - **学年ごとに下校時刻が異なる場合、dismissal_times に全学年分を列挙してください**
    - 例: 3/17 卒業式 → dismissal_times: [{{"grades":"1〜4年","time":"13:00"}},{{"grades":"5年","time":"13:30"}}]
  - これは保護者がお迎え時刻を判断するために非常に重要です
- **「給食なし」の日は、descriptionに必ず「給食なし」と明記してください**
- 始業式・修了式・卒業式など重要行事
- 授業参観、個人懇談、引き渡し訓練など保護者参加行事
- 個人懇談の場合、対象地区名もdescriptionに含めてください
- 春休み・夏休みなどの長期休暇の期間
- **4月の行事予定も含まれていれば、すべて抽出してください**（新年度の準備に必要）

### タスク（task_type: "task"）
- 「◯日までに△△を持たせてください」→ 持ち物タスク
- 「春休み中に点検・記名してください」→ 準備タスク
- 「ご家庭で保管してください」→ 保管タスク
- 「服装を確認してください」→ 確認タスク
- 教科書や道具の準備に関するもの

### 補足情報（notes）
- 「ノートは学校で用意します（購入不要）」のような、タスクではないが知っておくべき情報
- 制度変更のお知らせ（例:「令和8年度より個人懇談を実施」「月曜は5時間授業に変更」）

## 日付の推定
- 今日の日付は {today} です
- プリントに「令和◯年」とあればその年度で計算してください
- 曜日と日付の組み合わせからも年度を確認してください
- 「3月◯日」は今年度の3月、「4月◯日」は翌年度の4月と推定してください

## 予定表・カレンダー形式の読み取りルール
- 表（テーブル）形式の予定表では、**各行が1つの日に対応しています**。行の「日」列の数字がその日のイベントの日付です
- **異なる行（異なる日）のイベントを1つにまとめないでください**。例えば8日が「着任式・始業式」、9日が「入学式」なら、それぞれ別のイベントとして別の日付で抽出してください
- 表の「日」列の数字と、その月を組み合わせて正確な日付（YYYY-MM-DD）を生成してください
- 曜日列がある場合、日付と曜日が整合するか確認してください。不整合があれば曜日よりも日付番号を優先してください
- **1つの日のマスに行事が複数行書かれていることがあります**（例: 「4 水」の行に「クリーンタイム」と「親子ふれあい活動（2年）」）。**次の「日」の数字が現れるまでの行事は、すべて直前の日付に属します**。2行目以降の行事を次の日に割り当てないでください
- 日付と曜日だけで行事が空いている行（例: 「8 日」「9 月」）には、行事を割り当てないでください
- **曜日が書かれている予定は、必ず weekday_on_print にその曜日を入れてください**（受け取り側で日付と照合し、読み間違いを見つけるために使います）。曜日は **その行事が属する日付の行（複数行のマスでは「日」の数字がある行）** の曜日列から取ってください
- **各予定の source_text には、その日付を読み取った根拠の原文（「日」列の数字・曜日・行事名）をそのまま短く引用してください**
- **1つの行事を、読み取りのずれで別の日付にも重ねて出さないでください**（同じ行事は1回だけ）。個人懇談期間のように本当に複数日にわたる行事は、開始日を due_date にして description に期間（例: 「12月10日まで」）を明記してください

## 注意事項
- 保護者が「忘れると困る」情報を最優先で抽出してください
- 下校時刻の変更、給食の有無、持ち物の期限は特に見落とさないでください
- 学年別に下校時刻が異なる場合は **絶対に** dismissal_times を省略しないでください
- タスクが見つからない場合は tasks を空配列にしてください
"""


async def analyze_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """画像を解析してタスク・予定を抽出する"""
    today = datetime.now(JST).strftime("%Y年%m月%d日")
    prompt = SYSTEM_PROMPT.replace("{today}", today)

    try:
        # generate_content は同期(ブロッキング)呼び出しなので、別スレッドに逃がして
        # イベントループをブロックしないようにする（他リクエストの巻き添え499を防ぐ）
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text=prompt),
            ],
        )

        return _parse_response(response.text)

    except Exception as e:
        logger.error("[Gemini] 画像解析エラー: %s", e)
        return {
            "summary": "解析中にエラーが発生しました。",
            "tasks": [],
            "error": _user_error_message(e),
        }


async def analyze_pdf(pdf_bytes: bytes) -> dict:
    """PDFを解析してタスク・予定を抽出する"""
    today = datetime.now(JST).strftime("%Y年%m月%d日")
    prompt = SYSTEM_PROMPT.replace("{today}", today)

    try:
        # generate_content は同期(ブロッキング)呼び出しなので、別スレッドに逃がして
        # イベントループをブロックしないようにする（他リクエストの巻き添え499を防ぐ）
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                types.Part.from_text(text=prompt),
            ],
        )

        return _parse_response(response.text)

    except Exception as e:
        logger.error("[Gemini] PDF解析エラー: %s", e)
        return {
            "summary": "解析中にエラーが発生しました。",
            "tasks": [],
            "error": _user_error_message(e),
        }


def _user_error_message(e: Exception) -> str:
    """Gemini APIの例外をLINEユーザー向けの分かりやすいメッセージに変換する

    生のエラー内容（API応答の詳細）はログにのみ残し、ユーザーには見せない。
    """
    if isinstance(e, errors.APIError):
        if e.code == 402:
            return (
                "AIの利用料金の残高が不足しているため、解析できませんでした。\n"
                "Botの管理者に連絡してください。"
            )
        # 429 は短時間のレート制限だけでなく、日次クォータや費用上限の超過でも返る
        # （後者は待っても復旧しない）ため、続く場合は管理者への連絡も案内する
        if e.code == 429:
            return (
                "AIの利用回数が上限に達したため、解析できませんでした。\n"
                "しばらく時間をおいてから、もう一度送信してください。\n"
                "何度も続く場合はBotの管理者に連絡してください。"
            )
        # APIキーが無効な場合、Gemini は 401 ではなく 400 (API_KEY_INVALID) を返す
        if e.code in (401, 403) or (e.code == 400 and "API key" in (e.message or "")):
            return (
                "AIの認証に失敗したため、解析できませんでした。\n"
                "Botの管理者に連絡してください。"
            )
        if isinstance(e, errors.ServerError):
            return (
                "AIのサービスが一時的に混み合っています。\n"
                "しばらく時間をおいてから、もう一度送信してください。"
            )
    return "もう一度送信してみてください。"


def _parse_response(text: str) -> dict:
    """Geminiの応答テキストからJSONを抽出してパースする"""
    try:
        # ```json ... ``` で囲まれている場合に対応
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # そのままJSONとしてパース
            json_str = text.strip()

        result = json.loads(json_str)

        # バリデーション
        if "summary" not in result:
            result["summary"] = "要約を取得できませんでした。"
        tasks = result.get("tasks")
        tasks = tasks if isinstance(tasks, list) else []
        # title が文字列でないタスクは後段（表示・重複判定・DB保存）で扱えないので除外する。
        # 黙って落とすと保護者が欠落に気づけないので、件数だけ返信側に渡す（内容はログにも出さない）
        result["tasks"] = [
            _normalize_task(t)
            for t in tasks
            if isinstance(t, dict) and isinstance(t.get("title"), str) and t["title"].strip()
        ]
        result["dropped_task_count"] = len(tasks) - len(result["tasks"])
        if "notes" not in result:
            result["notes"] = []
        if "grade" not in result:
            result["grade"] = None

        return result

    except json.JSONDecodeError:
        logger.warning("[Gemini] JSONパース失敗。生テキスト: %s", text[:200])
        return {
            "summary": text[:200] if text else "解析結果を取得できませんでした。",
            "tasks": [],
            "notes": [],
            "grade": None,
            "dropped_task_count": 0,
        }


# 返信に引用する原文の長さの上限（LINE の1行に収まる程度）
SOURCE_TEXT_MAX_LENGTH = 60


def _normalize_task(task: dict) -> dict:
    """Gemini が返したタスクの補助フィールド（原文・曜日）を表示しやすい形に揃える"""
    source = task.get("source_text")
    if isinstance(source, str):
        source = " ".join(source.split())
        task["source_text"] = source[:SOURCE_TEXT_MAX_LENGTH] if source else None
    else:
        task["source_text"] = None

    task["weekday_on_print"] = _normalize_weekday(task.get("weekday_on_print"))
    return task


# "(木)" "（木）" のように括弧で囲まれた曜日
_WEEKDAY_IN_PARENS_RE = re.compile(r"[（(]([月火水木金土日])[)）]")
# "木" "木曜" "木曜日" のように曜日だけが書かれたもの
_WEEKDAY_ONLY_RE = re.compile(r"^([月火水木金土日])(?:曜日?)?$")


def _normalize_weekday(value) -> str | None:
    """"(木)" "木曜日" "木" などを "木" に揃える。曜日と読めなければ None

    "5日" のような日付を曜日の「日」と取り違えないよう、括弧内の1文字か、
    曜日だけの表記しか受け付けない。
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    m = _WEEKDAY_IN_PARENS_RE.search(value) or _WEEKDAY_ONLY_RE.match(value)
    return m.group(1) if m else None
