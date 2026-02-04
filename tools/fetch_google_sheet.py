"""
fetch_google_sheet.py
---------------------
Reads all rows from a Google Sheet and writes them to .tmp/sheet_data.json.

Requires:
  - credentials.json  (Google OAuth client credentials)
  - token.json        (cached OAuth token; auto-refreshed if expired)
  - .env              (GOOGLE_SHEET_ID, GOOGLE_SHEET_NAME)

Install dependencies:
  pip install google-auth google-auth-oauthlib google-api-python-client python-dotenv
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SHEET_ID   = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")
OUTPUT_PATH = BASE_DIR / ".tmp" / "sheet_data.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
CREDS_PATH  = BASE_DIR / "credentials.json"
TOKEN_PATH  = BASE_DIR / "token.json"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def get_credentials() -> Credentials:
    """Return valid Google OAuth credentials, refreshing or prompting as needed."""
    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH) as f:
            token_data = json.load(f)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_PATH.exists():
                raise FileNotFoundError(
                    "credentials.json not found. Download it from the Google Cloud "
                    "Console (APIs & Services → Credentials → OAuth 2.0 Client)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Persist the (possibly new) token
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds

# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def fetch_sheet() -> list[dict]:
    """Read all rows from the target sheet, return as list of dicts keyed by header."""
    creds  = get_credentials()
    client = build("sheets", "v4", credentials=creds)

    range_notation = f"'{SHEET_NAME}'"
    response = (
        client.spreadsheets()
        .values()
        .get(spreadsheetId=SHEET_ID, range=range_notation)
        .execute()
    )

    values = response.get("values", [])
    if len(values) < 2:
        print("Sheet has no data rows (only headers or is empty).")
        return []

    headers  = values[0]
    num_cols = len(headers)
    # Pad rows: Google Sheets API omits trailing empty cells.
    # zip() truncates to the shortest iterable, which would silently drop columns.
    rows = [
        dict(zip(headers, row + [""] * (num_cols - len(row))))
        for row in values[1:]
    ]
    return rows

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not SHEET_ID:
        raise ValueError("GOOGLE_SHEET_ID is not set in .env")

    print(f"Fetching sheet '{SHEET_NAME}' from {SHEET_ID} ...")
    rows = fetch_sheet()
    print(f"  -> {len(rows)} row(s) fetched.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    print(f"  -> Written to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
