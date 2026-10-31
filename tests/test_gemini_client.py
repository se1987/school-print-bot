"""
gemini_client.py のテスト
- _parse_response: Gemini APIレスポンスのJSONパース
- _user_error_message: APIエラーのユーザー向けメッセージ変換
"""

import json

from google.genai import errors

from gemini_client import _parse_response, _user_error_message

VALID_RESPONSE = {
    "grade": "1年",
    "summary": "運動会のお知らせです。",
    "tasks": [
        {
            "title": "運動会",
            "description": "雨天中止の場合あり",
            "due_date": "2026-05-25",
            "task_type": "event",
            "target_grades": ["全学年"],
            "dismissal_times": [],
        }
    ],
    "notes": ["弁当持参"],
}


class TestParseResponse:
    def test_json_code_block(self):
        text = f"```json\n{json.dumps(VALID_RESPONSE, ensure_ascii=False)}\n```"
        result = _parse_response(text)
        assert result["summary"] == "運動会のお知らせです。"
        assert len(result["tasks"]) == 1
        assert result["grade"] == "1年"
        assert result["notes"] == ["弁当持参"]

    def test_raw_json(self):
        text = json.dumps(VALID_RESPONSE, ensure_ascii=False)
        result = _parse_response(text)
        assert result["tasks"][0]["title"] == "運動会"

    def test_missing_summary_defaults(self):
        text = json.dumps({"tasks": []}, ensure_ascii=False)
        result = _parse_response(text)
        assert "summary" in result

    def test_missing_tasks_defaults(self):
        text = json.dumps({"summary": "テスト"}, ensure_ascii=False)
        result = _parse_response(text)
        assert result["tasks"] == []

    def test_missing_notes_defaults(self):
        text = json.dumps({"summary": "テスト", "tasks": []}, ensure_ascii=False)
        result = _parse_response(text)
        assert result["notes"] == []

    def test_missing_grade_defaults_to_none(self):
        text = json.dumps({"summary": "テスト", "tasks": []}, ensure_ascii=False)
        result = _parse_response(text)
        assert result["grade"] is None

    def test_invalid_json_fallback(self):
        result = _parse_response("これはJSONではありません")
        assert result["tasks"] == []
        assert result["notes"] == []
        assert result["grade"] is None

    def test_empty_string_fallback(self):
        result = _parse_response("")
        assert "tasks" in result


class TestUserErrorMessage:
    def test_prepayment_depleted(self):
        e = errors.ClientError(402, {"error": {"code": 402, "message": "Your prepayment credits are depleted.", "status": "RESOURCE_EXHAUSTED"}})
        msg = _user_error_message(e)
        assert "残高が不足" in msg
        assert "管理者" in msg
        assert "ai.studio" not in msg

    def test_rate_limited(self):
        e = errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}})
        msg = _user_error_message(e)
        assert "上限" in msg
        assert "管理者" in msg

    def test_invalid_api_key(self):
        e = errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}})
        assert "認証" in _user_error_message(e)

    def test_server_error(self):
        e = errors.ServerError(503, {"error": {"code": 503, "message": "The model is overloaded.", "status": "UNAVAILABLE"}})
        assert "混み合って" in _user_error_message(e)

    def test_unknown_error_hides_details(self):
        msg = _user_error_message(RuntimeError("secret internal detail"))
        assert "secret" not in msg
        assert "もう一度" in msg


class TestNormalizeTask:
    """_parse_response がタスクの補助フィールド（原文・曜日）を揃えること"""

    def _parse_tasks(self, tasks_json: str):
        return _parse_response(f'{{"summary": "s", "tasks": {tasks_json}}}')["tasks"]

    def test_weekday_variants_are_normalized(self):
        tasks = self._parse_tasks(
            '[{"title": "a", "weekday_on_print": "(木)"},'
            ' {"title": "b", "weekday_on_print": "木曜日"},'
            ' {"title": "c", "weekday_on_print": "木"}]'
        )
        assert [t["weekday_on_print"] for t in tasks] == ["木", "木", "木"]

    def test_weekday_without_day_char_becomes_none(self):
        tasks = self._parse_tasks('[{"title": "a", "weekday_on_print": "不明"}, {"title": "b", "weekday_on_print": 3}]')
        assert [t["weekday_on_print"] for t in tasks] == [None, None]

    def test_date_like_value_is_not_mistaken_for_sunday(self):
        # "5日" の「日」を日曜と取り違えない。括弧付きなら日付が混ざっていても曜日を拾う
        tasks = self._parse_tasks(
            '[{"title": "a", "weekday_on_print": "5日"},'
            ' {"title": "b", "weekday_on_print": "5日(金)"},'
            ' {"title": "c", "weekday_on_print": "（日）"},'
            ' {"title": "d", "weekday_on_print": "木曜"}]'
        )
        assert [t["weekday_on_print"] for t in tasks] == [None, "金", "日", "木"]

    def test_missing_fields_default_to_none(self):
        [task] = self._parse_tasks('[{"title": "a"}]')
        assert task["source_text"] is None
        assert task["weekday_on_print"] is None

    def test_source_text_is_trimmed_and_truncated(self):
        long_text = "あ" * 100
        tasks = self._parse_tasks(f'[{{"title": "a", "source_text": "  5日(水)\\n 親子ふれあい活動 "}}, {{"title": "b", "source_text": "{long_text}"}}]')
        assert tasks[0]["source_text"] == "5日(水) 親子ふれあい活動"
        assert len(tasks[1]["source_text"]) == 60

    def test_non_string_source_text_becomes_none(self):
        [task] = self._parse_tasks('[{"title": "a", "source_text": 123}]')
        assert task["source_text"] is None

    def test_non_list_tasks_and_non_dict_items_are_dropped(self):
        # 文字列など想定外の形は空扱い。ただし欠落を知らせるため1件の除外として数える
        result = _parse_response('{"summary": "s", "tasks": "none"}')
        assert result["tasks"] == []
        assert result["dropped_task_count"] == 1
        # null と空配列は「予定なし」で、欠落ではない
        assert _parse_response('{"summary": "s", "tasks": null}')["dropped_task_count"] == 0
        assert _parse_response('{"summary": "s", "tasks": []}')["dropped_task_count"] == 0
        assert self._parse_tasks('[{"title": "a"}, "junk", 1]') == [
            {"title": "a", "source_text": None, "weekday_on_print": None}
        ]

    def test_tasks_without_string_title_are_dropped(self):
        # title が数値・null・空文字のタスクは表示も重複判定もできないので落とす
        tasks = self._parse_tasks('[{"title": 123}, {"title": null}, {"title": "  "}, {"title": "ok"}]')
        assert [t["title"] for t in tasks] == ["ok"]

    def test_single_task_dict_is_wrapped_in_list(self):
        # 1件だけのときに配列で包み忘れた応答でも、その予定を落とさない
        result = _parse_response('{"summary": "s", "tasks": {"title": "運動会"}}')
        assert [t["title"] for t in result["tasks"]] == ["運動会"]
        assert result["dropped_task_count"] == 0

    def test_dropped_task_count_is_reported(self):
        # 除外した件数は返信で保護者に知らせるために残す
        result = _parse_response('{"summary": "s", "tasks": [{"title": null}, "junk", {"title": "ok"}]}')
        assert result["dropped_task_count"] == 2
        assert _parse_response('{"summary": "s", "tasks": [{"title": "ok"}]}')["dropped_task_count"] == 0
        assert _parse_response('{"summary": "s"}')["dropped_task_count"] == 0
        assert _parse_response("not json")["dropped_task_count"] == 0
