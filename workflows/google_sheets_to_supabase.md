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
| 2026-02-04 | Initial workflow created (Flow A — upsert) |
| 2026-02-04 | Flow B added: DROP+CREATE+INSERT via psycopg2; row-padding fix in fetch; SUPABASE_DB_URL added to .env.example |

---

## Flow B — Create New Table (DROP + CREATE + INSERT)

### Objective
Read a Google Sheet and create a **brand-new** Supabase table whose schema is
derived entirely from the sheet headers. If the table already exists it is
dropped and recreated. All data is copied in a single transaction.

### Inputs
| Input | Source | Description |
|---|---|---|
| `GOOGLE_SHEET_ID` | `.env` | The ID of the source Google Sheet |
| `GOOGLE_SHEET_NAME` | `.env` | The tab/sheet name within the workbook (default: `Sheet1`) |
| `SUPABASE_PROJECT_REF` | `.env` | Your Supabase project ref — visible in the dashboard URL |
| `SUPABASE_MANAGEMENT_KEY` | `.env` | Personal Access Token from Supabase Account → Access Tokens |
| `SUPABASE_TABLE` | `.env` | Name of the table to create (or drop-and-recreate) |

### Tools (in order)
1. **`tools/fetch_google_sheet.py`** — Same as Flow A. Writes `.tmp/sheet_data.json`. Trailing empty cells are padded so every row has all columns.
2. **`tools/create_table_and_insert.py`** — Posts DROP + CREATE + INSERT as a single SQL string to the Supabase Management API. Creates the table with `id SERIAL PRIMARY KEY` + one `TEXT` column per sheet header.

### Expected Outputs
- `.tmp/sheet_data.json` — Intermediate (same as Flow A, disposable)
- A new (or freshly recreated) table in Supabase with all sheet data

### Edge Cases & Known Behaviours
- **Table already exists:** Dropped and recreated. This is a full replace, not a merge.
- **Blank cells in the sheet:** Become `NULL` in the database (not empty strings).
- **Column-name collisions after sanitization:** Resolved by appending `_2`, `_3`, … The full mapping (original header → sanitized name) is printed to the console before any SQL runs.
- **Transaction rollback:** If the INSERT fails (e.g. connection drop mid-flight) the DROP and CREATE are also rolled back. The table is left in whatever state it was in *before* the script ran.
- **Empty sheet (headers only, no data rows):** Exits cleanly with a message; no SQL is executed.

### How to Run
```bash
# Step 1 — fetch data from Google Sheets (shared with Flow A)
python tools/fetch_google_sheet.py

# Step 2 — create table and insert
python tools/create_table_and_insert.py
```
