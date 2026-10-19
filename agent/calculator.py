from typing import Dict, Any, List
from database.db import query_db

def calculate_utility_bill(tenant_id: int, year: int) -> Dict[str, Any]:
    """
    Berechnet die Nebenkostenabrechnung für einen Mieter für ein bestimmtes Jahr
    exakt und deterministisch in Python (keine Rundungs- oder Rechenfehler durch KI).
    """
    # 1. Mieter- und Wohnungsdaten abrufen
    tenant_query = """
        SELECT 
            t.id as tenant_id, t.salutation, t.first_name, t.last_name, t.email, t.phone,
            t.cold_rent, t.utility_advance,
            u.id as unit_id, u.unit_number, u.floor, u.area_sqm as tenant_sqm,
            p.id as property_id, p.name as property_name, p.street, p.zip_code, p.city,
            p.total_area_sqm
        FROM tenants t
        JOIN units u ON t.unit_id = u.id
        JOIN properties p ON u.property_id = p.id
        WHERE t.id = ?;
    """
    tenants = query_db(tenant_query, (tenant_id,))
    if not tenants:
        raise ValueError(f"Mieter mit ID {tenant_id} wurde nicht gefunden.")
    
    tenant_info = tenants[0]
    property_id = tenant_info["property_id"]
    tenant_sqm = tenant_info["tenant_sqm"]
    total_sqm = tenant_info["total_area_sqm"]
    
    # Gesamtanzahl Einheiten der Immobilie abrufen
    units_count_res = query_db("SELECT COUNT(*) as count FROM units WHERE property_id = ?;", (property_id,))
    total_units = units_count_res[0]["count"] if units_count_res else 1

    # 2. Alle Ausgaben für das Jahr abrufen
    expenses_query = """
        SELECT id, category, description, amount, allocation_key, receipt_date
        FROM expenses
        WHERE property_id = ? AND year = ?
        ORDER BY category ASC;
    """
    expenses = query_db(expenses_query, (property_id, year))
    
    breakdown: List[Dict[str, Any]] = []
    total_tenant_share = 0.0
    total_property_expenses = 0.0

    for exp in expenses:
        cat = exp["category"]
        desc = exp["description"] or ""
        total_amt = float(exp["amount"])
        key = exp["allocation_key"]
        total_property_expenses += total_amt

        if key == "sqm":
            # Anteil nach Quadratmetern
            share_ratio = tenant_sqm / total_sqm if total_sqm > 0 else 0
            tenant_share = round(total_amt * share_ratio, 2)
            key_text = f"Fläche ({tenant_sqm:.1f} m² / {total_sqm:.1f} m²)"
        elif key == "units":
            # Anteil nach Wohneinheiten
            share_ratio = 1.0 / total_units if total_units > 0 else 1
            tenant_share = round(total_amt * share_ratio, 2)
            key_text = f"Einheit (1 / {total_units})"
        else: # direct
            tenant_share = round(total_amt, 2)
            key_text = "Direkt"

        total_tenant_share += tenant_share

        breakdown.append({
            "category": cat,
            "description": desc,
            "total_amount": total_amt,
            "allocation_key_text": key_text,
            "tenant_share": tenant_share
        })

    # 3. Geleistete Vorauszahlungen abrufen
    payments_query = """
        SELECT SUM(amount) as paid_sum
        FROM payments
        WHERE tenant_id = ? 
          AND strftime('%Y', payment_date) = ?
          AND payment_type IN ('utility_advance', 'total');
    """
    payments_res = query_db(payments_query, (tenant_id, str(year)))
    prepayments = float(payments_res[0]["paid_sum"] or 0.0)

    # 4. Differenz (Nachzahlung > 0 / Guthaben < 0)
    balance = round(total_tenant_share - prepayments, 2)

    return {
        "tenant": tenant_info,
        "year": year,
        "total_property_expenses": round(total_property_expenses, 2),
        "total_tenant_share": round(total_tenant_share, 2),
        "prepayments_paid": round(prepayments, 2),
        "balance": balance, # positiv = Nachzahlung, negativ = Guthaben
        "is_refund": balance < 0,
        "breakdown": breakdown
    }
