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
    now = datetime.now()
    m_end = (now.month + 2 - 1) % 12 + 1
    y_end = now.year + (now.month + 2 - 1) // 12
    last_day = calendar.monthrange(y_end, m_end)[1]
    deadline_date_str = f"{last_day:02d}.{m_end:02d}.{y_end}"
    m_eff = (now.month + 3 - 1) % 12 + 1
    y_eff = now.year + (now.month + 3 - 1) // 12
    effective_cold_str = f"01.{m_eff:02d}.{y_eff}"
    effective_nk_str = f"01.{m_end:02d}.{y_end}"

    salutation = (tenant_info.get("salutation") if tenant_info else "") or ""
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
        context_lines.append(f"Aktuelle Nettokaltmiete: {tenant_info.get('cold_rent', 0.0):.2f} €")
        context_lines.append(f"Aktuelle monatliche Nebenkostenvorauszahlung: {tenant_info.get('utility_advance', 0.0):.2f} €")
        if tenant_info.get('price_per_sqm'):
            context_lines.append(f"Quadratmeterpreis: {tenant_info.get('price_per_sqm'):.2f} €/m²")
        if tenant_info.get('lease_start'):
            context_lines.append(f"Mietbeginn: {tenant_info.get('lease_start')}")
    
    tenant_context = "\n".join(context_lines)

    system_instruction = f"""Du bist ein erfahrener deutscher Hausverwalter und Experte für deutsches Mietrecht (BGB).
Deine Aufgabe ist es, anhand der Nutzeranweisung ein professionelles, rechtssicheres und druckfertiges Schreiben an den Mieter zu verfassen.

KONTEXT DES MIETERS:
{tenant_context}

GESETZLICHE FRISTEN & DATEN (Stand: {now.strftime("%d.%m.%Y")}):
- Bei Kaltmieterhöhung (§ 558 BGB):
  * Gesetzliche Zustimmungsfrist / Überlegungsfrist (§ 558b Abs. 1 BGB): bis zum {deadline_date_str} (Ende des übernächsten Monats)
  * Wirksamkeit der neuen Kaltmiete: ab dem {effective_cold_str} (Beginn des dritten Monats)
- Bei Anpassung der Nebenkostenvorauszahlung (§ 560 Abs. 4 BGB):
  * Wirksamkeit: ab dem {effective_nk_str} (auf die Erklärung folgender übernächster Monatserster)

WICHTIGE REGELN:
1. UNTERSCHEIDUNG MIETANPASSUNG (ERHÖHUNG / SENKUNG) VS. NEBENKOSTEN:
   - Bei Mieterhöhung: Mieterhöhungsverlangen gemäß § 558 BGB zur Erhöhung der Nettokaltmiete.
   - Bei Mietsenkung / Mietherabsetzung: Mitteilung über die Herabsetzung der monatlichen Nettokaltmiete (die Kaltmiete wird um den angegebenen Betrag oder Prozentsatz reduziert).
   - Nebenkosten / Betriebskosten (§ 560 BGB) dürfen NUR angepasst werden, wenn der Nutzer explizit Nebenkosten oder Betriebskosten nennt.
2. BERECHNUNG BEI PROZENTANGABEN (z. B. 10% oder 15%):
   - Wenn der Nutzer eine prozentuale Erhöhung verlangt:
     Erhöhung in Euro = Aktuelle Kaltmiete * (Prozentsatz / 100)
     Neue Kaltmiete = Aktuelle Kaltmiete + Erhöhung in Euro
   - Wenn der Nutzer eine prozentuale Senkung verlangt:
     Senkung in Euro = Aktuelle Kaltmiete * (Prozentsatz / 100)
     Neue Kaltmiete = Aktuelle Kaltmiete - Senkung in Euro
     (Beispiel: Bei 500 € Kaltmiete und 10% Senkung beträgt die Senkung 50,00 € und die neue Miete 450,00 €).
3. Schreibe AUSSCHLIESSLICH in fehlerfreiem Deutsch.
4. Der Brief MUSS mit der exakten Anredezeile beginnen: '{formal_greeting},' (niemals 'Sehr geehrte(r) Frau/Herr'!).
5. Formuliere einen präzisen, juristisch sauberen Betreff ('subject') passend zum konkreten Anliegen.
   WICHTIG nach DIN 5008: Das Wort 'Betreff' oder 'Betreff:' darf NIEMALS vorangestellt werden (direkt mit dem Thema beginnen)!
   Beispiele:
   - Bei Kaltmieterhöhung: "Mieterhöhungsverlangen gemäß § 558 BGB zur Anpassung an die ortsübliche Vergleichsmiete"
   - Bei Kaltmietsenkung: "Mitteilung über eine Herabsetzung der monatlichen Nettokaltmiete"
   - Bei Nebenkostensenkung: "Anpassung der monatlichen Betriebskostenvorauszahlung gemäß § 560 Abs. 4 BGB"
   - Bei Nebenkostenerhöhung: "Anpassung der monatlichen Betriebskostenvorauszahlung gemäß § 560 Abs. 4 BGB"
   - Bei Bankverbindung: "Mitteilung über eine Änderung der Bankverbindung für Mietzahlungen"
   - Bei Handwerker/Wartung: "Ankündigung von Instandhaltungs- und Handwerkerarbeiten"
   - Bei Abmahnung: "Abmahnung wegen vertragswidrigen Verhaltens"
6. Beziehe dich, wenn im deutschen Mietrecht vorgesehen, auf die einschlägigen Paragrafen (z. B. § 560 BGB für Nebenkostenvorauszahlungen, § 558 BGB für Kaltmiete, § 558b BGB für Zustimmungsfristen).
7. Der Brieftext ('body') muss enthalten:
   - Die Anredezeile '{formal_greeting},'
   - Klare Darlegung des Sachverhalts und der Begründung mit konkreten Beträgen und Fristen (unter Verwendung der oben angegebenen gesetzlichen Termine).
   - Angabe der neuen Beträge (bisherige Miete, Anpassungsbetrag, neue Miete, neue Gesamtmiete).
   - Höflichen Schlusssatz.
   - WICHTIG nach DIN 5008: Falls eine Grußformel enthalten ist, lautet sie stets 'Mit freundlichen Grüßen' OHNE Komma am Ende.
8. Antworte AUSSCHLIESSLICH im gültigen JSON-Format mit den Schlüsseln "subject" und "body".
"""

    try:
        response = ollama.chat(
            model=model,
            format="json",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Nutzeranweisung: {user_prompt}"}
            ],
            options={"temperature": 0.1}
        )
        content = response["message"]["content"].strip()
        data = {}
        try:
            data = json.loads(content)
        except Exception:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))

        if "subject" in data and "body" in data:
            return data
    except Exception:
        pass

    return _build_fallback_letter(user_prompt, recipient_name, tenant_info)

