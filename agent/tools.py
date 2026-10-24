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

def get_all_properties() -> List[Dict[str, Any]]:
    """Gibt alle Liegenschaften mit aggregierter Einheiten- und Mieteranzahl sowie Alias zurück."""
    sql = """
        SELECT 
            p.id as property_id, p.name, p.alias, p.street, p.zip_code, p.city, p.total_area_sqm,
            COUNT(DISTINCT u.id) as unit_count,
            COUNT(DISTINCT t.id) as tenant_count
        FROM properties p
        LEFT JOIN units u ON u.property_id = p.id
        LEFT JOIN tenants t ON t.unit_id = u.id AND t.is_active = 1
        GROUP BY p.id
        ORDER BY p.name ASC;
    """
    return query_db(sql)

def get_property_by_id(property_id: int) -> Optional[Dict[str, Any]]:
    """Gibt eine einzelne Liegenschaft anhand ihrer ID zurück."""
    sql = """
        SELECT 
            p.id as property_id, p.name, p.alias, p.street, p.zip_code, p.city, p.total_area_sqm,
            COUNT(DISTINCT u.id) as unit_count,
            COUNT(DISTINCT t.id) as tenant_count
        FROM properties p
        LEFT JOIN units u ON u.property_id = p.id
        LEFT JOIN tenants t ON t.unit_id = u.id AND t.is_active = 1
        WHERE p.id = ?
        GROUP BY p.id;
    """
    rows = query_db(sql, (property_id,))
    return rows[0] if rows else None

def update_property_alias(property_id: int, alias: str) -> bool:
    """Aktualisiert den optionalen Alias einer Liegenschaft."""
    from database.db import execute_db
    execute_db("UPDATE properties SET alias = ? WHERE id = ?;", (alias.strip() if alias and alias.strip() else None, property_id))
    return True

def update_property(property_id: int, name: str, alias: Optional[str], street: str, zip_code: str, city: str, total_area_sqm: float) -> bool:
    """Aktualisiert die Stammdaten einer Liegenschaft."""
    from database.db import execute_db
    execute_db("""
        UPDATE properties
        SET name = ?, alias = ?, street = ?, zip_code = ?, city = ?, total_area_sqm = ?
        WHERE id = ?;
    """, (name.strip(), alias.strip() if alias and alias.strip() else None, street.strip(), zip_code.strip(), city.strip(), float(total_area_sqm), property_id))
    return True

def add_property(name: str, alias: Optional[str], street: str, zip_code: str, city: str, total_area_sqm: float) -> int:
    """Legt eine neue Liegenschaft in der Datenbank an."""
    from database.db import execute_db
    return execute_db("""
        INSERT INTO properties (name, alias, street, zip_code, city, total_area_sqm)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (name.strip(), alias.strip() if alias and alias.strip() else None, street.strip(), zip_code.strip(), city.strip(), float(total_area_sqm)))

def get_tenants_by_property(property_id: int) -> List[Dict[str, Any]]:
    """Gibt alle Mieter einer bestimmten Liegenschaft mit m²-Preis zurück."""
    sql = """
        SELECT 
            t.id as tenant_id, t.unit_id, t.salutation, t.first_name, t.last_name, t.email, t.phone,
            t.cold_rent, t.utility_advance, t.lease_start, t.lease_end, t.is_active,
            u.unit_number, u.area_sqm,
            p.id as property_id, p.name as property_name, p.alias as property_alias, p.street, p.zip_code, p.city
        FROM tenants t
        JOIN units u ON t.unit_id = u.id
        JOIN properties p ON u.property_id = p.id
        WHERE p.id = ?
        ORDER BY t.last_name ASC;
    """
    rows = query_db(sql, (property_id,))
    for r in rows:
        area = float(r.get("area_sqm") or 0.0)
        rent = float(r.get("cold_rent") or 0.0)
        r["price_per_sqm"] = round(rent / area, 2) if area > 0 else 0.0
        if not r.get("salutation"):
            r["salutation"] = "Herr"
    return rows

def get_units_by_property(property_id: int) -> List[Dict[str, Any]]:
    """Gibt alle Wohneinheiten einer bestimmten Liegenschaft zurück."""
    sql = """
        SELECT u.id as unit_id, u.unit_number, u.floor, u.area_sqm, p.name as property_name, p.id as property_id
        FROM units u
        JOIN properties p ON u.property_id = p.id
        WHERE p.id = ?
        ORDER BY u.unit_number ASC;
    """
    return query_db(sql, (property_id,))

def add_unit(property_id: int, unit_number: str, area_sqm: float, floor: str = "EG") -> int:
    """Fügt einer Liegenschaft eine neue Wohneinheit hinzu."""
    from database.db import execute_db
    return execute_db("""
        INSERT INTO units (property_id, unit_number, area_sqm, floor)
        VALUES (?, ?, ?, ?);
    """, (property_id, unit_number.strip(), float(area_sqm), floor.strip()))

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
            p.id as property_id, p.name as property_name, p.alias as property_alias, p.street, p.zip_code, p.city
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

def get_available_expense_years() -> List[int]:
    """Gibt alle in der Datenbank vorhandenen Abrechnungsjahre sortiert zurück (mindestens 2026 und 2025)."""
    rows = query_db("SELECT DISTINCT year FROM expenses ORDER BY year DESC;")
    years = [int(r["year"]) for r in rows if r.get("year")]
    for def_yr in [2026, 2025]:
        if def_yr not in years:
            years.append(def_yr)
    years.sort(reverse=True)
    return years

def get_expenses_for_year(year: int) -> List[Dict[str, Any]]:
    """Gibt alle detaillierten Betriebskosten inkl. ID für ein bestimmtes Jahr zurück."""
    sql = """
        SELECT e.id, e.property_id, e.year, e.category, e.description, e.amount, 
               e.allocation_key, e.receipt_date, p.name as property_name
        FROM expenses e
        JOIN properties p ON e.property_id = p.id
        WHERE e.year = ?
        ORDER BY e.category ASC, e.id ASC;
    """
    return query_db(sql, (year,))

def add_expense(
    property_id: int,
    year: int,
    category: str,
    amount: float,
    allocation_key: str = "sqm",
    description: str = "",
    receipt_date: Optional[str] = None
) -> int:
    """Fügt eine neue Betriebskostenposition ein."""
    from database.db import execute_db
    if not category.strip():
        raise ValueError("Kostenart darf nicht leer sein.")
    new_id = execute_db("""
        INSERT INTO expenses (property_id, year, category, description, amount, allocation_key, receipt_date)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (property_id, int(year), category.strip(), description.strip(), float(amount), allocation_key, receipt_date))
    return new_id

