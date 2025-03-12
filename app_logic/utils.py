# app_logic/utils.py

import socket
from pathlib import Path

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

# ============================================================================
# Detailed Documentation
# ============================================================================
#
# Purpose:
#   Provides utility functions for network operations and secure file path handling
#   across the Codeprinter application.
#
# Design Intent:
#   - **Reusability**: Groups general-purpose helpers for use in multiple modules.
#   - **Security**: Implements `safe_path` to prevent directory traversal attacks.
#   - **Flexibility**: Enables dynamic port selection for development environments.
#
# How It Works:
#   - **find_open_port**:
#     1. Starts at `start_port` (default 5000).
#     2. Attempts to bind a socket, incrementing the port until successful or `max_tries` is reached.
#     3. Raises an error if no port is available.
#   - **safe_path**:
#     1. Constructs an absolute path from `base_path` and `rel_path`.
#     2. Verifies the path stays within `base_path` to block traversal.
#     3. Returns the resolved path or raises an error.
#
# Integration with Broader Repo:
#   - **app.py**: Uses `find_open_port` to select a free port for the Flask server.
#   - **routes.py**: Employs `safe_path` in `file_contents` for secure local file access.
#   - Enhances security and usability, aligning with Codeprinter’s goal of safe codebase exploration.
#
# Notes:
#   - `find_open_port` is ideal for development; production may use a fixed port.
#   - `safe_path` uses `Path.resolve()` to normalize paths, handling symlinks safely.