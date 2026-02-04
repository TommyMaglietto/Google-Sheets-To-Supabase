"""
upsert_to_supabase.py
---------------------
Reads .tmp/sheet_data.json, applies the column mapping from .env,
and upserts the rows into the target Supabase table.

Requires:
  - .env  (SUPABASE_URL, SUPABASE_KEY, SUPABASE_TABLE, SUPABASE_PK, COLUMN_MAP)
  - .tmp/sheet_data.json  (output of fetch_google_sheet.py)

Install dependencies:
  pip install supabase python-dotenv
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY")
TABLE_NAME    = os.getenv("SUPABASE_TABLE")
PK_COLUMN     = os.getenv("SUPABASE_PK")
COLUMN_MAP_RAW = os.getenv("COLUMN_MAP", "{}")  # JSON: {"Sheet Header": "supabase_col"}

INPUT_PATH = BASE_DIR / ".tmp" / "sheet_data.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def apply_column_map(rows: list[dict], col_map: dict) -> list[dict]:
    """Rename keys in each row according to col_map. Unmapped keys are kept as-is."""
    mapped = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            new_key = col_map.get(key, key)
            new_row[new_key] = value
        mapped.append(new_row)
    return mapped

# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------
def upsert_rows(client: Client, rows: list[dict]):
    """Upsert rows into Supabase, resolving conflicts on PK_COLUMN."""
    if not rows:
        print("No rows to upsert.")
        return

    response = (
        client.table(TABLE_NAME)
        .upsert(rows, options={"resolution": "merge", "conflict": PK_COLUMN})
        .execute()
    )
    return response

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not TABLE_NAME or not PK_COLUMN:
        raise ValueError("SUPABASE_TABLE and SUPABASE_PK must be set in .env")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"{INPUT_PATH} not found. Run fetch_google_sheet.py first."
        )

    # Load intermediate data
    with open(INPUT_PATH, encoding="utf-8") as f:
        rows = json.load(f)

    if not rows:
        print("sheet_data.json is empty — nothing to upsert.")
        return

    # Apply column mapping
    col_map = json.loads(COLUMN_MAP_RAW)
    mapped_rows = apply_column_map(rows, col_map)
    print(f"Mapped {len(mapped_rows)} row(s) using COLUMN_MAP.")

    # Upsert
    client = get_client()
    print(f"Upserting into '{TABLE_NAME}' (PK: {PK_COLUMN}) ...")
    response = upsert_rows(client, mapped_rows)

    print(f"  → Done. Supabase response count: {len(response.data) if response.data else 0}")

if __name__ == "__main__":
    main()
