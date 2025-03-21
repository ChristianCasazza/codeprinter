# app_logic/database.py

import sqlite3
from datetime import datetime
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
    
    # New table for saved paths history
    c.execute('''CREATE TABLE IF NOT EXISTS saved_paths (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,  -- 'github' or 'local'
        path TEXT NOT NULL UNIQUE,
        last_used DATETIME NOT NULL,
        use_count INTEGER DEFAULT 1
    )''')
    
    # New table for persisting last selection per repository
    c.execute('''CREATE TABLE IF NOT EXISTS last_selections (
        repo_id INTEGER PRIMARY KEY,
        selection_data TEXT NOT NULL,  -- JSON array of file paths
        last_updated DATETIME NOT NULL,
        FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
    )''')
    
    conn.commit()
    conn.close()

# ============================================================================
# Notes:
# - Added `content TEXT` column to `files` table to store GitHub file contents.
# - Remains NULL for local files to keep disk usage lightweight.
# - Added saved_paths and last_selections tables for persistence
# ============================================================================

def save_path_history(path_type, path):
    """
    Store or update a path in history when it's used
    
    Args:
        path_type: 'github' or 'local'
        path: full path or URL to store
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Check if path already exists
        c.execute("SELECT id, use_count FROM saved_paths WHERE path = ?", (path,))
        result = c.fetchone()
        
        if result:
            # Update existing path
            path_id, count = result
            c.execute("UPDATE saved_paths SET last_used = ?, use_count = ? WHERE id = ?", 
                     (datetime.now(), count + 1, path_id))
        else:
            # Insert new path
            c.execute("INSERT INTO saved_paths (type, path, last_used, use_count) VALUES (?, ?, ?, ?)",
                     (path_type, path, datetime.now(), 1))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error saving path history: {e}")
    finally:
        conn.close()

def get_path_history(path_type):
    """
    Get saved paths history for a specific type
    
    Args:
        path_type: 'github' or 'local'
        
    Returns:
        List of paths sorted by use frequency and recency
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute("""
            SELECT path FROM saved_paths 
            WHERE type = ? 
            ORDER BY use_count DESC, last_used DESC 
            LIMIT 10
        """, (path_type,))
        paths = [row['path'] for row in c.fetchall()]
        return paths
    except sqlite3.Error as e:
        print(f"Database error retrieving path history: {e}")
        return []
    finally:
        conn.close()

def save_selection(repo_id, selected_paths):
    """
    Save a user's last selection for a repository
    
    Args:
        repo_id: Repository ID
        selected_paths: JSON string of selected file paths
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR REPLACE INTO last_selections (repo_id, selection_data, last_updated)
            VALUES (?, ?, ?)
        """, (repo_id, selected_paths, datetime.now()))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error saving selection: {e}")
    finally:
        conn.close()

def get_last_selection(repo_id):
    """
    Get the last selection for a repository
    
    Args:
        repo_id: Repository ID
        
    Returns:
        JSON string of selected file paths or None if not found
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT selection_data FROM last_selections WHERE repo_id = ?", (repo_id,))
        result = c.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        print(f"Database error retrieving last selection: {e}")
        return None
    finally:
        conn.close()

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