import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'calcontrol.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            color TEXT DEFAULT '#1a73e8',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS scene_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
            topic TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '',
            delay_seconds REAL DEFAULT 0,
            action_order INTEGER DEFAULT 0,
            description TEXT DEFAULT ''
        )
    """)
    try:
        c.execute("ALTER TABLE scene_actions ADD COLUMN description TEXT DEFAULT ''")
    except Exception:
        pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS macros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT ''
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS macro_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            macro_id INTEGER NOT NULL REFERENCES macros(id) ON DELETE CASCADE,
            trigger TEXT NOT NULL DEFAULT 'START',
            offset_minutes INTEGER DEFAULT 0,
            scene_name TEXT NOT NULL,
            entry_order INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS fired_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_event_id TEXT,
            scene_name TEXT,
            fired_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'ok',
            note TEXT DEFAULT ''
        )
    """)

    defaults = {
        'mqtt_host': '192.168.10.1',
        'mqtt_port': '1883',
        'mqtt_user': '',
        'mqtt_pass': '',
        'calendar_id': '',
        'check_ahead_minutes': '5',
        'max_offset_hours': '4',
        'timezone': 'Australia/Sydney',
        'valid_titles': '',
    }
    for key, value in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    conn.commit()
    conn.close()


def get_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}


def save_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_scenes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM scenes ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scene(scene_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_scene_by_name(name):
    conn = get_db()
    row = conn.execute("SELECT * FROM scenes WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_scene(name, description='', color='#1a73e8'):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO scenes (name, description, color) VALUES (?, ?, ?)",
        (name, description, color)
    )
    scene_id = c.lastrowid
    conn.commit()
    conn.close()
    return scene_id


def update_scene(scene_id, name, description, color):
    conn = get_db()
    conn.execute(
        "UPDATE scenes SET name=?, description=?, color=? WHERE id=?",
        (name, description, color, scene_id)
    )
    conn.commit()
    conn.close()


def delete_scene(scene_id):
    conn = get_db()
    conn.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
    conn.commit()
    conn.close()


def get_scene_actions(scene_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM scene_actions WHERE scene_id = ? ORDER BY action_order, id",
        (scene_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_action(scene_id, topic, payload, delay_seconds=0, action_order=0, description=''):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO scene_actions (scene_id, topic, payload, delay_seconds, action_order, description) VALUES (?, ?, ?, ?, ?, ?)",
        (scene_id, topic, payload, delay_seconds, action_order, description)
    )
    action_id = c.lastrowid
    conn.commit()
    conn.close()
    return action_id


def update_action(action_id, topic, payload, delay_seconds, action_order, description=''):
    conn = get_db()
    conn.execute(
        "UPDATE scene_actions SET topic=?, payload=?, delay_seconds=?, action_order=?, description=? WHERE id=?",
        (topic, payload, delay_seconds, action_order, description, action_id)
    )
    conn.commit()
    conn.close()


def delete_action(action_id):
    conn = get_db()
    conn.execute("DELETE FROM scene_actions WHERE id = ?", (action_id,))
    conn.commit()
    conn.close()


def get_macros():
    conn = get_db()
    rows = conn.execute("SELECT * FROM macros ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_macro(macro_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM macros WHERE id = ?", (macro_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_macro_by_name(name):
    conn = get_db()
    row = conn.execute("SELECT * FROM macros WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_macro(name, description=''):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO macros (name, description) VALUES (?, ?)", (name, description))
    macro_id = c.lastrowid
    conn.commit()
    conn.close()
    return macro_id


def update_macro(macro_id, name, description):
    conn = get_db()
    conn.execute("UPDATE macros SET name=?, description=? WHERE id=?", (name, description, macro_id))
    conn.commit()
    conn.close()


def delete_macro(macro_id):
    conn = get_db()
    conn.execute("DELETE FROM macros WHERE id = ?", (macro_id,))
    conn.commit()
    conn.close()


def get_macro_entries(macro_id, trigger=None):
    conn = get_db()
    if trigger:
        rows = conn.execute(
            "SELECT * FROM macro_entries WHERE macro_id = ? AND trigger = ? ORDER BY entry_order, id",
            (macro_id, trigger)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM macro_entries WHERE macro_id = ? ORDER BY entry_order, id",
            (macro_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_macro_entry(macro_id, trigger, offset_minutes, scene_name, entry_order=0):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO macro_entries (macro_id, trigger, offset_minutes, scene_name, entry_order) VALUES (?, ?, ?, ?, ?)",
        (macro_id, trigger, offset_minutes, scene_name, entry_order)
    )
    entry_id = c.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def update_macro_entry(entry_id, trigger, offset_minutes, scene_name, entry_order):
    conn = get_db()
    conn.execute(
        "UPDATE macro_entries SET trigger=?, offset_minutes=?, scene_name=?, entry_order=? WHERE id=?",
        (trigger, offset_minutes, scene_name, entry_order, entry_id)
    )
    conn.commit()
    conn.close()


def delete_macro_entry(entry_id):
    conn = get_db()
    conn.execute("DELETE FROM macro_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def log_fired_event(google_event_id, scene_name, status='ok', note=''):
    conn = get_db()
    conn.execute(
        "INSERT INTO fired_events (google_event_id, scene_name, status, note) VALUES (?, ?, ?, ?)",
        (google_event_id, scene_name, status, note)
    )
    conn.commit()
    conn.close()


def get_log(limit=100):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM fired_events ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
