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
    
    # Drop and recreate the file_formats table with the new is_pattern column
    c.execute('DROP TABLE IF EXISTS file_formats')
    c.execute('''CREATE TABLE file_formats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        extension TEXT NOT NULL UNIQUE,
        color TEXT NOT NULL,
        language TEXT,
        enabled INTEGER DEFAULT 1,
        display_order INTEGER DEFAULT 999,
        is_pattern INTEGER DEFAULT 0
    )''')
    
    # Insert default file formats if none exist
    c.execute("SELECT COUNT(*) FROM file_formats")
    if c.fetchone()[0] == 0:
        default_formats = [
            # Standard extensions
            ('.json', '#4A55A7', 'json', 1, 1, 0),
            ('.py', '#306998', 'python', 1, 2, 0),
            ('.js', '#F0DB4F', 'javascript', 1, 3, 0),
            ('.jsx', '#61DAFB', 'javascript', 1, 4, 0),
            ('.ts', '#007ACC', 'typescript', 1, 5, 0),
            ('.sql', '#E97B00', 'sql', 1, 6, 0),
            ('.yml', '#6C3483', 'yaml', 1, 7, 0),
            ('.svelte', '#FF3E00', 'svelte', 1, 8, 0),
            ('.md', '#6A737D', 'markdown', 1, 9, 0),
            ('.tsx', '#3178C6', 'typescript', 1, 10, 0),
            ('.yaml', '#6C3483', 'yaml', 1, 11, 0),
            ('.css', '#2965F1', 'css', 1, 12, 0),
            ('.html', '#E34F26', 'html', 1, 13, 0),
            ('.sh', '#4CAF50', 'bash', 1, 14, 0),
            ('.bat', '#8BC34A', 'batch', 1, 15, 0),
            ('.txt', '#5D6975', '', 1, 16, 0),
            ('.php', '#777BB3', 'php', 1, 17, 0),
            ('.toml', '#8D6E63', 'toml', 1, 18, 0),
            ('.tpl', '#1C86EE', 'html', 1, 19, 0),
            ('.go', '#00ADD8', 'go', 1, 20, 0),
            ('.mod', '#00ADD8', 'go', 1, 21, 0),
            ('.sum', '#5D6975', '', 1, 22, 0),
            ('.ipynb', '#F37726', 'json', 1, 23, 0),
            # Pattern formats - the language should be 'dockerfile' for proper highlighting
            ('Dockerfile*', '#2496ED', 'dockerfile', 1, 24, 1)
        ]
        c.executemany(
            "INSERT INTO file_formats (extension, color, language, enabled, display_order, is_pattern) VALUES (?, ?, ?, ?, ?, ?)",
            default_formats
        )
    
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

def get_file_formats():
    """
    Get all file formats from the database
    
    Returns:
        List of file format objects with extension, color, language, and enabled status
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM file_formats ORDER BY display_order, extension")
        rows = c.fetchall()
        formats = [dict(row) for row in rows]
        print(f"DB: Retrieved {len(formats)} file formats")
        return formats
    except sqlite3.Error as e:
        print(f"Database error retrieving file formats: {e}")
        return []
    finally:
        conn.close()

def add_file_format(extension, color, language, enabled=1, is_pattern=0):
    """
    Add a new file format
    
    Args:
        extension: File extension (e.g. '.js') or filename pattern (e.g. 'Dockerfile_*')
        color: Hex color code (e.g. '#F0DB4F')
        language: Language name for syntax highlighting (e.g. 'javascript')
        enabled: Whether this format is enabled (1) or disabled (0)
        is_pattern: Whether this is a pattern (1) or a simple extension (0)
        
    Returns:
        True if successful, False otherwise
    """
    print(f"DB: Adding file format - ext={extension}, color={color}, lang={language}, enabled={enabled}, is_pattern={is_pattern}")
    
    # Only ensure extension starts with a dot if it's not a pattern
    if not is_pattern and not extension.startswith('.'):
        extension = '.' + extension
        print(f"DB: Added dot to extension: {extension}")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Get the highest display_order
        c.execute("SELECT MAX(display_order) FROM file_formats")
        max_order = c.fetchone()[0] or 0
        
        c.execute(
            "INSERT INTO file_formats (extension, color, language, enabled, display_order, is_pattern) VALUES (?, ?, ?, ?, ?, ?)",
            (extension, color, language, enabled, max_order + 1, is_pattern)
        )
        conn.commit()
        print(f"DB: Format added successfully: {extension}")
        return True
    except sqlite3.Error as e:
        print(f"Database error adding file format: {e}")
        # Print traceback for more detail
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def update_file_format(format_id, extension=None, color=None, language=None, enabled=None, display_order=None, is_pattern=None):
    """
    Update an existing file format
    
    Args:
        format_id: ID of the format to update
        extension, color, language, enabled, display_order: Fields to update (None for no change)
        is_pattern: Whether this is a pattern (1) or a simple extension (0)
        
    Returns:
        True if successful, False otherwise
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Check if this format is a pattern
        current_is_pattern = 0
        if extension is not None:
            # Get the current is_pattern value if we're updating the extension
            c.execute("SELECT is_pattern FROM file_formats WHERE id = ?", (format_id,))
            result = c.fetchone()
            if result:
                current_is_pattern = result[0]
        
        # Build update query based on which fields are provided
        update_fields = []
        params = []
        
        if extension is not None:
            # Only ensure extension starts with a dot if it's not a pattern
            if not (is_pattern or current_is_pattern) and not extension.startswith('.'):
                extension = '.' + extension
            update_fields.append("extension = ?")
            params.append(extension)
        
        if color is not None:
            update_fields.append("color = ?")
            params.append(color)
            
        if language is not None:
            update_fields.append("language = ?")
            params.append(language)
            
        if enabled is not None:
            update_fields.append("enabled = ?")
            params.append(enabled)
            
        if display_order is not None:
            update_fields.append("display_order = ?")
            params.append(display_order)
            
        if is_pattern is not None:
            update_fields.append("is_pattern = ?")
            params.append(is_pattern)
            
        if not update_fields:
            return False  # Nothing to update
            
        query = f"UPDATE file_formats SET {', '.join(update_fields)} WHERE id = ?"
        params.append(format_id)
        
        c.execute(query, params)
        conn.commit()
        return c.rowcount > 0
    except sqlite3.Error as e:
        print(f"Database error updating file format: {e}")
        return False
    finally:
        conn.close()

def delete_file_format(format_id):
    """
    Delete a file format
    
    Args:
        format_id: ID of the format to delete
        
    Returns:
        True if successful, False otherwise
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM file_formats WHERE id = ?", (format_id,))
        conn.commit()
        return c.rowcount > 0
    except sqlite3.Error as e:
        print(f"Database error deleting file format: {e}")
        return False
    finally:
        conn.close()

def update_file_format_order(format_ids):
    """
    Update the display order of file formats
    
    Args:
        format_ids: List of format IDs in the desired order
        
    Returns:
        True if successful, False otherwise
    """
    if not format_ids:
        return False
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        for order, format_id in enumerate(format_ids, 1):
            c.execute("UPDATE file_formats SET display_order = ? WHERE id = ?", (order, format_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error updating file format order: {e}")
        return False
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