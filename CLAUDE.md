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
# DB tests run on SQLite only unless TEST_DATABASE_URL points at a PostgreSQL (CI uses a service container):
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres pytest tests/ -v

# Run locally (with hot reload)
python src/main.py

# Production (Cloud Run or Railway — the Dockerfile CMD runs this)
uvicorn main:app --host 0.0.0.0 --port $PORT --app-dir src

# One-off scripts
python scripts/authorize_google.py   # Google OAuth → prints JSON for GOOGLE_CALENDAR_CREDENTIALS_JSON
python scripts/setup_richmenu.py     # Create/upload LINE rich menu and set it as default
python scripts/migrate_sqlite_to_postgres.py school_prints.db   # Copy a SQLite file into DATABASE_URL (empty destination only)
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
- `DB_PATH` — SQLite file path (optional; default `school_prints.db`, `/app/data/school_prints.db` recommended for Docker). Ignored when `DATABASE_URL` is set
- `DATABASE_URL` — PostgreSQL connection string (optional). When set, PostgreSQL is used instead of SQLite. For Supabase use the Transaction pooler string (port 6543)
- `DB_SCHEMA` — PostgreSQL schema to use (optional; for sharing an existing database with other apps)
- `SCHEDULER_MODE` — `internal` (default; in-process APScheduler) or `external` (no in-process scheduler; an external cron POSTs `/cron/*`)
- `CRON_SECRET` — shared secret for `/cron/*`, sent in the `X-Cron-Secret` header (required when `SCHEDULER_MODE=external`)
- `PORT` — Server port (default: 8000)

`main.py:validate_env` exits on startup if a required variable is missing, if `SCHEDULER_MODE` is unknown, or if it is `external` without `CRON_SECRET`.

## Architecture

```
LINE Webhook → FastAPI (main.py) ── returns 200 immediately, processes in background
                  ↓
          line_handler.py       ← routes messages/postbacks, formats responses
         /      |       |       \
gemini_client.py  database.py  google_calendar.py  line_client.py
(AI analysis)  (SQLite/Postgres) (Calendar REST API) (LINE API wrapper)
       ↓
verification.py — consistency checks on extracted tasks (pure functions)
dates.py        — JST / weekday / "11/5(木)" formatting helpers

scheduler.py — daily reminders / April grade advance, run by APScheduler (internal)
               or by POST /cron/* from an external cron (external)
```

**Module responsibilities:**
- `main.py` — FastAPI app, env validation, webhook endpoint (`/callback`), lifespan (inits DB, starts the scheduler only in `internal` mode), and the cron endpoints `POST /cron/daily-reminder` / `POST /cron/advance-grades` (404 unless `SCHEDULER_MODE=external`, 401 without the right `X-Cron-Secret`; the job runs to completion before the response because Cloud Run throttles CPU afterwards; `advance-grades` is a no-op outside April so a manual "run now" cannot advance grades). Webhook events run as background tasks so LINE gets a 200 before Gemini analysis finishes (avoids 499 timeouts on heavy PDFs).
- `line_handler.py` — Message routing (image/PDF/text), postback handling (Quick Reply buttons), child management commands, calendar mode settings, response formatting
- `line_client.py` — reply / push / Quick Reply / content download wrappers around LINE Messaging API (lazy-initialized async client)
- `gemini_client.py` — Gemini 2.5 Flash calls; extracts grade, tasks, events, notes as structured JSON. Each task also carries `source_text` (short quote of the print text the date was read from) and `weekday_on_print` (the weekday printed next to it, normalized to one of 月〜日 or `None`); `_normalize_task` makes these fields safe to display. "Today" in the prompt is computed in JST.
- `verification.py` — `check_tasks(tasks)` returns per-task ⚠️ warnings, no I/O: printed weekday vs. `due_date` weekday (suggests the matching date within ±3 days), the same title on two consecutive days, and a `due_date` more than 60 days past / 400 days ahead (year misread). Runs on the whole Gemini result in `_save_and_reply`, before duplicate filtering.
- `dates.py` — `JST`, `today_jst()`, `weekday_ja()`, `format_date_ja()` (`"11/5(木)"`, year shown only when it differs from the current year)
- `google_calendar.py` — Registers tasks via Google Calendar API v3 (`googleapiclient`), with duplicate-event check. `RefreshError` (e.g. `invalid_grant`) is caught both in `_get_credentials` and around the API calls in `register_task_to_calendar` — the stored credentials JSON has no `expiry`, so in practice the refresh happens on a 401 inside `.execute()` — so calendar failures don't abort PDF analysis. All-day events use an exclusive `end.date` (due_date + 1 day).
- `database.py` — CRUD on SQLite or PostgreSQL (chosen by `DATABASE_URL`); grade-matching logic for filtering tasks by child's grade; per-user calendar mode; `claim_once` for once-only jobs. One SQL text serves both backends: write placeholders as `?` (converted to `%s` for psycopg — so no literal `?` or `%` inside SQL strings), get new ids with `RETURNING id` (not `lastrowid`), and pass "today" from Python (`dates.today_jst()`) instead of SQL date functions
- `scheduler.py` — the jobs themselves plus APScheduler triggers pinned to JST (independent of host time zone): 7:00 AM JST daily reminders per child; April 1 9:00 AM JST automatic grade advance. `advance_grades_april` runs at most once per year (`claim_once`), because an external cron may deliver twice

