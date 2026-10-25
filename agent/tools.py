import json
from typing import List, Dict, Any, Optional, Union
from database.db import query_db
from agent.calculator import calculate_utility_bill
from reports.pdf_generator import generate_utility_bill_pdf

def parse_co_tenants(raw_val: Any) -> List[Dict[str, str]]:
    """Parst co_tenants aus JSON oder gibt eine leere Liste zurück."""
    if not raw_val:
        return []
    if isinstance(raw_val, list):
        return raw_val
    try:
        data = json.loads(str(raw_val))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def format_tenant_names(tenant: Dict[str, Any]) -> str:
    """Gibt den kombinierten Anzeigenamen aller Mieter des Vertrags zurück (z. B. 'Markus Schmidt & Laura Schmidt')."""
    primary = f"{tenant.get('first_name', '')} {tenant.get('last_name', '')}".strip()
    co_list = parse_co_tenants(tenant.get("co_tenants"))
    if not co_list:
        return primary
    names = [primary]
    for c in co_list:
        c_name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        if c_name:
            names.append(c_name)
    return " & ".join(names)

def format_tenant_salutation(tenant: Dict[str, Any]) -> str:
    """Erzeugt die korrekte formelle DIN-Anrede für einen oder mehrere Mieter."""
    sal1 = tenant.get("salutation") or "Herr"
    ln1 = tenant.get("last_name") or ""
    co_list = parse_co_tenants(tenant.get("co_tenants"))
    if not co_list:
        return f"Sehr geehrte Frau {ln1}" if sal1 == "Frau" else f"Sehr geehrter Herr {ln1}"

    greetings = []
    greetings.append(f"Sehr geehrte Frau {ln1}" if sal1 == "Frau" else f"Sehr geehrter Herr {ln1}")
    for c in co_list:
        c_sal = c.get("salutation") or "Frau"
        c_ln = c.get("last_name") or ln1
        greetings.append(f"sehr geehrte Frau {c_ln}" if c_sal == "Frau" else f"sehr geehrter Herr {c_ln}")
    return ", ".join(greetings)

def format_tenant_address_block(tenant: Dict[str, Any]) -> str:
    """Erzeugt den Empfänger-Zeilenblock für DIN 5008 (untereinander)."""
    sal1 = tenant.get("salutation") or "Herr"
    sal_prefix1 = "Frau" if sal1 == "Frau" else "Herrn"
    fn1 = tenant.get("first_name") or ""
    ln1 = tenant.get("last_name") or ""
    lines = [f"{sal_prefix1} {fn1} {ln1}".strip()]

    co_list = parse_co_tenants(tenant.get("co_tenants"))
    for c in co_list:
        c_sal = c.get("salutation") or "Frau"
        c_prefix = "Frau" if c_sal == "Frau" else "Herrn"
        c_fn = c.get("first_name") or ""
        c_ln = c.get("last_name") or ""
        lines.append(f"{c_prefix} {c_fn} {c_ln}".strip())
    return "\n".join(lines)

def get_all_units() -> List[Dict[str, Any]]:
    """Gibt alle Wohneinheiten zurück."""
    sql = """
        SELECT u.id as unit_id, u.unit_number, u.floor, u.area_sqm, u.rooms, u.person_count, p.name as property_name, p.id as property_id
        FROM units u
        JOIN properties p ON u.property_id = p.id
        ORDER BY u.unit_number ASC;
    """
    return query_db(sql)

