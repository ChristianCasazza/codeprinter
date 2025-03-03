# app.py

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "flask",
#     "requests",
#     "python-dotenv",
# ]
# ///
import os
import re
import socket
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DB_PATH = "codeprinter.db"

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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_id INTEGER NOT NULL,
        path TEXT NOT NULL,
        url_type TEXT NOT NULL,
        url TEXT,
        FOREIGN KEY (repo_id) REFERENCES repositories(id),
        UNIQUE(repo_id, path)
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
        file_id INTEGER NOT NULL,
        FOREIGN KEY (grouping_id) REFERENCES groupings(id),
        FOREIGN KEY (file_id) REFERENCES files(id),
        UNIQUE(grouping_id, file_id)
    )''')
    conn.commit()
    conn.close()

def find_open_port(start_port=5000, max_tries=100):
    port = start_port
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError(f"No open port found after {max_tries} tries from {start_port}.")

def safe_path(base_path, rel_path):
    abs_path = Path(base_path).resolve() / rel_path
    if not str(abs_path).startswith(str(Path(base_path).resolve())):
        raise ValueError("Invalid path: directory traversal detected")
    return abs_path

@app.route("/")
def index():
    return render_template("index.html", has_github_token=bool(GITHUB_TOKEN))

@app.route("/api/local-tree", methods=["POST"])
def local_tree():
    data = request.get_json()
    local_path = data.get("localPath", "").strip()
    if not local_path:
        return jsonify({"error": "No path provided"}), 400
    if not os.path.exists(local_path):
        return jsonify({"error": f"Path does not exist: {local_path}"}), 404

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

    c.execute("SELECT id, path, url_type, url FROM files WHERE repo_id = ?", (repo_id,))
    result_tree = [{"id": row[0], "path": row[1], "type": "blob", "urlType": row[2], "url": row[3]} for row in c.fetchall()]
    conn.close()
    return jsonify(result_tree)

@app.route("/api/github-tree", methods=["POST"])
def github_tree():
    data = request.get_json()
    repo_url = data.get("repoUrl", "").strip()
    token = GITHUB_TOKEN if GITHUB_TOKEN else data.get("accessToken", "").strip()
    if not repo_url:
        return jsonify({"error": "No repository URL provided"}), 400

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

        # If no branch/path specified, fetch the repo's default branch
        if not last_string:
            try:
                ref_found = get_repo_default_branch(owner, repo, token)
                path_found = ""
            except ValueError as e:
                # Fallback to 'main' if something goes wrong
                ref_found = "main"
                path_found = ""
        else:
            # Attempt to match a known branch
            for ref in all_refs:
                if last_string.startswith(ref):
                    ref_found = ref
                    path_found = last_string[len(ref):].strip("/")
                    break

            if not ref_found:
                # If we have something like "branch/some/path"
                possible_branch = last_string.split("/", 1)[0]
                if possible_branch in all_refs:
                    ref_found = possible_branch
                    path_found = last_string[len(possible_branch):].strip("/")
                else:
                    # If the entire last_string isn't in refs, fallback to default branch or 'main'
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

        c.execute("SELECT id, path, url_type, url FROM files WHERE repo_id = ?", (repo_id,))
        result_tree = [{"id": row[0], "path": row[1], "type": "blob", "urlType": row[2], "url": row[3]} for row in c.fetchall()]
        conn.close()
        return jsonify(result_tree)
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
    file_ids = data.get("fileIds", [])
    token = GITHUB_TOKEN if GITHUB_TOKEN else data.get("accessToken", "").strip()

    if not repo_identifier or not file_ids:
        return jsonify({"error": "Missing repository identifier or file IDs"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    repo = c.execute("SELECT id, type FROM repositories WHERE identifier = ?", (repo_identifier,)).fetchone()
    if not repo:
        conn.close()
        return jsonify({"error": "Repository not found"}), 404
    repo_id, repo_type = repo

    query_placeholders = ",".join("?" for _ in file_ids)
    c.execute(f"SELECT id, path, url_type, url FROM files WHERE repo_id = ? AND id IN ({query_placeholders})",
              (repo_id, *file_ids))
    files = [{"id": row[0], "path": row[1], "urlType": row[2], "url": row[3]} for row in c.fetchall()]
    conn.close()

    contents = []
    for f in files:
        try:
            if f["urlType"] == "local":
                abs_path = safe_path(repo_identifier, f["path"])
                if not abs_path.exists():
                    contents.append({"path": f["path"], "text": f"File not found: {f['path']}"})
                    continue
                with open(abs_path, "r", encoding="utf-8", errors="replace") as file:
                    text = file.read()
            else:
                text = fetch_github_file(f["url"], token)
            contents.append({"path": f["path"], "text": text})
        except Exception as e:
            contents.append({"path": f["path"], "text": f"Error: {e}"})
    return jsonify(contents)

@app.route("/api/save-grouping", methods=["POST"])
def save_grouping():
    data = request.get_json()
    repo_identifier = data.get("repoIdentifier", "").strip()
    grouping_name = data.get("groupingName", "").strip()
    file_ids = data.get("fileIds", [])

    if not repo_identifier or not grouping_name or not file_ids:
        return jsonify({"error": "Missing repository identifier, grouping name, or file IDs"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    repo = c.execute("SELECT id FROM repositories WHERE identifier = ?", (repo_identifier,)).fetchone()
    if not repo:
        conn.close()
        return jsonify({"error": "Repository not found"}), 404
    repo_id = repo[0]

    c.execute("INSERT OR REPLACE INTO groupings (repo_id, name) VALUES (?, ?)", (repo_id, grouping_name))
    grouping_id = c.execute("SELECT id FROM groupings WHERE repo_id = ? AND name = ?", (repo_id, grouping_name)).fetchone()[0]

    c.execute("DELETE FROM grouping_files WHERE grouping_id = ?", (grouping_id,))
    c.executemany("INSERT OR IGNORE INTO grouping_files (grouping_id, file_id) VALUES (?, ?)",
                  [(grouping_id, fid) for fid in file_ids])
    conn.commit()
    conn.close()
    return jsonify({"message": f"Grouping '{grouping_name}' saved successfully"})

@app.route("/api/get-groupings", methods=["POST"])
def get_groupings():
    data = request.get_json()
    repo_identifier = data.get("repoIdentifier", "").strip()
    if not repo_identifier:
        return jsonify({"error": "Missing repository identifier"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    repo = c.execute("SELECT id FROM repositories WHERE identifier = ?", (repo_identifier,)).fetchone()
    if not repo:
        conn.close()
        return jsonify({"groupings": []})
    repo_id = repo[0]

    c.execute("SELECT id, name FROM groupings WHERE repo_id = ?", (repo_id,))
    groupings = [{"id": row[0], "name": row[1]} for row in c.fetchall()]

    result = []
    for g in groupings:
        c.execute("SELECT f.id, f.path, f.url_type, f.url FROM files f JOIN grouping_files gf ON f.id = gf.file_id WHERE gf.grouping_id = ?", (g["id"],))
        files = [{"id": row[0], "path": row[1], "type": "blob", "urlType": row[2], "url": row[3]} for row in c.fetchall()]
        result.append({"name": g["name"], "files": files})
    conn.close()
    return jsonify({"groupings": result})

def parse_repo_url(url: str):
    """
    Updated parser that handles GitHub URLs like:
      https://github.com/owner/repo
      https://github.com/owner/repo/tree/branch
      https://github.com/owner/repo/tree/branch/subdir
    """
    pattern = r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)(?:/tree/(?P<branch>[^/]+)(?:/(?P<subpath>.*))?)?$"
    match = re.match(pattern, url)
    if not match:
        raise ValueError("Invalid GitHub URL. Must be in the form: https://github.com/owner/repo or /tree/branch/path")

    owner = match.group("owner")
    repo = match.group("repo")
    branch = match.group("branch") or ""
    subpath = match.group("subpath") or ""

    if branch:
        last_string = branch
        if subpath:
            last_string += "/" + subpath
    else:
        last_string = ""

    return owner, repo, last_string

def get_github_refs(owner, repo, token):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    branches_url = f"https://api.github.com/repos/{owner}/{repo}/git/matching-refs/heads/"
    tags_url = f"https://api.github.com/repos/{owner}/{repo}/git/matching-refs/tags/"
    try:
        branches_resp = requests.get(branches_url, headers=headers)
        tags_resp = requests.get(tags_url, headers=headers)
        if not branches_resp.ok:
            handle_github_error(branches_resp)
        if not tags_resp.ok:
            handle_github_error(tags_resp)
        branches_data = branches_resp.json()
        tags_data = tags_resp.json()
        if not isinstance(branches_data, list) or not isinstance(tags_data, list):
            raise ValueError("GitHub API returned invalid data for refs")
        branches = [b["ref"].split("/", 2)[2] for b in branches_data]
        tags = [t["ref"].split("/", 2)[2] for t in tags_data]
        return branches, tags
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch refs: {str(e)}")

def get_repo_default_branch(owner, repo, token):
    """
    Fetch the default branch for the repository (often 'main' or 'master').
    Fallback to 'main' if not found.
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        handle_github_error(resp)
    data = resp.json()
    return data.get("default_branch", "main")

def fetch_repo_sha(owner, repo, ref, path, token):
    headers = {"Accept": "application/vnd.github.object+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/"
    if path:
        url += path
    if ref:
        separator = "&" if "?" in url else "?"
        url += f"{separator}ref={ref}"
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        handle_github_error(resp)
    data = resp.json()
    if isinstance(data, list):
        return data[0]["sha"] if data else None
    return data["sha"]

def fetch_repo_tree(owner, repo, sha, token):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1"
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        handle_github_error(resp)
    data = resp.json()
    return data.get("tree", [])

def fetch_github_file(file_url, token):
    headers = {"Accept": "application/vnd.github.v3.raw"}
    if token:
        headers["Authorization"] = f"token {token}"
    resp = requests.get(file_url, headers=headers)
    if not resp.ok:
        handle_github_error(resp)
    return resp.text

def handle_github_error(response):
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        reset_time = response.headers.get("X-RateLimit-Reset", "unknown time")
        raise ValueError(f"GitHub API rate limit exceeded. Retry after {reset_time}.")
    elif response.status_code == 404:
        raise ValueError("Repository, branch, or path not found. Check URL.")
    else:
        raise ValueError(f"GitHub request failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    init_db()
    port = find_open_port()
    print(f"Running on http://localhost:{port}")
    app.run(debug=True, port=port)
