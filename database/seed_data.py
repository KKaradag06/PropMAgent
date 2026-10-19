import os
import sys

# Projektwurzel zu sys.path hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db, execute_db, query_db

def seed():
    init_db()
    
    # Prüfen, ob bereits Objekte existieren
    existing = query_db("SELECT COUNT(*) as count FROM properties;")
    if existing and existing[0]["count"] > 0:
        print("Datenbank enthält bereits Daten. Überspringe Seed.")
        return

    print("Initialisiere Beispieldaten für PropMAgent...")

    # 1. Immobilie anlegen
    prop_id = execute_db("""
        INSERT INTO properties (name, street, zip_code, city, total_area_sqm)
        VALUES (?, ?, ?, ?, ?);
    """, ("Wohnanlage Sonnenhang", "Lindenstraße 14", "10115", "Berlin", 240.0))

    # 2. Einheiten anlegen (3 Wohnungen = 240 m² gesamt)
    u1_id = execute_db("""
        INSERT INTO units (property_id, unit_number, floor, area_sqm)
        VALUES (?, ?, ?, ?);
    """, (prop_id, "Wohnung 1 (EG links)", "Erdgeschoss", 80.0))

    u2_id = execute_db("""
        INSERT INTO units (property_id, unit_number, floor, area_sqm)
        VALUES (?, ?, ?, ?);
    """, (prop_id, "Wohnung 2 (1. OG)", "1. Obergeschoss", 100.0))

    u3_id = execute_db("""
        INSERT INTO units (property_id, unit_number, floor, area_sqm)
        VALUES (?, ?, ?, ?);
    """, (prop_id, "Wohnung 3 (DG)", "Dachgeschoss", 60.0))

    # 3. Mieter anlegen
    # Mieter 1: Max Mustermann
    t1_id = execute_db("""
        INSERT INTO tenants (unit_id, salutation, first_name, last_name, email, phone, lease_start, cold_rent, utility_advance, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (u1_id, "Herr", "Max", "Mustermann", "max.mustermann@example.de", "+49 170 1234567", "2023-01-01", 950.00, 220.00, 1))

    # Mieter 2: Laura Schmidt
    t2_id = execute_db("""
        INSERT INTO tenants (unit_id, salutation, first_name, last_name, email, phone, lease_start, cold_rent, utility_advance, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (u2_id, "Frau", "Laura", "Schmidt", "laura.schmidt@example.de", "+49 171 7654321", "2022-05-01", 1250.00, 280.00, 1))

    # Mieter 3: Jonas Weber
    t3_id = execute_db("""
        INSERT INTO tenants (unit_id, salutation, first_name, last_name, email, phone, lease_start, cold_rent, utility_advance, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (u3_id, "Herr", "Jonas", "Weber", "jonas.weber@example.de", "+49 172 9876543", "2024-01-01", 750.00, 180.00, 1))

    # 4. Betriebskosten für das Abrechnungsjahr 2025
    expenses = [
        ("Grundsteuer", "Grundsteuer B Stadt Berlin", 1200.00, "sqm", "2025-02-15"),
        ("Gebäudeversicherung", "Allianz Wohngebäude & Haftpflicht", 1450.00, "sqm", "2025-03-01"),
        ("Müllabfuhr", "BSR Abfallbeseitigung", 980.00, "sqm", "2025-06-30"),
        ("Allgemeinstrom", "Vattenfall Treppenhausbeleuchtung", 360.00, "sqm", "2025-12-10"),
        ("Schornsteinfeger / Wartung", "Messung Heizungsanlage", 240.00, "sqm", "2025-10-12"),
        ("Hausmeister / Gartenpflege", "Grünanlagenpflege Sommer/Herbst", 1100.00, "sqm", "2025-11-20"),
        ("Kabelanschluss / TV", "Breitbandkabelanschluss Pauschale", 480.00, "units", "2025-12-01"),
    ]

    for cat, desc, amount, key, r_date in expenses:
        execute_db("""
            INSERT INTO expenses (property_id, year, category, description, amount, allocation_key, receipt_date)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (prop_id, 2025, cat, desc, amount, key, r_date))

    # 5. Geleistete Nebenkostenvorauszahlungen 2025 (12 Monate)
    # Mieter 1: 12 x 220 = 2640 €
    for month in range(1, 13):
        m_str = f"{month:02d}"
        execute_db("""
            INSERT INTO payments (tenant_id, payment_date, amount, payment_type)
            VALUES (?, ?, ?, ?);
        """, (t1_id, f"2025-{m_str}-03", 220.00, "utility_advance"))

    # Mieter 2: 12 x 280 = 3360 €
    for month in range(1, 13):
        m_str = f"{month:02d}"
        execute_db("""
            INSERT INTO payments (tenant_id, payment_date, amount, payment_type)
            VALUES (?, ?, ?, ?);
        """, (t2_id, f"2025-{m_str}-03", 280.00, "utility_advance"))

    # Mieter 3: 12 x 180 = 2160 €
    for month in range(1, 13):
        m_str = f"{month:02d}"
        execute_db("""
            INSERT INTO payments (tenant_id, payment_date, amount, payment_type)
            VALUES (?, ?, ?, ?);
        """, (t3_id, f"2025-{m_str}-03", 180.00, "utility_advance"))

    print("Erfolgreich Beispieldaten für 'Wohnanlage Sonnenhang' eingefügt!")

if __name__ == "__main__":
    seed()
