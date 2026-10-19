from typing import List, Dict, Any, Optional
from database.db import query_db
from agent.calculator import calculate_utility_bill
from reports.pdf_generator import generate_utility_bill_pdf

def get_all_units() -> List[Dict[str, Any]]:
    """Gibt alle Wohneinheiten zurück."""
    sql = """
        SELECT u.id as unit_id, u.unit_number, u.floor, u.area_sqm, p.name as property_name, p.id as property_id
        FROM units u
        JOIN properties p ON u.property_id = p.id
        ORDER BY u.unit_number ASC;
    """
    return query_db(sql)

def add_new_tenant(
    first_name: str,
    last_name: str,
    salutation: str = "Herr",
    unit_id: Optional[int] = None,
    unit_search: Optional[str] = None,
    cold_rent: float = 0.0,
    utility_advance: float = 0.0,
    lease_start: str = "2025-01-01",
    email: str = "",
    phone: str = ""
) -> Dict[str, Any]:
    """Fügt einen neuen Mieter in die Datenbank ein."""
    from database.db import execute_db
    
    # Falls unit_id nicht direkt übergeben wurde, versuchen über unit_search zu finden
    if not unit_id and unit_search:
        units = query_db("SELECT id FROM units WHERE LOWER(unit_number) LIKE ? LIMIT 1;", (f"%{unit_search.lower()}%",))
        if units:
            unit_id = units[0]["id"]
            
    if not unit_id:
        # Standard: Erste gefundene Einheit nehmen
        units = query_db("SELECT id FROM units LIMIT 1;")
        if units:
            unit_id = units[0]["id"]
        else:
            raise ValueError("Keine Wohneinheit in der Datenbank vorhanden.")

    new_id = execute_db("""
        INSERT INTO tenants (unit_id, salutation, first_name, last_name, email, phone, lease_start, cold_rent, utility_advance, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
    """, (unit_id, salutation.strip(), first_name.strip(), last_name.strip(), email.strip(), phone.strip(), lease_start, float(cold_rent), float(utility_advance)))

    return {
        "tenant_id": new_id,
        "salutation": salutation,
        "first_name": first_name,
        "last_name": last_name,
        "unit_id": unit_id
    }

def update_tenant(
    tenant_id: int,
    first_name: str,
    last_name: str,
    unit_id: int,
    salutation: str = "Herr",
    cold_rent: float = 0.0,
    utility_advance: float = 0.0,
    lease_start: Optional[str] = None,
    lease_end: Optional[str] = None,
    email: Optional[str] = "",
    phone: Optional[str] = "",
    is_active: int = 1
) -> bool:
    """Aktualisiert die Daten eines bestehenden Mieters."""
    from database.db import execute_db
    if not first_name.strip() or not last_name.strip():
        raise ValueError("Vorname und Nachname dürfen nicht leer sein.")
        
    execute_db("""
        UPDATE tenants
        SET first_name = ?,
            last_name = ?,
            salutation = ?,
            unit_id = ?,
            cold_rent = ?,
            utility_advance = ?,
            lease_start = ?,
            lease_end = ?,
            email = ?,
            phone = ?,
            is_active = ?
        WHERE id = ?;
    """, (
        first_name.strip(),
        last_name.strip(),
        salutation.strip(),
        unit_id,
        float(cold_rent or 0.0),
        float(utility_advance or 0.0),
        lease_start,
        lease_end if lease_end else None,
        (email or "").strip(),
        (phone or "").strip(),
        1 if is_active else 0,
        tenant_id
    ))
    return True

def delete_tenant(tenant_id: int) -> bool:
    """Löscht einen Mieter aus der Datenbank."""
    from database.db import execute_db
    execute_db("DELETE FROM tenants WHERE id = ?;", (tenant_id,))
    return True

def get_all_tenants() -> List[Dict[str, Any]]:
    """Gibt alle Mieter mit Wohneinheit, Liegenschaft und berechnetem m²-Preis zurück."""
    sql = """
        SELECT 
            t.id as tenant_id, t.unit_id, t.salutation, t.first_name, t.last_name, t.email, t.phone,
            t.cold_rent, t.utility_advance, t.lease_start, t.lease_end, t.is_active,
            u.unit_number, u.area_sqm,
            p.name as property_name, p.street, p.zip_code, p.city
        FROM tenants t
        JOIN units u ON t.unit_id = u.id
        JOIN properties p ON u.property_id = p.id
        ORDER BY t.last_name ASC;
    """
    rows = query_db(sql)
    for r in rows:
        area = float(r.get("area_sqm") or 0.0)
        rent = float(r.get("cold_rent") or 0.0)
        r["price_per_sqm"] = round(rent / area, 2) if area > 0 else 0.0
        if not r.get("salutation"):
            r["salutation"] = "Herr"
    return rows

def find_tenant_by_name(name_query: str) -> Optional[Dict[str, Any]]:
    """Sucht einen Mieter nach Vor- oder Nachname (case-insensitive)."""
    search_term = f"%{name_query.strip().lower()}%"
    sql = """
        SELECT 
            t.id as tenant_id, t.unit_id, t.salutation, t.first_name, t.last_name,
            t.cold_rent, t.utility_advance,
            u.unit_number, u.area_sqm,
            p.name as property_name, p.street, p.zip_code, p.city
        FROM tenants t
        JOIN units u ON t.unit_id = u.id
        JOIN properties p ON u.property_id = p.id
        WHERE LOWER(t.first_name) LIKE ? OR LOWER(t.last_name) LIKE ?
           OR LOWER(t.first_name || ' ' || t.last_name) LIKE ?
        LIMIT 1;
    """
    results = query_db(sql, (search_term, search_term, search_term))
    if results:
        res = results[0]
        area = float(res.get("area_sqm") or 0.0)
        rent = float(res.get("cold_rent") or 0.0)
        res["price_per_sqm"] = round(rent / area, 2) if area > 0 else 0.0
        if not res.get("salutation"):
            res["salutation"] = "Herr"
        return res
    return None

def get_expenses_summary(year: int) -> List[Dict[str, Any]]:
    """Gibt die Betriebskosten eines Jahres zurück."""
    sql = """
        SELECT category, description, amount, allocation_key, receipt_date, p.name as property_name
        FROM expenses e
        JOIN properties p ON e.property_id = p.id
        WHERE e.year = ?
        ORDER BY category ASC;
    """
    return query_db(sql, (year,))

def create_utility_statement_for_tenant(tenant_id: int, year: int, intro_text: str = "") -> Dict[str, Any]:
    """Berechnet die Abrechnung und erzeugt das fertige PDF."""
    bill_data = calculate_utility_bill(tenant_id, year)
    pdf_path = generate_utility_bill_pdf(bill_data, custom_message=intro_text)
    bill_data["pdf_path"] = pdf_path
    return bill_data
