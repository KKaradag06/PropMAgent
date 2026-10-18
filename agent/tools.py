from typing import List, Dict, Any, Optional
from database.db import query_db
from agent.calculator import calculate_utility_bill
from reports.pdf_generator import generate_utility_bill_pdf

def get_all_tenants() -> List[Dict[str, Any]]:
    """Gibt alle Mieter mit Wohneinheit und Liegenschaft zurück."""
    sql = """
        SELECT 
            t.id as tenant_id, t.first_name, t.last_name, t.email, t.phone,
            t.cold_rent, t.utility_advance, t.lease_start, t.lease_end,
            u.unit_number, u.area_sqm,
            p.name as property_name
        FROM tenants t
        JOIN units u ON t.unit_id = u.id
        JOIN properties p ON u.property_id = p.id
        ORDER BY t.last_name ASC;
    """
    return query_db(sql)

def find_tenant_by_name(name_query: str) -> Optional[Dict[str, Any]]:
    """Sucht einen Mieter nach Vor- oder Nachname (case-insensitive)."""
    search_term = f"%{name_query.strip().lower()}%"
    sql = """
        SELECT 
            t.id as tenant_id, t.first_name, t.last_name,
            u.unit_number, p.name as property_name
        FROM tenants t
        JOIN units u ON t.unit_id = u.id
        JOIN properties p ON u.property_id = p.id
        WHERE LOWER(t.first_name) LIKE ? OR LOWER(t.last_name) LIKE ?
           OR LOWER(t.first_name || ' ' || t.last_name) LIKE ?
        LIMIT 1;
    """
    results = query_db(sql, (search_term, search_term, search_term))
    return results[0] if results else None

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
