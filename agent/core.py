import json
import re
from typing import Dict, Any, Optional
from datetime import datetime
import ollama
from agent.tools import (
    get_all_tenants, 
    find_tenant_by_name, 
    get_expenses_summary, 
    create_utility_statement_for_tenant,
    add_new_tenant,
    get_all_units
)
from reports.pdf_generator import generate_formal_letter_pdf

SYSTEM_PROMPT = """Du bist PropMAgent, ein intelligenter deutscher KI-Assistent für Immobilienverwaltung und Vermietung.
Deine Aufgabe ist es, Nutzeranfragen zu analysieren und strukturierte Aktionen auszuführen.

Verfügbare Aktionen:
1. "write_letter": Wenn der Nutzer einen Brief, ein Anschreiben oder ein Mieterhöhungsschreiben / Mahnung verfassen möchte.
   Parameter: {
     "action": "write_letter",
     "letter_type": "mieterhoehung" | "mahnung" | "allgemein",
     "tenant_name": "Name des Mieters (z. B. Kirdar Karadag)",
     "increase_amount": 50.0,
     "details": "Details oder Begründung aus der Anfrage"
   }
2. "count_tenants": Wenn der Nutzer nach der Anzahl der Mieter fragt (z. B. "wie viele Mieter gibt es?").
   Parameter: {"action": "count_tenants"}
3. "list_tenants": Wenn der Nutzer wissen möchte, wer aktuell im Objekt wohnt oder die Mieterliste sehen will.
   Parameter: {"action": "list_tenants"}
4. "generate_statement": Wenn der Nutzer eine Nebenkostenabrechnung oder Abrechnung erstellen möchte.
   Parameter: {"action": "generate_statement", "tenant_name": "Nachname oder Vorname", "year": 2025}
5. "add_tenant": Wenn der Nutzer einen neuen Mieter anlegen oder hinzufügen möchte.
   Parameter: {
     "action": "add_tenant", 
     "first_name": "Vorname (Pflicht)", 
     "last_name": "Nachname (Pflicht)", 
     "unit_number": "z.B. Wohnung 1 (optional)",
     "cold_rent": 900.0,
     "utility_advance": 200.0,
     "lease_start": "2025-01-01"
   }
6. "list_expenses": Wenn der Nutzer Ausgaben oder Betriebskosten sehen möchte.
   Parameter: {"action": "list_expenses", "year": 2025}
7. "general_chat": Für allgemeine Fragen, Begrüßungen oder Mietrechtsfragen.
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
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        res = json.loads(content)
        if res.get("action") == "add_tenant" and not res.get("first_name") and not res.get("last_name"):
            pass
        elif res.get("action"):
            return res
    except Exception:
        pass

    # Heuristik & Fallback
    prompt_lower = user_prompt.lower()
    
    # 1. Briefe & Mieterhöhung (Priorität vor Mieterliste!)
    if any(w in prompt_lower for w in ["brief", "schreiben", "anschreiben", "mieterhöhung", "mieterhoehung", "erhöhung", "mahnung", "abmahnung"]):
        # Betrag suchen (z. B. "um 50€", "um 50 Euro", "50 €")
        amt_match = re.search(r"(?:um|von|betrag)?\s*(\d+(?:[.,]\d+)?)\s*(?:€|euro|\beuro\b)?", prompt_lower)
        inc_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:€|euro)", prompt_lower)
        
        amount = 0.0
        if inc_match:
            amount = float(inc_match.group(1).replace(",", "."))
        elif amt_match:
            try:
                amount = float(amt_match.group(1).replace(",", "."))
            except Exception:
                amount = 0.0

        # Mietername suchen nach "von", "für", "an"
        name_match = re.search(r"(?:von|für|an)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)", user_prompt)
        tenant_name = name_match.group(1).strip() if name_match else ""
        
        # Falls Name nicht mit Präposition gefunden wurde, vorhandene Mieter prüfen
        if not tenant_name:
            for t in get_all_tenants():
                if t["last_name"].lower() in prompt_lower or t["first_name"].lower() in prompt_lower:
                    tenant_name = f"{t['first_name']} {t['last_name']}"
                    break

        l_type = "mieterhoehung" if any(w in prompt_lower for w in ["mieterhöhung", "mieterhoehung", "erhöhung"]) else "allgemein"
        return {
            "action": "write_letter",
            "letter_type": l_type,
            "tenant_name": tenant_name,
            "increase_amount": amount,
            "details": user_prompt
        }

    # 2. Mieter zählen (z. B. "wie viele Mieter gibt es?")
    if any(p in prompt_lower for p in ["wie viele mieter", "wieviel mieter", "wieviele mieter", "anzahl mieter", "anzahl der mieter"]):
        return {"action": "count_tenants"}

    # 3. Jahr ermitteln (z.B. 2024, 2025)
    year_match = re.search(r"\b(202\d)\b", user_prompt)
    year = int(year_match.group(1)) if year_match else 2025
    
    # 4. Neuer Mieter anlegen
    if any(w in prompt_lower for w in ["hinzufügen", "anlegen", "neu", "erstellen"]) and "mieter" in prompt_lower and not ("abrechnung" in prompt_lower or "nebenkosten" in prompt_lower):
        name_match = re.search(r"(?:mieter(?:\s+neu(?:en)?)?|name(?:n)?)\s+([A-ZÄÖÜ][a-zäöüß]+)\s+([A-ZÄÖÜ][a-zäöüß]+)", user_prompt)
        first_name = name_match.group(1) if name_match else ""
        last_name = name_match.group(2) if name_match else ""
        
        rent_match = re.search(r"(?:kaltmiete|miete)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", prompt_lower)
        cold_rent = float(rent_match.group(1).replace(",", ".")) if rent_match else 0.0

        nk_match = re.search(r"(?:nk|nebenkosten|vorauszahlung)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", prompt_lower)
        utility_advance = float(nk_match.group(1).replace(",", ".")) if nk_match else 0.0

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

    # 5. Nebenkostenabrechnung
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
    
    # 6. Mieter auflisten (NUR bei expliziter Formulierung, nie bei bloßem "mieter")
    if any(w in prompt_lower for w in ["welche mieter", "wer wohnt", "mieterliste", "alle mieter", "zeige mieter", "liste der mieter"]):
        return {"action": "list_tenants"}
        
    if "kosten" in prompt_lower or "ausgaben" in prompt_lower or "beleg" in prompt_lower:
        return {"action": "list_expenses", "year": year}
        
    return {"action": "general_chat", "answer": "Wie kann ich dir bei deinen Mietern, Objekten, Abrechnungen oder Briefen helfen?"}

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

    elif action == "count_tenants":
        tenants = get_all_tenants()
        count = len(tenants)
        if count == 0:
            return {
                "success": True,
                "message": "Es sind aktuell keine Mieter im Objekt erfasst.",
                "data": []
            }
        
        tenant_summary = ", ".join([f"**{t['first_name']} {t['last_name']}** ({t['unit_number']})" for t in tenants])
        return {
            "success": True,
            "message": (
                f"Aktuell sind **{count} Mieter** in deinen Objekten erfasst:\n\n"
                f"{tenant_summary}\n\n"
                "💡 *Wenn du alle Kontaktdaten und Mieten einsehen möchtest, frage: 'Welche Mieter wohnen aktuell im Objekt?'*"
            ),
            "data": tenants
        }

    elif action == "write_letter":
        letter_type = intent.get("letter_type", "mieterhoehung")
        raw_name = (intent.get("tenant_name") or "").strip()
        increase_amt = float(intent.get("increase_amount") or 0.0)

        if not raw_name:
            return {
                "success": False,
                "message": "Für welchen Mieter soll ich das Schreiben verfassen? Bitte nenne mir den Namen des Mieters (z. B. 'für Max Mustermann' oder 'für Kirdar Karadag').",
                "data": None
            }

        # Prüfen, ob der Mieter in der Datenbank existiert
        db_tenant = find_tenant_by_name(raw_name)

        if db_tenant:
            full_name = f"{db_tenant['first_name']} {db_tenant['last_name']}"
            unit_info = f"{db_tenant['unit_number']} ({db_tenant['property_name']})"
            old_rent = float(db_tenant.get("cold_rent") or 900.0)
            addr_line = "Lindenstraße 14, 10115 Berlin"
            prop_name = db_tenant.get("property_name", "Wohnanlage Sonnenhang")
            note = f"👤 *Mieter aus deiner Datenbank zugeordnet: {full_name} ({unit_info})*"
        else:
            full_name = raw_name
            unit_info = "Ihrer Wohneinheit"
            old_rent = 900.0
            addr_line = "Musterstraße 1, 10115 Berlin"
            prop_name = "Immobilienverwaltung"
            note = f"💡 *Hinweis: '{raw_name}' ist bisher nicht in deiner Mieter-Datenbank hinterlegt. Das Schreiben wurde mit Vorlagendaten für diesen Namen erstellt.*"

        new_rent = old_rent + increase_amt

        if letter_type == "mieterhoehung":
            subject = "Mieterhöhungsverlangen gemäß § 558 BGB zur Anpassung an die ortsübliche Vergleichsmiete"
            letter_text = (
                f"Sehr geehrte(r) Frau/Herr {full_name},\n\n"
                f"hiermit kündigen wir Ihnen eine Anpassung der monatlichen Nettokaltmiete für die von Ihnen gemietete Wohnung ({unit_info}) an.\n\n"
                f"Gemäß § 558 BGB sind wir als Vermieter berechtigt, die Miete bis zur ortsüblichen Vergleichsmiete zu erhöhen. "
                f"Die bisherige Miete ist seit mehr als 15 Monaten unverändert geblieben. Die gesetzliche Kappungsgrenze wird dabei strikt beachtet.\n\n"
                f"Die neue Mietzusammensetzung stellt sich wie folgt dar:\n"
                f"• Bisherige Nettokaltmiete: {old_rent:.2f} €\n"
                f"• Monatlicher Erhöhungsbetrag: + {increase_amt:.2f} €\n"
                f"• Neue monatliche Nettokaltmiete: {new_rent:.2f} €\n\n"
                f"Die vereinbarten Vorauszahlungen für die Betriebskosten bleiben hiervon unberührt.\n\n"
                f"Wir bitten Sie höflich, der Mieterhöhung gemäß § 558b Abs. 1 BGB bis zum Ablauf des übernächsten Kalendermonats schriftlich zuzustimmen. "
                f"Die geänderte Miete ist ab dem dritten Monat nach Zugang dieses Schreibens erstmals geschuldet.\n\n"
                f"Für Rückfragen oder Einsicht in die Begründungsunterlagen stehen wir Ihnen gerne zur Verfügung."
            )
        else:
            subject = "Mitteilung der Hausverwaltung"
            letter_text = (
                f"Sehr geehrte(r) Frau/Herr {full_name},\n\n"
                f"wir wenden uns heute bezüglich Ihres Mietverhältnisses ({unit_info}) an Sie.\n\n"
                f"{intent.get('details', '')}\n\n"
                f"Bitte nehmen Sie diese Mitteilung zur Kenntnis. Bei Rückfragen stehen wir Ihnen jederzeit gern zur Verfügung."
            )

        pdf_path = generate_formal_letter_pdf(
            recipient_name=full_name,
            subject=subject,
            letter_text=letter_text,
            address_line=addr_line,
            sender_name="Hausverwaltung",
            property_name=prop_name
        )

        msg = (
            f"📄 **Offizielles Schreiben für {full_name} erstellt!**\n\n"
            f"{note}\n\n"
            f"**Betreff:** {subject}\n\n"
            f"---\n\n"
            f"{letter_text}\n\n"
            f"---\n\n"
            f"📥 *Das druckfertige PDF-Dokument wurde generiert und steht unten zum Download bereit.*"
        )

        return {
            "success": True,
            "message": msg,
            "pdf_path": pdf_path,
            "data": None
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
