import os
from datetime import datetime
from typing import Dict, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
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
    sender_line = f"Immobilienverwaltung {tenant['property_name']} · {tenant['street']} · {tenant['zip_code']} {tenant['city']}"
    elements.append(Paragraph(sender_line, style_sender))
    elements.append(Spacer(1, 0.5 * cm))

    # 2. Empfängeradresse
    recipient_text = f"""
    <b>{tenant['first_name']} {tenant['last_name']}</b><br/>
    {tenant['street']}<br/>
    {tenant['unit_number']}<br/>
    {tenant['zip_code']} {tenant['city']}
    """
    elements.append(Paragraph(recipient_text, style_normal))
    elements.append(Spacer(1, 1.0 * cm))

    # 3. Datum & Betreff
    today_str = datetime.now().strftime("%d.%m.%Y")
    elements.append(Paragraph(f"<para align='right'>{tenant['city']}, den {today_str}</para>", style_normal))
    elements.append(Spacer(1, 0.4 * cm))

    elements.append(Paragraph(f"<b>Nebenkostenabrechnung für das Abrechnungsjahr {year}</b>", style_title))
    elements.append(Paragraph(f"Mietobjekt: {tenant['property_name']}, {tenant['unit_number']} (Wohnfläche: {tenant['tenant_sqm']} m² von {tenant['total_area_sqm']} m²)", style_subtitle))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=15, spaceBefore=10))

    # 4. Anschreiben
    if custom_message:
        intro_text = custom_message.replace("\n", "<br/>")
    else:
        intro_text = f"""
        Sehr geehrte(r) Frau/Herr {tenant['last_name']},<br/><br/>
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

    # 6. Schlusssatz & Grußformel
    if balance > 0:
        conclusion = f"Wir bitten Sie höflich, den Nachzahlungsbetrag in Höhe von <b>{balance:.2f} €</b> innerhalb von 30 Tagen auf das bekannte Mietkonto zu überweisen."
    elif balance < 0:
        conclusion = f"Das Guthaben in Höhe von <b>{abs(balance):.2f} €</b> wird mit Ihrer nächsten Mietzahlung verrechnet oder auf Ihr hinterlegtes Bankkonto überwiesen."
    else:
        conclusion = "Ihr Abrechnungskonto für das Jahr ist exakt ausgeglichen. Eine Zahlung ist nicht erforderlich."

    elements.append(Paragraph(conclusion, style_normal))
    elements.append(Spacer(1, 0.6 * cm))
    elements.append(Paragraph("Mit freundlichen Grüßen,<br/>Ihre Hausverwaltung", style_normal))

    doc.build(elements)
    return pdf_path
