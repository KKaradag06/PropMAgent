import os
import sqlite3
from typing import List, Dict, Any, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "prop_management.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

def get_connection() -> sqlite3.Connection:
    """Stellt Verbindung zur SQLite-Datenbank her und aktiviert Foreign Keys."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db() -> None:
    """Initialisiert die Tabellen basierend auf schema.sql und migriert fehlende Spalten."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    with get_connection() as conn:
        conn.executescript(schema)
        # Migration: salutation Spalte sicherstellen
        columns = [row[1] for row in conn.execute("PRAGMA table_info(tenants);").fetchall()]
        if "salutation" not in columns:
            conn.execute("ALTER TABLE tenants ADD COLUMN salutation TEXT DEFAULT 'Herr';")
        # Automatisch korrigieren falls Laura Schmidt noch Herr hat
        conn.execute("UPDATE tenants SET salutation = 'Frau' WHERE first_name = 'Laura' OR last_name = 'Schmidt';")
        conn.commit()
    from database.settings import init_settings
    init_settings()

def query_db(query: str, args: tuple = ()) -> List[Dict[str, Any]]:
    """Führt eine SELECT-Abfrage aus und gibt eine Liste von Dictionaries zurück."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, args)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def execute_db(query: str, args: tuple = ()) -> int:
    """Führt INSERT, UPDATE oder DELETE aus und gibt die lastrowid zurück."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, args)
        conn.commit()
        return cursor.lastrowid
