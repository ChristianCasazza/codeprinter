import os
import json
from datetime import datetime
import sqlite3
import concurrent.futures
from flask import request, jsonify, render_template
from .config import app, GITHUB_TOKEN, DB_PATH
from .utils import safe_path
from .github_api import (parse_repo_url, get_github_refs, get_repo_default_branch,
                         fetch_repo_sha, fetch_repo_tree, fetch_github_file)
from .database import (save_path_history, get_path_history, save_selection, get_last_selection,
                      get_file_formats, add_file_format, update_file_format,
                      delete_file_format, update_file_format_order)

@app.route("/")
def index():
    return render_template("index.html", has_github_token=bool(GITHUB_TOKEN))

@app.route("/api/get-saved-paths", methods=["POST"])
def get_saved_paths():
    """API endpoint to retrieve saved path history"""
    data = request.get_json()
    path_type = data.get("type", "").strip()
    
    if not path_type or path_type not in ["github", "local"]:
        return jsonify({"error": "Invalid path type"}), 400
        
    paths = get_path_history(path_type)
    return jsonify({"paths": paths})

@app.route("/api/local-tree", methods=["POST"])
def local_tree():
    data = request.get_json()
    local_path = data.get("localPath", "").strip()
    if not local_path:
        return jsonify({"error": "No path provided"}), 400
    if not os.path.exists(local_path):
        return jsonify({"error": f"Path does not exist: {local_path}"}), 404

    # Save this path to history for future use
    save_path_history("local", local_path)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO repositories (type, identifier, last_updated) VALUES (?, ?, ?)",
              ("local", local_path, datetime.now()))
    repo_id = c.execute("SELECT id FROM repositories WHERE identifier = ?", (local_path,)).fetchone()[0]

    c.execute("DELETE FROM files WHERE repo_id = ?", (repo_id,))
    skip_dirs = {".venv", "node_modules", ".git", ".vscode", ".evidence", "target"}
    files_to_insert = []
    for root, dirs, files in os.walk(local_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for filename in files:
            rel_path = os.path.relpath(os.path.join(root, filename), start=local_path).replace("\\", "/")
            files_to_insert.append((repo_id, rel_path, "local", None))

    c.executemany("INSERT OR IGNORE INTO files (repo_id, path, url_type, url) VALUES (?, ?, ?, ?)", files_to_insert)
    conn.commit()

    c.execute("SELECT repo_id, path, url_type, url FROM files WHERE repo_id = ?", (repo_id,))
    result_tree = [{"repoId": row[0], "path": row[1], "type": "blob", "urlType": row[2], "url": row[3]} for row in c.fetchall()]
    
    # Get last selection for this repo if it exists
    last_selection = get_last_selection(repo_id)
    
    conn.close()
    return jsonify({
        "tree": result_tree,
        "repoId": repo_id,
        "lastSelection": last_selection
    })

@app.route("/api/github-tree", methods=["POST"])
def github_tree():
    data = request.get_json()
    repo_url = data.get("repoUrl", "").strip().rstrip("/")
    token = GITHUB_TOKEN if GITHUB_TOKEN else data.get("accessToken", "").strip()
    if not repo_url:
        return jsonify({"error": "No repository URL provided"}), 400

    # Save this GitHub repo URL to history
    save_path_history("github", repo_url)

    try:
        owner, repo, last_string = parse_repo_url(repo_url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO repositories (type, identifier, last_updated) VALUES (?, ?, ?)",
              ("github", repo_url, datetime.now()))
    repo_id = c.execute("SELECT id FROM repositories WHERE identifier = ?", (repo_url,)).fetchone()[0]

    try:
        branches, tags = get_github_refs(owner, repo, token)
        if not isinstance(branches, list) or not isinstance(tags, list):
            return jsonify({"error": "Failed to retrieve valid branches or tags from GitHub"}), 500

        all_refs = branches + tags
        ref_found, path_found = None, None

        if not last_string:
            try:
                ref_found = get_repo_default_branch(owner, repo, token)
                path_found = ""
            except ValueError:
                ref_found = "main"
                path_found = ""
        else:
            for ref in all_refs:
                if last_string.startswith(ref):
                    ref_found = ref
                    path_found = last_string[len(ref):].strip("/")
                    break

            if not ref_found:
                possible_branch = last_string.split("/", 1)[0]
                if possible_branch in all_refs:
                    ref_found = possible_branch
                    path_found = last_string[len(possible_branch):].strip("/")
                else:
                    try:
                        if last_string in all_refs:
                            ref_found = last_string
                            path_found = ""
                        else:
                            ref_found = get_repo_default_branch(owner, repo, token)
                            path_found = last_string
                    except ValueError:
                        ref_found = "main"
                        path_found = last_string

        sha = fetch_repo_sha(owner, repo, ref_found, path_found, token)
        tree = fetch_repo_tree(owner, repo, sha, token)

        c.execute("DELETE FROM files WHERE repo_id = ?", (repo_id,))
        files_to_insert = [(repo_id, item["path"], "github", item["url"]) for item in tree if item["type"] == "blob"]
        c.executemany("INSERT OR IGNORE INTO files (repo_id, path, url_type, url) VALUES (?, ?, ?, ?)", files_to_insert)
        conn.commit()

        c.execute("SELECT repo_id, path, url_type, url FROM files WHERE repo_id = ?", (repo_id,))
        result_tree = [{"repoId": row[0], "path": row[1], "type": "blob", "urlType": row[2], "url": row[3]} for row in c.fetchall()]
        
        # Get last selection for this repo if it exists
        last_selection = get_last_selection(repo_id)
        
        conn.close()
        return jsonify({
            "tree": result_tree,
            "repoId": repo_id,
            "lastSelection": last_selection
        })
    except ValueError as e:
        conn.close()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Unexpected error fetching GitHub tree: {str(e)}"}), 500

@app.route("/api/file-contents", methods=["POST"])
def file_contents():
    data = request.get_json()
    repo_identifier = data.get("repoIdentifier", "").strip()
    file_paths = data.get("filePaths", [])
    token = GITHUB_TOKEN if GITHUB_TOKEN else data.get("accessToken", "").strip()

    if not repo_identifier or not file_paths:
        return jsonify({"error": "Missing repository identifier or file paths"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    repo = c.execute("SELECT id, type FROM repositories WHERE identifier = ?", (repo_identifier,)).fetchone()
    if not repo:
        conn.close()
        return jsonify({"error": "Repository not found"}), 404
    repo_id, repo_type = repo

    query_placeholders = ",".join("?" for _ in file_paths)
    c.execute(f"SELECT repo_id, path, url_type, url FROM files WHERE repo_id = ? AND path IN ({query_placeholders})",
              (repo_id, *file_paths))
    files = [{"repoId": row[0], "path": row[1], "urlType": row[2], "url": row[3]} for row in c.fetchall()]
    conn.close()

    def fetch_file_content(file_info):
        try:
            if file_info["urlType"] == "local":
                abs_path = safe_path(repo_identifier, file_info["path"])
                if not abs_path.exists():
                    return {"path": file_info["path"], "text": f"File not found: {file_info['path']}"}
                with open(abs_path, "r", encoding="utf-8", errors="replace") as file:
                    text = file.read()
            else:
                text = fetch_github_file(file_info["url"], token)
            return {"path": file_info["path"], "text": text}
        except Exception as e:
            return {"path": file_info["path"], "text": f"Error: {e}"}

    # Use concurrent processing for faster file fetching (especially for GitHub files)
    contents = []
    # Use a smaller number of workers for GitHub to prevent API rate limits
    max_workers = 5 if repo_type == "github" else 10
    
    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all file fetching tasks
        futures = [executor.submit(fetch_file_content, f) for f in files]
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(futures):
            contents.append(future.result())
    
    # Sort contents by path to maintain consistent order
    contents.sort(key=lambda x: x["path"])
    return jsonify(contents)

@app.route("/api/save-grouping", methods=["POST"])
def save_grouping():
    data = request.get_json()
    repo_identifier = data.get("repoIdentifier", "").strip()
    grouping_name = data.get("groupingName", "").strip()
    file_paths = data.get("filePaths", [])

    if not repo_identifier or not grouping_name or not file_paths:
        return jsonify({"error": "Missing repository identifier, grouping name, or file paths"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        repo = c.execute("SELECT id FROM repositories WHERE identifier = ?", (repo_identifier,)).fetchone()
        if not repo:
            return jsonify({"error": "Repository not found"}), 404
        repo_id = repo[0]

        c.execute("INSERT OR REPLACE INTO groupings (repo_id, name) VALUES (?, ?)", (repo_id, grouping_name))
        grouping_id = c.execute("SELECT id FROM groupings WHERE repo_id = ? AND name = ?", (repo_id, grouping_name)).fetchone()[0]

        c.execute("DELETE FROM grouping_files WHERE grouping_id = ?", (grouping_id,))
        c.executemany("INSERT OR IGNORE INTO grouping_files (grouping_id, repo_id, path) VALUES (?, ?, ?)",
                      [(grouping_id, repo_id, path) for path in file_paths])
        conn.commit()
        return jsonify({"message": f"Grouping '{grouping_name}' saved successfully"})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@app.route("/api/get-groupings", methods=["POST"])
def get_groupings():
    data = request.get_json()
    repo_identifier = data.get("repoIdentifier", "").strip()
    if not repo_identifier:
        return jsonify({"error": "Missing repository identifier"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        repo = c.execute("SELECT id FROM repositories WHERE identifier = ?", (repo_identifier,)).fetchone()
        if not repo:
            return jsonify({"groupings": []})
        repo_id = repo[0]

        c.execute("SELECT id, name FROM groupings WHERE repo_id = ?", (repo_id,))
        groupings = [{"id": row[0], "name": row[1]} for row in c.fetchall()]

        result = []
        for g in groupings:
            c.execute("SELECT f.repo_id, f.path, f.url_type, f.url FROM files f JOIN grouping_files gf ON f.repo_id = gf.repo_id AND f.path = gf.path WHERE gf.grouping_id = ?", (g["id"],))
            files = [{"repoId": row[0], "path": row[1], "type": "blob", "urlType": row[2], "url": row[3]} for row in c.fetchall()]
            result.append({"name": g["name"], "files": files})
        return jsonify({"groupings": result})
    except sqlite3.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()
        
@app.route("/api/save-selection", methods=["POST"])
def save_current_selection():
    """Save the current file selection for a repository"""
    data = request.get_json()
    repo_id = data.get("repoId")
    selection = data.get("selection")
    
    if not repo_id or not isinstance(selection, list):
        return jsonify({"error": "Missing repo ID or invalid selection data"}), 400
        
    try:
        # Convert selection to JSON string
        selection_json = json.dumps(selection)
        save_selection(repo_id, selection_json)
        return jsonify({"status": "success", "message": "Selection saved"})
    except Exception as e:
        return jsonify({"error": f"Error saving selection: {str(e)}"}), 500

@app.route("/api/file-formats", methods=["GET"])
def get_all_file_formats():
    """Get all file formats"""
    try:
        formats = get_file_formats()
        print(f"API: Retrieved {len(formats)} file formats")
        return jsonify({
            "formats": formats,
            "extensions": [f["extension"] for f in formats if f["enabled"]],
            "colors": {f["extension"].lstrip('.'): f["color"] for f in formats if f["enabled"]},
            "languages": {f["extension"].lstrip('.'): f["language"] for f in formats if f["enabled"] and f["language"] and f["language"] != ""},
            "patterns": [f for f in formats if f["enabled"] and f.get("is_pattern", 0)]
        })
    except Exception as e:
        return jsonify({"error": f"Error retrieving file formats: {str(e)}"}), 500

@app.route("/api/file-formats", methods=["POST"])
def add_new_file_format():
    """Add a new file format"""
    data = request.get_json()
    print(f"Received new format data: {data}")
    
    extension = data.get("extension", "").strip()
    color = data.get("color", "").strip()
    language = data.get("language", "").strip()
    enabled = data.get("enabled", 1)
    is_pattern = data.get("is_pattern", 0)
    
    print(f"Processed format data: ext={extension}, color={color}, lang={language}, enabled={enabled}, is_pattern={is_pattern}")
    
    if not extension or not color:
        return jsonify({"error": "Extension and color are required"}), 400
    
    try:
        success = add_file_format(extension, color, language, enabled, is_pattern)
        if success:
            print(f"API: Successfully added format {extension}")
            return jsonify({"status": "success", "message": f"File format {extension} added successfully"})
        else:
            print(f"API: Failed to add format {extension}")
            return jsonify({"error": "Failed to add file format - database error"}), 500
    except Exception as e:
        import traceback
        print(f"API: Exception adding format: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": f"Error adding file format: {str(e)}"}), 500

@app.route("/api/file-formats/<int:format_id>", methods=["PUT"])
def update_existing_file_format(format_id):
    """Update an existing file format"""
    data = request.get_json()
    extension = data.get("extension")
    color = data.get("color")
    language = data.get("language")
    enabled = data.get("enabled")
    display_order = data.get("display_order")
    is_pattern = data.get("is_pattern")
    
    try:
        success = update_file_format(
            format_id, extension, color, language, enabled, display_order, is_pattern
        )
        if success:
            return jsonify({"status": "success", "message": "File format updated successfully"})
        else:
            return jsonify({"error": "File format not found or no changes made"}), 404
    except Exception as e:
        return jsonify({"error": f"Error updating file format: {str(e)}"}), 500

@app.route("/api/file-formats/<int:format_id>", methods=["DELETE"])
def remove_file_format(format_id):
    """Delete a file format"""
    try:
        success = delete_file_format(format_id)
        if success:
            return jsonify({"status": "success", "message": "File format deleted successfully"})
        else:
            return jsonify({"error": "File format not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Error deleting file format: {str(e)}"}), 500

@app.route("/api/file-formats/order", methods=["PUT"])
def reorder_file_formats():
    """Update the display order of file formats"""
    data = request.get_json()
    format_ids = data.get("formatIds", [])
    
    if not format_ids or not isinstance(format_ids, list):
        return jsonify({"error": "Format IDs must be a non-empty list"}), 400
    
    try:
        success = update_file_format_order(format_ids)
        if success:
            return jsonify({"status": "success", "message": "File format order updated successfully"})
        else:
            return jsonify({"error": "Failed to update file format order"}), 500
    except Exception as e:
        return jsonify({"error": f"Error updating file format order: {str(e)}"}), 500