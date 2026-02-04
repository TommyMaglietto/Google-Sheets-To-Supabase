# Google Sheets To Supabase

This project is an automation tool designed to sync data from Google Sheets to a Supabase database. It follows the **WAT framework** (Workflows, Agents, Tools) to ensure reliable and scalable execution.

## Architecture

The project is structured around the WAT framework:
- **Workflows**: Markdown SOPs defining objectives and steps (in `workflows/`).
- **Agents**: AI-driven coordination (that's me/you).
- **Tools**: Python scripts for deterministic execution (in `tools/`).

## Setup

1.  **Environment Variables**: Copy `.env.example` to `.env` and fill in your API keys (Supabase, Google Cloud credentials, etc.).
2.  **Dependencies**: Install required Python packages (e.g., `pip install -r requirements.txt` if available).
3.  **Google Auth**: Place `credentials.json` in the root directory for Google Sheets API access.

## Usage

Follow the specific workflows in the `workflows/` directory to run automations.
