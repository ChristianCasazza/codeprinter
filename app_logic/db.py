"""Light‑weight helper that gives every part of the app the same, safe DB
connection without repeating boiler‑plate."""

from contextlib import contextmanager
import sqlite3

from .config import DB_PATH


@contextmanager
def get_db():
    """Yield a SQLite connection with sensible defaults.

    * rows are dict‑like (`sqlite3.Row`)
    * foreign keys are enforced
    * commit on success, rollback on exception
    """
    conn = sqlite3.connect(
        DB_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
        conn.commit()
    except Exception:  # noqa: BLE001
        conn.rollback()
        raise
    finally:
        conn.close()
