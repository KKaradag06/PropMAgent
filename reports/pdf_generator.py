import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
pt = 1
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports")

def generate_utility_bill_pdf(bill_data: Dict[str, Any], custom_message: str = "") -> str:
    """
    Erstellt ein professionelles PDF-Dokument für die Nebenkostenabrechnung
    inklusive Anschreiben und tabellarischer Kostenaufstellung.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    tenant = bill_data["tenant"]
    year = bill_data["year"]
    tenant_id = tenant.get("tenant_id") or tenant.get("id") or 1
    filename = f"Nebenkostenabrechnung_{year}_{tenant['last_name']}_{tenant_id}.pdf"
    pdf_path = os.path.join(REPORTS_DIR, filename)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=2.0 * cm,
        leftMargin=2.0 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm
    )

    styles = getSampleStyleSheet()
    
    # Custom Styles
    style_normal = styles["Normal"]
    style_normal.fontSize = 10
    style_normal.leading = 14

    style_bold = ParagraphStyle("Bold", parent=style_normal, fontName="Helvetica-Bold")
    style_title = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=16, leading=20, textColor=colors.HexColor("#1e293b"))
    style_subtitle = ParagraphStyle("SubTitle", parent=styles["Heading2"], fontSize=12, leading=16, textColor=colors.HexColor("#475569"))
    style_sender = ParagraphStyle("Sender", parent=style_normal, fontSize=8, leading=10, textColor=colors.gray)

    elements = []

    # 1. Absenderzeile (Fensterkuvert-Zeile nach DIN)
    from database.settings import get_all_settings
    settings = get_all_settings()
    landlord_name = settings.get("landlord_name", f"Immobilienverwaltung {tenant.get('property_name', '')}")
    landlord_street = settings.get("landlord_street", tenant.get("street", ""))
    landlord_zip = settings.get("landlord_zip", tenant.get("zip_code", ""))
    landlord_city = settings.get("landlord_city", tenant.get("city", ""))
    landlord_iban = settings.get("landlord_iban", "")
    landlord_bank = settings.get("landlord_bank_name", "")
    closing_phrase = settings.get("default_closing_phrase", "Mit freundlichen Grüßen")
    signature_title = settings.get("default_signature_title", landlord_name)
    deadline_days = settings.get("default_payment_deadline_days", "30")

    sender_line = f"{landlord_name} · {landlord_street} · {landlord_zip} {landlord_city}"
    elements.append(Paragraph(sender_line, style_sender))
    elements.append(Spacer(1, 0.5 * cm))

    # 2. Empfängeradresse
    salutation = tenant.get("salutation") or "Herr"
    sal_title = f"{salutation} " if salutation in ("Herr", "Frau") else ""
    sal_greeting = f"Sehr geehrte Frau {tenant['last_name']}" if salutation == "Frau" else f"Sehr geehrter Herr {tenant['last_name']}"

    recipient_text = f"""
    <b>{sal_title}{tenant['first_name']} {tenant['last_name']}</b><br/>
    {tenant['street']}<br/>
    {tenant['unit_number']}<br/>
    {tenant['zip_code']} {tenant['city']}
    """
    elements.append(Paragraph(recipient_text, style_normal))
    elements.append(Spacer(1, 1.0 * cm))

    # 3. Datum & Betreff
    today_str = datetime.now().strftime("%d.%m.%Y")
    effective_date_city = (settings.get("letter_city") or landlord_city or tenant.get("city") or "Berlin").strip()
    elements.append(Paragraph(f"<para align='right'>{effective_date_city}, den {today_str}</para>", style_normal))
    elements.append(Spacer(1, 0.4 * cm))

    elements.append(Paragraph(f"<b>Nebenkostenabrechnung für das Abrechnungsjahr {year}</b>", style_title))
    elements.append(Paragraph(f"Mietobjekt: {tenant['property_name']}, {tenant['unit_number']} (Wohnfläche: {tenant['tenant_sqm']} m² von {tenant['total_area_sqm']} m²)", style_subtitle))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=15, spaceBefore=10))

    # 4. Anschreiben
    if custom_message:
        intro_text = custom_message.replace("\n", "<br/>")
    else:
        intro_text = f"""
        {sal_greeting},<br/><br/>
        anbei erhalten Sie die Abrechnung über die Betriebskosten für das Kalenderjahr {year}.
        Die Kosten wurden gemäß den Vereinbarungen Ihres Mietvertrages und der Betriebskostenverordnung ermittelt.
        """
    elements.append(Paragraph(intro_text, style_normal))
    elements.append(Spacer(1, 0.6 * cm))

    # 5. Kostenaufstellung Tabelle
    table_data = [
        [
            Paragraph("<b>Kostenart</b>", style_bold),
            Paragraph("<b>Gesamtkosten</b>", style_bold),
            Paragraph("<b>Umlageschlüssel</b>", style_bold),
            Paragraph("<b>Ihr Anteil</b>", style_bold)
        ]
    ]

    for item in bill_data["breakdown"]:
        table_data.append([
            Paragraph(item["category"], style_normal),
            Paragraph(f"{item['total_amount']:.2f} €", style_normal),
            Paragraph(item["allocation_key_text"], style_normal),
            Paragraph(f"{item['tenant_share']:.2f} €", style_normal),
        ])

    # Summenzeilen
    table_data.append([
        Paragraph("<b>Gesamtkosten / Ihr Kostenanteil</b>", style_bold),
        Paragraph(f"<b>{bill_data['total_property_expenses']:.2f} €</b>", style_bold),
        Paragraph("", style_normal),
        Paragraph(f"<b>{bill_data['total_tenant_share']:.2f} €</b>", style_bold)
    ])
    table_data.append([
        Paragraph("Abzüglich geleistete Vorauszahlungen", style_normal),
        Paragraph("", style_normal),
        Paragraph("", style_normal),
        Paragraph(f"- {bill_data['prepayments_paid']:.2f} €", style_normal)
    ])

    balance = bill_data["balance"]
    if balance > 0:
        balance_label = "<b>Nachzahlung zu Ihren Lasten:</b>"
        balance_val = f"<b><font color='#b91c1c'>+ {balance:.2f} €</font></b>"
    elif balance < 0:
        balance_label = "<b>Guthaben zu Ihren Gunsten:</b>"
        balance_val = f"<b><font color='#15803d'>- {abs(balance):.2f} €</font></b>"
    else:
        balance_label = "<b>Saldo ausgeglichen:</b>"
        balance_val = "<b>0,00 €</b>"

    table_data.append([
        Paragraph(balance_label, style_bold),
        Paragraph("", style_normal),
        Paragraph("", style_normal),
        Paragraph(balance_val, style_bold)
    ])

    t = Table(table_data, colWidths=[6.0*cm, 3.2*cm, 4.5*cm, 3.3*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, colors.HexColor("#94a3b8")),
        ('LINEBELOW', (0, -3), (-1, -3), 1, colors.HexColor("#cbd5e1")),
        ('LINEBELOW', (0, -2), (-1, -2), 1, colors.HexColor("#cbd5e1")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#f8fafc")),
        ('LINEBELOW', (0, -1), (-1, -1), 1.5, colors.HexColor("#0f172a")),
    ]))

    elements.append(t)
    elements.append(Spacer(1, 0.8 * cm))

    # 6. Schlusssatz & Grußformel (DIN 5008: ohne Komma, 3 Leerzeilen für Unterschrift)
    if balance > 0:
        bank_info = f" auf das Mietkonto ({landlord_iban}, {landlord_bank})" if landlord_iban else " auf das bekannte Mietkonto"
        conclusion = f"Wir bitten Sie höflich, den Nachzahlungsbetrag in Höhe von <b>{balance:.2f} €</b> innerhalb von {deadline_days} Tagen{bank_info} zu überweisen."
    elif balance < 0:
        conclusion = f"Das Guthaben in Höhe von <b>{abs(balance):.2f} €</b> wird mit Ihrer nächsten Mietzahlung verrechnet oder auf Ihr hinterlegtes Bankkonto überwiesen."
    else:
        conclusion = "Ihr Abrechnungskonto für das Jahr ist exakt ausgeglichen. Eine Zahlung ist nicht erforderlich."

    elements.append(Paragraph(conclusion, style_normal))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(f"{closing_phrase}<br/><br/><br/><b>{signature_title}</b>", style_normal))

    doc.build(elements)
    return pdf_path

def _build_confirmation_pdf_elements(
    confirmation_data: Dict[str, Any],
    sender_name: str,
    sender_street: str,
    sender_city: str,
    is_private: bool,
    styles: Any
) -> List[Any]:
    """
    Erstellt die Elemente für Seite 2: Das offizielle Bestätigungsschreiben / die Zustimmungserklärung
    des Mieters zum Ausfüllen, Unterschreiben und Zurücksenden.
    """
    conf_elements = [PageBreak()]

    style_ret_head = ParagraphStyle("ConfRetHead", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.HexColor("#475569"))
    style_ret_body = ParagraphStyle("ConfRetBody", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#1e293b"))
    style_ret_meta = ParagraphStyle("ConfRetMeta", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, alignment=2, textColor=colors.HexColor("#334155"))
    style_conf_title = ParagraphStyle("ConfTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=colors.HexColor("#0f172a"))
    style_conf_ref = ParagraphStyle("ConfRef", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#334155"))
    style_conf_body = ParagraphStyle("ConfBody", parent=styles["Normal"], fontName="Helvetica", fontSize=10.5, leading=14.5, textColor=colors.HexColor("#0f172a"))
    style_conf_note = ParagraphStyle("ConfNote", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=9, leading=12.5, textColor=colors.HexColor("#64748b"))
    style_tbl_head = ParagraphStyle("ConfTblHead", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=colors.HexColor("#0f172a"))
    style_tbl_cell = ParagraphStyle("ConfTblCell", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=12, textColor=colors.HexColor("#1e293b"))
    style_tbl_bold = ParagraphStyle("ConfTblBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=colors.HexColor("#0f172a"))

    let_date = confirmation_data.get("letter_date") or datetime.now().strftime("%d.%m.%Y")
    prop_name = confirmation_data.get("property_name") or ""
    unit_no = confirmation_data.get("unit_number") or ""
    tenant_names = confirmation_data.get("tenant_names") or []
    names_str = ", ".join(tenant_names) if tenant_names else "Mieter/in"
    conf_type = confirmation_data.get("type", "allgemein")

    # 1. Rücksende-Kopfzeile
    ret_title_suffix = " (Vermieter)" if is_private else ""
    left_meta = [
        Paragraph("<b>Rückantwort an den Absender:</b>", style_ret_head),
        Spacer(1, 2 * pt),
        Paragraph(f"<b>{sender_name}</b>{ret_title_suffix}<br/>{sender_street}<br/>{sender_city}", style_ret_body)
    ]
    right_meta = [
        Paragraph(
            f"<b>Datum:</b> {let_date}<br/>" +
            (f"<b>Mietobjekt:</b> {prop_name}<br/>" if prop_name else "") +
            (f"<b>Einheit:</b> {unit_no}" if unit_no else ""),
            style_ret_meta
        )
    ]
    hdr_table = Table([[left_meta, right_meta]], colWidths=[9.5 * cm, 7.0 * cm])
    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    conf_elements.append(hdr_table)
    conf_elements.append(Spacer(1, 10 * pt))

    # 2. Überschrift
    if conf_type == "mieterhoehung":
        title_text = "Zustimmungserklärung zur Mieterhöhung"
    elif conf_type == "nebenkosten":
        title_text = "Bestätigung der Anpassung der Nebenkostenvorauszahlung"
    else:
        title_text = "Bestätigungsschreiben / Rückantwort"

    conf_elements.append(Paragraph(f"<b>{title_text}</b>", style_conf_title))
    conf_elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94a3b8"), spaceAfter=8, spaceBefore=4))

    # 3. Referenzzeile
    conf_elements.append(Paragraph(f"<b>Mietobjekt:</b> {prop_name}, {unit_no} &nbsp;·&nbsp; <b>Mieter:</b> {names_str} &nbsp;·&nbsp; <b>Bezug:</b> Schreiben vom {let_date}", style_conf_ref))
    conf_elements.append(Spacer(1, 8 * pt))

    # 4. Bestätigungstext und Beträge
    if conf_type == "mieterhoehung":
        eff_date = confirmation_data.get("effective_date", "")
        old_c = confirmation_data.get("old_cold", 0.0)
        diff_c = confirmation_data.get("diff_cold", 0.0)
        new_c = confirmation_data.get("new_cold", 0.0)
        old_nk = confirmation_data.get("old_nk", 0.0)
        new_tot = confirmation_data.get("new_total", 0.0)
        old_tot = confirmation_data.get("old_total", old_c + old_nk)
        deadline = confirmation_data.get("deadline_date", "")

        conf_elements.append(Paragraph(
            f"Hiermit erkläre ich / erklären wir mein / unser uneingeschränktes Einverständnis mit der im Schreiben "
            f"vom {let_date} dargelegten Erhöhung der monatlichen Nettokaltmiete gemäß § 558 BGB.",
            style_conf_body
        ))
        conf_elements.append(Spacer(1, 8 * pt))

        tbl_data = [
            [Paragraph("<b>Mietbestandteil</b>", style_tbl_head),
             Paragraph("<b>Bisher</b>", style_tbl_head),
             Paragraph("<b>Erhöhung</b>", style_tbl_head),
             Paragraph(f"<b>Neu ab {eff_date}</b>", style_tbl_head)],
            [Paragraph("Nettokaltmiete", style_tbl_cell),
             Paragraph(f"{old_c:.2f} €", style_tbl_cell),
             Paragraph(f"+ {diff_c:.2f} €", style_tbl_cell),
             Paragraph(f"<b>{new_c:.2f} €</b>", style_tbl_bold)],
            [Paragraph("Betriebskostenvorauszahlung", style_tbl_cell),
             Paragraph(f"{old_nk:.2f} €", style_tbl_cell),
             Paragraph("unverändert", style_tbl_cell),
             Paragraph(f"{old_nk:.2f} €", style_tbl_cell)],
            [Paragraph("<b>Monatliche Gesamtmiete</b>", style_tbl_bold),
             Paragraph(f"<b>{old_tot:.2f} €</b>", style_tbl_bold),
             Paragraph(f"<b>+ {diff_c:.2f} €</b>", style_tbl_bold),
             Paragraph(f"<b>{new_tot:.2f} €</b>", style_tbl_bold)],
        ]
        rent_table = Table(tbl_data, colWidths=[6.0 * cm, 3.2 * cm, 3.3 * cm, 4.0 * cm])
        rent_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.HexColor("#94a3b8")),
            ('LINEBELOW', (0, 1), (-1, 2), 0.5, colors.HexColor("#e2e8f0")),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#f8fafc")),
            ('LINEBELOW', (0, 3), (-1, 3), 1.2, colors.HexColor("#0f172a")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        conf_elements.append(rent_table)
        conf_elements.append(Spacer(1, 8 * pt))

        conf_elements.append(Paragraph(
            f"Ich / Wir verpflichten uns, die neue monatliche Gesamtmiete in Höhe von <b>{new_tot:.2f} €</b> "
            f"ab dem <b>{eff_date}</b> pünktlich zum Fälligkeitstermin auf das angegebene Mietkonto "
            f"zu entrichten und den bestehenden Dauerauftrag rechtzeitig anzupassen.",
            style_conf_body
        ))
        conf_elements.append(Spacer(1, 8 * pt))

        dl_note = f" bis spätestens zum <b>{deadline}</b>" if deadline else ""
        conf_elements.append(Paragraph(
            f"<i>Hinweis: Bitte senden Sie diese Erklärung{dl_note} ausgefüllt und von allen im "
            f"Mietvertrag genannten Personen unterzeichnet an den Vermieter zurück.</i>",
            style_conf_note
        ))

    elif conf_type == "nebenkosten":
        eff_date = confirmation_data.get("effective_date", "")
        old_c = confirmation_data.get("old_cold", 0.0)
        old_nk = confirmation_data.get("old_nk", 0.0)
        diff_nk = confirmation_data.get("diff_nk", 0.0)
        new_nk = confirmation_data.get("new_nk", 0.0)
        new_tot = confirmation_data.get("new_total", 0.0)
        old_tot = confirmation_data.get("old_total", old_c + old_nk)
        is_inc = confirmation_data.get("is_nk_inc", False)
        diff_sym = f"+ {diff_nk:.2f} €" if is_inc else f"- {diff_nk:.2f} €"

        conf_elements.append(Paragraph(
            f"Hiermit bestätige ich / bestätigen wir den Erhalt Ihres Schreibens vom {let_date} und erklären "
            f"das Einverständnis mit der Anpassung der monatlichen Betriebskostenvorauszahlung gemäß § 560 Abs. 4 BGB.",
            style_conf_body
        ))
        conf_elements.append(Spacer(1, 8 * pt))

        tbl_data = [
            [Paragraph("<b>Mietbestandteil</b>", style_tbl_head),
             Paragraph("<b>Bisher</b>", style_tbl_head),
             Paragraph("<b>Anpassung</b>", style_tbl_head),
             Paragraph(f"<b>Neu ab {eff_date}</b>", style_tbl_head)],
            [Paragraph("Nettokaltmiete", style_tbl_cell),
             Paragraph(f"{old_c:.2f} €", style_tbl_cell),
             Paragraph("unverändert", style_tbl_cell),
             Paragraph(f"{old_c:.2f} €", style_tbl_cell)],
            [Paragraph("Betriebskostenvorauszahlung", style_tbl_cell),
             Paragraph(f"{old_nk:.2f} €", style_tbl_cell),
             Paragraph(diff_sym, style_tbl_cell),
             Paragraph(f"<b>{new_nk:.2f} €</b>", style_tbl_bold)],
            [Paragraph("<b>Monatliche Gesamtmiete</b>", style_tbl_bold),
             Paragraph(f"<b>{old_tot:.2f} €</b>", style_tbl_bold),
             Paragraph(f"<b>{diff_sym}</b>", style_tbl_bold),
             Paragraph(f"<b>{new_tot:.2f} €</b>", style_tbl_bold)],
        ]
        rent_table = Table(tbl_data, colWidths=[6.0 * cm, 3.2 * cm, 3.3 * cm, 4.0 * cm])
        rent_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.HexColor("#94a3b8")),
            ('LINEBELOW', (0, 1), (-1, 2), 0.5, colors.HexColor("#e2e8f0")),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#f8fafc")),
            ('LINEBELOW', (0, 3), (-1, 3), 1.2, colors.HexColor("#0f172a")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        conf_elements.append(rent_table)
        conf_elements.append(Spacer(1, 8 * pt))

        conf_elements.append(Paragraph(
            f"Ich / Wir werden die monatlichen Mietzahlungen bzw. den bestehenden Dauerauftrag ab dem "
            f"<b>{eff_date}</b> rechtzeitig auf den neuen Gesamtbetrag von <b>{new_tot:.2f} €</b> anpassen.",
            style_conf_body
        ))
        conf_elements.append(Spacer(1, 8 * pt))
        conf_elements.append(Paragraph(
            "<i>Hinweis: Bitte senden Sie diese Bestätigung ausgefüllt und von allen Mietvertragsparteien unterzeichnet an den Vermieter zurück.</i>",
            style_conf_note
        ))

    else:
        subj = confirmation_data.get("subject", "")
        conf_elements.append(Paragraph(
            f"Hiermit bestätige ich / bestätigen wir den ordnungsgemäßen Erhalt und die Kenntnisnahme "
            f"Ihres Schreibens vom {let_date}" + (f" betreffend <b>{subj}</b>." if subj else "."),
            style_conf_body
        ))
        conf_elements.append(Spacer(1, 10 * pt))
        conf_elements.append(Paragraph(
            "Die im genannten Schreiben aufgeführten Mitteilungen bzw. Vereinbarungen wurden zur Kenntnis "
            "genommen und werden hiermit vollinhaltlich bestätigt.",
            style_conf_body
        ))
        conf_elements.append(Spacer(1, 10 * pt))
        conf_elements.append(Paragraph(
            "<i>Hinweis: Bitte senden Sie diese Empfangsbestätigung ausgefüllt und unterzeichnet an den Absender zurück.</i>",
            style_conf_note
        ))

    # 5. Unterschriftenbereich
    conf_elements.append(Spacer(1, 14 * pt))
    conf_elements.append(Paragraph("Ort, Datum: ____________________________________________________", style_conf_body))
    conf_elements.append(Spacer(1, 24 * pt))

    if len(tenant_names) <= 1:
        sig_name = tenant_names[0] if tenant_names else "Mieter/in"
        conf_elements.append(Paragraph("____________________________________________________", style_conf_body))
        conf_elements.append(Paragraph(f"Unterschrift: <b>{sig_name}</b> (Mieter/in)", style_conf_body))
    else:
        sig_cols = []
        for name in tenant_names[:2]:
            sig_cols.append([
                Paragraph("________________________________________", style_conf_body),
                Spacer(1, 2 * pt),
                Paragraph(f"Unterschrift: <b>{name}</b>", style_conf_body)
            ])
        if len(sig_cols) == 1:
            sig_cols.append([Paragraph("", style_conf_body)])
        sig_table = Table([sig_cols], colWidths=[8.0 * cm, 8.0 * cm])
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        conf_elements.append(sig_table)

    return conf_elements

def generate_formal_letter_pdf(
    recipient_name: str,
    subject: str,
    letter_text: str,
    address_line: str = "",
    sender_name: Optional[str] = None,
    property_name: Optional[str] = None,
    sender_street: Optional[str] = None,
    sender_city: Optional[str] = None,
    sender_phone: Optional[str] = None,
    sender_email: Optional[str] = None,
    sign_person: Optional[str] = None,
    confirmation_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Erstellt ein formelles Brief-PDF nach DIN 5008:2020 Form B.
    Nutzt standardmäßig die in den Einstellungen hinterlegten Vermieterdaten.
    """
    import re
    from reportlab.platypus import KeepTogether
    from database.settings import get_all_settings
    settings = get_all_settings()

    is_private = settings.get("landlord_type", "private") == "private"
    default_sender = "Kirdar Karadag" if is_private else "Hausverwaltung Sonnenhang"
    sender_name = sender_name or settings.get("landlord_name", default_sender)
    if is_private and sender_name == "Hausverwaltung Sonnenhang":
        sender_name = settings.get("landlord_contact_person") or "Kirdar Karadag"

    property_name = property_name or settings.get("landlord_name", "Wohnanlage Sonnenhang")
    sender_street = sender_street or settings.get("landlord_street", "Lindenstraße 14")
    sender_city = sender_city or f"{settings.get('landlord_zip', '10115')} {settings.get('landlord_city', 'Berlin')}"
    sender_phone = sender_phone or settings.get("landlord_phone", "+49 30 12345678")
    sender_email = sender_email or settings.get("landlord_email", "kirdar@karadag.de" if is_private else "verwaltung@sonnenhang.de")
    closing_phrase = settings.get("default_closing_phrase", "Mit freundlichen Grüßen")
    sign_title = sign_person or settings.get("default_signature_title")
    if not sign_title or (is_private and "hausverwaltung" in sign_title.lower()):
        sign_title = f"{sender_name}\n(Vermieter)" if is_private else sender_name

    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    clean_first_line = recipient_name.split("\n")[0].strip()
    clean_name = "".join(c for c in clean_first_line if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")[:35]
    today_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Brief_{clean_name}_{today_str}.pdf"
    pdf_path = os.path.join(REPORTS_DIR, filename)

    # DIN 5008 Form B Seitenränder: Oben 4.5 cm, Links 2.5 cm, Unten 2.5 cm, Rechts 2.0 cm
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        topMargin=4.5 * cm,
        leftMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        rightMargin=2.0 * cm
    )

    styles = getSampleStyleSheet()
    
    # 11 pt Fließtext, einfacher Zeilenabstand (14 pt leading)
    style_body = ParagraphStyle(
        "DIN5008_Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        firstLineIndent=0,
        spaceAfter=11,
        textColor=colors.HexColor("#0f172a")
    )

    # Rücksendeangabe im Sichtfenster: genau 8 pt (darf laut DIN nicht unter 8 pt fallen)
    style_sender_return = ParagraphStyle(
        "DIN5008_SenderReturn",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#64748b")
    )

    # Empfängeradresse im Anschriftfeld: 11 pt, leading 14 pt
    style_recipient = ParagraphStyle(
        "DIN5008_Recipient",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0f172a")
    )

    # Info-Block rechts (Eigene Adresse & Datum): rechtsbündig
    style_info_block = ParagraphStyle(
        "DIN5008_InfoBlock",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        alignment=2,  # TA_RIGHT
        textColor=colors.HexColor("#334155")
    )

    # Betreffzeile: 12 pt, fett, kein vorangestelltes "Betreff:"
    style_subject = ParagraphStyle(
        "DIN5008_Subject",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a")
    )

    # Betreff und Fließtext bereinigen
    clean_subject = re.sub(r"^(?:Betreff|Subject)\s*:\s*", "", subject, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r"\n*(?:Mit freundlichen Grüßen|Freundliche Grüße|Herzliche Grüße)[,\s]*.*$", "", letter_text, flags=re.IGNORECASE | re.DOTALL).strip()

    elements = []

    # 1. Anschriftfeld (links, max. 8,5 cm) und Info-Block mit Datum (rechts, 8,0 cm)
    # Rücksendeangabe
    sender_return_line = f"<u>{sender_name} · {sender_street} · {sender_city}</u>"
    
    # Empfänger-Adressblock
    clean_addr = address_line.replace("<br/>", "\n").replace("<br>", "\n")
    addr_lines = [line.strip() for line in clean_addr.split("\n") if line.strip()]
    if not addr_lines:
        addr_lines = ["Musterstraße 1", "10115 Berlin"]
    
    recipient_html = f"<b>{recipient_name}</b><br/>" + "<br/>".join(addr_lines)

    left_cell_elements = [
        Paragraph(sender_return_line, style_sender_return),
        Spacer(1, 0.4 * cm),
        Paragraph(recipient_html, style_recipient)
    ]

    date_display = datetime.now().strftime("%d.%m.%Y")
    sender_city_name = ""
    if sender_city:
        parts = sender_city.strip().split()
        if len(parts) > 1 and parts[0].isdigit():
            sender_city_name = " ".join(parts[1:])
        elif parts:
            sender_city_name = parts[-1]
    effective_date_city = (settings.get("letter_city") or settings.get("landlord_city") or sender_city_name or "Berlin").strip()
    date_line_text = f"{effective_date_city}, den {date_display}"

    sender_title_line = f"<b>{sender_name}</b> (Vermieter)<br/>" if is_private else f"<b>{sender_name}</b><br/>"
    prop_line = f"{property_name}<br/>" if (property_name and property_name != sender_name and not is_private) else ""
    right_cell_html = (
        f"{sender_title_line}"
        f"{prop_line}"
        f"{sender_street}<br/>"
        f"{sender_city}<br/>"
        f"Tel.: {sender_phone}<br/>"
        f"E-Mail: {sender_email}<br/><br/>"
        f"{date_line_text}"
    )
    right_cell_elements = [
        Paragraph(right_cell_html, style_info_block)
    ]

    # Tabelle: Links genau 8.5 cm (DIN Fenster), Rechts 8.0 cm -> Gesamtbreite 16.5 cm
    header_table = Table([[left_cell_elements, right_cell_elements]], colWidths=[8.5 * cm, 8.0 * cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)

    # 2. Betreff beginnt zwei Zeilen unter dem Datum (ca. 24 pt)
    elements.append(Spacer(1, 24 * pt))
    elements.append(Paragraph(f"<b>{clean_subject}</b>", style_subject))

    # 3. Fließtext beginnt zwei Zeilen unter dem Betreff (ca. 24 pt)
    elements.append(Spacer(1, 24 * pt))

    # Absätze des Fließtexts (gegliedert durch jeweils 1 Leerzeile, kein Erstzeileneinzug)
    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [clean_text]

    for p in paragraphs:
        formatted_p = p.replace("\n", "<br/>")
        elements.append(Paragraph(formatted_p, style_body))

    # 4. Grußformel: nach einer Leerzeile, OHNE Komma, danach 3 Leerzeilen für Unterschrift
    closing_elements = [
        Spacer(1, 11 * pt),
        Paragraph(closing_phrase, style_body),
        Spacer(1, 33 * pt),  # 3 Leerzeilen für handschriftliche Unterschrift
        Paragraph(f"<b>{sign_title}</b>", style_body)
    ]
    elements.append(KeepTogether(closing_elements))

    # 5. Optionale 2. Seite: Bestätigungsschreiben / Zustimmungserklärung
    if confirmation_data and confirmation_data.get("enabled", True):
        elements.extend(_build_confirmation_pdf_elements(
            confirmation_data=confirmation_data,
            sender_name=sender_name,
            sender_street=sender_street,
            sender_city=sender_city,
            is_private=is_private,
            styles=styles
        ))

    doc.build(elements)
    return pdf_path

