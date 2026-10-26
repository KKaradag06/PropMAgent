import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

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
        # Migration: tenants Spalten sicherstellen
        columns_tenants = [row[1] for row in conn.execute("PRAGMA table_info(tenants);").fetchall()]
        if "salutation" not in columns_tenants:
            conn.execute("ALTER TABLE tenants ADD COLUMN salutation TEXT DEFAULT 'Herr';")
        if "co_tenants" not in columns_tenants:
            conn.execute("ALTER TABLE tenants ADD COLUMN co_tenants TEXT DEFAULT '[]';")

        # Automatisch korrigieren falls Laura Schmidt noch Herr hat
        conn.execute("UPDATE tenants SET salutation = 'Frau' WHERE first_name = 'Laura' OR last_name = 'Schmidt';")

        # Migration: properties Spalten sicherstellen
        columns_props = [row[1] for row in conn.execute("PRAGMA table_info(properties);").fetchall()]
        if "alias" not in columns_props:
            conn.execute("ALTER TABLE properties ADD COLUMN alias TEXT;")
        if "construction_year" not in columns_props:
            conn.execute("ALTER TABLE properties ADD COLUMN construction_year TEXT;")
        if "heating_type" not in columns_props:
            conn.execute("ALTER TABLE properties ADD COLUMN heating_type TEXT;")
        if "energy_source" not in columns_props:
            conn.execute("ALTER TABLE properties ADD COLUMN energy_source TEXT;")

        # Migration: units Spalten sicherstellen
        columns_units = [row[1] for row in conn.execute("PRAGMA table_info(units);").fetchall()]
        if "rooms" not in columns_units:
            conn.execute("ALTER TABLE units ADD COLUMN rooms REAL DEFAULT 2;")
        if "person_count" not in columns_units:
            conn.execute("ALTER TABLE units ADD COLUMN person_count INTEGER DEFAULT 1;")

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

REQUIRED_BACKUP_TABLES = {"properties", "units", "tenants", "expenses", "payments", "settings"}

def validate_backup_file(file_bytes: bytes) -> Tuple[bool, str, Dict[str, int]]:
    """
    Validiert eine hochgeladene SQLite-Datenbankdatei (.db).
    Gibt (is_valid, message, stats_dict) zurück.
    """
    if not file_bytes:
        return False, "Die hochgeladene Datei ist leer.", {}

    if len(file_bytes) < 100 or not file_bytes.startswith(b"SQLite format 3\x00"):
        return False, "Die Datei ist keine gültige SQLite-Datenbank (ungültiger Datei-Header).", {}

    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        tmp_file = tmp_path

        conn = sqlite3.connect(tmp_path)
        try:
            # 1. Integritätsprüfung
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            integrity_rows = cursor.fetchall()
            if not integrity_rows or integrity_rows[0][0] != "ok":
                return False, "Die SQLite-Integritätsprüfung ist fehlgeschlagen (beschädigte Datei).", {}

            # 2. Tabellenprüfung
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing_tables = {row[0] for row in cursor.fetchall()}
            missing = REQUIRED_BACKUP_TABLES - existing_tables
            if missing:
                missing_str = ", ".join(sorted(missing))
                return False, f"Erforderliche PropMAgent-Tabellen fehlen: {missing_str}. Bitte lade ausschließlich Original-Backups aus PropMAgent hoch.", {}

            # 3. Statistiken ermitteln
            stats = {}
            for tbl in ["properties", "units", "tenants", "expenses", "payments"]:
                cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
                stats[tbl] = cursor.fetchone()[0]

            return True, "Gültige PropMAgent-Datenbank erkannt.", stats
        finally:
            conn.close()
    except Exception as e:
        return False, f"Fehler beim Lesen der Datenbankdatei: {str(e)}", {}
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass

def restore_backup_file(file_bytes: bytes) -> Tuple[bool, str, Dict[str, int]]:
    """
    Stellt ein Backup aus Bytes wieder her:
    1. Validiert die Bytes.
    2. Erstellt eine Sicherheitskopie der aktuellen DB im Ordner data/backups/.
    3. Überschreibt DB_PATH mit den neuen Bytes.
    4. Ruft init_db() für Schema-Migrationen auf.
    Gibt (success, message, stats) zurück.
    """
    is_valid, msg, stats = validate_backup_file(file_bytes)
    if not is_valid:
        return False, msg, {}

    try:
        os.makedirs(DB_DIR, exist_ok=True)
        # Sicherheitskopie der aktuellen Datenbank anlegen
        if os.path.exists(DB_PATH):
            backup_subfolder = os.path.join(DB_DIR, "backups")
            os.makedirs(backup_subfolder, exist_ok=True)
            safety_copy = os.path.join(
                backup_subfolder,
                f"prop_management_vor_wiederherstellung_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            )
            shutil.copy2(DB_PATH, safety_copy)

        # Neue DB-Datei schreiben
        with open(DB_PATH, "wb") as f:
            f.write(file_bytes)

        # Schema-Migrationen ausführen (falls das Backup aus einer älteren Version stammt)
        init_db()

        return True, "Datenbank erfolgreich wiederhergestellt.", stats
    except Exception as e:
        return False, f"Fehler beim Ersetzen der Datenbank: {str(e)}", {}