def get_all_properties() -> List[Dict[str, Any]]:
    """Gibt alle Liegenschaften mit aggregierter Einheiten- und Mieteranzahl sowie Alias, Baujahr und Heizart zurück."""
    sql = """
        SELECT 
            p.id as property_id, p.name, p.alias, p.street, p.zip_code, p.city, p.total_area_sqm,
            p.construction_year, p.heating_type, p.energy_source,
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
            p.construction_year, p.heating_type, p.energy_source,
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

def update_property(
    property_id: int,
    name: str,
    alias: Optional[str],
    street: str,
    zip_code: str,
    city: str,
    total_area_sqm: float,
    construction_year: Optional[str] = None,
    heating_type: Optional[str] = None,
    energy_source: Optional[str] = None
) -> bool:
    """Aktualisiert die Stammdaten einer Liegenschaft inklusive Baujahr, Heizungsart und Energieträger."""
    from database.db import execute_db
    execute_db("""
        UPDATE properties
        SET name = ?, alias = ?, street = ?, zip_code = ?, city = ?, total_area_sqm = ?,
            construction_year = ?, heating_type = ?, energy_source = ?
        WHERE id = ?;
    """, (
        name.strip(),
        alias.strip() if alias and alias.strip() else None,
        street.strip(),
        zip_code.strip(),
        city.strip(),
        float(total_area_sqm),
        construction_year.strip() if construction_year and str(construction_year).strip() else None,
        heating_type.strip() if heating_type and heating_type.strip() else None,
        energy_source.strip() if energy_source and energy_source.strip() else None,
        property_id
    ))
    return True

def delete_property(property_id: int) -> bool:
    """Löscht eine Liegenschaft mitsamt aller zugehörigen Einheiten, Mieter, Zahlungen und Betriebskosten."""
    from database.db import execute_db
    # 1. Zahlungen löschen
    execute_db("""
        DELETE FROM payments 
        WHERE tenant_id IN (
            SELECT t.id FROM tenants t 
            JOIN units u ON t.unit_id = u.id 
            WHERE u.property_id = ?
        );
    """, (property_id,))
    # 2. Mieter löschen
    execute_db("""
        DELETE FROM tenants 
        WHERE unit_id IN (SELECT id FROM units WHERE property_id = ?);
    """, (property_id,))
    # 3. Einheiten löschen
    execute_db("DELETE FROM units WHERE property_id = ?;", (property_id,))
    # 4. Betriebskosten löschen
    execute_db("DELETE FROM expenses WHERE property_id = ?;", (property_id,))
    # 5. Liegenschaft löschen
    execute_db("DELETE FROM properties WHERE id = ?;", (property_id,))
    return True

def add_property(
    name: str,
    alias: Optional[str],
    street: str,
    zip_code: str,
    city: str,
    total_area_sqm: float,
    construction_year: Optional[str] = None,
    heating_type: Optional[str] = None,
    energy_source: Optional[str] = None
) -> int:
    """Legt eine neue Liegenschaft in der Datenbank an."""
    from database.db import execute_db
    return execute_db("""
        INSERT INTO properties (name, alias, street, zip_code, city, total_area_sqm, construction_year, heating_type, energy_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        name.strip(),
        alias.strip() if alias and alias.strip() else None,
        street.strip(),
        zip_code.strip(),
        city.strip(),
        float(total_area_sqm),
        construction_year.strip() if construction_year and str(construction_year).strip() else None,
        heating_type.strip() if heating_type and heating_type.strip() else None,
        energy_source.strip() if energy_source and energy_source.strip() else None
    ))

def get_tenants_by_property(property_id: int) -> List[Dict[str, Any]]:
    """Gibt alle Mieter einer bestimmten Liegenschaft mit m²-Preis und Mitmietern zurück."""
    sql = """
        SELECT 
            t.id as tenant_id, t.unit_id, t.salutation, t.first_name, t.last_name, t.email, t.phone,
            t.co_tenants, t.cold_rent, t.utility_advance, t.lease_start, t.lease_end, t.is_active,
            u.unit_number, u.area_sqm, u.rooms, u.person_count,
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
        r["display_name"] = format_tenant_names(r)
        r["combined_salutation"] = format_tenant_salutation(r)
        r["address_recipient"] = format_tenant_address_block(r)
    return rows

def get_units_by_property(property_id: int) -> List[Dict[str, Any]]:
    """Gibt alle Wohneinheiten einer bestimmten Liegenschaft samt Zimmern und Personenzahl zurück."""
    sql = """
        SELECT u.id as unit_id, u.unit_number, u.floor, u.area_sqm, u.rooms, u.person_count, p.name as property_name, p.id as property_id
        FROM units u
        JOIN properties p ON u.property_id = p.id
        WHERE p.id = ?
        ORDER BY u.unit_number ASC;
    """
    rows = query_db(sql, (property_id,))
    for r in rows:
        if r.get("person_count") is None or r.get("person_count") == "":
            r["person_count"] = 1
        if r.get("rooms") is None or r.get("rooms") == "":
            r["rooms"] = 2
    return rows

def add_unit(property_id: int, unit_number: str, area_sqm: float, floor: str = "EG", rooms: float = 2.0, person_count: int = 1) -> int:
    """Fügt einer Liegenschaft eine neue Wohneinheit hinzu."""
    from database.db import execute_db
    return execute_db("""
        INSERT INTO units (property_id, unit_number, area_sqm, floor, rooms, person_count)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (property_id, unit_number.strip(), float(area_sqm), floor.strip(), float(rooms), int(person_count)))

