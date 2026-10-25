import re
import json
import io
from typing import Dict, Any, List, Optional, Union
import pypdf
import ollama
from database.settings import get_all_settings

def extract_text_from_pdf(pdf_source: Union[str, bytes, io.BytesIO, Any]) -> str:
    """Extrahiert den vollständigen Text aus einer PDF-Datei (Pfad, Bytes oder UploadedFile)."""
    text_parts: List[str] = []
    try:
        if isinstance(pdf_source, str):
            reader = pypdf.PdfReader(pdf_source)
        elif isinstance(pdf_source, bytes):
            reader = pypdf.PdfReader(io.BytesIO(pdf_source))
        elif hasattr(pdf_source, "read"):
            # Streamlit UploadedFile oder BytesIO
            data = pdf_source.read()
            if hasattr(pdf_source, "seek"):
                pdf_source.seek(0)
            reader = pypdf.PdfReader(io.BytesIO(data))
        else:
            reader = pypdf.PdfReader(pdf_source)

        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(f"--- Seite {idx + 1} ---\n{page_text.strip()}")
    except Exception as e:
        raise RuntimeError(f"Fehler beim Auslesen der PDF-Datei: {e}")

    full_text = "\n\n".join(text_parts).strip()
    return full_text

def heuristic_extract_property_data(text: str) -> Dict[str, Any]:
    """Deterministischer deutscher Heuristik- & Regex-Parser für Liegenschafts- und Zensusdokumente."""
    result: Dict[str, Any] = {
        "property_name": "",
        "alias": "",
        "street": "",
        "zip_code": "",
        "city": "",
        "total_area_sqm": 0.0,
        "unit_count": 0,
        "units": []
    }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 1. Adresse suchen (z. B. "Straße 12, 12345 Stadt" oder getrennt)
    addr_match = re.search(
        r"(?:Anschrift|Liegenschaft|Adresse|Gebäude|Objekt|Lage)[\s:]*([A-Za-zÄÖÜäöüß\s\.\-]+?\s+\d+[a-zA-Z]?)[,\s]+(\d{5})\s+([A-Za-zÄÖÜäöüß\-\s]+)",
        text,
        re.IGNORECASE
    )
    if addr_match:
        result["street"] = addr_match.group(1).strip()
        result["zip_code"] = addr_match.group(2).strip()
        result["city"] = addr_match.group(3).strip().splitlines()[0].strip()
    else:
        # Separate Suche nach PLZ + Stadt
        zip_city_match = re.search(r"\b(\d{5})\s+([A-Za-zÄÖÜäöüß\-]+(?:\s+[A-Za-zÄÖÜäöüß\-]+)?)", text)
        if zip_city_match:
            result["zip_code"] = zip_city_match.group(1).strip()
            result["city"] = zip_city_match.group(2).strip()

        # Separate Suche nach Straße + Hausnummer
        street_match = re.search(
            r"\b([A-Za-zÄÖÜäöüß\.\-]+(?:straße|str\.|allee|weg|platz|gasse|ring|hang|chaussee|ufer|promenade)?\s+\d+[a-zA-Z]?)\b",
            text,
            re.IGNORECASE
        )
        if street_match:
            result["street"] = street_match.group(1).strip()

    # 2. Name & Alias vorschlagen
    if result["street"]:
        result["property_name"] = f"Liegenschaft {result['street']}"
        # Alias: z. B. Straßenname ohne Hausnummer
        alias_candidate = re.sub(r"\s*\d+[a-zA-Z]?$", "", result["street"]).strip()
        result["alias"] = alias_candidate

    # 3. Gesamtfläche & Wohnungsanzahl
    tot_area_match = re.search(r"(?:Gesamtwohnfläche|Gesamtfläche|Wohnfläche\s+gesamt)[\s:]*([0-9.,]+)\s*(?:m²|qm)", text, re.IGNORECASE)
    if tot_area_match:
        try:
            result["total_area_sqm"] = float(tot_area_match.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass

    unit_cnt_match = re.search(r"(?:Gesamtzahl\s+der\s+Wohnungen|Zahl\s+der\s+Wohnungen|Anzahl\s+Wohnungen|Wohneinheiten)[\s:]*(\d+)", text, re.IGNORECASE)
    if unit_cnt_match:
        try:
            result["unit_count"] = int(unit_cnt_match.group(1))
        except ValueError:
            pass

    # 4. Einzelne Wohnungen erkennen
    # Block-basierte Suche: "Wohnung 1", "WE 01", "Wohnung 2" etc.
    unit_blocks = re.split(r"(?=(?:Wohnung|Wohneinheit|WE\s*\d+|Einheit)\s*\d+)", text, flags=re.IGNORECASE)
    detected_units = []

    for block in unit_blocks:
        u_header = re.search(r"(Wohnung\s*\d+|WE\s*\d+|Wohneinheit\s*\d+|Einheit\s*\d+)", block, re.IGNORECASE)
        if not u_header:
            continue

        unit_name = u_header.group(1).strip().capitalize()
        # Fläche
        area_m = re.search(r"(?:Wohnfläche|Fläche)[\s:]*([0-9.,]+)\s*(?:m²|qm)", block, re.IGNORECASE)
        if not area_m:
            area_m = re.search(r"([0-9.,]+)\s*(?:m²|qm)", block, re.IGNORECASE)
        area = float(area_m.group(1).replace(".", "").replace(",", ".")) if area_m else 65.0

        # Lage / Etage
        floor = "EG"
        floor_m = re.search(r"(?:Lage|Etage|Geschoss|Stockwerk)[\s:]*([^\n,;]+)", block, re.IGNORECASE)
        if floor_m:
            floor = floor_m.group(1).strip()
        elif re.search(r"\b(EG|Erdgeschoss)\b", block, re.IGNORECASE):
            floor = "EG"
        elif re.search(r"\b(\d+)\.\s*(?:OG|Obergeschoss)\b", block, re.IGNORECASE):
            m = re.search(r"\b(\d+)\.\s*(?:OG|Obergeschoss)\b", block, re.IGNORECASE)
            floor = f"{m.group(1)}. OG"
        elif re.search(r"\b(DG|Dachgeschoss)\b", block, re.IGNORECASE):
            floor = "DG"
        elif re.search(r"\b(UG|Keller|Souterrain)\b", block, re.IGNORECASE):
            floor = "UG"

        # Zimmeranzahl
        rooms = 2
        rooms_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:Zimmer|Räume|Wohnräume)", block, re.IGNORECASE)
        if rooms_m:
            try:
                rooms = int(float(rooms_m.group(1).replace(",", ".")))
            except ValueError:
                pass

        # Mietername falls vorhanden
        tenant_sal = "Herr"
        first_name = ""
        last_name = ""
        tenant_m = re.search(r"(?:Mieter|Bewohner|Name)[\s:]*(Frau|Herr)?\s*([A-Za-zÄÖÜäöüß]+)\s+([A-Za-zÄÖÜäöüß]+)", block, re.IGNORECASE)
        if tenant_m:
            if tenant_m.group(1):
                tenant_sal = "Frau" if "frau" in tenant_m.group(1).lower() else "Herr"
            first_name = tenant_m.group(2).strip()
            last_name = tenant_m.group(3).strip()

        # Miete falls vorhanden
        cold_rent = 0.0
        rent_m = re.search(r"(?:Kaltmiete|Grundmiete|Nettokaltmiete)[\s:]*([0-9.,]+)\s*(?:€|EUR)", block, re.IGNORECASE)
        if rent_m:
            try:
                cold_rent = float(rent_m.group(1).replace(".", "").replace(",", "."))
            except ValueError:
                pass

        # Nebenkosten falls vorhanden
        utility_adv = 0.0
        nk_m = re.search(r"(?:Nebenkosten|Betriebskosten|Vorauszahlung|NK)[\s:]*([0-9.,]+)\s*(?:€|EUR)", block, re.IGNORECASE)
        if nk_m:
            try:
                utility_adv = float(nk_m.group(1).replace(".", "").replace(",", "."))
            except ValueError:
                pass

        detected_units.append({
            "unit_number": unit_name,
            "floor": floor,
            "area_sqm": area,
            "rooms": rooms,
            "salutation": tenant_sal,
            "first_name": first_name,
            "last_name": last_name,
            "cold_rent": cold_rent,
            "utility_advance": utility_adv
        })

    result["units"] = detected_units
    if not result["unit_count"]:
        result["unit_count"] = len(detected_units)
    if result["total_area_sqm"] == 0.0 and detected_units:
        result["total_area_sqm"] = sum(u["area_sqm"] for u in detected_units)

    return result

