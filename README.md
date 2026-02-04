# Google Sheets To Supabase

Pulls data from a Google Sheet and creates a table in Supabase, populated with all rows and columns from the sheet. Built on the WAT framework (Workflows, Agents, Tools).

## Setup

1. **Google credentials** — Download `credentials.json` from Google Cloud Console (APIs & Services → Credentials → OAuth 2.0 Client ID, Desktop app type). Place it in the project root. The first run opens a browser for sign-in and caches a `token.json` — subsequent runs skip this step.

2. **Environment** — Copy `.env.example` → `.env` and fill in:
   - `GOOGLE_SHEET_ID` — from your Google Sheet URL
   - `SUPABASE_PROJECT_REF` — visible in your Supabase dashboard URL
   - `SUPABASE_MANAGEMENT_KEY` — Personal Access Token (Supabase Account → Access Tokens)
   - `SUPABASE_TABLE` — name for the target table (created automatically)

3. **Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Run

```bash
# Step 1 — fetch sheet data
python tools/fetch_google_sheet.py

# Step 2 — create table and insert
python tools/create_table_and_insert.py
```

## How it works

| Step | Script | What it does |
|---|---|---|
| 1 | `tools/fetch_google_sheet.py` | Authenticates via Google OAuth, reads all rows, writes `.tmp/sheet_data.json` |
| 2 | `tools/create_table_and_insert.py` | Sanitizes column names, drops the table if it exists, creates it, and bulk-inserts all rows via the Supabase Management API |

- An `id SERIAL PRIMARY KEY` column is added automatically.
- All sheet columns become `TEXT` type (lossless — no data lost to type guessing).
- Blank cells become `NULL` in the database.
- Rows missing **both** email and phone are excluded.
- Known test entries are filtered out before insert.
- Re-running the pipeline drops and recreates the table from the latest sheet data.

## Project structure

```
tools/              # Python execution scripts
  fetch_google_sheet.py       # Reads Google Sheet -> .tmp/sheet_data.json
  create_table_and_insert.py  # Creates Supabase table and inserts rows
  upsert_to_supabase.py       # (Alt flow) Upserts into a pre-existing table
workflows/          # Markdown SOPs
  google_sheets_to_supabase.md
.tmp/               # Intermediate files (auto-generated, gitignored)
.env                # Secrets (gitignored)
.env.example        # Template - copy to .env and fill in
credentials.json    # Google OAuth credentials (gitignored)
requirements.txt    # Python dependencies
CLAUDE.md           # WAT framework agent instructions
```
