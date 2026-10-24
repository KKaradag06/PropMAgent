import os
import re
from datetime import datetime
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports")

def generate_formal_letter_docx(
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
    sign_person: Optional[str] = None
) -> str:
    """
    Erstellt ein formelles DOCX-Word-Dokument nach DIN 5008:2020 Form B.
    Nutzt standardmäßig die in den Einstellungen hinterlegten Vermieterdaten.
    """
    from database.settings import get_all_settings
    settings = get_all_settings()

    sender_name = sender_name or settings.get("landlord_name", "Hausverwaltung Sonnenhang")
    property_name = property_name or settings.get("landlord_name", "Wohnanlage Sonnenhang")
    sender_street = sender_street or settings.get("landlord_street", "Lindenstraße 14")
    sender_city = sender_city or f"{settings.get('landlord_zip', '10115')} {settings.get('landlord_city', 'Berlin')}"
    sender_phone = sender_phone or settings.get("landlord_phone", "+49 30 12345678")
    sender_email = sender_email or settings.get("landlord_email", "verwaltung@sonnenhang.de")
    closing_phrase = settings.get("default_closing_phrase", "Mit freundlichen Grüßen")
    sign_title = sign_person or settings.get("landlord_contact_person") or settings.get("default_signature_title", sender_name)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    clean_name = "".join(c for c in recipient_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    today_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Brief_{clean_name}_{today_str}.docx"
    docx_path = os.path.join(REPORTS_DIR, filename)

    doc = Document()
    
    # 1. DIN 5008 Form B Seitenränder: Oben 4.5 cm, Links 2.5 cm, Unten 2.5 cm, Rechts 2.0 cm
    for section in doc.sections:
        section.top_margin = Cm(4.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.0)

    # Betreff und Fließtext bereinigen
    clean_subject = re.sub(r"^(?:Betreff|Subject)\s*:\s*", "", subject, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r"\n*(?:Mit freundlichen Grüßen|Freundliche Grüße|Herzliche Grüße)[,\s]*.*$", "", letter_text, flags=re.IGNORECASE | re.DOTALL).strip()

    # 2. Anschriftfeld (links, max. 8,5 cm) und Info-Block mit Datum (rechts, 8,0 cm)
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    table.columns[0].width = Cm(8.5)
    table.columns[1].width = Cm(8.0)

    cell_left = table.cell(0, 0)
    cell_right = table.cell(0, 1)

    # Linke Spalte (Anschriftzone):
    # Rücksendeangabe (genau 8 pt unterstrichen)
    p_ret = cell_left.paragraphs[0]
    p_ret.paragraph_format.space_before = Pt(0)
    p_ret.paragraph_format.space_after = Pt(8)
    r_ret = p_ret.add_run(f"{sender_name} · {sender_street} · {sender_city}")
    r_ret.font.name = "Arial"
    r_ret.font.size = Pt(8.0)
    r_ret.font.underline = True
    r_ret.font.color.rgb = RGBColor(100, 116, 139)

    # Empfänger-Adresse (11 pt)
    p_rec = cell_left.add_paragraph()
    p_rec.paragraph_format.space_before = Pt(0)
    p_rec.paragraph_format.space_after = Pt(0)
    p_rec.paragraph_format.line_spacing = 1.0
    r_name = p_rec.add_run(f"{recipient_name}\n")
    r_name.font.name = "Arial"
    r_name.font.size = Pt(11.0)
    r_name.font.bold = True

    clean_addr = address_line.replace("<br/>", "\n").replace("<br>", "\n")
    addr_lines = [line.strip() for line in clean_addr.split("\n") if line.strip()]
    if not addr_lines:
        addr_lines = ["Musterstraße 1", "10115 Berlin"]

    for idx, line in enumerate(addr_lines):
        suffix = "\n" if idx < len(addr_lines) - 1 else ""
        r_line = p_rec.add_run(f"{line}{suffix}")
        r_line.font.name = "Arial"
        r_line.font.size = Pt(11.0)

    # Rechte Spalte (Info-Block & Datum, rechtsbündig):
    date_display = datetime.now().strftime("%d.%m.%Y")
    p_info = cell_right.paragraphs[0]
    p_info.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_info.paragraph_format.space_before = Pt(0)
    p_info.paragraph_format.space_after = Pt(0)
    p_info.paragraph_format.line_spacing = 1.0

    r_snd1 = p_info.add_run(f"{sender_name}\n")
    r_snd1.font.name = "Arial"
    r_snd1.font.size = Pt(10.0)
    r_snd1.font.bold = True

    info_text = (
        f"{property_name}\n"
        f"{sender_street}\n"
        f"{sender_city}\n"
        f"Tel.: {sender_phone}\n"
        f"E-Mail: {sender_email}\n\n"
        f"Datum: {date_display}"
    )
    r_snd2 = p_info.add_run(info_text)
    r_snd2.font.name = "Arial"
    r_snd2.font.size = Pt(9.5)
    r_snd2.font.color.rgb = RGBColor(51, 65, 85)

    # 3. Betreff: 2 Zeilen unter dem Datum, fett, ohne das Wort 'Betreff'
    p_subj = doc.add_paragraph()
    p_subj.paragraph_format.space_before = Pt(24)
    p_subj.paragraph_format.space_after = Pt(24)
    r_subj = p_subj.add_run(clean_subject)
    r_subj.font.name = "Arial"
    r_subj.bold = True
    r_subj.font.size = Pt(12.0)
    r_subj.font.color.rgb = RGBColor(15, 23, 42)

    # 4. Fließtext: 11 pt, einfacher Zeilenabstand (1.0), keine Erstzeileneinrückung, 1 Leerzeile nach Absatz
    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [clean_text]

    for p in paragraphs:
        p_body = doc.add_paragraph()
        p_body.paragraph_format.left_indent = Pt(0)
        p_body.paragraph_format.first_line_indent = Pt(0)
        p_body.paragraph_format.line_spacing = 1.0
        p_body.paragraph_format.space_after = Pt(11)  # Leerzeile
        r_body = p_body.add_run(p)
        r_body.font.name = "Arial"
        r_body.font.size = Pt(11.0)
        r_body.font.color.rgb = RGBColor(15, 23, 42)

    # 5. Grußformel: nach einer Leerzeile, OHNE Komma, 3 Leerzeilen für handschriftliche Unterschrift
    p_gruss = doc.add_paragraph()
    p_gruss.paragraph_format.space_before = Pt(11)
    p_gruss.paragraph_format.space_after = Pt(33)  # 3 Leerzeilen für Unterschrift
    r_gruss = p_gruss.add_run(closing_phrase)
    r_gruss.font.name = "Arial"
    r_gruss.font.size = Pt(11.0)

    # Name des Unterzeichners / Absenders in Druckschrift
    p_sign = doc.add_paragraph()
    p_sign.paragraph_format.space_before = Pt(0)
    p_sign.paragraph_format.space_after = Pt(0)
    r_sign = p_sign.add_run(sign_title)
    r_sign.font.name = "Arial"
    r_sign.font.size = Pt(11.0)
    r_sign.font.bold = True

    doc.save(docx_path)
    return docx_path
