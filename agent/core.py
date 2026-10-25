import json
import re
from typing import Dict, Any, Optional, Tuple
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
from reports.docx_generator import generate_formal_letter_docx
from database.settings import get_all_settings, get_setting

SYSTEM_PROMPT = """Du bist PropMAgent, ein intelligenter deutscher KI-Assistent für Immobilienverwaltung und Vermietung.
Deine Aufgabe ist es, Nutzeranfragen zu analysieren und strukturierte Aktionen auszuführen.

Verfügbare Aktionen:
1. "write_letter": Wenn der Nutzer einen Brief, ein Anschreiben oder ein formelles Vermieterschreiben verfassen möchte (z. B. Mieterhöhung, Nebenkostensenkung, Nebenkostenerhöhung, Anpassung, Mahnung, Kündigung, Bankverbindung, Information).
   Parameter: {
     "action": "write_letter",
     "tenant_name": "Name des Mieters (z. B. Kirdar oder Max Mustermann)",
     "user_instruction": "Die genaue Anweisung des Nutzers für das Schreiben"
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

def draft_letter_with_ai(
    user_prompt: str,
    recipient_name: str,
    tenant_info: Optional[Dict[str, Any]] = None,
    model: str = "llama3"
) -> Dict[str, str]:
    """
    Nutzt Ollama (Llama 3), um jedes beliebige Vermieterschreiben maßgeschneidert,
    juristisch fundiert nach deutschem Mietrecht (BGB) und im perfekten Tonfall zu verfassen.
    Gibt ein Dict mit {"subject": ..., "body": ...} zurück.
    """
    import calendar
    from datetime import timedelta
    now = datetime.now()
    today_str = now.strftime("%d.%m.%Y")
    due_in_7_days = (now + timedelta(days=7)).strftime("%d.%m.%Y")
    due_in_14_days = (now + timedelta(days=14)).strftime("%d.%m.%Y")

    m_end = (now.month + 2 - 1) % 12 + 1
    y_end = now.year + (now.month + 2 - 1) // 12
    last_day = calendar.monthrange(y_end, m_end)[1]
    deadline_date_str = f"{last_day:02d}.{m_end:02d}.{y_end}"
    m_eff = (now.month + 3 - 1) % 12 + 1
    y_eff = now.year + (now.month + 3 - 1) // 12
    effective_cold_str = f"01.{m_eff:02d}.{y_eff}"
    effective_nk_str = f"01.{m_end:02d}.{y_end}"

    salutation = (tenant_info.get("salutation") if tenant_info else "") or ""
    is_all_tenants = (tenant_info and tenant_info.get("is_all_tenants")) or any(
        term in recipient_name.lower() or term in user_prompt.lower()
        for term in ["alle mieter", "alle mieterinnen", "hausgemeinschaft", "sämtliche mieter", "alle bewohner"]
    )

    if is_all_tenants:
        salutation = "alle"
        formal_greeting = "Sehr geehrte Mieterinnen und Mieter"
        prop_str = (tenant_info.get("property_name") if tenant_info else "") or "Ihrer Wohnanlage"
        context_lines = [
            f"Empfänger: Alle Mieterinnen und Mieter der Liegenschaft ({prop_str})",
            f"Verbindliche Briefanredezeile: {formal_greeting},",
            f"Mietobjekt / Liegenschaft: {prop_str}"
        ]
    else:
        if tenant_info and tenant_info.get("combined_salutation"):
            formal_greeting = tenant_info["combined_salutation"]
            disp_name = tenant_info.get("display_name", recipient_name)
            context_lines = [
                f"Empfänger: {disp_name}",
                f"Anrede: Gemeinschaftlicher Mietvertrag (mehrere Mieter)",
                f"Verbindliche Briefanredezeile: {formal_greeting},"
            ]
        else:
            if not salutation:
                salutation = "Frau" if any(fn in recipient_name.lower() for fn in ["laura", "sabine", "anna", "maria", "sarah", "julia", "lisa"]) else "Herr"
            last_name = (tenant_info.get("last_name") if tenant_info else recipient_name.split()[-1]).strip()
            formal_greeting = f"Sehr geehrte Frau {last_name}" if salutation == "Frau" else f"Sehr geehrter Herr {last_name}"
            context_lines = [
                f"Empfänger: {recipient_name}",
                f"Anrede: {salutation}",
                f"Verbindliche Briefanredezeile: {formal_greeting},"
            ]
        if tenant_info:
            context_lines.append(f"Mietobjekt: {tenant_info.get('property_name', 'Wohnanlage')}")
            context_lines.append(f"Wohneinheit: {tenant_info.get('unit_number', '')}")
            context_lines.append(f"Reguläre monatliche Nettokaltmiete: {tenant_info.get('cold_rent', 0.0):.2f} €")
            context_lines.append(f"Reguläre monatliche Nebenkostenvorauszahlung: {tenant_info.get('utility_advance', 0.0):.2f} €")
            if tenant_info.get('price_per_sqm'):
                context_lines.append(f"Quadratmeterpreis: {tenant_info.get('price_per_sqm'):.2f} €/m²")
            if tenant_info.get('lease_start'):
                context_lines.append(f"Mietbeginn: {tenant_info.get('lease_start')}")
    
    tenant_context = "\n".join(context_lines)

    settings = get_all_settings()
    is_private = settings.get("landlord_type", "private") == "private"
    default_sender = "Kirdar Karadag" if is_private else "Hausverwaltung Sonnenhang"
    landlord_name = settings.get("landlord_name", default_sender)
    if is_private and landlord_name == "Hausverwaltung Sonnenhang":
        landlord_name = settings.get("landlord_contact_person") or "Kirdar Karadag"
    landlord_contact = settings.get("landlord_contact_person", "")
    landlord_street = settings.get("landlord_street", "Lindenstraße 14")
    landlord_zip = settings.get("landlord_zip", "10115")
    landlord_city = settings.get("landlord_city", "Berlin")
    landlord_phone = settings.get("landlord_phone", "+49 30 12345678")
    landlord_email = settings.get("landlord_email", "kirdar@karadag.de" if is_private else "verwaltung@sonnenhang.de")
    landlord_iban = settings.get("landlord_iban", "")
    landlord_bic = settings.get("landlord_bic", "")
    landlord_bank = settings.get("landlord_bank_name", "")
    landlord_holder = settings.get("landlord_account_holder", landlord_name)
    closing_phrase = settings.get("default_closing_phrase", "Mit freundlichen Grüßen")
    signature_title = settings.get("default_signature_title", landlord_name)
    if is_private and "hausverwaltung" in signature_title.lower():
        signature_title = f"{landlord_name}\n(Vermieter)"
    def_deadline = settings.get("default_payment_deadline_days", "14")

    if is_private:
        landlord_context = f"""KONTEXT DES ABSENDERS (PRIVATER VERMIETER):
- Vermieter (Privatperson): {landlord_name}
- Organisationsform: PRIVATER VERMIETER (Privatperson, KEINE Hausverwaltung)
- Anschrift: {landlord_street}, {landlord_zip} {landlord_city}
- Kontakt: Telefon {landlord_phone}, E-Mail {landlord_email}
- Bankverbindung: IBAN {landlord_iban}, BIC {landlord_bic}, Kreditinstitut {landlord_bank}, Kontoinhaber {landlord_holder}
- Standard-Zahlungsfrist: {def_deadline} Tage
- Grußformel: {closing_phrase}
- Unterschrift: {signature_title}

STRIKTE VORGABEN FÜR PRIVATEN VERMIETER:
- Das Schreiben stammt direkt von einem PRIVATEN VERMIETER (Privatperson, keine Hausverwaltung).
- Verwende NIEMALS Wörter wie 'Hausverwaltung', 'Verwaltung' oder 'unsere Verwaltung' im Text oder im Betreff!
- Betreffzeilen dürfen niemals 'Hausverwaltung' enthalten (z. B. 'Mitteilung Ihres Vermieters' statt 'Mitteilung der Hausverwaltung').
- Formuliere professionell aus Sicht des privaten Vermieters ('als Ihr Vermieter', 'ich bitte Sie', 'stehe ich Ihnen gerne zur Verfügung')."""
    else:
        landlord_context = f"""KONTEXT DES ABSENDERS (HAUSVERWALTUNG):
