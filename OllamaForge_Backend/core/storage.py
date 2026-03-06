import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "persistent_storage.db")

def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        model TEXT,
        source TEXT,
        rag_path TEXT,
        db_path TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT
    )
    """)

    conn.commit()
    conn.close()


# -------------------------
# SESSION FUNCTIONS
# -------------------------

def create_session(session_id, model="llama3", source="Direct Chat"):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO sessions (session_id, model, source)
    VALUES (?, ?, ?)
    """, (session_id, model, source))

    conn.commit()
    conn.close()


def get_session(session_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT model, source, rag_path, db_path
        FROM sessions
        WHERE session_id=?
    """, (session_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "model": row[0],
        "source": row[1],
        "rag_path": row[2],
        "db_path": row[3]
    }



def update_source(session_id, source):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE sessions SET source=? WHERE session_id=?
    """, (source, session_id))

    conn.commit()
    conn.close()


def update_model(session_id, model):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE sessions SET model=? WHERE session_id=?
    """, (model, session_id))

    conn.commit()
    conn.close()

def update_rag_path(session_id, rag_path):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE sessions SET rag_path=? WHERE session_id=?
    """, (rag_path, session_id))

    conn.commit()
    conn.close()


def update_db_path(session_id, db_path):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE sessions SET db_path=? WHERE session_id=?
    """, (db_path, session_id))

    conn.commit()
    conn.close()



# -------------------------
# MESSAGE MEMORY
# -------------------------

def save_message(session_id, role, content):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO messages (session_id, role, content)
    VALUES (?, ?, ?)
    """, (session_id, role, content))

    conn.commit()
    conn.close()


def get_messages(session_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT role, content FROM messages WHERE session_id=?
    ORDER BY id ASC
    """, (session_id,))

    rows = cursor.fetchall()
    conn.close()

    return [{"role": r[0], "content": r[1]} for r in rows]
