# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

学校プリント管理Bot — A LINE messaging bot for Japanese parents to manage school documents. Parents send screenshots/PDFs of school printouts via LINE, and the bot uses Gemini AI to extract tasks, events, and deadlines, then sends personalized daily reminders filtered by each child's grade.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (with hot reload)
python src/main.py

# Production (Railway)
uvicorn main:app --host 0.0.0.0 --port $PORT --app-dir src
```

No test or lint commands are configured.

## Environment Variables

Copy `.env.example` and fill in:
- `LINE_CHANNEL_SECRET` — LINE webhook signature verification
- `LINE_CHANNEL_ACCESS_TOKEN` — LINE API authentication
- `GEMINI_API_KEY` — Google Gemini API key
- `DATABASE_URL` — SQLite path (default: `sqlite:///./school_prints.db`)
- `PORT` — Server port (default: 8000)

## Architecture

```
LINE Webhook → FastAPI (main.py)
                  ↓
          line_handler.py       ← routes messages, formats responses
         /      |       \
gemini_client.py  database.py  scheduler.py
(AI analysis)    (SQLite)      (Daily 7AM JST reminders)
```

**Module responsibilities:**
- `main.py` — FastAPI app, webhook endpoint, lifespan (starts scheduler, inits DB)
- `line_handler.py` — Message routing (image/PDF/text), child management commands, response formatting
- `gemini_client.py` — Gemini 2.5 Flash calls; extracts grade, tasks, events, notes as structured JSON
- `database.py` — SQLite CRUD; grade-matching logic for filtering tasks by child's grade
- `scheduler.py` — APScheduler cron job at 22:00 UTC (= 7:00 AM JST); sends personalized push notifications per child

## Database Schema

Three SQLite tables:
- **prints** — Raw document records (user_id, grade, original_text, summary)
- **tasks** — Extracted items (title, description, due_date, task_type, target_grades JSON, dismissal_times JSON, is_reminded)
- **children** — Registered child profiles (user_id, name, grade)

`target_grades` and `dismissal_times` are stored as JSON strings to support multi-grade documents.

## Key Domain Logic

**Grade-specific dismissal times** is the core differentiator. A single school print may list different dismissal times per grade (e.g., 1〜4年 at 13:00, 5年 at 13:30). The bot must:
1. Parse range notation (`1〜4年`, `1-4年`, `1～4年`) in `database.py:is_task_relevant_to_child`
2. Show only the relevant dismissal time for each registered child via `get_dismissal_time_for_child`

**LINE user commands:**
| Input | Action |
|-------|--------|
| Image/PDF | Analyze with Gemini, store tasks |
| Keyword text | Full-text search of past prints |
| `タスク一覧` | List pending tasks |
| `子ども登録 NAME GRADE` | Register child (e.g., `子ども登録 たろう 1年`) |
| `子ども一覧` | List children |
| `子ども削除 NAME` | Remove child |
| `ヘルプ` | Show help |

## Deployment (Railway)

1. Push to GitHub
2. Set env vars in Railway dashboard
3. Set LINE webhook URL to `https://your-app.up.railway.app/callback`
4. SQLite DB persists on Railway's filesystem

## Planned but Not Yet Implemented

Google Calendar integration — `google-api-python-client` and `google-auth-oauthlib` are in `requirements.txt` and `GOOGLE_CALENDAR_CREDENTIALS_JSON` is in `.env.example`, but the integration is not yet built. `is_registered_to_calendar` field exists in the tasks table for this future feature.