## Database Schema

Five tables (created in `database.py:init_db` from `_SQLITE_SCHEMA` / `_POSTGRES_SCHEMA` — keep the two in sync; SQLite column additions go through `ALTER TABLE` migrations there). In PostgreSQL `due_date` is `TEXT` (`YYYY-MM-DD`) and flags are `INTEGER` so both backends return identical values:
- **prints** — Raw document records (user_id, grade, original_text, summary)
- **tasks** — Extracted items (print_id, title, description, due_date, task_type, target_grades JSON, dismissal_times JSON, is_registered_to_calendar, calendar_event_id, is_reminded)
- **children** — Registered child profiles (user_id, name, grade)
- **user_settings** — Per-user settings (user_id, calendar_mode: `auto` / `off` / `ask`, default `auto`)
- **app_state** — key/value records of once-only jobs (e.g. `grades_advanced_year`)

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

**Extraction evidence in the reply.** Table-style prints (学年だより) can make Gemini read a date one row off, so the analysis reply shows, per task, the date with its weekday, `📝 原文:「…」` (the `source_text` quote) and any ⚠️ from `verification.check_tasks`; the footer counts the warnings and points the parent to fix the event in Google Calendar. Warnings do not block registration — in `auto` mode the event is already on the calendar by the time the reply is sent.

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
- Re-auth: run `scripts/authorize_google.py` and replace `GOOGLE_CALENDAR_CREDENTIALS_JSON` in the hosting environment (Cloud Run: new Secret Manager version + redeploy; Railway: Variables).

## Deployment

The same image runs in two configurations, selected by env vars only. Run exactly one of them at a time — two live deployments send every morning reminder twice.

**Cloud Run (free-tier setup):** `DATABASE_URL` (PostgreSQL, e.g. Supabase) + `SCHEDULER_MODE=external` + `CRON_SECRET`; Cloud Scheduler POSTs `/cron/daily-reminder` (07:00 Asia/Tokyo daily) and `/cron/advance-grades` (09:00 on April 1). Deploy with `gcloud run deploy --source .` using `--no-cpu-throttling` (instance-based billing): the webhook answers LINE first and analyzes in a background task, which stalls under the default request-based billing. Keep `--max-instances 1`.

**Railway (always-on setup):** no `DATABASE_URL`, default `SCHEDULER_MODE`; SQLite on a Volume mounted at the directory of `DB_PATH` (the container filesystem is ephemeral, so data is lost on redeploy otherwise).

LINE webhook URL is `https://<host>/callback` in both.

See `docs/operations.md` for console-side settings that are easy to lose (database persistence, OAuth publishing, Gemini billing), the secret-rotation runbook, and the Cloud Run setup / Railway → Cloud Run migration steps.
