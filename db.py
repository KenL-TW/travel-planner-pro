import os
import sqlite3
from contextlib import contextmanager

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "travel_planner.db")


def ensure_db_dir():
    os.makedirs(DB_DIR, exist_ok=True)


@contextmanager
def get_conn():
    ensure_db_dir()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        cur = conn.cursor()

        # trips
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            trip_id TEXT PRIMARY KEY,
            trip_title TEXT NOT NULL,
            destination TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            currency TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

        # members (team)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            member_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT DEFAULT '',
            email TEXT DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """)

        # trip_members mapping
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trip_members (
            trip_id TEXT NOT NULL,
            member_id TEXT NOT NULL,
            PRIMARY KEY (trip_id, member_id),
            FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
            FOREIGN KEY (member_id) REFERENCES members(member_id)
        );
        """)

        # days
        cur.execute("""
        CREATE TABLE IF NOT EXISTS days (
            day_id TEXT PRIMARY KEY,
            trip_id TEXT NOT NULL,
            day_no INTEGER NOT NULL,
            date TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(trip_id, day_no),
            FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
        );
        """)

        # events
        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            trip_id TEXT NOT NULL,
            day_id TEXT NOT NULL,
            time TEXT DEFAULT '12:00',
            title TEXT DEFAULT '',
            location TEXT DEFAULT '',
            category TEXT DEFAULT '其他',
            cost REAL NOT NULL DEFAULT 0,
            notes TEXT DEFAULT '',
            tags TEXT DEFAULT '',          -- comma-separated
            created_at TEXT NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
            FOREIGN KEY (day_id) REFERENCES days(day_id)
        );
        """)

        # tasks (assignable)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            trip_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'todo',  -- todo/doing/done
            assignee_id TEXT DEFAULT NULL,
            due_date TEXT DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 3,  -- 1 high ... 5 low
            created_at TEXT NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
            FOREIGN KEY (event_id) REFERENCES events(event_id),
            FOREIGN KEY (assignee_id) REFERENCES members(member_id)
        );
        """)

        # checklists
        cur.execute("""
        CREATE TABLE IF NOT EXISTS checklists (
            checklist_id TEXT PRIMARY KEY,
            trip_id TEXT NOT NULL,
            list_key TEXT NOT NULL, -- documents/packing/custom
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES trips(trip_id)
        );
        """)

        # checklist_items
        cur.execute("""
        CREATE TABLE IF NOT EXISTS checklist_items (
            item_id TEXT PRIMARY KEY,
            checklist_id TEXT NOT NULL,
            text TEXT NOT NULL,
            checked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (checklist_id) REFERENCES checklists(checklist_id)
        );
        """)

        conn.commit()
