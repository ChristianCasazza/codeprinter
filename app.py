# app.py

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "flask",
#     "requests",
#     "python-dotenv",
# ]
# ///

from app_logic.config import app
from app_logic.database import init_db
from app_logic.utils import find_open_port
import app_logic.routes  # Importing routes registers them with the app

if __name__ == "__main__":
    init_db()  # Initialize database
    port = find_open_port()
    print(f"Running on http://localhost:{port}")
    app.run(debug=True, port=port)