- Name der Hausverwaltung: {landlord_name}
- Ansprechpartner: {landlord_contact}
- Anschrift: {landlord_street}, {landlord_zip} {landlord_city}
- Kontakt: Telefon {landlord_phone}, E-Mail {landlord_email}
- Bankverbindung: IBAN {landlord_iban}, BIC {landlord_bic}, Kreditinstitut {landlord_bank}, Kontoinhaber {landlord_holder}
- Standard-Zahlungsfrist: {def_deadline} Tage
- Grußformel: {closing_phrase}
- Unterschrift: {signature_title}"""

    cur_cold = float(tenant_info.get("cold_rent", 900.0)) if tenant_info else 900.0
    cur_nk = float(tenant_info.get("utility_advance", 220.0)) if tenant_info else 220.0
    unit_str = tenant_info.get("unit_number", "Wohneinheit") if tenant_info else "Wohneinheit"
    prompt_lower = user_prompt.lower()

    # Prozent- oder Euro-Beträge vorab extrahieren und berechnen
    pct_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|prozent)", prompt_lower)
    is_percentage = bool(pct_match)
    pct_val = float(pct_match.group(1).replace(",", ".")) if pct_match else 0.0

    amt_match = re.search(r"(?:rückstand|rueckstand|betrag|von|um|über|ueber)?\s*(\d+(?:[.,]\d+)?)\s*(?:€|euro|\beuro\b)?", prompt_lower)
    euro_val = float(amt_match.group(1).replace(",", ".")) if amt_match and not is_percentage else 0.0

    # Mieterhöhung Berechnungen
    calc_ma_diff = round(cur_cold * (pct_val / 100.0), 2) if is_percentage else (euro_val if euro_val > 0 else 50.0)
    calc_ma_inc_str = f"+ {pct_val:.1f} % (+ {calc_ma_diff:.2f} €)" if is_percentage else f"+ {calc_ma_diff:.2f} €"
    calc_ma_new_cold = cur_cold + calc_ma_diff
    calc_ma_new_total = calc_ma_new_cold + cur_nk

    # Mietsenkung Berechnungen
    calc_ms_diff = round(cur_cold * (pct_val / 100.0), 2) if is_percentage else (euro_val if euro_val > 0 else 50.0)
    calc_ms_dec_str = f"- {pct_val:.1f} % (- {calc_ms_diff:.2f} €)" if is_percentage else f"- {calc_ms_diff:.2f} €"
    calc_ms_new_cold = max(0.0, cur_cold - calc_ms_diff)
    calc_ms_new_total = calc_ms_new_cold + cur_nk

    # Nebenkosten Berechnungen
    calc_nk_diff = round(cur_nk * (pct_val / 100.0), 2) if is_percentage else (euro_val if euro_val > 0 else 20.0)
    calc_nk_diff_str = f"{pct_val:.1f} % ({calc_nk_diff:.2f} €)" if is_percentage else f"{calc_nk_diff:.2f} €"
    calc_nke_new_nk = cur_nk + calc_nk_diff
    calc_nke_total = cur_cold + calc_nke_new_nk
    calc_nks_new_nk = max(0.0, cur_nk - calc_nk_diff)
    calc_nks_total = cur_cold + calc_nks_new_nk

    # Zahlungsrückstand & Frist
    overdue_calc = euro_val if euro_val > 0 else 80.0
    days_match = re.search(r"(?:frist|innerhalb)?\s*(?:von)?\s*(\d+)\s*(?:tagen|tage|t)\b", prompt_lower)
    calc_days = int(days_match.group(1)) if days_match else 7
    due_calc_str = (now + timedelta(days=calc_days)).strftime("%d.%m.%Y")

    role_desc = "ein privater Vermieter und Experte für deutsches Mietrecht (BGB)" if is_private else "ein erfahrener Hausverwalter und Experte für deutsches Mietrecht (BGB)"
    system_instruction = f"""Du bist {role_desc}.
Deine Aufgabe ist es, anhand der Nutzeranweisung ein professionelles, rechtssicheres und druckfertiges Schreiben an den Mieter zu verfassen.

{landlord_context}

KONTEXT DES MIETERS:
{tenant_context}

GESETZLICHE FRISTEN & VORBERECHNETE WERTE (Stand: {today_str}):
- Reguläre Nettokaltmiete: {cur_cold:.2f} €
- Reguläre Nebenkostenvorauszahlung: {cur_nk:.2f} €
- Bei Mieterhöhung (§ 558 BGB):
  * Erhöhung: {calc_ma_inc_str}
  * Neue Kaltmiete: {calc_ma_new_cold:.2f} € | Neue Gesamtmiete: {calc_ma_new_total:.2f} €
  * Wirksamkeit der neuen Miete ab: {effective_cold_str}
  * Gesetzliche Zustimmungsfrist (§ 558b Abs. 1 BGB): bis zum {deadline_date_str}
- Bei Mietsenkung:
  * Senkung: {calc_ms_dec_str}
  * Neue Kaltmiete: {calc_ms_new_cold:.2f} € | Neue Gesamtmiete: {calc_ms_new_total:.2f} €
  * Wirksamkeit ab: {effective_nk_str}
- Bei Nebenkostenanpassung (§ 560 Abs. 4 BGB):
  * Anpassung: {calc_nk_diff_str}
  * Wirksamkeit ab: {effective_nk_str}
- Bei Zahlungsfristen:
  * Zahlungsfrist ({calc_days} Tage): bis zum {due_calc_str}
  * Rückstand: {overdue_calc:.2f} €

WICHTIGE REGELN & PFLICHTINHALTE NACH KATEGORIE:

1. MIETERHÖHUNG (KALTMIETE nach § 558 BGB):
   - Betreff: "Mieterhöhungsverlangen gemäß § 558 BGB für {unit_str}"
   - Der Brieftext MUSS ausformuliert sein (mindestens 4 Absätze):
     1. Ankündigung der Erhöhung der Nettokaltmiete gemäß § 558 BGB zur Anpassung an die ortsübliche Vergleichsmiete und Hinweis auf Einhaltung der Jahressperrfrist sowie der gesetzlichen Kappungsgrenze.
     2. Genaue Aufstellung der Miete:
        • Bisherige monatliche Nettokaltmiete: {cur_cold:.2f} €
        • Erhöhungsbetrag: {calc_ma_inc_str}
        • Neue monatliche Nettokaltmiete ab dem {effective_cold_str}: {calc_ma_new_cold:.2f} €
        • Unveränderte Nebenkostenvorauszahlung: {cur_nk:.2f} €
        • Neue monatliche Gesamtmiete: {calc_ma_new_total:.2f} €
     3. Aufforderung zur schriftlichen Zustimmung gemäß § 558b Abs. 1 BGB bis zum Ablauf der Zustimmungsfrist am {deadline_date_str} sowie Bitte um rechtzeitige Anpassung der Mietzahlung / des Dauerauftrags ab {effective_cold_str}.
     4. Höflicher Schlusssatz mit Bereitschaft für Rückfragen.

2. MIETSENKUNG (KALTMIETE):
   - Betreff: "Mitteilung über eine Herabsetzung der monatlichen Nettokaltmiete für {unit_str}"
   - Ausführlicher Brieftext:
     1. Erfreuliche Mitteilung über die Senkung der Kaltmiete ab {effective_nk_str}.
     2. Genaue Aufstellung: bisherige Kaltmiete ({cur_cold:.2f} €), Senkungsbetrag ({calc_ms_dec_str}), neue Kaltmiete ({calc_ms_new_cold:.2f} €), neue Gesamtmiete ({calc_ms_new_total:.2f} €).
     3. Bitte um Anpassung des Dauerauftrags bzw. Hinweis auf automatische Lastschriftanpassung.

3. NEBENKOSTENANPASSUNG (§ 560 Abs. 4 BGB):
   - Betreff: "Anpassung der monatlichen Betriebskostenvorauszahlung gemäß § 560 Abs. 4 BGB für {unit_str}"
   - Ausführlicher Brieftext:
     1. Begründung der Anpassung nach § 560 Abs. 4 BGB (veränderte Bewirtschaftungskosten/Abrechnung) ab {effective_nk_str}.
     2. Aufstellung: bisherige Vorauszahlung ({cur_nk:.2f} €), Anpassung ({calc_nk_diff_str}), neue Vorauszahlung, unveränderte Kaltmiete ({cur_cold:.2f} €), neue Gesamtmiete.
     3. Bitte um Anpassung des Dauerauftrags.

4. ZAHLUNGSERINNERUNGEN & MAHNUNGEN:
   - Betreff: "Zahlungserinnerung: Ausstehende Mietzahlung für {unit_str}"
   - Ausführlicher Brieftext:
     1. Höflicher Hinweis auf den konkreten Zahlungsrückstand in Höhe von {overdue_calc:.2f} €.
     2. Fristsetzung innerhalb von {calc_days} Tagen (bis zum {due_calc_str}) auf das Mietkonto (IBAN: {landlord_iban}, Bank: {landlord_bank}).
     3. Gegenstandslosklausel für den Fall, dass der Betrag bereits überwiesen wurde.

5. ABMAHNUNGEN:
   - Wegen Zahlungsverzugs: Konkreten Zahlungsrückstand ({overdue_calc:.2f} €) nennen, Frist setzen bis {due_calc_str}, ausdrücklicher rechtlicher Hinweis auf § 543 Abs. 2 Nr. 3 BGB (außerordentliche Kündigung).
   - Wegen Hausordnung / Verhalten: Konkreten Vorfall darlegen, Aufforderung zur sofortigen Unterlassung, Kündigungsandrohung bei Wiederholung.

6. MIETBESCHEINIGUNGEN:
   - Betreff: "Miet- und Mietschuldenfreiheitsbescheinigung für {unit_str}"
   - Bestätigung des Mietverhältnisses, der Miethöhe und dass alle Mietzahlungen stets vollständig und fristgerecht geleistet wurden (Mietschuldenfreiheit).