def update_expense(
    expense_id: int,
    category: str,
    amount: float,
    allocation_key: str = "sqm",
    description: str = "",
    receipt_date: Optional[str] = None
) -> bool:
    """Aktualisiert eine bestehende Betriebskostenposition."""
    from database.db import execute_db
    if not category.strip():
        raise ValueError("Kostenart darf nicht leer sein.")
    execute_db("""
        UPDATE expenses
        SET category = ?,
            description = ?,
            amount = ?,
            allocation_key = ?,
            receipt_date = ?
        WHERE id = ?;
    """, (category.strip(), description.strip(), float(amount), allocation_key, receipt_date, expense_id))
    return True

def delete_expense(expense_id: int) -> bool:
    """Löscht eine Betriebskostenposition anhand ihrer ID."""
    from database.db import execute_db
    execute_db("DELETE FROM expenses WHERE id = ?;", (expense_id,))
    return True

def copy_expenses_from_year(source_year: int, target_year: int, property_id: Optional[int] = None) -> int:
    """Kopiert alle Kostenpositionen eines Quelljahres in ein Zieljahr als Basis/Vorlage."""
    from database.db import execute_db
    if property_id:
        source_expenses = query_db("SELECT * FROM expenses WHERE year = ? AND property_id = ?;", (source_year, property_id))
    else:
        source_expenses = query_db("SELECT * FROM expenses WHERE year = ?;", (source_year,))
    
    count = 0
    for exp in source_expenses:
        r_date = exp.get("receipt_date")
        if r_date and len(str(r_date)) >= 4:
            new_date = f"{target_year}{str(r_date)[4:]}"
        else:
            new_date = f"{target_year}-01-01"
            
        execute_db("""
            INSERT INTO expenses (property_id, year, category, description, amount, allocation_key, receipt_date)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (exp["property_id"], target_year, exp["category"], exp["description"], exp["amount"], exp["allocation_key"], new_date))
        count += 1
    return count

def get_annual_utility_statements(year: int) -> List[Dict[str, Any]]:
    """Erstellt eine tabellarische Übersicht aller Mieterabrechnungen für ein bestimmtes Jahr."""
    tenants = get_all_tenants()
    statements = []
    for t in tenants:
        try:
            bill = calculate_utility_bill(t["tenant_id"], year)
            statements.append({
                "tenant_id": t["tenant_id"],
                "salutation": t.get("salutation", "Herr"),
                "first_name": t["first_name"],
                "last_name": t["last_name"],
                "full_name": f"{t.get('salutation', 'Herr')} {t['first_name']} {t['last_name']}",
                "unit_number": t.get("unit_number", ""),
                "area_sqm": float(t.get("area_sqm") or 0.0),
                "total_property_expenses": bill["total_property_expenses"],
                "tenant_share": bill["total_tenant_share"],
                "prepayments_paid": bill["prepayments_paid"],
                "balance": bill["balance"],
                "is_refund": bill["is_refund"],
                "status_label": "Guthaben" if bill["is_refund"] else ("Ausgeglichen" if bill["balance"] == 0 else "Nachzahlung")
            })
        except Exception:
            continue
    return statements

def create_utility_statement_for_tenant(tenant_id: int, year: int, intro_text: str = "") -> Dict[str, Any]:
    """Berechnet die Abrechnung und erzeugt das fertige PDF."""
    bill_data = calculate_utility_bill(tenant_id, year)
    pdf_path = generate_utility_bill_pdf(bill_data, custom_message=intro_text)
    bill_data["pdf_path"] = pdf_path
    return bill_data
