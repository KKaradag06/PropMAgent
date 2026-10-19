# PropMAgent

PropMAgent ist ein lokaler, datenschutzkonformer KI-Assistent fuer private Vermieter und Hausverwaltungen. Das System verbindet deterministische Rechen- und Datenbanklogik (Python und SQLite) mit einem lokalen Open-Source-Sprachmodell (Ollama / Llama 3) sowie einem Web-Dashboard auf Basis von Streamlit.

---

## Kernmerkmale

- **Vollstaendiger lokaler Datenschutz:** Alle Mieterdaten, Vertraege und Betriebskostenabrechnungen werden in einer lokalen SQLite-Datenbank auf dem eigenen Rechner gespeichert. Keine Datenuebertragung an externe Cloud-Dienste.
- **Deterministische Finanzberechnungen:** Kostenumlagen (nach Flaeche, Einheiten oder Direktzuordnung) und Verrechnungen von Vorauszahlungen werden mathematisch exakt ueber Python ausgefuehrt. Das Sprachmodell uebernimmt ausschliesslich Textverstaendnis, Intent-Erkennung und Formulierung.
- **Universelle Brieferstellung:** Dynamisches Verfassen formeller Vermieterschreiben (Mieterhoehungen nach Paragraph 558 BGB, Anpassungen der Betriebskostenvorauszahlung nach Paragraph 560 Abs. 4 BGB, Handwerkerankuendigungen, Mahnungen, Mitteilungen geaenderter Bankverbindungen).
- **Export in PDF und DOCX:** Gleichzeitige Ausgabe druckfertiger Dokumente (PDF) sowie editierbarer Textdokumente (DOCX fuer Microsoft Word, LibreOffice Writer und OpenOffice).
- **Keine API- oder Tokenkosten:** Vollstaendiger Betrieb ueber lokale Sprachmodelle via Ollama.

---

## Systemarchitektur

```text
+-------------------------------------------------------------+
| 1. Praesentationsebene (Streamlit Dashboard)                |
|    - Mieterverwaltung (CRUD-Formulare und Uebersichten)     |
|    - Betriebskosten- und Ausgabenuebersicht                 |
|    - Interaktiver Chat-Assistent und Dokumenten-Download    |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| 2. Agenten- und Logikschicht (Python)                       |
|    - Intent-Klassifizierung und strukturierte Aktionswahl   |
|    - Dynamische Textgenerierung ueber Ollama (Llama 3)      |
|    - Exakte Betriebskostenberechnung (calculator.py)        |
+------------------------------+------------------------------+
                               |
               +---------------+---------------+
               v                               v
+-----------------------------+ +-----------------------------+
| 3. Datenspeicherung         | | 4. Dokumentengenerierung    |
|    - Lokale SQLite-DB       | |    - ReportLab (PDF)        |
|    - Relationales Schema    | |    - python-docx (DOCX/ODT) |
+-----------------------------+ +-----------------------------+
```

---

## Voraussetzungen

- Python 3.10 oder neuer
- Ollama mit lokal geladenem Modell (z. B. Llama 3):
  ```bash
  ollama run llama3
  ```

---

## Installation und Inbetriebnahme

### 1. Repository klonen und Verzeichnis wechseln
```bash
git clone https://github.com/KKaradag06/PropMAgent.git
cd PropMAgent
```

### 2. Virtuelle Umgebung erstellen und aktivieren
```bash
python -m venv venv
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate
```

### 3. Abhaengigkeiten installieren
```bash
pip install -r requirements.txt
```

### 4. Datenbank initialisieren (inklusive Beispieldaten)
```bash
python database/seed_data.py
```

### 5. Anwendung starten
```bash
streamlit run app.py
```

Die Benutzeroberflaeche oeffnet sich anschliessend im Webbrowser unter `http://localhost:8501`.

---

## Projektstruktur

```text
PropMAgent/
|-- .gitignore               # Ausschluss von lokalen Datenbanken und Dokumenten
|-- README.md                # Projektdokumentation
|-- requirements.txt         # Benoetigte Python-Pakete
|-- app.py                   # Streamlit Web-Anwendung und UI
|-- agent/
|   |-- __init__.py
|   |-- calculator.py        # Deterministische Nebenkostenberechnung
|   |-- core.py              # Agentenlogik, Intent-Erkennung, Ollama-Anbindung
|   |-- tools.py             # Datenbank-Abfragen und Mieter-CRUD-Funktionen
|-- database/
|   |-- __init__.py
|   |-- db.py                # SQLite-Verbindungshandler
|   |-- schema.sql           # Tabellenschema (Properties, Units, Tenants, Expenses, Payments)
|   |-- seed_data.py         # Beispieldatensatz zur Demonstration
|-- reports/
|   |-- __init__.py
|   |-- docx_generator.py    # Generierung editierbarer Word-Dokumente
|   |-- pdf_generator.py     # Generierung von PDF-Dokumenten nach DIN-Standard
+-- data/                    # Lokales Verzeichnis fuer SQLite-Datenbank und Exporte (Git-ignoriert)
```