def update_unit(unit_id: int, unit_number: str, area_sqm: float, floor: str = "EG", rooms: float = 2.0, person_count: int = 1) -> bool:
    """Aktualisiert eine bestehende Wohneinheit."""
    from database.db import execute_db
    execute_db("""
        UPDATE units
        SET unit_number = ?, area_sqm = ?, floor = ?, rooms = ?, person_count = ?
        WHERE id = ?;
    """, (unit_number.strip(), float(area_sqm), floor.strip(), float(rooms), int(person_count), unit_id))
    return True

def save_imported_property_data(
    prop_data: Dict[str, Any],
    units: List[Dict[str, Any]],
    existing_property_id: Optional[int] = None
) -> int:
    """Speichert oder aktualisiert eine Liegenschaft samt Wohneinheiten und ggf. Mietern aus einem Dokument-Import."""
    import pandas as pd
    from database.db import execute_db, query_db

    c_year = str(prop_data.get("construction_year") or "").strip() or None
    h_type = str(prop_data.get("heating_type") or "").strip() or None
    e_source = str(prop_data.get("energy_source") or "").strip() or None

    if existing_property_id:
        prop_id = existing_property_id
        if prop_data.get("total_area_sqm"):
            execute_db("UPDATE properties SET total_area_sqm = ? WHERE id = ?;", (float(prop_data["total_area_sqm"]), prop_id))
        if c_year or h_type or e_source:
            execute_db("""
                UPDATE properties 
                SET construction_year = COALESCE(?, construction_year),
                    heating_type = COALESCE(?, heating_type),
                    energy_source = COALESCE(?, energy_source)
                WHERE id = ?;
            """, (c_year, h_type, e_source, prop_id))
    else:
        name = (prop_data.get("name") or prop_data.get("property_name") or "Neue Liegenschaft").strip()
        alias = (prop_data.get("alias") or "").strip() or None
        street = (prop_data.get("street") or "Musterstraße 1").strip()
        zip_code = (prop_data.get("zip_code") or "10115").strip()
        city = (prop_data.get("city") or "Berlin").strip()
        total_area = float(prop_data.get("total_area_sqm") or 0.0)

        prop_id = add_property(
            name=name,
            alias=alias,
            street=street,
            zip_code=zip_code,
            city=city,
            total_area_sqm=total_area,
            construction_year=c_year,
            heating_type=h_type,
            energy_source=e_source
        )

    for u in units:
        raw_num = u.get("unit_number")
        if pd.isna(raw_num):
            continue
        u_num = str(raw_num).strip()
        if not u_num or u_num.lower() == "nan":
            continue

        raw_area = u.get("area_sqm")
        if pd.isna(raw_area):
            area = 50.0
        else:
            try:
                area = float(str(raw_area).replace(",", "."))
            except (ValueError, TypeError):
                area = 50.0

        raw_floor = u.get("floor")
        floor = "EG" if pd.isna(raw_floor) else str(raw_floor).strip()
        if not floor or floor.lower() == "nan":
            floor = "EG"

        try:
            rooms_val = float(str(u.get("rooms", 2.0)).replace(",", "."))
        except Exception:
            rooms_val = 2.0

        try:
            persons_val = int(u.get("person_count", 1))
        except Exception:
            persons_val = 1

        # Prüfen ob Einheit schon existiert
        existing = query_db("SELECT id FROM units WHERE property_id = ? AND LOWER(unit_number) = LOWER(?);", (prop_id, u_num))
        if existing:
            unit_id = existing[0]["id"]
            execute_db("UPDATE units SET area_sqm = ?, floor = ?, rooms = ?, person_count = ? WHERE id = ?;", (area, floor, rooms_val, persons_val, unit_id))
        else:
            unit_id = add_unit(prop_id, u_num, area, floor, rooms=rooms_val, person_count=persons_val)

        # Mieter anlegen falls Vor- oder Nachname angegeben ist
        raw_fn = u.get("first_name")
        raw_ln = u.get("last_name")
        fn = "" if pd.isna(raw_fn) else str(raw_fn).strip()
        ln = "" if pd.isna(raw_ln) else str(raw_ln).strip()
        if fn.lower() == "nan": fn = ""
        if ln.lower() == "nan": ln = ""

        co_tenants_json = "[]"
        if u.get("co_tenants"):
            if isinstance(u["co_tenants"], str):
                co_tenants_json = u["co_tenants"]
            elif isinstance(u["co_tenants"], list):
                co_tenants_json = json.dumps(u["co_tenants"], ensure_ascii=False)

        if fn or ln:
            raw_sal = u.get("salutation")
            sal = "Herr" if pd.isna(raw_sal) else str(raw_sal).strip()
            if sal not in ["Herr", "Frau"]:
                sal = "Frau" if any(x in fn.lower() for x in ["anna", "maria", "sabine", "laura", "julia"]) else "Herr"

            try:
                raw_cr = u.get("cold_rent")
                cr = 0.0 if pd.isna(raw_cr) else float(str(raw_cr).replace(",", "."))
            except (ValueError, TypeError):
                cr = 0.0

            try:
                raw_nk = u.get("utility_advance")
                nk = 0.0 if pd.isna(raw_nk) else float(str(raw_nk).replace(",", "."))
            except (ValueError, TypeError):
                nk = 0.0

            active_t = query_db("SELECT id FROM tenants WHERE unit_id = ? AND is_active = 1;", (unit_id,))
            if not active_t:
                execute_db("""
                    INSERT INTO tenants (unit_id, salutation, first_name, last_name, email, phone, co_tenants, lease_start, cold_rent, utility_advance, is_active)
                    VALUES (?, ?, ?, ?, '', '', ?, date('now'), ?, ?, 1);
                """, (unit_id, sal, fn or "Mieter", ln or "Unbekannt", co_tenants_json, cr, nk))

    return prop_id