def parse_property_document(text: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Analysiert einen Dokumenttext (Zensus 2022, Mietverträge etc.) zuerst per Ollama und nutzt Heuristik als Fallback."""
    if not model:
        settings = get_all_settings()
        model = settings.get("ollama_model", "llama3")

    prompt = f"""Du bist ein KI-Assistent für deutsche Immobilienverwaltung.
Analysiere den folgenden Dokumenttext (z. B. Zensus 2022 Gebäude- und Wohnungszählung, Teilungserklärung, Mietverträge oder Wohnungsliste).
Extrahiere alle Angaben zur Liegenschaft (Adresse, Gesamtfläche, Wohnungsanzahl) sowie die einzelnen Wohneinheiten (Wohnungsnummer/Bezeichnung, Etage/Lage, Wohnfläche in m², Zimmeranzahl, Mietername falls genannt).

Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt ohne Erklärungen oder Markdown-Fences nach diesem Schema:
{{
  "property_name": "Name oder Anschrift der Liegenschaft (z. B. Wohnanlage Friedrichstraße 42)",
  "alias": "Prägnanter Kurzname (z. B. Friedrichstraße)",
  "street": "Straße und Hausnummer (z. B. Friedrichstraße 42)",
  "zip_code": "5-stellige PLZ (z. B. 10117)",
  "city": "Ort / Stadt (z. B. Berlin)",
  "total_area_sqm": 215.0,
  "unit_count": 3,
  "document_type": "Zensus 2022 / Gebäude- & Wohnungszählung",
  "units": [
    {{
      "unit_number": "Wohnung 1",
      "floor": "EG links",
      "area_sqm": 68.5,
      "rooms": 3,
      "salutation": "Herr oder Frau (falls vorhanden)",
      "first_name": "Vorname (falls im Text vorhanden, sonst leer)",
      "last_name": "Nachname (falls im Text vorhanden, sonst leer)",
      "cold_rent": 0.0,
      "utility_advance": 0.0
    }}
  ]
}}

Dokumenttext:
\"\"\"
{text[:7000]}
\"\"\"
"""

    parsed_result: Optional[Dict[str, Any]] = None

    # Versuch 1: Lokales Ollama Modell
    try:
        response = ollama.chat(
            model=model,
            format="json",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0}
        )
        content = response["message"]["content"].strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        data = json.loads(content)
        if isinstance(data, dict) and data.get("units") and len(data["units"]) > 0:
            parsed_result = data
    except Exception:
        pass

    # Heuristik-Fallback falls Ollama keine Einheiten fand oder fehlschlug
    heuristic_data = heuristic_extract_property_data(text)

    if not parsed_result or not parsed_result.get("units"):
        parsed_result = heuristic_data
        parsed_result["extracted_by"] = "heuristic"
    else:
        parsed_result["extracted_by"] = "ollama"
        # Fehlende Adressfelder aus Heuristik ergänzen falls Ollama etwas übersehen hat
        for field in ["street", "zip_code", "city", "property_name", "alias"]:
            if not parsed_result.get(field) and heuristic_data.get(field):
                parsed_result[field] = heuristic_data[field]

    # Daten säubern & validieren
    units = parsed_result.get("units", [])
    clean_units = []
    for idx, u in enumerate(units, 1):
        try:
            area = float(str(u.get("area_sqm", 0.0)).replace(",", "."))
        except (ValueError, TypeError):
            area = 50.0

        try:
            cr = float(str(u.get("cold_rent", 0.0)).replace(",", "."))
        except (ValueError, TypeError):
            cr = 0.0

        try:
            nk = float(str(u.get("utility_advance", 0.0)).replace(",", "."))
        except (ValueError, TypeError):
            nk = 0.0

        u_num = str(u.get("unit_number") or f"Wohnung {idx}").strip()
        floor = str(u.get("floor") or "EG").strip()
        first_name = str(u.get("first_name") or "").strip()
        last_name = str(u.get("last_name") or "").strip()
        sal = str(u.get("salutation") or "Herr").strip()
        if sal not in ["Herr", "Frau"]:
            sal = "Frau" if any(fn in first_name.lower() for fn in ["anna", "maria", "sabine", "laura", "julia"]) else "Herr"

        clean_units.append({
            "unit_number": u_num,
            "floor": floor,
            "area_sqm": round(area, 2),
            "rooms": int(u.get("rooms") or 2),
            "salutation": sal,
            "first_name": first_name,
            "last_name": last_name,
            "cold_rent": round(cr, 2),
            "utility_advance": round(nk, 2)
        })

    parsed_result["units"] = clean_units
    if clean_units:
        calc_total = sum(u["area_sqm"] for u in clean_units)
        if not parsed_result.get("total_area_sqm") or parsed_result.get("total_area_sqm") == 0:
            parsed_result["total_area_sqm"] = round(calc_total, 2)
        parsed_result["unit_count"] = len(clean_units)

    if not parsed_result.get("property_name"):
        if parsed_result.get("street"):
            parsed_result["property_name"] = f"Liegenschaft {parsed_result['street']}"
        else:
            parsed_result["property_name"] = "Neue Liegenschaft (aus Dokument)"

    if not parsed_result.get("alias") and parsed_result.get("street"):
        parsed_result["alias"] = re.sub(r"\s*\d+[a-zA-Z]?$", "", parsed_result["street"]).strip()

    return parsed_result
