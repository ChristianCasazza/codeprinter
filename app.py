# app.py

import os
import re
import json
from flask import Flask, render_template, request, jsonify, send_file
import requests
from io import BytesIO
import zipfile

app = Flask(__name__)

##############################################################################
# 1) Serve the main page
##############################################################################
@app.route("/")
def index():
    """Serve the front-end HTML."""
    return render_template("index.html")


##############################################################################
# 2) Local Mode: Build directory tree from a given path
##############################################################################
@app.route("/api/local-tree", methods=["POST"])
def local_tree():
    """
    Expects JSON body: { "localPath": "/home/user/myrepo" }
    Returns JSON: a list of file objects 
      [ 
        {
          "path": "folder/file.txt",
          "type": "blob",
          "urlType": "local"
        }, ...
      ]

    Skips .venv, node_modules, .git, .vscode, .evidence, target folders.
    """
    data = request.get_json()
    local_path = data.get("localPath", "").strip()
    if not local_path:
        return jsonify({"error": "No path provided"}), 400

    if not os.path.exists(local_path):
        return jsonify({"error": f"Path does not exist: {local_path}"}), 404

    skip_dirs = {".venv", "node_modules", ".git", ".vscode", ".evidence", "target"}
    result_tree = []
    for root, dirs, files in os.walk(local_path):
        # Remove the skip_dirs from the directory list
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for filename in files:
            rel_path = os.path.relpath(os.path.join(root, filename), start=local_path)
            rel_path = rel_path.replace("\\", "/")  # unify path separators
            result_tree.append({
                "path": rel_path,
                "type": "blob",
                "urlType": "local"
            })

    return jsonify(result_tree)


##############################################################################
# 3) Local Mode: Return the contents of selected files
##############################################################################
@app.route("/api/local-file-contents", methods=["POST"])
def local_file_contents():
    data = request.get_json()
    local_path = data.get("localPath", "").strip()
    files = data.get("files", [])

    if not os.path.exists(local_path):
        return jsonify({"error": f"Path not found: {local_path}"}), 404

    contents = []
    for rel_path in files:
        abs_path = os.path.join(local_path, rel_path)
        if not os.path.exists(abs_path):
            continue
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            contents.append({
                "path": rel_path,
                "text": text
            })
        except Exception as e:
            contents.append({
                "path": rel_path,
                "text": f"Error reading file: {e}"
            })

    return jsonify(contents)


##############################################################################
# 4) Local Mode: Download Zip of selected files
##############################################################################
@app.route("/api/local-zip", methods=["POST"])
def local_zip():
    data = request.get_json()
    local_path = data.get("localPath", "").strip()
    files = data.get("files", [])

    if not os.path.exists(local_path):
        return jsonify({"error": f"Path not found: {local_path}"}), 404

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path in files:
            abs_path = os.path.join(local_path, rel_path)
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                zf.write(abs_path, arcname=rel_path)
    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="partial_repo.zip"
    )


##############################################################################
# 5) GitHub Mode: Fetch Directory Structure (tree)
##############################################################################
@app.route("/api/github-tree", methods=["POST"])
def github_tree():
    data = request.get_json()
    repo_url = data.get("repoUrl", "").strip()
    token = data.get("accessToken", "").strip()

    try:
        owner, repo, last_string = parse_repo_url(repo_url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # fetch refs
    branches, tags = get_github_refs(owner, repo, token)
    all_refs = branches + tags
    ref_found = ""
    path_found = ""
    for possible_ref in all_refs:
        if last_string.startswith(possible_ref):
            ref_found = possible_ref
            path_found = last_string[len(possible_ref)+1:]
            break

    if not ref_found:
        ref_found = last_string

    # fetch sha
    sha = fetch_repo_sha(owner, repo, ref_found, path_found, token)
    # fetch tree
    tree = fetch_repo_tree(owner, repo, sha, token)

    # convert to simpler format
    result_tree = []
    for item in tree:
        if item["type"] == "blob":
            result_tree.append({
                "path": item["path"],
                "type": "blob",
                "urlType": "github",
                "url": item["url"]
            })
    return jsonify(result_tree)


##############################################################################
# 6) GitHub Mode: Fetch File Contents
##############################################################################
@app.route("/api/github-file-contents", methods=["POST"])
def github_file_contents():
    data = request.get_json()
    token = data.get("accessToken", "").strip()
    files = data.get("files", [])

    result = []
    for f in files:
        url = f["url"]
        path = f["path"]
        try:
            text = fetch_github_file(url, token)
            result.append({"path": path, "text": text})
        except Exception as e:
            result.append({"path": path, "text": f"Error: {e}"})
    return jsonify(result)


##############################################################################
# 7) GitHub Mode: Download ZIP of selected files
##############################################################################
@app.route("/api/github-zip", methods=["POST"])
def github_zip():
    data = request.get_json()
    token = data.get("accessToken", "").strip()
    files = data.get("files", [])

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            url = f["url"]
            path = f["path"]
            try:
                text = fetch_github_file(url, token)
                zf.writestr(path, text)
            except Exception as e:
                zf.writestr(path, f"Error fetching file: {e}")
    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="partial_repo.zip"
    )


##############################################################################
# Helper functions for GitHub logic
##############################################################################
def parse_repo_url(url: str):
    pattern = r"^https://github\.com/([^/]+)/([^/]+)(/tree/(.+))?$"
    match = re.match(pattern, url)
    if not match:
        raise ValueError("Invalid GitHub URL. Must be https://github.com/owner/repo or /tree/branch/path")
    owner = match.group(1)
    repo = match.group(2)
    last_string = match.group(4) or ""
    return (owner, repo, last_string)

def get_github_refs(owner, repo, token):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    branches_url = f"https://api.github.com/repos/{owner}/{repo}/git/matching-refs/heads/"
    tags_url = f"https://api.github.com/repos/{owner}/{repo}/git/matching-refs/tags/"
    branches_resp = requests.get(branches_url, headers=headers)
    tags_resp = requests.get(tags_url, headers=headers)
    if not branches_resp.ok or not tags_resp.ok:
        raise ValueError("Could not fetch references (branches/tags)")
    branches = [b["ref"].split("/", 2)[2] for b in branches_resp.json()]
    tags = [t["ref"].split("/", 2)[2] for t in tags_resp.json()]
    return branches, tags

def fetch_repo_sha(owner, repo, ref, path, token):
    headers = {"Accept": "application/vnd.github.object+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/"
    if path:
        url += path
    if ref:
        url += f"?ref={ref}"
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        handle_github_error(resp)
    data = resp.json()
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
    return data["tree"]

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
        raise ValueError("GitHub API rate limit exceeded. Provide a valid token or wait.")
    elif response.status_code == 404:
        raise ValueError("Not found. Check URL/branch/path.")
    else:
        raise ValueError(f"GitHub request failed. Status: {response.status_code}")


if __name__ == "__main__":
    app.run(debug=True)