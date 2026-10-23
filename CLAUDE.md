# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

学校プリント管理Bot — A LINE messaging bot for Japanese parents to manage school documents. Parents send screenshots/PDFs of school printouts via LINE, and the bot uses Gemini AI to extract tasks, events, and deadlines, registers them to Google Calendar, then sends personalized daily reminders filtered by each child's grade.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run tests (same as CI: .github/workflows/test.yml, Python 3.12)
pytest tests/ -v

# Run locally (with hot reload)
python src/main.py

# Production (Railway)
uvicorn main:app --host 0.0.0.0 --port $PORT --app-dir src

# One-off scripts
python scripts/authorize_google.py   # Google OAuth → prints JSON for GOOGLE_CALENDAR_CREDENTIALS_JSON
python scripts/setup_richmenu.py     # Create/upload LINE rich menu and set it as default
```

No lint command is configured. Docker (`Dockerfile`, `docker-compose.yml`) is also available.

Dependency updates come from Dependabot (`.github/dependabot.yml`): pip and GitHub Actions are checked every Monday 04:00 JST, with a 3-day cooldown after each release. Minor/patch updates arrive grouped in one PR; majors arrive as separate PRs. Nothing is auto-merged — PRs are reviewed (CI green + `pytest`) before merging.

PR reviews also come from CodeRabbit, configured in `.coderabbit.yaml` (Japanese comments, `chill` profile, path-specific instructions, Ruff and secret scanning enabled). The repository is public: never commit credentials, LINE user IDs, real names, or incident-specific details; `docs/operations.md` holds runbooks only.

## Environment Variables

Copy `.env.example` and fill in:
- `LINE_CHANNEL_SECRET` — LINE webhook signature verification (required)
- `LINE_CHANNEL_ACCESS_TOKEN` — LINE API authentication (required)
- `GEMINI_API_KEY` — Google Gemini API key (required)
- `GOOGLE_CALENDAR_CREDENTIALS_JSON` — OAuth credentials JSON from `scripts/authorize_google.py` (optional; if unset, calendar integration is skipped and everything else works)
- `GOOGLE_CALENDAR_ID` — Target calendar (optional; default `primary`)
- `DB_PATH` — SQLite file path (optional; default `school_prints.db`, `/app/data/school_prints.db` recommended for Docker)
- `PORT` — Server port (default: 8000)

`main.py:validate_env` exits on startup if a required variable is missing.

## Architecture

```
LINE Webhook → FastAPI (main.py) ── returns 200 immediately, processes in background
                  ↓
          line_handler.py       ← routes messages/postbacks, formats responses
         /      |       |       \
gemini_client.py  database.py  google_calendar.py  line_client.py
(AI analysis)    (SQLite)      (Calendar REST API) (LINE API wrapper)

scheduler.py — APScheduler jobs (daily reminders, April grade advance)
```

**Module responsibilities:**
- `main.py` — FastAPI app, env validation, webhook endpoint (`/callback`), lifespan (inits DB, starts scheduler). Webhook events run as background tasks so LINE gets a 200 before Gemini analysis finishes (avoids 499 timeouts on heavy PDFs).
- `line_handler.py` — Message routing (image/PDF/text), postback handling (Quick Reply buttons), child management commands, calendar mode settings, response formatting
- `line_client.py` — reply / push / Quick Reply / content download wrappers around LINE Messaging API (lazy-initialized async client)
- `gemini_client.py` — Gemini 2.5 Flash calls; extracts grade, tasks, events, notes as structured JSON
- `google_calendar.py` — Registers tasks via Google Calendar API v3 (`googleapiclient`), with duplicate-event check. `RefreshError` (e.g. `invalid_grant`) is caught both in `_get_credentials` and around the API calls in `register_task_to_calendar` — the stored credentials JSON has no `expiry`, so in practice the refresh happens on a 401 inside `.execute()` — so calendar failures don't abort PDF analysis. All-day events use an exclusive `end.date` (due_date + 1 day).
- `database.py` — SQLite CRUD; grade-matching logic for filtering tasks by child's grade; per-user calendar mode
- `scheduler.py` — APScheduler cron jobs pinned to JST (independent of host time zone): 7:00 AM JST daily reminders per child; April 1 9:00 AM JST automatic grade advance

## Database Schema

Four SQLite tables (created in `database.py:init_db`; new columns are added via `ALTER TABLE` migrations there):
- **prints** — Raw document records (user_id, grade, original_text, summary)
- **tasks** — Extracted items (print_id, title, description, due_date, task_type, target_grades JSON, dismissal_times JSON, is_registered_to_calendar, calendar_event_id, is_reminded)
- **children** — Registered child profiles (user_id, name, grade)
- **user_settings** — Per-user settings (user_id, calendar_mode: `auto` / `off` / `ask`, default `auto`)

`target_grades` and `dismissal_times` are stored as JSON strings to support multi-grade documents.

## Key Domain Logic

**Grade-specific dismissal times** is the core differentiator. A single school print may list different dismissal times per grade (e.g., 1〜4年 at 13:00, 5年 at 13:30). The bot must:
1. Parse range notation (`1〜4年`, `1-4年`, `1～4年`) in `database.py:is_task_relevant_to_child`
2. Show only the relevant dismissal time for each registered child via `get_dismissal_time_for_child`

**Calendar modes** (`user_settings.calendar_mode`):
- `auto` — register tasks to Google Calendar right after analysis
- `off` — never register
- `ask` — show Quick Reply buttons (`cal_register` / `cal_skip` postbacks) after each analysis

Re-uploading a print whose tasks already exist re-registers tasks that were not yet on the calendar (e.g., after the mode was changed).

**LINE user commands:**
| Input | Action |
|-------|--------|
| Image/PDF | Analyze with Gemini, store tasks, register to calendar per mode |
| Keyword text | Full-text search of past prints |
| `タスク一覧` | List pending tasks |
| `全タスク` | List all tasks including overdue |
| `通知テスト` | Run the reminder immediately |
| `子ども登録 NAME GRADE` | Register child (e.g., `子ども登録 たろう 1年`) |
| `子ども一覧` | List children |
| `子ども削除 NAME` | Remove child |
| `カレンダー設定` | Show/switch calendar mode via buttons |
| `ヘルプ` | Show help |

## Google OAuth Notes

- The calendar integration calls the Google Calendar REST API directly from deterministic Python code (scope: `calendar.events`). Gemini only extracts data; it does not call Google APIs. The app does not use Google Workspace MCP. Not using MCP alone does not settle whether Google classifies the OAuth client as agentic, though — in `auto` mode Gemini's output decides which events are created on the user's behalf. When Google changes its agentic-client rules (e.g. the `is_agentic` setting), assess the client against Google's current criteria in the Cloud Console docs rather than relying on this note.
- The OAuth consent screen must be in production ("公開") — in testing mode refresh tokens expire after 7 days.
- Re-auth: run `scripts/authorize_google.py` and replace `GOOGLE_CALENDAR_CREDENTIALS_JSON` in Railway.

## Deployment (Railway)

1. Push to GitHub
2. Set env vars in Railway dashboard
3. Set LINE webhook URL to `https://your-app.up.railway.app/callback`
4. Mount a Railway Volume on the directory of `DB_PATH` — the container filesystem is ephemeral, so SQLite data is lost on redeploy otherwise

See `docs/operations.md` for console-side settings that are easy to lose (Volume, OAuth publishing, Gemini billing) and the secret-rotation runbook for a suspected leak.