def add_new_tenant(
    first_name: str,
    last_name: str,
    salutation: str = "Herr",
    unit_id: Optional[int] = None,
    unit_search: Optional[str] = None,
    cold_rent: float = 0.0,
    utility_advance: float = 0.0,
    lease_start: str = "2025-01-01",
    lease_end: Optional[str] = None,
    email: str = "",
    phone: str = "",
    co_tenants: Optional[Union[str, List[Dict[str, str]]]] = None
) -> Dict[str, Any]:
    """Fügt einen neuen Mieter (inklusive optionaler Mitmieter auf demselben Mietvertrag) in die Datenbank ein."""
    from database.db import execute_db
    
    # Falls unit_id nicht direkt übergeben wurde, versuchen über unit_search zu finden
    if not unit_id and unit_search:
        units = query_db("SELECT id FROM units WHERE LOWER(unit_number) LIKE ? LIMIT 1;", (f"%{unit_search.lower()}%",))
        if units:
            unit_id = units[0]["id"]
            
    if not unit_id:
        units = query_db("SELECT id FROM units LIMIT 1;")
        if units:
            unit_id = units[0]["id"]
        else:
            raise ValueError("Keine Wohneinheit in der Datenbank vorhanden.")

    if isinstance(co_tenants, list):
        co_tenants_str = json.dumps(co_tenants, ensure_ascii=False)
    elif isinstance(co_tenants, str):
        co_tenants_str = co_tenants.strip() or "[]"
    else:
        co_tenants_str = "[]"

    new_id = execute_db("""
        INSERT INTO tenants (unit_id, salutation, first_name, last_name, email, phone, co_tenants, lease_start, lease_end, cold_rent, utility_advance, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
    """, (unit_id, salutation.strip(), first_name.strip(), last_name.strip(), email.strip(), phone.strip(), co_tenants_str, lease_start, lease_end, float(cold_rent), float(utility_advance)))

    return {
        "tenant_id": new_id,
        "salutation": salutation,
        "first_name": first_name,
        "last_name": last_name,
        "co_tenants": co_tenants_str,
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
    is_active: int = 1,
    co_tenants: Optional[Union[str, List[Dict[str, str]]]] = None
) -> bool:
    """Aktualisiert die Daten eines bestehenden Mieters samt Mitmietern."""
    from database.db import execute_db
    if not first_name.strip() or not last_name.strip():
        raise ValueError("Vorname und Nachname dürfen nicht leer sein.")
        
    if isinstance(co_tenants, list):
        co_tenants_str = json.dumps(co_tenants, ensure_ascii=False)
    elif isinstance(co_tenants, str):
        co_tenants_str = co_tenants.strip() or "[]"
    else:
        co_tenants_str = "[]"

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
            is_active = ?,
            co_tenants = ?
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
        co_tenants_str,
        tenant_id
    ))
    return True

