"""
Gemini API クライアント
PDF/画像からテキスト抽出＋タスク・日付を構造化データとして返す
"""

import json
import os
import re
from datetime import datetime

from google import genai
from google.genai import types

# Gemini クライアント初期化
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 使用するモデル（無料枠あり・高速）
MODEL_NAME = "gemini-2.0-flash"

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
      ]
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

## 注意事項
- 保護者が「忘れると困る」情報を最優先で抽出してください
- 下校時刻の変更、給食の有無、持ち物の期限は特に見落とさないでください
- 学年別に下校時刻が異なる場合は **絶対に** dismissal_times を省略しないでください
- タスクが見つからない場合は tasks を空配列にしてください
"""


async def analyze_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    画像を解析してタスク・予定を抽出する

    Args:
        image_bytes: 画像のバイトデータ
        mime_type: 画像のMIMEタイプ

    Returns:
        {"summary": "...", "tasks": [...]} 形式の辞書
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    prompt = SYSTEM_PROMPT.replace("{today}", today)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text=prompt),
            ],
        )

        return _parse_response(response.text)

    except Exception as e:
        print(f"❌ Gemini API エラー: {e}")
        return {
            "summary": "解析中にエラーが発生しました。",
            "tasks": [],
            "error": str(e),
        }


async def analyze_pdf(pdf_bytes: bytes) -> dict:
    """
    PDFを解析してタスク・予定を抽出する

    Args:
        pdf_bytes: PDFのバイトデータ

    Returns:
        {"summary": "...", "tasks": [...]} 形式の辞書
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    prompt = SYSTEM_PROMPT.replace("{today}", today)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                types.Part.from_text(text=prompt),
            ],
        )

        return _parse_response(response.text)

    except Exception as e:
        print(f"❌ Gemini API エラー: {e}")
        return {
            "summary": "解析中にエラーが発生しました。",
            "tasks": [],
            "error": str(e),
        }


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
        if "tasks" not in result:
            result["tasks"] = []
        if "notes" not in result:
            result["notes"] = []
        if "grade" not in result:
            result["grade"] = None

        return result

    except json.JSONDecodeError:
        print(f"⚠️ JSONパース失敗。生テキスト: {text[:200]}")
        return {
            "summary": text[:200] if text else "解析結果を取得できませんでした。",
            "tasks": [],
            "notes": [],
            "grade": None,
        }
