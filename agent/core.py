import json
import re
from typing import Dict, Any, Optional
import ollama
from agent.tools import (
    get_all_tenants, 
    find_tenant_by_name, 
    get_expenses_summary, 
    create_utility_statement_for_tenant
)

SYSTEM_PROMPT = """Du bist PropMAgent, ein intelligenter deutscher KI-Assistent für Immobilienverwaltung und Vermietung.
Deine Aufgabe ist es, Nutzeranfragen zu analysieren und strukturierte Aktionen auszuführen.

Verfügbare Aktionen:
1. "generate_statement": Wenn der Nutzer eine Nebenkostenabrechnung oder Abrechnung erstellen möchte.
   Parameter: {"action": "generate_statement", "tenant_name": "Nachname oder Vorname", "year": 2025}
2. "list_tenants": Wenn der Nutzer wissen möchte, welche Mieter es gibt oder Mieterdaten sucht.
   Parameter: {"action": "list_tenants"}
3. "list_expenses": Wenn der Nutzer Ausgaben oder Betriebskosten sehen möchte.
   Parameter: {"action": "list_expenses", "year": 2025}
4. "general_chat": Für allgemeine Fragen zum Mietrecht, zur Bedienung oder Erklärungen.
   Parameter: {"action": "general_chat", "answer": "Deine freundliche und fundierte Antwort"}

Antworte IMMER im gültigen JSON-Format ohne Markdown-Codeblöcke wie ```json. Nur das rohe JSON.
Beispiel:
{"action": "generate_statement", "tenant_name": "Schmidt", "year": 2025}
"""

def parse_user_intent_ollama(user_prompt: str, model: str = "llama3") -> Dict[str, Any]:
    """Analysiert den Nutzerprompt mit Ollama (Llama 3)."""
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            options={"temperature": 0.1}
        )
        content = response["message"]["content"].strip()
        # JSON bereinigen, falls Backticks vorhanden sind
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        return json.loads(content)
    except Exception as e:
        # Fallback Heuristik, falls Modell nicht erreichbar oder unformatiert
        prompt_lower = user_prompt.lower()
        
        # Jahr ermitteln (z.B. 2024, 2025)
        year_match = re.search(r"\b(202\d)\b", user_prompt)
        year = int(year_match.group(1)) if year_match else 2025
        
        if "abrechnung" in prompt_lower or "nebenkosten" in prompt_lower or "pdf" in prompt_lower:
            # Mietername suchen
            tenants = get_all_tenants()
            found_name = None
            for t in tenants:
                if t["last_name"].lower() in prompt_lower or t["first_name"].lower() in prompt_lower:
                    found_name = t["last_name"]
                    break
            if found_name:
                return {"action": "generate_statement", "tenant_name": found_name, "year": year}
        
        if "mieter" in prompt_lower:
            return {"action": "list_tenants"}
        if "kosten" in prompt_lower or "ausgaben" in prompt_lower or "beleg" in prompt_lower:
            return {"action": "list_expenses", "year": year}
            
        return {"action": "general_chat", "answer": "Wie kann ich dir bei deinen Mietern, Objekten oder Nebenkostenabrechnungen helfen?"}

def handle_agent_request(user_prompt: str, model: str = "llama3") -> Dict[str, Any]:
    """Zentrale Verarbeitungslogik für Benutzeranfragen."""
    intent = parse_user_intent_ollama(user_prompt, model=model)
    action = intent.get("action")

    if action == "generate_statement":
        tenant_name = intent.get("tenant_name", "")
        year = intent.get("year", 2025)
        tenant = find_tenant_by_name(tenant_name)
        
        if not tenant:
            return {
                "success": False,
                "message": f"Kein Mieter mit dem Namen '{tenant_name}' in der Datenbank gefunden.",
                "data": None
            }
        
        bill = create_utility_statement_for_tenant(tenant["tenant_id"], year)
        
        res_type = "Guthaben" if bill["is_refund"] else "Nachzahlung"
        amt = abs(bill["balance"])
        msg = (
            f"✅ **Nebenkostenabrechnung für {bill['tenant']['first_name']} {bill['tenant']['last_name']} ({year}) erfolgreich erstellt!**\n\n"
            f"- **Wohnung:** {bill['tenant']['unit_number']} ({bill['tenant']['tenant_sqm']} m²)\n"
            f"- **Gesamtkosten Mieteranteil:** {bill['total_tenant_share']:.2f} €\n"
            f"- **Geleistete Vorauszahlungen:** {bill['prepayments_paid']:.2f} €\n"
            f"- **Ergebnis:** **{res_type} von {amt:.2f} €**\n\n"
            f"📄 Das druckfertige PDF wurde generiert: `{bill['pdf_path']}`"
        )
        return {
            "success": True,
            "message": msg,
            "pdf_path": bill["pdf_path"],
            "bill_data": bill
        }

    elif action == "list_tenants":
        tenants = get_all_tenants()
        return {
            "success": True,
            "message": f"Es wurden {len(tenants)} Mieter in deiner Datenbank gefunden.",
            "data": tenants
        }

    elif action == "list_expenses":
        year = intent.get("year", 2025)
        expenses = get_expenses_summary(year)
        total = sum(e["amount"] for e in expenses)
        return {
            "success": True,
            "message": f"Betriebskosten für {year}: Insgesamt {len(expenses)} Positionen mit Gesamtsumme **{total:.2f} €**.",
            "data": expenses
        }

    else:
        answer = intent.get("answer", "Ich bin bereit für deine Anweisungen.")
        return {
            "success": True,
            "message": answer,
            "data": None
        }