7. HANDWERKER / WARTUNG:
   - Betreff: "Ankündigung von Handwerker- und Instandhaltungsarbeiten"
   - Art der Arbeiten, Termin / Zeitfenster, Bitte um Zutritt, Kontaktdaten für Rückfragen.

8. BANKVERBINDUNG:
   - Betreff: "Wichtige Mitteilung: Aktualisierung der Bankverbindung für Mietzahlungen"
   - Datum des Wechsels, vollständige neue Kontodaten (IBAN {landlord_iban}, BIC {landlord_bic}, {landlord_bank}), Hinweis zur Dauerauftragsanpassung.

9. HAUSORDNUNG / RUNDSCHREIBEN (AN ALLE MIETER):
   - Aussagekräftiger Betreff, klare Darlegung der Regeln/Ruhezeiten, Appell an gegenseitige Rücksichtnahme.

10. ALLGEMEINE ANWEISUNGEN:
    - Verfasse in mindestens 2-3 Absätzen ein vollständiges, höfliches Schreiben, das genau auf die Nutzeranweisung eingeht.

STRENGSTE REGELN FÜR DEN SCHLÜSSEL 'body':
- 'body' darf NIEMALS leer sein oder nur aus Anrede und Grußformel bestehen!
- 'body' MUSS den gesamten, VOLLSTÄNDIGEN Fließtext des Schreibens enthalten (mindestens 3-5 vollständige Absätze mit Einleitung, allen Beträgen/Fristen/Begründungen und Schlusssatz)!
- Der Brieftext MUSS mit der exakten Anredezeile beginnen: '{formal_greeting},'
- Grußformel stets 'Mit freundlichen Grüßen' OHNE Komma am Ende.
- In der Betreffzeile NIEMALS das Wort 'Betreff' oder 'Betreff:' voranstellen.
- Antworte AUSSCHLIESSLICH im gültigen JSON-Format mit den Schlüsseln "subject" und "body".
"""

    def _is_substantive_letter(d: Any) -> bool:
        if not isinstance(d, dict):
            return False
        b = str(d.get("body", "")).strip()
        if len(b) < 120:
            return False
        # Prüfen, ob nach Entfernen von Anrede und Grußformel noch echter Inhalt vorliegt
        cl = re.sub(r"^(?:Sehr geehrte[^\n]*|Hallo[^\n]*|Guten Tag[^\n]*)\s*", "", b, flags=re.IGNORECASE)
        cl = re.sub(r"\n*(?:Mit freundlichen Grüßen|Freundliche Grüße|Herzliche Grüße)[,\s]*.*$", "", cl, flags=re.IGNORECASE | re.DOTALL).strip()
        return len(cl) >= 80

    try:
        response = ollama.chat(
            model=model,
            format="json",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Nutzeranweisung: {user_prompt}"}
            ],
            options={"temperature": 0.2}
        )
        content = response["message"]["content"].strip()
        data = {}
        try:
            data = json.loads(content)
        except Exception:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))

        if _is_substantive_letter(data):
            # Bei gemeinschaftlichen Mietverträgen DIN-Anredezeile für alle Vertragspartner garantieren
            if tenant_info and tenant_info.get("combined_salutation"):
                expected_greeting = tenant_info["combined_salutation"]
                body_lines = data["body"].split("\n")
                if body_lines and not (expected_greeting.lower() in body_lines[0].lower()):
                    if any(w in body_lines[0].lower() for w in ["sehr geehrte", "sehr geehrter", "hallo", "guten tag"]):
                        body_lines[0] = f"{expected_greeting},"
                        data["body"] = "\n".join(body_lines)
            return data
    except Exception:
        pass

    return _build_fallback_letter(user_prompt, recipient_name, tenant_info)

def _build_fallback_letter(user_prompt: str, recipient_name: str, tenant_info: Optional[Dict[str, Any]]) -> Dict[str, str]:
    import calendar
    from datetime import timedelta
    prompt_lower = user_prompt.lower()
    
    settings = get_all_settings()
    is_private = settings.get("landlord_type", "private") == "private"
    default_sender = "Kirdar Karadag" if is_private else "Hausverwaltung Sonnenhang"
    landlord_name = settings.get("landlord_name", default_sender)
    if is_private and landlord_name == "Hausverwaltung Sonnenhang":
        landlord_name = settings.get("landlord_contact_person") or "Kirdar Karadag"
    landlord_holder = settings.get("landlord_account_holder", landlord_name)
    if is_private and (not landlord_holder or "hausverwaltung" in landlord_holder.lower()):
        landlord_holder = landlord_name
    landlord_iban = settings.get("landlord_iban", "DE12 1005 0000 0123 4567 89")
    landlord_bic = settings.get("landlord_bic", "BELADEB1XXX")
    landlord_bank = settings.get("landlord_bank_name", "Berliner Sparkasse")
    landlord_phone = settings.get("landlord_phone", "")
    default_days = int(settings.get("default_payment_deadline_days", "14"))
    
    is_all_tenants = (tenant_info and tenant_info.get("is_all_tenants")) or any(
        term in recipient_name.lower() or term in user_prompt.lower()
        for term in ["alle mieter", "alle mieterinnen", "hausgemeinschaft", "sämtliche mieter", "alle bewohner"]
    )

    if is_all_tenants:
        sal_greeting = "Sehr geehrte Mieterinnen und Mieter"
        prop_str = (tenant_info.get('property_name') if tenant_info else "") or "Ihrer Wohnanlage"
        unit_str = f"in der Liegenschaft {prop_str}"
        unit_label = f"Liegenschaft {prop_str}"
    else:
        if tenant_info and tenant_info.get("combined_salutation"):
            sal_greeting = tenant_info["combined_salutation"]
            recipient_name = tenant_info.get("display_name", recipient_name)
        else:
            salutation = (tenant_info.get("salutation") if tenant_info else "") or ""
            if not salutation:
                salutation = "Frau" if any(fn in recipient_name.lower() for fn in ["laura", "sabine", "anna", "maria", "sarah", "julia", "lisa"]) else "Herr"

            last_name = (tenant_info.get("last_name") if tenant_info else recipient_name.split()[-1]).strip()
            sal_greeting = f"Sehr geehrte Frau {last_name}" if salutation == "Frau" else f"Sehr geehrter Herr {last_name}"
        unit_str = tenant_info.get("unit_number", "Ihrer gemieteten Wohneinheit") if tenant_info else "Ihrer gemieteten Wohneinheit"
        unit_label = unit_str if unit_str.lower().startswith("wohnung") else f"Wohnung {unit_str}"

    # 1. Prozentangabe prüfen (z. B. "15%", "15 Prozent", "15 %")
    pct_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|prozent)", prompt_lower)
    is_percentage = bool(pct_match)
    pct_val = float(pct_match.group(1).replace(",", ".")) if pct_match else 0.0

    # 2. Absoluten Euro-Betrag ermitteln
    amt_match = re.search(r"(?:rückstand|rueckstand|betrag|von|um|über|ueber)?\s*(\d+(?:[.,]\d+)?)\s*(?:€|euro|\beuro\b)?", prompt_lower)
    euro_val = float(amt_match.group(1).replace(",", ".")) if amt_match and not is_percentage else 0.0

    def fmt_eur(val: float) -> str:
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"

    cur_cold = float(tenant_info.get("cold_rent", 900.0)) if tenant_info else 900.0
    cur_nk = float(tenant_info.get("utility_advance", 220.0)) if tenant_info else 220.0

    # Gesetzliche Termine berechnen (DIN / BGB)
    now = datetime.now()
    m_end = (now.month + 2 - 1) % 12 + 1
    y_end = now.year + (now.month + 2 - 1) // 12
    last_day = calendar.monthrange(y_end, m_end)[1]
    deadline_date_str = f"{last_day:02d}.{m_end:02d}.{y_end}"

    m_eff = (now.month + 3 - 1) % 12 + 1
    y_eff = now.year + (now.month + 3 - 1) // 12
    effective_cold_str = f"01.{m_eff:02d}.{y_eff}"
    effective_nk_str = f"01.{m_end:02d}.{y_end}"

    # 0. Zahlungserinnerung / Mahnung
    is_zahlungserinnerung = any(w in prompt_lower for w in ["zahlungserinnerung", "erinnerung", "mahnung", "rückstand", "rueckstand"]) and not ("abmahnung" in prompt_lower)
    if is_zahlungserinnerung:
        # Rückstandsbetrag extrahieren
        overdue_amt = 80.0
        rueck_match = re.search(r"(?:rückstand|rueckstand|von|über|ueber)\s*(?:von)?\s*(\d+(?:[.,]\d+)?)\s*(?:€|euro)?", prompt_lower)
        if rueck_match:
            overdue_amt = float(rueck_match.group(1).replace(",", "."))
        elif euro_val > 0:
            overdue_amt = euro_val

        # Frist in Tagen extrahieren
        days_match = re.search(r"(?:frist|innerhalb)?\s*(?:von)?\s*(\d+)\s*(?:tagen|tage|t)\b", prompt_lower)
        days = int(days_match.group(1)) if days_match else 7
        due_date_calc = (now + timedelta(days=days)).strftime("%d.%m.%Y")

        subject = f"Zahlungserinnerung: Ausstehende Mietzahlung für {unit_label}"
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"bei der Durchsicht meiner Mietkontoeingänge habe ich festgestellt, dass für die von Ihnen angemietete {unit_label} "
                f"aktuell ein Zahlungsrückstand in Höhe von {fmt_eur(overdue_amt)} offen ist.\n\n"
                f"Sicherlich handelt es sich hierbei nur um ein vorübergehendes Versehen. Ich bitte Sie daher höflich, den offenen Betrag von {fmt_eur(overdue_amt)} "
                f"innerhalb einer Frist von {days} Tagen (bis spätestens zum {due_date_calc}) auf mein Mietkonto zu überweisen.\n\n"
                f"Bankverbindung für Mietzahlungen:\n"
                f"• Kontoinhaber: {landlord_holder}\n"
                f"• IBAN: {landlord_iban}\n"
                f"• BIC: {landlord_bic}\n"
                f"• Kreditinstitut: {landlord_bank}\n"
                f"• Verwendungszweck: Mietrückstand {unit_label} - {recipient_name}\n\n"
                f"Sollten Sie den fälligen Betrag in den letzten Tagen bereits angewiesen haben, betrachten Sie diese Erinnerung bitte als gegenstandslos.\n\n"
                f"Für Rückfragen stehe ich Ihnen jederzeit gern zur Verfügung."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"bei der Durchsicht unserer Mietkontoeingänge haben wir festgestellt, dass für die von Ihnen angemietete {unit_label} "
                f"aktuell ein Zahlungsrückstand in Höhe von {fmt_eur(overdue_amt)} offen ist.\n\n"
                f"Sicherlich handelt es sich hierbei nur um ein vorübergehendes Versehen. Wir bitten Sie daher höflich, den offenen Betrag von {fmt_eur(overdue_amt)} "
                f"innerhalb einer Frist von {days} Tagen (bis spätestens zum {due_date_calc}) auf unser Mietkonto zu überweisen.\n\n"
                f"Bankverbindung für Mietzahlungen:\n"
                f"• Kontoinhaber: {landlord_holder}\n"
                f"• IBAN: {landlord_iban}\n"
                f"• BIC: {landlord_bic}\n"
                f"• Kreditinstitut: {landlord_bank}\n"
                f"• Verwendungszweck: Mietrückstand {unit_label} - {recipient_name}\n\n"
                f"Sollten Sie den fälligen Betrag in den letzten Tagen bereits angewiesen haben, betrachten Sie diese Erinnerung bitte als gegenstandslos.\n\n"
                f"Für Rückfragen stehen wir Ihnen jederzeit gern zur Verfügung."
            )
        return {"subject": subject, "body": body}

    # 0b. Abmahnung Zahlungsverzug
    if "abmahnung" in prompt_lower and any(w in prompt_lower for w in ["zahlung", "rückstand", "rueckstand", "miete"]):
        days_match = re.search(r"(?:frist|innerhalb)?\s*(?:von)?\s*(\d+)\s*(?:tagen|tage|t)\b", prompt_lower)
        days = int(days_match.group(1)) if days_match else 7
        due_date_calc = (now + timedelta(days=days)).strftime("%d.%m.%Y")
        overdue_amt = euro_val if euro_val > 0 else cur_cold

        subject = f"Abmahnung wegen Zahlungsverzugs für {unit_label}"
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"hiermit mahne ich Sie wegen Zahlungsverzugs im Mietverhältnis über die {unit_label} förmlich ab.\n\n"
                f"Trotz Fälligkeit ist für das genannte Mietobjekt ein Zahlungsrückstand in Höhe von {fmt_eur(overdue_amt)} aufgelaufen. "
                f"Ich fordere Sie hiermit nachdrücklich auf, den offenen Betrag von {fmt_eur(overdue_amt)} unverzüglich, spätestens jedoch bis zum {due_date_calc}, "
                f"auf mein Ihnen bekanntes Mietkonto zu zahlen.\n\n"
                f"Ich weise darauf hin, dass ich mir bei fruchtlosem Fristablauf oder weiterem Zahlungsverzug vorbehalte, das Mietverhältnis "
                f"gemäß § 543 Abs. 2 Nr. 3 BGB außerordentlich fristlos zu kündigen.\n\n"
                f"Ich gehe davon aus, dass Sie den Ausgleich unverzüglich vornehmen."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"hiermit mahnen wir Sie wegen Zahlungsverzugs im Mietverhältnis über die {unit_label} förmlich ab.\n\n"
                f"Trotz Fälligkeit ist für das genannte Mietobjekt ein Zahlungsrückstand in Höhe von {fmt_eur(overdue_amt)} aufgelaufen. "
                f"Wir fordern Sie hiermit nachdrücklich auf, den offenen Betrag von {fmt_eur(overdue_amt)} unverzüglich, spätestens jedoch bis zum {due_date_calc}, "
                f"auf das Ihnen bekannte Mietkonto zu zahlen.\n\n"
                f"Wir weisen darauf hin, dass wir uns bei fruchtlosem Fristablauf oder weiterem Zahlungsverzug vorbehalten, das Mietverhältnis "
                f"gemäß § 543 Abs. 2 Nr. 3 BGB außerordentlich fristlos zu kündigen.\n\n"
                f"Wir gehen davon aus, dass Sie den Ausgleich unverzüglich vornehmen."
            )
        return {"subject": subject, "body": body}

    # 0c. Abmahnung Hausordnung / Pflichtverletzung
    if "abmahnung" in prompt_lower:
        clean_incident = re.sub(r"^(?:schreibe|erstelle|verfasse|sende)\s+(?:ein(?:en)?\s+)?(?:brief|anschreiben|abmahnung|mitteilung|nachricht|schreiben)\s+(?:an\s+[^\s,]+(?:\s+[^\s,]+)?\s+)?(?:bezüglich|wegen|über|ueber|zu|aufgrund von)\s*:?\s*", "", user_prompt, flags=re.I).strip()
        incident_str = clean_incident if clean_incident else user_prompt
        subject = f"Abmahnung wegen Verletzung der mietvertraglichen Pflichten ({unit_str})"
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"ich muss mich heute leider mit einer formellen Abmahnung bezüglich Ihres Mietverhältnisses über die Wohnung ({unit_str}) an Sie wenden.\n\n"
                f"Es wurde wiederholt festgestellt, dass gegen die geltende Hausordnung und die mietvertraglichen Pflichten verstoßen wurde:\n"
                f"• {incident_str}\n\n"
                f"Ein derartiges Verhalten beeinträchtigt den Hausfrieden nachhaltig und kann von der Hausgemeinschaft nicht toleriert werden. "
                f"Ich fordere Sie hiermit auf, dieses Verhalten ab sofort dauerhaft einzustellen und sich an die Hausordnung zu halten.\n\n"
                f"Sollte es erneut zu gleichartigen Pflichtverletzungen kommen, sehe ich mich gezwungen, das Mietverhältnis fristlos zu kündigen."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"wir müssen uns heute leider mit einer formellen Abmahnung bezüglich Ihres Mietverhältnisses über die Wohnung ({unit_str}) an Sie wenden.\n\n"
                f"Es wurde wiederholt festgestellt, dass gegen die geltende Hausordnung und die mietvertraglichen Pflichten verstoßen wurde:\n"
                f"• {incident_str}\n\n"
                f"Ein derartiges Verhalten beeinträchtigt den Hausfrieden nachhaltig und kann von der Hausgemeinschaft nicht toleriert werden. "
                f"Wir fordern Sie hiermit auf, dieses Verhalten ab sofort dauerhaft einzustellen und sich an die Hausordnung zu halten.\n\n"
                f"Sollte es erneut zu gleichartigen Pflichtverletzungen kommen, sehen wir uns gezwungen, das Mietverhältnis fristlos zu kündigen."
            )
        return {"subject": subject, "body": body}

    # 0d. Mietbescheinigung
    if any(w in prompt_lower for w in ["mietbescheinigung", "bescheinigung", "mietschuldenfreiheit"]):
        start_date = tenant_info.get("lease_start", "Mietbeginn") if tenant_info else "Mietbeginn"
        total_rent = cur_cold + cur_nk
        subject = f"Miet- und Mietschuldenfreiheitsbescheinigung für die Wohnung {unit_str}"
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"hiermit bescheinige ich Ihnen für Ihre Unterlagen das bestehende Mietverhältnis über die folgende Wohneinheit:\n\n"
                f"• Mietobjekt: {tenant_info.get('property_name', 'Wohnanlage') if tenant_info else 'Wohnanlage'}\n"
                f"• Wohneinheit: {unit_str}\n"
                f"• Mieter: {recipient_name}\n"
                f"• Mietbeginn: seit {start_date}\n"
                f"• Aktuelle monatliche Nettokaltmiete: {cur_cold:.2f} €\n"
                f"• Aktuelle Betriebskostenvorauszahlung: {cur_nk:.2f} €\n"
                f"• Monatliche Gesamtmiete: {total_rent:.2f} €\n\n"
                f"Ich bestätige, dass die vereinbarte Miete bis zum heutigen Tag stets pünktlich und vollständig gezahlt wurde. "
                f"Es bestehen keinerlei Mietrückstände (Mietschuldenfreiheit)."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"hiermit bescheinigen wir Ihnen für Ihre Unterlagen das bestehende Mietverhältnis über die folgende Wohneinheit:\n\n"
                f"• Mietobjekt: {tenant_info.get('property_name', 'Wohnanlage') if tenant_info else 'Wohnanlage'}\n"
                f"• Wohneinheit: {unit_str}\n"
                f"• Mieter: {recipient_name}\n"
                f"• Mietbeginn: seit {start_date}\n"
                f"• Aktuelle monatliche Nettokaltmiete: {cur_cold:.2f} €\n"
                f"• Aktuelle Betriebskostenvorauszahlung: {cur_nk:.2f} €\n"
                f"• Monatliche Gesamtmiete: {total_rent:.2f} €\n\n"
                f"Wir bestätigen, dass die vereinbarte Miete bis zum heutigen Tag stets pünktlich und vollständig gezahlt wurde. "
                f"Es bestehen keinerlei Mietrückstände (Mietschuldenfreiheit)."
            )
        return {"subject": subject, "body": body}

    # Eindeutige Erkennung der Briefkategorie
    is_mieterhoehung = (
        any(w in prompt_lower for w in ["mieterhöhung", "mieterhoehung"])
        or ("kaltmiete" in prompt_lower and any(w in prompt_lower for w in ["erhöh", "anheb", "anpass"]))
        or ("miete" in prompt_lower and any(w in prompt_lower for w in ["erhöh", "anheb"]) and not any(w in prompt_lower for w in ["nebenkosten", "betriebskosten"]))
    )

    is_mietsenkung = (
        any(w in prompt_lower for w in ["mietsenkung", "miete senken", "kaltmiete senken", "senkung der miete", "senkung der kaltmiete"])
        or (any(w in prompt_lower for w in ["senk", "reduzier"]) and ("kaltmiete" in prompt_lower or ("miete" in prompt_lower and not any(w in prompt_lower for w in ["nebenkosten", "betriebskosten"]))))
    )

    is_nk_senkung = not is_mietsenkung and any(w in prompt_lower for w in ["senk", "reduzier", "verringer", "nachlass"]) and (
        any(w in prompt_lower for w in ["nebenkosten", "betriebskosten", "vorauszahlung"]) or bool(re.search(r"\bnk\b", prompt_lower))
    )

    is_nk_erhoehung = not is_mieterhoehung and not is_mietsenkung and any(w in prompt_lower for w in ["erhöh", "anheb", "anpass"]) and (
        any(w in prompt_lower for w in ["nebenkosten", "betriebskosten", "vorauszahlung"]) or bool(re.search(r"\bnk\b", prompt_lower))
    )

    # 1. Kaltmieterhöhung (§ 558 BGB)
    if is_mieterhoehung:
        if is_percentage:
            diff = round(cur_cold * (pct_val / 100.0), 2)
            inc_label = f"Erhöhung um {pct_val:.1f} %: + {diff:.2f} €"
        else:
            diff = euro_val if euro_val > 0 else 50.0
            inc_label = f"Monatlicher Erhöhungsbetrag: + {diff:.2f} €"

        new_cold = cur_cold + diff
        total_rent = new_cold + cur_nk
        subject = "Mieterhöhungsverlangen gemäß § 558 BGB zur Anpassung an die ortsübliche Vergleichsmiete"
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"hiermit kündige ich Ihnen eine Erhöhung der monatlichen Nettokaltmiete für die von Ihnen angemietete Wohnung ({unit_str}) an.\n\n"
                f"Gemäß § 558 BGB bin ich berechtigt, die Miete bis zur ortsüblichen Vergleichsmiete anzupassen. "
                f"Die gesetzliche Kappungsgrenze sowie die 15-monatige Wartefrist seit Mietbeginn bzw. der letzten Mieterhöhung werden dabei vollständig eingehalten.\n\n"
                f"Zusammensetzung der Miete ab dem {effective_cold_str}:\n"
                f"• Bisherige monatliche Nettokaltmiete: {cur_cold:.2f} €\n"
                f"• {inc_label}\n"
                f"• Neue monatliche Nettokaltmiete: {new_cold:.2f} €\n\n"
                f"Die monatliche Betriebskostenvorauszahlung in Höhe von {cur_nk:.2f} € bleibt hiervon unberührt. "
                f"Die neue monatliche Gesamtmiete beträgt somit {total_rent:.2f} €.\n\n"
                f"Ich bitte Sie höflich, der Mieterhöhung gemäß § 558b Abs. 1 BGB bis zum Ablauf der gesetzlichen Überlegungsfrist am {deadline_date_str} schriftlich zuzustimmen und Ihre Mietzahlungen ab dem {effective_cold_str} entsprechend anzupassen.\n\n"
                f"Für Rückfragen stehe ich Ihnen jederzeit gern zur Verfügung."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"hiermit kündigen wir Ihnen eine Erhöhung der monatlichen Nettokaltmiete für die von Ihnen angemietete Wohnung ({unit_str}) an.\n\n"
                f"Gemäß § 558 BGB sind wir berechtigt, die Miete bis zur ortsüblichen Vergleichsmiete anzupassen. "
                f"Die gesetzliche Kappungsgrenze sowie die 15-monatige Wartefrist seit Mietbeginn bzw. der letzten Mieterhöhung werden dabei vollständig eingehalten.\n\n"
                f"Zusammensetzung der Miete ab dem {effective_cold_str}:\n"
                f"• Bisherige monatliche Nettokaltmiete: {cur_cold:.2f} €\n"
                f"• {inc_label}\n"
                f"• Neue monatliche Nettokaltmiete: {new_cold:.2f} €\n\n"
                f"Die monatliche Betriebskostenvorauszahlung in Höhe von {cur_nk:.2f} € bleibt hiervon unberührt. "
                f"Die neue monatliche Gesamtmiete beträgt somit {total_rent:.2f} €.\n\n"
                f"Wir bitten Sie höflich, der Mieterhöhung gemäß § 558b Abs. 1 BGB bis zum Ablauf der gesetzlichen Überlegungsfrist am {deadline_date_str} schriftlich zuzustimmen und Ihre Mietzahlungen ab dem {effective_cold_str} entsprechend anzupassen.\n\n"
                f"Für Rückfragen stehen wir Ihnen jederzeit gern zur Verfügung."
            )
        return {"subject": subject, "body": body}

    # 2. Kaltmietsenkung
    if is_mietsenkung:
        if is_percentage:
            diff = round(cur_cold * (pct_val / 100.0), 2)
            dec_label = f"Senkung um {pct_val:.1f} %: - {diff:.2f} €"
        else:
            diff = euro_val if euro_val > 0 else 50.0
            dec_label = f"Monatlicher Senkungsbetrag: - {diff:.2f} €"

        new_cold = max(0.0, cur_cold - diff)
        total_rent = new_cold + cur_nk
        subject = "Mitteilung über eine Herabsetzung der monatlichen Nettokaltmiete"
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"bezugnehmend auf das Mietverhältnis für die Wohnung ({unit_str}) möchte ich Ihnen eine erfreuliche Anpassung Ihrer monatlichen Nettokaltmiete mitteilen.\n\n"
                f"Ich senke Ihre monatliche Nettokaltmiete zum rechtlich nächstmöglichen Zeitpunkt ab dem {effective_nk_str} um {diff:.2f} €.\n\n"
                f"Zusammensetzung der Miete ab dem {effective_nk_str}:\n"
                f"• Bisherige monatliche Nettokaltmiete: {cur_cold:.2f} €\n"
                f"• {dec_label}\n"
                f"• Neue monatliche Nettokaltmiete: {new_cold:.2f} €\n\n"
                f"Die monatliche Betriebskostenvorauszahlung in Höhe von {cur_nk:.2f} € bleibt hiervon unberührt. "
                f"Die neue monatliche Gesamtmiete beläuft sich somit auf {total_rent:.2f} €.\n\n"
                f"Bitte passen Sie Ihren Dauerauftrag bzw. Ihre monatliche Banküberweisung zum genannten Stichtag entsprechend an. "
                f"Falls Sie mir ein SEPA-Lastschriftmandat erteilt haben, buche ich den reduzierten Betrag ab diesem Zeitpunkt automatisch ab.\n\n"
                f"Für Rückfragen stehe ich Ihnen jederzeit gern zur Verfügung."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"bezugnehmend auf das Mietverhältnis für die Wohnung ({unit_str}) möchten wir Ihnen eine erfreuliche Anpassung Ihrer monatlichen Nettokaltmiete mitteilen.\n\n"
                f"Wir senken Ihre monatliche Nettokaltmiete zum rechtlich nächstmöglichen Zeitpunkt ab dem {effective_nk_str} um {diff:.2f} €.\n\n"
                f"Zusammensetzung der Miete ab dem {effective_nk_str}:\n"
                f"• Bisherige monatliche Nettokaltmiete: {cur_cold:.2f} €\n"
                f"• {dec_label}\n"
                f"• Neue monatliche Nettokaltmiete: {new_cold:.2f} €\n\n"
                f"Die monatliche Betriebskostenvorauszahlung in Höhe von {cur_nk:.2f} € bleibt hiervon unberührt. "
                f"Die neue monatliche Gesamtmiete beläuft sich somit auf {total_rent:.2f} €.\n\n"
                f"Bitte passen Sie Ihren Dauerauftrag bzw. Ihre monatliche Banküberweisung zum genannten Stichtag entsprechend an. "
                f"Falls Sie uns ein SEPA-Lastschriftmandat erteilt haben, buchen wir den reduzierten Betrag ab diesem Zeitpunkt automatisch ab.\n\n"
                f"Für Rückfragen stehen wir Ihnen jederzeit gern zur Verfügung."
            )
        return {"subject": subject, "body": body}

    # 3. Nebenkostensenkung (§ 560 Abs. 4 BGB)
    if is_nk_senkung:
        if is_percentage:
            diff = round(cur_nk * (pct_val / 100.0), 2)
            dec_label = f"Monatlicher Senkungsbetrag ({pct_val:.1f} %): - {diff:.2f} €"
        else:
            diff = euro_val if euro_val > 0 else 20.0
            dec_label = f"Monatlicher Senkungsbetrag: - {diff:.2f} €"

        new_nk = max(0.0, cur_nk - diff)
        total_rent = cur_cold + new_nk
        subject = "Anpassung der monatlichen Betriebskostenvorauszahlung gemäß § 560 Abs. 4 BGB"
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"bezugnehmend auf das bestehende Mietverhältnis für die Wohnung ({unit_str}) möchte ich Ihnen eine erfreuliche Anpassung Ihrer Betriebskostenvorauszahlung mitteilen.\n\n"
                f"Gemäß § 560 Abs. 4 BGB sind die Vertragsparteien berechtigt, nach einer Abrechnung bzw. bei veränderten Kostenprognosen die Vorauszahlungen auf eine angemessene Höhe anzupassen. "
                f"Da die laufenden Betriebskosten geringer ausfallen, senke ich Ihre monatliche Vorauszahlung zum rechtlich nächstmöglichen Zeitpunkt (ab dem {effective_nk_str}).\n\n"
                f"Zusammensetzung ab dem {effective_nk_str}:\n"
                f"• Bisherige monatliche Vorauszahlung: {cur_nk:.2f} €\n"
                f"• {dec_label}\n"
                f"• Neue monatliche Betriebskostenvorauszahlung: {new_nk:.2f} €\n\n"
                f"Ihre monatliche Nettokaltmiete in Höhe von {cur_cold:.2f} € bleibt hiervon unberührt. "
                f"Die neue monatliche Gesamtmiete beläuft sich somit auf {total_rent:.2f} €.\n\n"
                f"Bitte passen Sie Ihren Dauerauftrag bzw. Ihre monatliche Banküberweisung zum genannten Stichtag entsprechend an. Falls Sie mir ein SEPA-Lastschriftmandat erteilt haben, buche ich den reduzierten Betrag ab diesem Zeitpunkt automatisch ab.\n\n"
                f"Für Rückfragen stehe ich Ihnen jederzeit gern zur Verfügung."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"bezugnehmend auf das bestehende Mietverhältnis für die Wohnung ({unit_str}) möchten wir Ihnen eine erfreuliche Anpassung Ihrer Betriebskostenvorauszahlung mitteilen.\n\n"
                f"Gemäß § 560 Abs. 4 BGB sind die Vertragsparteien berechtigt, nach einer Abrechnung bzw. bei veränderten Kostenprognosen die Vorauszahlungen auf eine angemessene Höhe anzupassen. "
                f"Da die laufenden Betriebskosten geringer ausfallen, senken wir Ihre monatliche Vorauszahlung zum rechtlich nächstmöglichen Zeitpunkt (ab dem {effective_nk_str}).\n\n"
                f"Zusammensetzung ab dem {effective_nk_str}:\n"
                f"• Bisherige monatliche Vorauszahlung: {cur_nk:.2f} €\n"
                f"• {dec_label}\n"
                f"• Neue monatliche Betriebskostenvorauszahlung: {new_nk:.2f} €\n\n"
                f"Ihre monatliche Nettokaltmiete in Höhe von {cur_cold:.2f} € bleibt hiervon unberührt. "
                f"Die neue monatliche Gesamtmiete beläuft sich somit auf {total_rent:.2f} €.\n\n"
                f"Bitte passen Sie Ihren Dauerauftrag bzw. Ihre monatliche Banküberweisung zum genannten Stichtag entsprechend an. Falls Sie uns ein SEPA-Lastschriftmandat erteilt haben, buchen wir den reduzierten Betrag ab diesem Zeitpunkt automatisch ab.\n\n"
                f"Für Rückfragen stehen wir Ihnen jederzeit gern zur Verfügung."
            )
        return {"subject": subject, "body": body}

    # 4. Nebenkostenerhöhung (§ 560 Abs. 4 BGB)
    if is_nk_erhoehung:
        if is_percentage:
            diff = round(cur_nk * (pct_val / 100.0), 2)
            inc_label = f"Monatlicher Anpassungsbetrag ({pct_val:.1f} %): + {diff:.2f} €"
        else:
            diff = euro_val if euro_val > 0 else 30.0
            inc_label = f"Monatlicher Anpassungsbetrag: + {diff:.2f} €"

        new_nk = cur_nk + diff
        total_rent = cur_cold + new_nk
        subject = "Anpassung der monatlichen Betriebskostenvorauszahlung gemäß § 560 Abs. 4 BGB"
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"bezugnehmend auf das Mietverhältnis für die Wohnung ({unit_str}) teile ich Ihnen hiermit eine Anpassung der monatlichen Vorauszahlungen auf die Betriebskosten mit.\n\n"
                f"Gemäß § 560 Abs. 4 BGB passe ich die monatliche Vorauszahlung an die gestiegenen Bewirtschaftungskosten an, um hohe Nachzahlungen bei der nächsten Jahresabrechnung zu vermeiden. "
                f"Die Anpassung erfolgt zum rechtlich nächstmöglichen Zeitpunkt ab dem {effective_nk_str} (auf die Erklärung folgender übernächster Monatserster).\n\n"
                f"Übersicht der Anpassung:\n"
                f"• Bisherige Vorauszahlung: {cur_nk:.2f} €\n"
                f"• {inc_label}\n"
                f"• Neue monatliche Betriebskostenvorauszahlung: {new_nk:.2f} €\n\n"
                f"Die Nettokaltmiete ({cur_cold:.2f} €) bleibt unverändert. Die neue monatliche Gesamtmiete beträgt somit {total_rent:.2f} €.\n\n"
                f"Bitte passen Sie Ihre Zahlungsanweisung zum genannten Termin an.\n\n"
                f"Für Rückfragen stehe ich Ihnen jederzeit gern zur Verfügung."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"bezugnehmend auf das Mietverhältnis für die Wohnung ({unit_str}) teilen wir Ihnen hiermit eine Anpassung der monatlichen Vorauszahlungen auf die Betriebskosten mit.\n\n"
                f"Gemäß § 560 Abs. 4 BGB passen wir die monatliche Vorauszahlung an die gestiegenen Bewirtschaftungskosten an, um hohe Nachzahlungen bei der nächsten Jahresabrechnung zu vermeiden. "
                f"Die Anpassung erfolgt zum rechtlich nächstmöglichen Zeitpunkt ab dem {effective_nk_str} (auf die Erklärung folgender übernächster Monatserster).\n\n"
                f"Übersicht der Anpassung:\n"
                f"• Bisherige Vorauszahlung: {cur_nk:.2f} €\n"
                f"• {inc_label}\n"
                f"• Neue monatliche Betriebskostenvorauszahlung: {new_nk:.2f} €\n\n"
                f"Die Nettokaltmiete ({cur_cold:.2f} €) bleibt unverändert. Die neue monatliche Gesamtmiete beträgt somit {total_rent:.2f} €.\n\n"
                f"Bitte passen Sie Ihre Zahlungsanweisung zum genannten Termin an."
            )
        return {"subject": subject, "body": body}

    # 5. Bankverbindung / Kontaktdaten
    if any(w in prompt_lower for w in ["bankverbindung", "konto", "iban", "kontaktdaten"]):
        subject = "Wichtige Mitteilung: Aktualisierung der Bankverbindung für Mietzahlungen"
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"ich möchte Sie darüber informieren, dass sich meine Bankverbindung für die Überweisung der monatlichen Miet- und Nebenkostenzahlungen {unit_str} ändert.\n\n"
                f"Bitte richten Sie Ihre Zahlungen ab dem kommenden Monatsersten an folgendes Konto:\n"
                f"• Kontoinhaber: {landlord_holder}\n"
                f"• IBAN: {landlord_iban}\n"
                f"• BIC: {landlord_bic}\n"
                f"• Kreditinstitut: {landlord_bank}\n"
                f"• Verwendungszweck: Miete {unit_str}\n\n"
                f"Sollten Sie einen Dauerauftrag eingerichtet haben, passen Sie diesen bitte rechtzeitig an. Falls Sie mir ein SEPA-Lastschriftmandat erteilt haben, buche ich den Betrag ab diesem Zeitpunkt automatisch vom neuen Konto ab.\n\n"
                f"Vielen Dank für Ihre Unterstützung."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"wir möchten Sie darüber informieren, dass sich unsere Bankverbindung für die Überweisung der monatlichen Miet- und Nebenkostenzahlungen {unit_str} ändert.\n\n"
                f"Bitte richten Sie Ihre Zahlungen ab dem kommenden Monatsersten an folgendes Konto:\n"
                f"• Kontoinhaber: {landlord_holder}\n"
                f"• IBAN: {landlord_iban}\n"
                f"• BIC: {landlord_bic}\n"
                f"• Kreditinstitut: {landlord_bank}\n"
                f"• Verwendungszweck: Miete {unit_str}\n\n"
                f"Sollten Sie einen Dauerauftrag eingerichtet haben, passen Sie diesen bitte rechtzeitig an. Falls Sie uns ein SEPA-Lastschriftmandat erteilt haben, buchen wir den Betrag ab diesem Zeitpunkt automatisch vom neuen Konto ab.\n\n"
                f"Vielen Dank für Ihre Unterstützung."
            )
        return {"subject": subject, "body": body}

    # 6. Handwerker / Wartung
    if any(w in prompt_lower for w in ["handwerker", "wartung", "reparatur", "begehung", "ablesung"]):
        subject = "Ankündigung von Handwerker- und Instandhaltungsarbeiten"
        scope_str = unit_str if is_all_tenants else f"in Ihrer Wohnanlage ({unit_str})"
        contact_str = f"unter Tel. {landlord_phone}" if (is_private and landlord_phone) else "Ihres Vermieters" if is_private else "unserer Hausverwaltung"
        clean_hw = re.sub(r"^(?:schreibe|erstelle|verfasse|sende)\s+(?:ein(?:en)?\s+)?(?:brief|anschreiben|mitteilung|nachricht|ankündigungsschreiben|schreiben)\s+(?:an\s+[^\s,]+(?:\s+[^\s,]+)?\s+)?(?:bezüglich|wegen|über|ueber|zu)\s*:?\s*", "", user_prompt, flags=re.I).strip()
        hw_detail = clean_hw if clean_hw else user_prompt
        if is_private:
            body = (
                f"{sal_greeting},\n\n"
                f"ich kündige Ihnen hiermit anstehende Arbeiten {scope_str} an.\n\n"
                f"Grund / Vorgesehene Arbeiten: {hw_detail}\n\n"
                f"Bitte gewähren Sie den beauftragten Handwerkern zum vereinbarten Termin ungehinderten Zutritt zu den entsprechenden Bereichen. "
                f"Sollten Sie Fragen oder Terminkollisionen haben, bitte ich um rechtzeitige Benachrichtigung ({contact_str}).\n\n"
                f"Vielen Dank für Ihre Unterstützung und Ihr Verständnis."
            )
        else:
            body = (
                f"{sal_greeting},\n\n"
                f"wir kündigen Ihnen hiermit anstehende Arbeiten {scope_str} an.\n\n"
                f"Grund / Vorgesehene Arbeiten: {hw_detail}\n\n"
                f"Bitte gewähren Sie den beauftragten Handwerkern zum vereinbarten Termin ungehinderten Zutritt zu den entsprechenden Bereichen. "
                f"Sollten Sie Fragen oder Terminkollisionen haben, bitten wir um rechtzeitige Benachrichtigung ({contact_str}).\n\n"
                f"Vielen Dank für Ihre Unterstützung und Ihr Verständnis."
            )
        return {"subject": subject, "body": body}

    # Standard
    subject = f"Mitteilung Ihres Vermieters ({landlord_name})" if is_private else "Mitteilung Ihrer Hausverwaltung"
    clean_prompt_body = re.sub(r"^(?:schreibe|erstelle|verfasse|sende)\s+(?:ein(?:en)?\s+)?(?:brief|anschreiben|mitteilung|nachricht|schreiben)\s+(?:an\s+[^\s,]+(?:\s+[^\s,]+)?\s+)?(?:bezüglich|wegen|über|ueber|zu|dass)\s*:?\s*", "", user_prompt, flags=re.I).strip()
    if clean_prompt_body:
        clean_prompt_body = clean_prompt_body[0].upper() + clean_prompt_body[1:]
    else:
        clean_prompt_body = user_prompt

    if is_private:
        body = (
            f"{sal_greeting},\n\n"
            f"ich wende mich heute mit einer Mitteilung bezüglich {unit_str} an Sie.\n\n"
            f"{clean_prompt_body}\n\n"
            f"Bei Rückfragen stehe ich Ihnen jederzeit gerne zur Verfügung."
        )
    else:
        body = (
            f"{sal_greeting},\n\n"
            f"wir wenden uns heute mit einer Mitteilung bezüglich {unit_str} an Sie.\n\n"
            f"{clean_prompt_body}\n\n"
            f"Bei Rückfragen stehen wir Ihnen jederzeit gerne zur Verfügung."
        )
    return {"subject": subject, "body": body}

def parse_user_intent_ollama(user_prompt: str, model: str = "llama3") -> Dict[str, Any]:
    """Analysiert den Nutzerprompt mit Ollama (Llama 3)."""
    try:
        response = ollama.chat(
            model=model,
            format="json",
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
    
    # 1. Briefe & Schreiben jeglicher Art (Priorität vor Mieterliste!)
    if any(w in prompt_lower for w in [
        "brief", "schreiben", "anschreiben", "abmahnung", "mahnung", 
        "zahlungserinnerung", "erinnerung", "mitteilung an", "nachricht an", 
        "mieterhöhung", "mieterhoehung", "mietsenkung", "bescheinigung", "mietbescheinigung"
    ]) or (
        any(w in prompt_lower for w in ["nebenkosten", "kaltmiete", "betriebskosten", "miete"]) and any(w in prompt_lower for w in ["senk", "erhöh", "anpass", "reduzier"])
    ):
        if any(term in prompt_lower for term in ["alle mieter", "alle mieterinnen", "hausgemeinschaft", "sämtliche mieter", "alle bewohner"]):
            tenant_name = "alle Mieterinnen und Mieter"
        else:
            name_match = re.search(r"(?:an|für|von)\s+([A-Za-zÄÖÜäöüß]+(?:\s+[A-Za-zÄÖÜäöüß]+)?)", user_prompt, re.IGNORECASE)
            tenant_name = name_match.group(1).strip() if name_match else ""
            
            if not tenant_name:
                for t in get_all_tenants():
                    if t["last_name"].lower() in prompt_lower or t["first_name"].lower() in prompt_lower:
                        tenant_name = f"{t['first_name']} {t['last_name']}"
                        break

        return {
            "action": "write_letter",
            "tenant_name": tenant_name,
            "user_instruction": user_prompt
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
        if any(term in prompt_lower for term in ["alle mieter", "alle mieterinnen", "alle abrechnungen", "sämtliche mieter", "für alle"]):
            return {"action": "generate_statement", "tenant_name": "alle", "year": year}
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

        # Prüfung: Abrechnung für alle Mieter gewünscht?
        if any(term in tenant_name.lower() or term in user_prompt.lower() for term in ["alle mieter", "alle mieterinnen", "alle abrechnungen", "sämtliche mieter", "für alle", "alle"]):
            from agent.tools import get_annual_utility_statements
            statements = get_annual_utility_statements(year)
            if not statements:
                return {
                    "success": False,
                    "message": f"Für das Abrechnungsjahr {year} konnten keine Abrechnungen generiert werden. Bitte prüfe die erfassten Betriebskosten und Mieter.",
                    "data": None
                }
            lines = [f"📊 **Übersicht der Nebenkostenabrechnungen für das Jahr {year} aller Mieter:**\n"]
            for s in statements:
                res_sym = "🟢 Guthaben" if s["is_refund"] else "🔴 Nachzahlung"
                lines.append(f"- **{s['full_name']}** ({s['unit_number']}, {s['area_sqm']:.0f} m²): Anteil {s['tenant_share']:.2f} € | Vorauszahlung {s['prepayments_paid']:.2f} € ➔ **{res_sym}: {abs(s['balance']):.2f} €**")
            lines.append(f"\n💡 *Die vollständigen Einzelabrechnungen und druckfertigen Nachweise findest du im Bereich **'Betriebskosten & Finanzen'**.*")
            return {
                "success": True,
                "message": "\n".join(lines),
                "data": statements
            }

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
        
        tenant_summary = ", ".join([f"**{t.get('salutation', 'Herr')} {t['first_name']} {t['last_name']}** ({t['unit_number']}, {t.get('price_per_sqm', 0.0):.2f} €/m²)" for t in tenants])
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
        raw_name = (intent.get("tenant_name") or "").strip()

        # Prüfen ob Rundschreiben an alle Mieter
        is_all_tenants = any(term in raw_name.lower() or term in user_prompt.lower() for term in [
            "alle mieter", "alle mieterinnen", "hausgemeinschaft", "sämtliche mieter", "alle bewohner"
        ])

        if not raw_name and not is_all_tenants:
            # Letzter Versuch: Aus prompt_lower nach Namen suchen
            from agent.tools import parse_co_tenants
            for t in get_all_tenants():
                if (t["last_name"].lower() in user_prompt.lower() or 
                    t["first_name"].lower() in user_prompt.lower() or 
                    any(c.get("last_name", "").lower() in user_prompt.lower() for c in parse_co_tenants(t.get("co_tenants")))):
                    raw_name = f"{t['first_name']} {t['last_name']}"
                    break

        if not raw_name and not is_all_tenants:
            return {
                "success": False,
                "message": "Für welchen Mieter soll ich das Schreiben verfassen? Bitte nenne mir den Namen des Mieters oder wähle 'Alle Mieter' aus.",
                "data": None
            }

        settings = get_all_settings()
        is_private = settings.get("landlord_type", "private") == "private"
        default_sender = "Kirdar Karadag" if is_private else "Hausverwaltung Sonnenhang"
        sender_name = settings.get("landlord_name", default_sender)
        if is_private and sender_name == "Hausverwaltung Sonnenhang":
            sender_name = settings.get("landlord_contact_person") or "Kirdar Karadag"

        sender_street = settings.get("landlord_street", "Lindenstraße 14")
        sender_city = f"{settings.get('landlord_zip', '10115')} {settings.get('landlord_city', 'Berlin')}".strip()
        sender_phone = settings.get("landlord_phone", "+49 30 12345678")
        sender_email = settings.get("landlord_email", "kirdar@karadag.de" if is_private else "verwaltung@sonnenhang.de")
        sign_person = settings.get("landlord_contact_person")
        if not sign_person or (is_private and "hausverwaltung" in sign_person.lower()):
            sign_person = f"{sender_name}\n(Vermieter)" if is_private else sender_name

        if is_all_tenants:
            from agent.tools import get_all_properties
            props = get_all_properties()
            matched_p = None
            for p in props:
                if p["name"].lower() in user_prompt.lower() or (p.get("alias") and p["alias"].lower() in user_prompt.lower()):
                    matched_p = p
                    break
            if not matched_p and props:
                matched_p = props[0]

            prop_title = matched_p["name"] if matched_p else sender_name
            p_street = matched_p["street"] if matched_p else sender_street
            p_city = f"{matched_p.get('zip_code', '10115')} {matched_p.get('city', 'Berlin')}".strip() if matched_p else sender_city

            full_name = f"An alle Mieterinnen und Mieter\n{prop_title}"
            addr_line = f"{p_street}\n{p_city}"
            prop_name = prop_title
            db_tenant = {
                "is_all_tenants": True,
                "property_name": prop_title,
                "salutation": "alle",
                "unit_number": "gesamtes Objekt",
                "cold_rent": 0.0,
                "utility_advance": 0.0
            }
            note = f"👥 *Rundschreiben an alle Mieterinnen und Mieter ({prop_title}) erstellt*"
        else:
            db_tenant = find_tenant_by_name(raw_name)
            if db_tenant:
                full_name = db_tenant.get("address_recipient") or db_tenant.get("display_name") or f"{db_tenant['first_name']} {db_tenant['last_name']}"
                disp_label = db_tenant.get("display_name") or f"{db_tenant['first_name']} {db_tenant['last_name']}"
                unit_info = f"{db_tenant['unit_number']} ({db_tenant['property_name']})"
                addr_line = f"{db_tenant.get('street', 'Lindenstraße 14')}\n{db_tenant.get('zip_code', '10115')} {db_tenant.get('city', 'Berlin')}"
                prop_name = db_tenant.get("property_name", sender_name)
                note = f"👤 *Mieter aus deiner Datenbank zugeordnet: {disp_label} ({unit_info})*"
            else:
                full_name = raw_name
                addr_line = "Musterstraße 1\n10115 Berlin"
                prop_name = sender_name
                note = f"💡 *Hinweis: '{raw_name}' ist bisher nicht in deiner Mieter-Datenbank hinterlegt. Das Schreiben wurde mit Vorlagendaten für diesen Namen erstellt.*"

        # Brief mit KI entwerfen
        letter_content = draft_letter_with_ai(
            user_prompt=user_prompt,
            recipient_name=full_name,
            tenant_info=db_tenant,
            model=model
        )
        default_subject = f"Mitteilung Ihres Vermieters ({sender_name})" if is_private else "Mitteilung der Hausverwaltung"
        subject = letter_content.get("subject", default_subject)
        letter_text = letter_content.get("body", "")

        # 1. PDF nach DIN 5008:2020 Form B generieren
        pdf_path = generate_formal_letter_pdf(
            recipient_name=full_name,
            subject=subject,
            letter_text=letter_text,
            address_line=addr_line,
            sender_name=sender_name,
            property_name=prop_name,
            sender_street=sender_street,
            sender_city=sender_city,
            sender_phone=sender_phone,
            sender_email=sender_email,
            sign_person=sign_person
        )

        # 2. Word / DOCX (auch für LibreOffice ODT) nach DIN 5008:2020 Form B generieren
        docx_path = generate_formal_letter_docx(
            recipient_name=full_name,
            subject=subject,
            letter_text=letter_text,
            address_line=addr_line,
            sender_name=sender_name,
            property_name=prop_name,
            sender_street=sender_street,
            sender_city=sender_city,
            sender_phone=sender_phone,
            sender_email=sender_email,
            sign_person=sign_person
        )

        clean_subj = re.sub(r"^(?:Betreff|Subject)\s*:\s*", "", subject, flags=re.IGNORECASE).strip()
        clean_body = re.sub(r"\n*(?:Mit freundlichen Grüßen|Freundliche Grüße|Herzliche Grüße)[,\s]*.*$", "", letter_text, flags=re.IGNORECASE | re.DOTALL).strip()

        msg = (
            f"📄 **Offizielles Schreiben für {full_name} erstellt! (DIN 5008 Form B)**\n\n"
            f"{note}\n\n"
            f"**{clean_subj}**\n\n"
            f"---\n\n"
            f"{clean_body}\n\n"
            f"Mit freundlichen Grüßen\n\n\n"
            f"**{sender_name}**" + (" *(Vermieter)*\n\n" if is_private else "\n\n") +
            f"---\n\n"
            f"📥 *Das Dokument wurde nach der offiziellen **DIN 5008:2020 (Form B)** als druckfertiges **PDF** und editierbares **Word / DOCX** (kompatibel mit MS Word & LibreOffice) generiert.*"
        )

        return {
            "success": True,
            "message": msg,
            "pdf_path": pdf_path,
            "docx_path": docx_path,
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
            sal = t.get("salutation", "Herr")
            price_sqm = t.get("price_per_sqm", 0.0)
            msg += f"{idx}. **{sal} {t['first_name']} {t['last_name']}**\n"
            msg += f"   - 🚪 **Wohnung:** {t['unit_number']} ({t['area_sqm']:.1f} m²)\n"
            msg += f"   - 💶 **Kaltmiete:** {t['cold_rent']:.2f} € ({price_sqm:.2f} €/m²) | **NK-Vorauszahlung:** {t['utility_advance']:.2f} €\n"
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
        
        if not last_name and not first_name:
            units = get_all_units()
            unit_list = ", ".join([u["unit_number"] for u in units]) if units else "Wohnung 1, Wohnung 2"
            return {
                "success": True,
                "message": (
                    "Ja, sehr gerne! Um einen neuen Mieter anzulegen, nenne mir bitte folgende Daten:\n\n"
                    "- **Anrede & Name:** z. B. *Frau Sabine Meier* oder *Herr Peter Müller*\n"
                    f"- **Wohnung:** (Verfügbar: *{unit_list}*)\n"
                    "- **Kaltmiete & Nebenkostenvorauszahlung:** z. B. *850 € Kaltmiete, 200 € NK*\n"
                    "- **Mietbeginn:** z. B. *01.05.2025*\n\n"
                    "💡 *Beispiel-Eingabe:* `Füge Frau Sabine Meier hinzu für Wohnung 2, Kaltmiete 850, NK 200 ab 01.05.2025`"
                ),
                "data": None
            }

        salutation = intent.get("salutation")
        if not salutation:
            salutation = "Frau" if any(fn in f"{first_name} {user_prompt}".lower() for fn in ["frau", "sabine", "laura", "anna", "maria", "sarah", "julia", "lisa"]) else "Herr"

        cold_rent = float(intent.get("cold_rent") or 0.0)
        utility_advance = float(intent.get("utility_advance") or 0.0)
        lease_start = intent.get("lease_start") or "2025-01-01"
        unit_number = intent.get("unit_number") or ""
        
        try:
            res = add_new_tenant(
                first_name=first_name,
                last_name=last_name,
                salutation=salutation,
                unit_search=unit_number,
                cold_rent=cold_rent,
                utility_advance=utility_advance,
                lease_start=lease_start
            )
            return {
                "success": True,
                "message": (
                    f"✅ **Mieter {salutation} {first_name} {last_name} wurde erfolgreich angelegt!**\n\n"
                    f"- **Anrede:** {salutation}\n"
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
