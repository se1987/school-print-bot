"""
gemini_client.py のテスト
- _parse_response: Gemini APIレスポンスのJSONパース
"""

import json

from gemini_client import _parse_response

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
