# app_logic/config.py

import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()
# Move up one directory from app_logic/ to the root (codeprinter/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))  # Explicitly set template folder to root/templates/
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DB_PATH = os.path.join(BASE_DIR, "codeprinter.db")  # Database at root level

# ============================================================================
# Detailed Documentation
# ============================================================================
#
# Purpose:
#   This module centralizes configuration settings and Flask app initialization for
#   the Codeprinter application, ensuring consistent access to global variables and
#   the app instance across backend modules.
#
# Design Intent:
#   - **Centralization**: Consolidates configuration (e.g., Flask app, tokens, paths)
#     in one file for easy updates.
#   - **Consistency**: Anchors DB_PATH and template folder to the root directory
#     (where app.py resides), avoiding issues with execution context or relative paths.
#   - **Reusability**: Exports key variables and the app instance for use in other
#     modules (e.g., routes.py, database.py).
#
# How It Works:
#   1. Loads environment variables from a `.env` file using `python-dotenv`.
#   2. Sets `BASE_DIR` to the parent directory of app_logic/ (i.e., codeprinter/),
#      ensuring paths are rooted at the application level.
#   3. Initializes the Flask app instance with an explicit `template_folder` path
#      pointing to codeprinter/templates/.
#   4. Retrieves `GITHUB_TOKEN` from the environment for GitHub API authentication.
#   5. Constructs `DB_PATH` to point to `codeprinter.db` in the root directory.
#
# Integration with Broader Repo:
#   - **app.py**: Uses the `app` instance to run the Flask server and calls `init_db`.
#   - **routes.py**: Imports `app` to register routes and uses `GITHUB_TOKEN` and `DB_PATH`.
#   - **database.py**: Uses `DB_PATH` for SQLite connections.
#   - **github_api.py**: Accesses `GITHUB_TOKEN` for API requests.
#   - Acts as the foundational layer, enabling modular backend development with correct
#     template and database resolution.
#
# Notes:
#   - `BASE_DIR` uses `os.path.dirname` twice to move up from app_logic/ to codeprinter/,
#     aligning with the intent for `DB_PATH` and templates to be at the root.
#   - The `template_folder` parameter ensures Flask finds `templates/` regardless of
#     the working directory or module location.
#   - `GITHUB_TOKEN` is optional; routes handle its absence by prompting for a user-provided token.