import os
import sqlite3
import urllib.request
import json
from typing import Dict, Any, List, Optional, Tuple
from database.db import get_connection

DEFAULT_SETTINGS: Dict[str, str] = {
    # KI- & Ollama-Konfiguration
    "ollama_model": "llama3",
    "ollama_url": "http://localhost:11434",
    "ai_temperature": "0.1",

    # Vermieter-Typ: "private" (Privater Vermieter) oder "property_management" (Hausverwaltung)
    "landlord_type": "private",

    # Vermieter- & Kontaktdaten (Briefkopf & Absenderzeile nach DIN 5008)
    "landlord_name": "Kirdar Karadag",
    "landlord_contact_person": "Kirdar Karadag",
    "landlord_street": "Lindenstraße 14",
    "landlord_zip": "10115",
    "landlord_city": "Berlin",
    "landlord_phone": "+49 30 12345678",
    "landlord_email": "kirdar@karadag.de",

    # Bankverbindung für Miete und Abrechnungen
    "landlord_account_holder": "Kirdar Karadag",
    "landlord_iban": "DE12 1005 0000 0123 4567 89",
    "landlord_bic": "BELADEB1XXX",
    "landlord_bank_name": "Berliner Sparkasse",
    "landlord_tax_id": "27/123/45678",

    # Brief- & Abrechnungsvorgaben
    "default_payment_deadline_days": "14",
    "default_utility_objection_days": "30",
    "default_closing_phrase": "Mit freundlichen Grüßen",
    "default_signature_title": "Ihr Vermieter",
    "letter_city": "",
    "letter_include_bank_details": "true"
}

def init_settings() -> None:
    """Erstellt die settings-Tabelle und befüllt fehlende Standardeinstellungen."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        # Prüfen, welche Keys bereits vorhanden sind
        cursor = conn.cursor()
        cursor.execute("SELECT key FROM settings;")
        existing_keys = {row["key"] for row in cursor.fetchall()}

        for k, v in DEFAULT_SETTINGS.items():
            if k not in existing_keys:
                conn.execute("INSERT INTO settings (key, value) VALUES (?, ?);", (k, str(v)))
        conn.commit()

def get_setting(key: str, default: Optional[str] = None) -> str:
    """Liest einen einzelnen Einstellungswert aus der Datenbank."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?;", (key,))
            row = cursor.fetchone()
            if row and row["value"] is not None:
                return str(row["value"])
    except Exception:
        pass
    return str(default if default is not None else DEFAULT_SETTINGS.get(key, ""))

def get_all_settings() -> Dict[str, str]:
    """Gibt alle hinterlegten Einstellungen als Dictionary zurück."""
    init_settings()
    settings = dict(DEFAULT_SETTINGS)
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings;")
            for row in cursor.fetchall():
                settings[row["key"]] = str(row["value"])
    except Exception:
        pass
    return settings

def set_setting(key: str, value: Any) -> None:
    """Setzt oder aktualisiert einen einzelnen Einstellungswert."""
    init_settings()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value;
        """, (key, str(value)))
        conn.commit()

def save_settings(settings_dict: Dict[str, Any]) -> None:
    """Speichert mehrere Einstellungen in einer Transaktion."""
    init_settings()
    with get_connection() as conn:
        for k, v in settings_dict.items():
            conn.execute("""
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """, (k, str(v)))
        conn.commit()

def reset_settings_to_default() -> None:
    """Setzt alle Einstellungen auf die Standardwerte zurück."""
    with get_connection() as conn:
        conn.execute("DELETE FROM settings;")
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?);", (k, str(v)))
        conn.commit()

def check_ollama_status(url: Optional[str] = None) -> Dict[str, Any]:
    """
    Prüft die Erreichbarkeit des lokalen Ollama-Servers und listet installierte Modelle auf.
    Gibt ein Dict mit {"online": bool, "message": str, "models": List[str]} zurück.
    """
    base_url = (url or get_setting("ollama_url", "http://localhost:11434")).rstrip("/")
    tags_url = f"{base_url}/api/tags"
    
    try:
        req = urllib.request.Request(tags_url, headers={"User-Agent": "PropMAgent/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                return {
                    "online": True,
                    "message": f"Ollama ist aktiv ({len(models)} lokale Modelle installiert)",
                    "models": models
                }
    except Exception as e:
        return {
            "online": False,
            "message": f"Keine Verbindung zu Ollama unter {base_url} ({type(e).__name__})",
            "models": []
        }

    return {
        "online": False,
        "message": f"Ollama unter {base_url} nicht erreichbar",
        "models": []
    }