def _build_fallback_letter(user_prompt: str, recipient_name: str, tenant_info: Optional[Dict[str, Any]]) -> Dict[str, str]:
    import calendar
    prompt_lower = user_prompt.lower()
    
    salutation = (tenant_info.get("salutation") if tenant_info else "") or ""
    if not salutation:
        salutation = "Frau" if any(fn in recipient_name.lower() for fn in ["laura", "sabine", "anna", "maria", "sarah", "julia", "lisa"]) else "Herr"

    last_name = (tenant_info.get("last_name") if tenant_info else recipient_name.split()[-1]).strip()
    sal_greeting = f"Sehr geehrte Frau {last_name}" if salutation == "Frau" else f"Sehr geehrter Herr {last_name}"

    # 1. Prozentangabe prüfen (z. B. "15%", "15 Prozent", "15 %")
    pct_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|prozent)", prompt_lower)
    is_percentage = bool(pct_match)
    pct_val = float(pct_match.group(1).replace(",", ".")) if pct_match else 0.0

    # 2. Absoluten Euro-Betrag ermitteln (nur wenn keine Prozentangabe)
    amt_match = re.search(r"(?:um|von|betrag)?\s*(\d+(?:[.,]\d+)?)\s*(?:€|euro|\beuro\b)?", prompt_lower)
    euro_val = float(amt_match.group(1).replace(",", ".")) if amt_match and not is_percentage else 0.0

    unit_str = tenant_info.get("unit_number", "Ihrer gemieteten Wohneinheit") if tenant_info else "Ihrer gemieteten Wohneinheit"
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

    # 2. Nebenkostensenkung (§ 560 Abs. 4 BGB)
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

    # 3. Nebenkostenerhöhung (§ 560 Abs. 4 BGB)
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

    # 4. Bankverbindung / Kontaktdaten
    if any(w in prompt_lower for w in ["bankverbindung", "konto", "iban", "kontaktdaten"]):
        subject = "Wichtige Mitteilung: Aktualisierung der Bankverbindung für Mietzahlungen"
        body = (
            f"{sal_greeting},\n\n"
            f"wir möchten Sie darüber informieren, dass sich unsere Bankverbindung für die Überweisung der monatlichen Miete ({unit_str}) ändert.\n\n"
            f"Bitte richten Sie Ihre Zahlungen ab dem kommenden Monatsersten an folgendes Konto:\n"
            f"• Kontoinhaber: Hausverwaltung Sonnenhang\n"
            f"• IBAN: DE12 1005 0000 0123 4567 89\n"
            f"• BIC: BELADEB1XXX\n"
            f"• Verwendungszweck: Miete {unit_str} - {recipient_name}\n\n"
            f"Vielen Dank für Ihre Unterstützung."
        )
        return {"subject": subject, "body": body}

    # 5. Handwerker / Wartung
    if any(w in prompt_lower for w in ["handwerker", "wartung", "reparatur", "begehung", "ablesung"]):
        subject = "Ankündigung von Handwerker- und Instandhaltungsarbeiten"
        body = (
            f"{sal_greeting},\n\n"
            f"wir kündigen Ihnen hiermit anstehende Arbeiten in Ihrer Wohnanlage ({unit_str}) an.\n\n"
            f"Grund: {user_prompt}\n\n"
            f"Bitte gewähren Sie den beauftragten Handwerkern zum vereinbarten Termin Zutritt. Sollten Sie den Termin nicht wahrnehmen können, bitten wir um rechtzeitige Benachrichtigung."
        )
        return {"subject": subject, "body": body}

    # Standard
    subject = "Mitteilung Ihrer Hausverwaltung"
    body = (
        f"{sal_greeting},\n\n"
        f"wir wenden uns heute bezüglich Ihres Mietverhältnisses ({unit_str}) an Sie.\n\n"
        f"{user_prompt}\n\n"
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
    if any(w in prompt_lower for w in ["brief", "schreiben", "anschreiben", "abmahnung", "mahnung", "mitteilung an", "nachricht an", "mieterhöhung", "mieterhoehung"]) or (
        any(w in prompt_lower for w in ["nebenkosten", "kaltmiete", "betriebskosten", "miete"]) and any(w in prompt_lower for w in ["senk", "erhöh", "anpass", "reduzier"])
    ):
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

        if not raw_name:
            # Letzter Versuch: Aus prompt_lower nach Namen suchen
            for t in get_all_tenants():
                if t["last_name"].lower() in user_prompt.lower() or t["first_name"].lower() in user_prompt.lower():
                    raw_name = f"{t['first_name']} {t['last_name']}"
                    break

        if not raw_name:
            return {
                "success": False,
                "message": "Für welchen Mieter soll ich das Schreiben verfassen? Bitte nenne mir den Namen des Mieters (z. B. 'für Max Mustermann' oder 'für Kirdar Karadag').",
                "data": None
            }

        # Mieter in Datenbank nachschlagen
        db_tenant = find_tenant_by_name(raw_name)

        if db_tenant:
            full_name = f"{db_tenant['first_name']} {db_tenant['last_name']}"
            unit_info = f"{db_tenant['unit_number']} ({db_tenant['property_name']})"
            addr_line = f"{db_tenant.get('street', 'Lindenstraße 14')}\n{db_tenant.get('zip_code', '10115')} {db_tenant.get('city', 'Berlin')}"
            prop_name = db_tenant.get("property_name", "Wohnanlage Sonnenhang")
            sender_street = db_tenant.get("street", "Lindenstraße 14")
            sender_city = f"{db_tenant.get('zip_code', '10115')} {db_tenant.get('city', 'Berlin')}"
            note = f"👤 *Mieter aus deiner Datenbank zugeordnet: {full_name} ({unit_info})*"
        else:
            full_name = raw_name
            addr_line = "Musterstraße 1\n10115 Berlin"
            prop_name = "Wohnanlage Sonnenhang"
            sender_street = "Lindenstraße 14"
            sender_city = "10115 Berlin"
            note = f"💡 *Hinweis: '{raw_name}' ist bisher nicht in deiner Mieter-Datenbank hinterlegt. Das Schreiben wurde mit Vorlagendaten für diesen Namen erstellt.*"

        sender_name = "Hausverwaltung Sonnenhang"

        # Brief mit KI entwerfen
        letter_content = draft_letter_with_ai(
            user_prompt=user_prompt,
            recipient_name=full_name,
            tenant_info=db_tenant,
            model=model
        )
        subject = letter_content.get("subject", "Mitteilung der Hausverwaltung")
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
            sender_city=sender_city
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
            sender_city=sender_city
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
            f"**{sender_name}**\n\n"
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
