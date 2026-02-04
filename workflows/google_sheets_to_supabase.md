# Google Sheets → Supabase Sync

## Objective
Read rows from a Google Sheet and upsert them into a Supabase table. Keeps the two in sync on demand.

## Inputs
| Input | Source | Description |
|---|---|---|
| `GOOGLE_SHEET_ID` | `.env` | The ID of the source Google Sheet |
| `GOOGLE_SHEET_NAME` | `.env` | The tab/sheet name within the workbook (default: `Sheet1`) |
| `SUPABASE_TABLE` | `.env` | Target Supabase table name |
| `SUPABASE_PK` | `.env` | Primary key column name in Supabase (used for upsert conflict resolution) |
| `COLUMN_MAP` | `.env` | JSON mapping of Sheet column headers → Supabase column names. Example: `{"Sheet Header":"supabase_col"}` |

## Tools (in order)
1. **`tools/fetch_google_sheet.py`** — Authenticates with Google Sheets API, reads all rows from the specified sheet, writes them to `.tmp/sheet_data.json`
2. **`tools/upsert_to_supabase.py`** — Reads `.tmp/sheet_data.json`, applies the column mapping, and upserts into Supabase

## Expected Outputs
- `.tmp/sheet_data.json` — Raw row data from Google Sheets (intermediate, disposable)
- Console log confirming number of rows upserted and any skipped/errored rows

## Edge Cases & Known Behaviors
- **Auth failure (Google):** Requires `credentials.json` and a valid `token.json`. If token is expired, the script will attempt a refresh. If refresh fails, delete `token.json` and re-run to trigger a fresh OAuth flow.
- **Auth failure (Supabase):** Double-check `SUPABASE_URL` and `SUPABASE_KEY` in `.env`. The key must have write permissions on the target table.
- **Schema mismatch:** If a column in `COLUMN_MAP` doesn't exist in the Supabase table, the upsert will fail. Verify your table schema first.
- **Empty sheet:** If the sheet has headers but no data rows, the upsert step is skipped cleanly.
- **Duplicate primary keys:** Upsert uses `on_conflict` resolution on `SUPABASE_PK` — existing rows are updated, new rows are inserted.

## How to Run
```bash
# Step 1 — fetch data from Google Sheets
python tools/fetch_google_sheet.py

# Step 2 — upsert into Supabase
python tools/upsert_to_supabase.py
```

## Change Log
| Date | What changed |
|---|---|
| 2026-02-04 | Initial workflow created |
