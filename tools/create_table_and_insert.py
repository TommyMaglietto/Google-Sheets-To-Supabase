"""
create_table_and_insert.py
--------------------------
Reads .tmp/sheet_data.json (output of fetch_google_sheet.py), creates a brand-
new table in Supabase via the Management API, and bulk-inserts all rows.

Behaviour:
  - If the target table already exists it is DROPPED and recreated.
  - An `id SERIAL PRIMARY KEY` column is added automatically.
  - Every sheet column becomes a TEXT column; column names are sanitised from
    the raw header strings.
  - Empty strings from the sheet become NULL in the database.
  - DROP, CREATE, and INSERT are sent as a single SQL string — if any
    statement fails the later ones do not execute.

Requires:
  - .env              (SUPABASE_PROJECT_REF, SUPABASE_MANAGEMENT_KEY, SUPABASE_TABLE)
  - .tmp/sheet_data.json  (output of fetch_google_sheet.py)

Install dependencies:
  pip install requests python-dotenv
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR        = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

PROJECT_REF     = os.getenv("SUPABASE_PROJECT_REF")
MANAGEMENT_KEY  = os.getenv("SUPABASE_MANAGEMENT_KEY")
TABLE_NAME      = os.getenv("SUPABASE_TABLE")
INPUT_PATH      = BASE_DIR / ".tmp" / "sheet_data.json"

# ---------------------------------------------------------------------------
# Column-name sanitization
# ---------------------------------------------------------------------------
def sanitize_column_name(raw: str) -> str:
    """
    Turn an arbitrary sheet-header string into a valid PostgreSQL identifier.

    Steps (applied in order):
      1. Strip whitespace.
      2. Replace empty result with '_unnamed'.
      3. Lowercase everything.
      4. Replace any char outside [a-z0-9_] with '_'.
      5. Collapse consecutive underscores into one.
      6. Strip leading underscores.
      7. Prepend 'col_' if the name starts with a digit.
      8. Truncate to 63 characters (PostgreSQL NAMEDATALEN - 1).
    """
    name = raw.strip()
    if not name:
        return "_unnamed"

    name = name.lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.lstrip("_")

    if not name:
        return "_unnamed"

    if name[0].isdigit():
        name = "col_" + name

    return name[:63]


def build_column_map(headers: list[str]) -> list[tuple[str, str]]:
    """
    Return [(original_header, sanitized_name), ...] preserving header order.
    Duplicates after sanitization are resolved by appending _2, _3, …
    """
    # Reserve "id" — it's used by the auto-added SERIAL PRIMARY KEY column.
    # Any sheet header that sanitizes to "id" will be renamed to "id_2", etc.
    seen: dict[str, int] = {"id": 1}
    result: list[tuple[str, str]] = []

    for header in headers:
        base = sanitize_column_name(header)

        if base not in seen:
            seen[base] = 1
            result.append((header, base))
        else:
            seen[base] += 1
            candidate = f"{base}_{seen[base]}"[:63]
            while candidate in seen:
                seen[base] += 1
                candidate = f"{base}_{seen[base]}"[:63]
            seen[candidate] = 1
            result.append((header, candidate))

    return result

# ---------------------------------------------------------------------------
# Data loading & transformation
# ---------------------------------------------------------------------------
def load_rows() -> list[dict]:
    """Read and return the row list from the intermediate JSON file."""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"{INPUT_PATH} not found. Run fetch_google_sheet.py first."
        )
    with open(INPUT_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise ValueError(f"Expected a JSON array in {INPUT_PATH}; got {type(rows).__name__}")
    return rows


# Known test entries to strip out (case-insensitive match on given + family name)
TEST_ENTRIES = [
    ("john", "doe"),
    ("test", "subject"),
]

def filter_rows(rows: list[dict]) -> list[dict]:
    """
    Remove rows that should not be inserted:
      1. Known test entries (given_name + family_name pairs).
      2. Rows with no email AND no phone — at least one is required.
    """
    kept = []
    for row in rows:
        given  = row.get("given_name", "").strip().lower()
        family = row.get("family_name", "").strip().lower()
        email  = row.get("email_address", "").strip()
        phone  = row.get("phone_number", "").strip()

        # Drop known test entries
        if (given, family) in TEST_ENTRIES:
            continue

        # Drop rows missing both email and phone
        if not email and not phone:
            continue

        kept.append(row)
    return kept


def rows_to_values(rows: list[dict], headers: list[str]) -> list[list]:
    """
    Convert each row-dict into a list aligned to the header order.
    Empty strings become None (→ SQL NULL).  Missing keys also become None.
    """
    return [
        [None if (v := row.get(h, "")) == "" else v for h in headers]
        for row in rows
    ]

# ---------------------------------------------------------------------------
# SQL building
# ---------------------------------------------------------------------------
def escape_sql_value(val) -> str:
    """Escape a single value for safe inclusion in a SQL VALUES literal."""
    if val is None:
        return "NULL"
    # Standard SQL: single quotes inside a string are escaped by doubling them
    return "'" + str(val).replace("'", "''") + "'"


def build_values_clause(rows: list[list]) -> str:
    """Turn a list of row-lists into a VALUES clause: (v1, v2), (v3, v4), …"""
    return ",\n".join(
        "(" + ", ".join(escape_sql_value(v) for v in row) + ")"
        for row in rows
    )


def build_full_sql(table: str, col_names: list[str], value_rows: list[list]) -> str:
    """
    Build the complete multi-statement SQL:
      DROP TABLE IF EXISTS …;
      CREATE TABLE … (id SERIAL PRIMARY KEY, …);
      INSERT INTO … VALUES …;
    """
    # DROP
    drop = f'DROP TABLE IF EXISTS "{table}";'

    # CREATE
    cols_ddl = ",\n    ".join(f'"{col}" TEXT' for col in col_names)
    create = (
        f'CREATE TABLE "{table}" (\n'
        f'    id SERIAL PRIMARY KEY,\n'
        f'    {cols_ddl}\n'
        f');'
    )

    # INSERT
    cols_list = ", ".join(f'"{col}"' for col in col_names)
    values    = build_values_clause(value_rows)
    insert    = f'INSERT INTO "{table}" ({cols_list}) VALUES\n{values};'

    return f"{drop}\n{create}\n{insert}"

# ---------------------------------------------------------------------------
# Management API
# ---------------------------------------------------------------------------
def run_query(sql: str):
    """POST sql to the Supabase Management API query endpoint."""
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    headers = {
        "Authorization": f"Bearer {MANAGEMENT_KEY}",
        "Content-Type":  "application/json",
    }
    resp = requests.post(url, headers=headers, json={"query": sql})

    if resp.status_code not in (200, 201):
        print(f"\n  [ERR] Management API returned {resp.status_code}:", file=sys.stderr)
        print(f"    {resp.text}", file=sys.stderr)
        resp.raise_for_status()

    return resp.json()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # ----- validate config -------------------------------------------------
    if not PROJECT_REF:
        raise ValueError("SUPABASE_PROJECT_REF is not set in .env")
    if not MANAGEMENT_KEY:
        raise ValueError("SUPABASE_MANAGEMENT_KEY is not set in .env")
    if not TABLE_NAME:
        raise ValueError("SUPABASE_TABLE is not set in .env")

    # ----- load & filter data ---------------------------------------------
    rows = load_rows()
    if not rows:
        print("sheet_data.json is empty — nothing to insert.")
        sys.exit(0)

    before = len(rows)
    rows   = filter_rows(rows)
    print(f"  Filtered: {before} raw rows -> {len(rows)} after removing test entries & no-contact rows.")

    if not rows:
        print("  No rows left after filtering — nothing to insert.")
        sys.exit(0)

    # All rows have the same keys after the row-padding fix in fetch_google_sheet.py
    original_headers = list(rows[0].keys())

    # ----- build column mapping --------------------------------------------
    col_map         = build_column_map(original_headers)
    sanitized_names = [san for _, san in col_map]

    # ----- print mapping report --------------------------------------------
    print("=" * 60)
    print(f"  Table : {TABLE_NAME}")
    print(f"  Cols  : {len(sanitized_names)}  |  Rows : {len(rows)}")
    print("-" * 60)
    print(f"  {'Original Header':<30} {'Sanitized Name'}")
    print(f"  {'-'*30} {'-'*28}")
    for orig, san in col_map:
        flag = " (renamed)" if orig.strip().lower() != san else ""
        print(f"  {orig:<30} {san}{flag}")
    print("=" * 60)

    # ----- convert rows (empty string → None) -----------------------------
    value_rows = rows_to_values(rows, original_headers)

    # ----- build & send SQL ------------------------------------------------
    sql = build_full_sql(TABLE_NAME, sanitized_names, value_rows)

    print(f"\n  Sending to Supabase Management API ...")
    run_query(sql)
    print(f"\n  [OK] {len(value_rows)} row(s) inserted into \"{TABLE_NAME}\".\n")


if __name__ == "__main__":
    main()
