# app_logic/database.py

import sqlite3
from .config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS repositories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        identifier TEXT NOT NULL UNIQUE,
        last_updated DATETIME
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS files (
        repo_id INTEGER NOT NULL,
        path TEXT NOT NULL,
        url_type TEXT NOT NULL,
        url TEXT,
        content TEXT,  -- Added to store GitHub file contents
        FOREIGN KEY (repo_id) REFERENCES repositories(id),
        PRIMARY KEY (repo_id, path)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS groupings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        FOREIGN KEY (repo_id) REFERENCES repositories(id),
        UNIQUE(repo_id, name)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS grouping_files (
        grouping_id INTEGER NOT NULL,
        repo_id INTEGER NOT NULL,
        path TEXT NOT NULL,
        FOREIGN KEY (grouping_id) REFERENCES groupings(id),
        FOREIGN KEY (repo_id, path) REFERENCES files(repo_id, path),
        UNIQUE(grouping_id, repo_id, path)
    )''')
    conn.commit()
    conn.close()

# ============================================================================
# Notes:
# - Added `content TEXT` column to `files` table to store GitHub file contents.
# - Remains NULL for local files to keep disk usage lightweight.
# ============================================================================

# ============================================================================
# Detailed Documentation
# ============================================================================
#
# Purpose:
#   Initializes the SQLite database for Codeprinter, setting up the schema to store
#   repository, file, and grouping data.
#
# Design Intent:
#   - **Isolation**: Separates database logic from other functionality, simplifying
#     schema updates or potential database swaps.
#   - **Simplicity**: Provides a single idempotent function called at startup.
#   - **Reliability**: Leverages `DB_PATH` from config.py to ensure consistent database
#     location.
#
# How It Works:
#   1. Connects to the SQLite database at `DB_PATH`.
#   2. Creates four tables if they don’t exist:
#      - `repositories`: Stores repo metadata (type, identifier, timestamp).
#      - `files`: Tracks file paths and URLs with a composite key (repo_id, path).
#      - `groupings`: Manages named file groups per repository.
#      - `grouping_files`: Links files to groupings with referential integrity.
#   3. Commits changes and closes the connection.
#
# Integration with Broader Repo:
#   - **app.py**: Calls `init_db` at startup to ensure the database is ready.
#   - **routes.py**: Interacts with these tables for tree fetching, file content retrieval,
#     and grouping management.
#   - Supports the app’s core feature set: exploring codebases and saving selections.
#
# Notes:
#   - `IF NOT EXISTS` makes the function safe to call repeatedly without data loss.
#   - Foreign keys ensure data consistency (e.g., no files without a repository).
#   - SQLite’s lightweight nature suits Codeprinter’s single-file database needs.