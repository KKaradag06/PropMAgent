import json
import re
from typing import Dict, Any, Optional
import ollama
from agent.tools import (
    get_all_tenants, 
    find_tenant_by_name, 
    get_expenses_summary, 
    create_utility_statement_for_tenant,
    add_new_tenant,
    get_all_units
)

SYSTEM_PROMPT = """Du bist PropMAgent, ein intelligenter deutscher KI-Assistent für Immobilienverwaltung und Vermietung.
Deine Aufgabe ist es, Nutzeranfragen zu analysieren und strukturierte Aktionen auszuführen.

Verfügbare Aktionen:
1. "generate_statement": Wenn der Nutzer eine Nebenkostenabrechnung oder Abrechnung erstellen möchte.
   Parameter: {"action": "generate_statement", "tenant_name": "Nachname oder Vorname", "year": 2025}
2. "list_tenants": Wenn der Nutzer wissen möchte, welche Mieter es gibt, wer aktuell im Objekt wohnt oder Mieterdaten sucht.
   Parameter: {"action": "list_tenants"}
3. "add_tenant": Wenn der Nutzer einen neuen Mieter anlegen oder hinzufügen möchte.
   Parameter: {
     "action": "add_tenant", 
     "first_name": "Vorname (Pflicht)", 
     "last_name": "Nachname (Pflicht)", 
     "unit_number": "z.B. Wohnung 1 (optional)",
     "cold_rent": 900.0,
     "utility_advance": 200.0,
     "lease_start": "2025-01-01"
   }
   WICHTIG: Nur Vorname und Nachname sind Pflicht! Wenn der Nutzer z. B. nur sagt "Füge Mieter Max Mustermann hinzu", setze first_name="Max", last_name="Mustermann", cold_rent=0, utility_advance=0.
4. "list_expenses": Wenn der Nutzer Ausgaben oder Betriebskosten sehen möchte.
   Parameter: {"action": "list_expenses", "year": 2025}
5. "general_chat": Für allgemeine Fragen, Begrüßungen oder wenn Informationen erfragt werden.
   Parameter: {"action": "general_chat", "answer": "Deine freundliche und fundierte Antwort"}

Antworte IMMER im gültigen JSON-Format ohne Markdown-Codeblöcke wie ```json. Nur das rohe JSON.
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
        res = json.loads(content)
        # Wenn add_tenant erkannt wurde, aber Namen fehlen, Fallback-Prüfung erlauben
        if res.get("action") == "add_tenant" and not res.get("first_name") and not res.get("last_name"):
            pass
        else:
            return res
    except Exception:
        pass

    # Heuristik & Fallback
    prompt_lower = user_prompt.lower()
    
    # Jahr ermitteln (z.B. 2024, 2025)
    year_match = re.search(r"\b(202\d)\b", user_prompt)
    year = int(year_match.group(1)) if year_match else 2025
    
    # Neuer Mieter anlegen
    if any(w in prompt_lower for w in ["hinzufügen", "anlegen", "neu", "erstellen"]) and "mieter" in prompt_lower and not ("abrechnung" in prompt_lower or "nebenkosten" in prompt_lower):
        # Versuche Namen nach 'mieter' oder 'name' zu extrahieren (z. B. "Mieter Hans Peter", "neuen Mieter Max Mustermann hinzufügen")
        name_match = re.search(r"(?:mieter(?:\s+neu(?:en)?)?|name(?:n)?)\s+([A-ZÄÖÜ][a-zäöüß]+)\s+([A-ZÄÖÜ][a-zäöüß]+)", user_prompt)
        first_name = name_match.group(1) if name_match else ""
        last_name = name_match.group(2) if name_match else ""
        
        # Miete suchen
        rent_match = re.search(r"(?:kaltmiete|miete)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", prompt_lower)
        cold_rent = float(rent_match.group(1).replace(",", ".")) if rent_match else 0.0

        # NK suchen
        nk_match = re.search(r"(?:nk|nebenkosten|vorauszahlung)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", prompt_lower)
        utility_advance = float(nk_match.group(1).replace(",", ".")) if nk_match else 0.0

        # Wohnung suchen
        unit_match = re.search(r"(?:wohnung|whg\.?)\s*(\d+[a-zA-Z]?)", prompt_lower)
        unit_str = f"Wohnung {unit_match.group(1)}" if unit_match else ""

        return {
            "action": "add_tenant",
            "first_name": first_name,
            "last_name": last_name,
            "cold_rent": cold_rent,
            "utility_advance": utility_advance,
            "unit_number": unit_str
        }

    # Nebenkostenabrechnung
    if "abrechnung" in prompt_lower or "nebenkosten" in prompt_lower or "pdf" in prompt_lower:
        tenants = get_all_tenants()
        found_name = None
        for t in tenants:
            if t["last_name"].lower() in prompt_lower or t["first_name"].lower() in prompt_lower:
                found_name = t["last_name"]
                break
        if found_name:
            return {"action": "generate_statement", "tenant_name": found_name, "year": year}
        return {"action": "general_chat", "answer": "Für welchen Mieter soll ich die Abrechnung erstellen? (Z. B. Schmidt oder Mustermann)"}
    
    # Mieter auflisten
    if any(w in prompt_lower for w in ["welche mieter", "wer wohnt", "mieterliste", "alle mieter", "mieter"]) and not any(w in prompt_lower for w in ["hinzufügen", "anlegen"]):
        return {"action": "list_tenants"}
        
    if "kosten" in prompt_lower or "ausgaben" in prompt_lower or "beleg" in prompt_lower:
        return {"action": "list_expenses", "year": year}
        
    return {"action": "general_chat", "answer": "Wie kann ich dir bei deinen Mietern, Objekten oder Nebenkostenabrechnungen helfen?"}

def handle_agent_request(user_prompt: str, model: str = "llama3") -> Dict[str, Any]:
    """Zentrale Verarbeitungslogik für Benutzeranfragen."""
    intent = parse_user_intent_ollama(user_prompt, model=model) or {}
    action = intent.get("action", "general_chat")

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
        if not tenants:
            return {
                "success": True,
                "message": "Es sind aktuell keine Mieter in der Datenbank hinterlegt.",
                "data": []
            }
        
        msg = f"### 👥 Aktuelle Mieter im Objekt ({len(tenants)} aktiv):\n\n"
        for idx, t in enumerate(tenants, 1):
            msg += f"{idx}. **{t['first_name']} {t['last_name']}**\n"
            msg += f"   - 🚪 **Wohnung:** {t['unit_number']} ({t['area_sqm']:.1f} m²)\n"
            msg += f"   - 💶 **Kaltmiete:** {t['cold_rent']:.2f} € | **NK-Vorauszahlung:** {t['utility_advance']:.2f} €\n"
            msg += f"   - 📅 **Mietbeginn:** {t['lease_start']}\n"
            if t.get("phone"):
                msg += f"   - 📞 **Telefon:** {t['phone']}\n"
            if t.get("email"):
                msg += f"   - ✉️ **E-Mail:** {t['email']}\n"
            msg += "\n"

        return {
            "success": True,
            "message": msg,
            "data": tenants
        }

    elif action == "add_tenant":
        last_name = intent.get("last_name") or ""
        first_name = intent.get("first_name") or ""
        
        # Falls keine Namen übergeben wurden, Details erfragen
        if not last_name and not first_name:
            units = get_all_units()
            unit_list = ", ".join([u["unit_number"] for u in units]) if units else "Wohnung 1, Wohnung 2"
            return {
                "success": True,
                "message": (
                    "Ja, sehr gerne! Um einen neuen Mieter anzulegen, nenne mir bitte folgende Daten:\n\n"
                    "- **Name:** z. B. *Sabine Meier*\n"
                    f"- **Wohnung:** (Verfügbar: *{unit_list}*)\n"
                    "- **Kaltmiete & Nebenkostenvorauszahlung:** z. B. *850 € Kaltmiete, 200 € NK*\n"
                    "- **Mietbeginn:** z. B. *01.05.2025*\n\n"
                    "💡 *Beispiel-Eingabe:* `Füge Sabine Meier hinzu für Wohnung 2, Kaltmiete 850, NK 200 ab 01.05.2025`"
                ),
                "data": None
            }

        cold_rent = float(intent.get("cold_rent") or 0.0)
        utility_advance = float(intent.get("utility_advance") or 0.0)
        lease_start = intent.get("lease_start") or "2025-01-01"
        unit_number = intent.get("unit_number") or ""
        
        try:
            res = add_new_tenant(
                first_name=first_name,
                last_name=last_name,
                unit_search=unit_number,
                cold_rent=cold_rent,
                utility_advance=utility_advance,
                lease_start=lease_start
            )
            return {
                "success": True,
                "message": (
                    f"✅ **Mieter {first_name} {last_name} wurde erfolgreich angelegt!**\n\n"
                    f"- **Kaltmiete:** {cold_rent:.2f} €\n"
                    f"- **NK-Vorauszahlung:** {utility_advance:.2f} €\n"
                    f"- **Mietbeginn:** {lease_start}\n\n"
                    "Der Mieter ist ab sofort in deiner Mieterliste und für Nebenkostenabrechnungen verfügbar."
                ),
                "data": res
            }
        except Exception as err:
            return {
                "success": False,
                "message": f"Fehler beim Anlegen des Mieters: {str(err)}",
                "data": None
            }

    elif action == "list_expenses":
        year = intent.get("year", 2025)
        expenses = get_expenses_summary(year)
        total = sum(e["amount"] for e in expenses)
        
        msg = f"### 📊 Betriebskosten für das Abrechnungsjahr {year} (Gesamt: {total:,.2f} €):\n\n"
        for e in expenses:
            msg += f"- **{e['category']}**: {e['amount']:.2f} € *(Umlage: {e['allocation_key']}, Details: {e['description']})*\n"
            
        return {
            "success": True,
            "message": msg,
            "data": expenses
        }

    else:
        answer = intent.get("answer", "Ich bin bereit für deine Anweisungen.")
        return {
            "success": True,
            "message": answer,
            "data": None
        }
