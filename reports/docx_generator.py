import os
from datetime import datetime
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports")

def generate_formal_letter_docx(
    recipient_name: str,
    subject: str,
    letter_text: str,
    address_line: str = "",
    sender_name: str = "Hausverwaltung",
    property_name: str = "Wohnanlage Sonnenhang"
) -> str:
    """
    Erstellt ein formelles DOCX-Word-Dokument (DIN 5008 ähnlich),
    das sowohl in Microsoft Word als auch in LibreOffice / OpenOffice geöffnet und editiert werden kann.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    clean_name = "".join(c for c in recipient_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    today_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Brief_{clean_name}_{today_str}.docx"
    docx_path = os.path.join(REPORTS_DIR, filename)

    doc = Document()
    
    # Seitenränder einstellen
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # 1. Absenderzeile (klein, grau)
    p_sender = doc.add_paragraph()
    r_sender = p_sender.add_run(f"{sender_name} · {property_name}")
    r_sender.font.name = "Arial"
    r_sender.font.size = Pt(8.5)
    r_sender.font.color.rgb = RGBColor(120, 120, 120)
    p_sender.paragraph_format.space_after = Pt(14)

    # 2. Empfängeradresse
    p_addr = doc.add_paragraph()
    r_name = p_addr.add_run(f"{recipient_name}\n")
    r_name.font.name = "Arial"
    r_name.bold = True
    r_name.font.size = Pt(10.5)
    
    clean_addr = address_line.replace("<br/>", "\n").replace("<br>", "\n")
    addr_lines = [line.strip() for line in clean_addr.split("\n") if line.strip()]
    if not addr_lines:
        addr_lines = ["Musterstraße 1", "10115 Berlin"]
        
    for line in addr_lines:
        r_line = p_addr.add_run(f"{line}\n")
        r_line.font.name = "Arial"
        r_line.font.size = Pt(10.5)
    p_addr.paragraph_format.space_after = Pt(20)

    # 3. Datum (rechtsbündig)
    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_date = p_date.add_run(datetime.now().strftime("%d.%m.%Y"))
    r_date.font.name = "Arial"
    r_date.font.size = Pt(10.5)
    p_date.paragraph_format.space_after = Pt(16)

    # 4. Betreff (fett, hervorgehoben)
    p_subj = doc.add_paragraph()
    r_subj = p_subj.add_run(subject)
    r_subj.font.name = "Arial"
    r_subj.bold = True
    r_subj.font.size = Pt(12.5)
    r_subj.font.color.rgb = RGBColor(15, 23, 42)
    p_subj.paragraph_format.space_after = Pt(14)

    # 5. Brieftext (Absätze sauber formatieren)
    paragraphs = [p.strip() for p in letter_text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [letter_text]

    for p in paragraphs:
        p_body = doc.add_paragraph()
        r_body = p_body.add_run(p)
        r_body.font.name = "Arial"
        r_body.font.size = Pt(10.5)
        p_body.paragraph_format.line_spacing = 1.15
        p_body.paragraph_format.space_after = Pt(8)

    # 6. Grußformel & Signatur
    p_sign = doc.add_paragraph()
    p_sign.paragraph_format.space_before = Pt(14)
    r_sign1 = p_sign.add_run("Mit freundlichen Grüßen,\n\n\n")
    r_sign1.font.name = "Arial"
    r_sign1.font.size = Pt(10.5)
    r_sign2 = p_sign.add_run(sender_name)
    r_sign2.font.name = "Arial"
    r_sign2.bold = True
    r_sign2.font.size = Pt(10.5)

    doc.save(docx_path)
    return docx_path