def delete_tenant(tenant_id: int) -> bool:
    """Löscht einen Mieter aus der Datenbank."""
    from database.db import execute_db
    execute_db("DELETE FROM tenants WHERE id = ?;", (tenant_id,))
    return True

def get_all_tenants() -> List[Dict[str, Any]]:
    """Gibt alle Mieter mit Wohneinheit, Liegenschaft und kombiniertem Namen zurück."""
    sql = """
        SELECT 
            t.id as tenant_id, t.unit_id, t.salutation, t.first_name, t.last_name, t.email, t.phone,
            t.co_tenants, t.cold_rent, t.utility_advance, t.lease_start, t.lease_end, t.is_active,
            u.unit_number, u.area_sqm, u.rooms, u.person_count,
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
        r["display_name"] = format_tenant_names(r)
        r["combined_salutation"] = format_tenant_salutation(r)
        r["address_recipient"] = format_tenant_address_block(r)
    return rows

def find_tenant_by_name(name_query: str) -> Optional[Dict[str, Any]]:
    """Sucht einen Mieter nach Vor- oder Nachname (auch unter Mitmietern)."""
    search_term = f"%{name_query.strip().lower()}%"
    sql = """
        SELECT 
            t.id as tenant_id, t.unit_id, t.salutation, t.first_name, t.last_name, t.co_tenants,
            t.cold_rent, t.utility_advance, t.lease_start, t.lease_end,
            u.unit_number, u.area_sqm, u.rooms, u.person_count,
            p.id as property_id, p.name as property_name, p.alias as property_alias, p.street, p.zip_code, p.city
        FROM tenants t
        JOIN units u ON t.unit_id = u.id
        JOIN properties p ON u.property_id = p.id
        WHERE LOWER(t.first_name) LIKE ? OR LOWER(t.last_name) LIKE ?
           OR LOWER(t.first_name || ' ' || t.last_name) LIKE ?
           OR LOWER(t.co_tenants) LIKE ?
        LIMIT 1;
    """
    results = query_db(sql, (search_term, search_term, search_term, search_term))
    if results:
        res = results[0]
        area = float(res.get("area_sqm") or 0.0)
        rent = float(res.get("cold_rent") or 0.0)
        res["price_per_sqm"] = round(rent / area, 2) if area > 0 else 0.0
        if not res.get("salutation"):
            res["salutation"] = "Herr"
        res["display_name"] = format_tenant_names(res)
        res["combined_salutation"] = format_tenant_salutation(res)
        res["address_recipient"] = format_tenant_address_block(res)
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
