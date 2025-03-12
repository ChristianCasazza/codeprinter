# app_logic/github_api.py

import re
import requests
from .config import GITHUB_TOKEN

def parse_repo_url(url: str):
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
    
    # Add timeout to prevent long-running requests
    # Add streaming to start processing data immediately
    with requests.get(file_url, headers=headers, stream=True, timeout=10) as resp:
        if not resp.ok:
            handle_github_error(resp)
        
        # Use a size limit to prevent extremely large files
        max_size = 5 * 1024 * 1024  # 5MB limit
        content = ""
        total_size = 0
        
        for chunk in resp.iter_content(chunk_size=8192, decode_unicode=True):
            if chunk:
                total_size += len(chunk)
                if total_size > max_size:
                    return content + "\n\n[...File truncated due to size...]"
                content += chunk
        
        return content

def handle_github_error(response):
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        reset_time = response.headers.get("X-RateLimit-Reset", "unknown time")
        raise ValueError(f"GitHub API rate limit exceeded. Retry after {reset_time}.")
    elif response.status_code == 404:
        raise ValueError("Repository, branch, or path not found. Check URL.")
    else:
        raise ValueError(f"GitHub request failed: {response.status_code} - {response.text}")

# ============================================================================
# Detailed Documentation
# ============================================================================
#
# Purpose:
#   Encapsulates all GitHub API interactions for Codeprinter, providing functions to
#   parse URLs, fetch repository metadata, and retrieve file contents.
#
# Design Intent:
#   - **Specialization**: Isolates GitHub-specific logic from local file handling and
#     database operations.
#   - **Robustness**: Centralizes error handling in `handle_github_error` for consistent
#     error reporting.
#   - **Modularity**: Enables easy updates to GitHub API calls without affecting other code.
#
# How It Works:
#   - **parse_repo_url**: Parses GitHub URLs into owner, repo, and branch/path components.
#   - **get_github_refs**: Retrieves branches and tags from a repository.
#   - **get_repo_default_branch**: Fetches the default branch (e.g., "main").
#   - **fetch_repo_sha**: Gets the SHA for a specific ref and path.
#   - **fetch_repo_tree**: Retrieves a recursive file tree for a given SHA.
#   - **fetch_github_file**: Downloads raw file content from a GitHub URL.
#   - **handle_github_error**: Processes HTTP errors with descriptive messages.
#
# Integration with Broader Repo:
#   - **routes.py**: Uses these functions in `github_tree` and `file_contents` for GitHub
#     data retrieval.
#   - **config.py**: Relies on `GITHUB_TOKEN` for authentication, with fallback to UI input.
#   - Supports Codeprinter’s goal of exploring GitHub-hosted codebases seamlessly.
#
# Notes:
#   - Functions prioritize token usage for higher rate limits and private repo access.
#   - Error handling ensures `ValueError` exceptions are raised for `routes.py` to catch.
#   - The URL parsing regex is strict, complementing the trailing slash fix in `github_tree`.