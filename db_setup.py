# db_setup.py
import sqlite3
from contextlib import closing
import csv

DATABASE_NAME = 'prompts.db'

def init_db():
    with closing(sqlite3.connect(DATABASE_NAME)) as conn:
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS reusable_prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS prompt_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    block_order INTEGER NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS block_tags (
                    block_id INTEGER,
                    tag_id INTEGER,
                    FOREIGN KEY (block_id) REFERENCES prompt_blocks(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY (block_id, tag_id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS repos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS repo_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_id INTEGER,
                    file_path TEXT NOT NULL,
                    is_selected INTEGER DEFAULT 0,
                    FOREIGN KEY (repo_id) REFERENCES repos(id) ON DELETE CASCADE,
                    UNIQUE (repo_id, file_path)
                )
            ''')

def get_connection():
    return sqlite3.connect(DATABASE_NAME)

# ---- HELPER FUNCTIONS FOR REUSABLE PROMPTS ----

def get_all_reusable_prompts():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, name, content FROM reusable_prompts ORDER BY id DESC')
    data = c.fetchall()
    conn.close()
    return data

def add_reusable_prompt(name, content):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO reusable_prompts (name, content) VALUES (?, ?)', (name, content))
    conn.commit()
    conn.close()

def delete_reusable_prompt(prompt_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM reusable_prompts WHERE id = ?', (prompt_id,))
    conn.commit()
    conn.close()

def get_reusable_prompt(prompt_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, name, content FROM reusable_prompts WHERE id = ?', (prompt_id,))
    data = c.fetchone()
    conn.close()
    return data

def update_reusable_prompt(prompt_id, name, content):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE reusable_prompts SET name = ?, content = ? WHERE id = ?', (name, content, prompt_id))
    conn.commit()
    conn.close()

# ---- HELPER FUNCTIONS FOR PROMPT BLOCKS ----

def get_prompt_blocks():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, content, block_order FROM prompt_blocks ORDER BY block_order ASC')
    blocks = c.fetchall()
    conn.close()
    return blocks

def add_prompt_block(content, block_order):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO prompt_blocks (content, block_order) VALUES (?, ?)', (content, block_order))
    block_id = c.lastrowid
    conn.commit()
    conn.close()
    return block_id

def delete_prompt_block(block_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM prompt_blocks WHERE id = ?', (block_id,))
    conn.commit()
    conn.close()

def update_prompt_block(block_id, content):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE prompt_blocks SET content = ? WHERE id = ?', (content, block_id))
    conn.commit()
    conn.close()

def reorder_prompt_block(block_id, new_order):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE prompt_blocks SET block_order = ? WHERE id = ?', (new_order, block_id))
    conn.commit()
    conn.close()

def clear_prompt_blocks():
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM prompt_blocks')
    conn.commit()
    conn.close()

def reorder_blocks(block_id, new_position):
    conn = get_connection()
    c = conn.cursor()
    blocks = get_prompt_blocks()
    num_blocks = len(blocks)
    
    if new_position <= 0:
        new_position = 1
    elif new_position > num_blocks:
        new_position = num_blocks
    
    current_blocks = sorted(blocks, key=lambda x: x[2])
    for i, block in enumerate(current_blocks, 1):
        if block[0] == block_id:
            c.execute('UPDATE prompt_blocks SET block_order = ? WHERE id = ?', (new_position, block_id))
        elif i >= new_position:
            c.execute('UPDATE prompt_blocks SET block_order = ? WHERE id = ?', (i + 1 if i < new_position else i, block[0]))
        else:
            c.execute('UPDATE prompt_blocks SET block_order = ? WHERE id = ?', (i, block[0]))
    
    conn.commit()
    conn.close()

# ---- HELPER FUNCTIONS FOR TAGS ----

def get_all_tags():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, name FROM tags ORDER BY name')
    tags = c.fetchall()
    conn.close()
    return tags

def add_tag(name):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (name,))
    conn.commit()
    conn.close()

def delete_tag(tag_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM block_tags WHERE tag_id = ?', (tag_id,))
    c.execute('DELETE FROM tags WHERE id = ?', (tag_id,))
    conn.commit()
    conn.close()

def update_tag(tag_id, name):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE tags SET name = ? WHERE id = ?', (name, tag_id))
    conn.commit()
    conn.close()

def assign_tag_to_block(block_id, tag_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO block_tags (block_id, tag_id) VALUES (?, ?)', (block_id, tag_id))
    conn.commit()
    conn.close()

def get_tags_for_block(block_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT t.id, t.name FROM tags t JOIN block_tags bt ON t.id = bt.tag_id WHERE bt.block_id = ?', (block_id,))
    tags = c.fetchall()
    conn.close()
    return tags

# ---- HELPER FUNCTIONS FOR REPO PROFILES ----

def save_repo_profile(repo_path, repo_name, files, selected_files):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO repos (path, name) VALUES (?, ?)', (repo_path, repo_name))
    repo_id = c.lastrowid if c.lastrowid else c.execute('SELECT id FROM repos WHERE path = ?', (repo_path,)).fetchone()[0]
    c.execute('DELETE FROM repo_files WHERE repo_id = ?', (repo_id,))
    for file_path in files:
        is_selected = 1 if file_path in selected_files else 0
        c.execute('INSERT INTO repo_files (repo_id, file_path, is_selected) VALUES (?, ?, ?)', (repo_id, file_path, is_selected))
    conn.commit()
    conn.close()
    return repo_id

def get_repo_profile(repo_path):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id FROM repos WHERE path = ?', (repo_path,))
    repo_id = c.fetchone()
    if not repo_id:
        conn.close()
        return None
    repo_id = repo_id[0]
    c.execute('SELECT file_path, is_selected FROM repo_files WHERE repo_id = ?', (repo_id,))
    files = c.fetchall()
    conn.close()
    return {'repo_id': repo_id, 'files': [(f[0], f[1]) for f in files]}

# ---- EXPORT FUNCTION ----

def export_to_csv():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('SELECT id, name, content FROM reusable_prompts')
    with open('reusable_prompts.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'name', 'content'])
        writer.writerows(c.fetchall())
    
    c.execute('SELECT id, name FROM tags')
    with open('tags.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'name'])
        writer.writerows(c.fetchall())
    
    conn.close()