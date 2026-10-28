# PropMAgent

**PropMAgent** ist ein 100% lokaler, datenschutzkonformer KI-Assistent und Verwaltungsmanager für private Vermieter und Hausverwaltungen. Das System verbindet deterministische Rechen- und Datenbanklogik (Python und SQLite) mit einem lokalen Open-Source-Sprachmodell (Ollama / Llama 3) sowie einem modernen Web-Dashboard auf Basis von Streamlit.

---

## 🌟 Kernmerkmale

- 🔒 **100% Lokaler Datenschutz:** Alle Mieterdaten, Verträge, Liegenschaftsdaten und Betriebskostenabrechnungen werden in einer lokalen SQLite-Datenbank auf deinem Rechner gespeichert. Zu keinem Zeitpunkt verlassen Daten oder Dokumente dein Gerät.
- 🏠 **Zentrale Startseite & Dashboard:**
  - **Persönliche Begrüßung:** Herzliches Willkommen mit dem in den Einstellungen hinterlegten Namen des Vermieters oder der Hausverwaltung.
  - **Live-Portfolio-Kennzahlen:** Liegenschaften, Wohneinheiten, Vermietungsquote, aktive Mieter sowie monatliche Soll-Mieteinnahmen auf einen Blick.
  - **Schnellstart-Aktionen:** Direkteinstieg in KI-Schreiben, Liegenschaftsverwaltung, Betriebskostenabrechnung und Dokument-Import.
  - **Liegenschafts-Portfolio:** Kompakte Übersicht aller Immobilien mit Baujahr, Heizungsart, Belegung und 1-Klick-Direktlink in die Detailansicht.
  - **Klickbares Logo:** 1-Klick-Rückkehr zur Startseite durch Klick auf `🏢 PropMAgent` in der Seitenleiste.
- 👤🏢 **Duale Betriebsmodi (Privater Vermieter & Hausverwaltung):**
  - **Privater Vermieter:** Briefe und Dokumente werden persönlich aus Vermietersicht formuliert (keine Hausverwaltungsfloskeln, Kennzeichnung mit *(Vermieter)*).
  - **Hausverwaltung:** Professioneller Agentur-/Verwaltungsauftritt mit Firmenname, Ansprechpartner und Geschäftskonto.
- 🏢 **Liegenschafts- & Einheitenverwaltung (Multi-Level-Übersicht):**
  - Strukturierte Verwaltung mit prägnanten Kurznamen (Alias) und Adressen.
  - Gebäude-Stammdaten: **Baujahr**, **Heizungsart** (*Zentralheizung, Etagenheizung, Fernwärme, Wärmepumpe etc.*) und **Energieträger** (*Erdgas, Heizöl, Fernwärme, Strom / Wärmepumpe, Holzpellets*).
  - Wohneinheiten mit **Wohnfläche (m²)**, **Zimmeranzahl** und **Anzahl der lebenden Personen**.
  - **Liegenschaften sicher löschen:** Kaskadierende Löschung mit Sicherheitsbestätigung (entfernt Liegenschaft, Einheiten, Mieter, Zahlungen und Betriebskosten ohne Datenreste).
- 🛡️ **Schutz vor Datenverlust & Sofort-Feedback:**
  - **Ungespeicherte Änderungen (Dirty-Form-Tracking):** Sobald Eingaben geändert werden, signalisiert ein roter Punkt (`🔴`) im Menü und auf den Reitern den ungespeicherten Zustand.
  - **Intelligenter Navigations-Schutz:** Beim Verlassen eines Bereichs mit ungespeicherten Daten warnt ein Dialog mit 3 Optionen: *Änderungen speichern*, *Änderungen verwerfen* oder *Weiter bearbeiten*.
  - **Toast-Benachrichtigungen:** Kurzes, klares visuelles Feedback nach jedem Speichern, Bearbeiten oder Löschen in allen Bereichen.
- 👥 **Gemeinschaftliche Mietverträge (Mehrere Mieter pro Wohnung):**
  - Vollständige Unterstützung mehrerer Mieter auf demselben Mietvertrag (z. B. Ehepaare, eingetragene Lebenspartner oder Wohngemeinschaften).
  - Automatische, DIN-konforme Zusammenführung von Namen und mehrteiligen Briefanreden (*"Sehr geehrter Herr Mustermann, sehr geehrte Frau Mustermann"*).
  - Volltext- und Namenssuche über Haupt- und Mitmieter im Chat und in Dropdown-Menüs.
- 📄 **Dokumenten-Import & Auto-Fill (z. B. Zensus 2022 Gebäude- & Wohnungszählung):**
  - Dokumente (z. B. Zensus-2022-Erfassungsbögen, Teilungserklärungen oder Wohnungslisten) einfach als PDF per Drag & Drop hochladen.
  - Hybride Extraktion: Lokale KI-Analyse via Ollama mit robustem Heuristik-Fallback.
  - Automatische Erfassung von Liegenschaftsadresse, Baujahr, Heizungsart, Energieträger sowie aller Einheiten (Wohnungsnummer, Etage, m², Zimmer, Personenzahl, Mieter).
  - Interaktive Prüf- und Korrekturmaske (`st.data_editor`) vor der Übernahme in die Datenbank.
- ✍️ **Intelligenter KI-Assistent & Schriftverkehr:**
  - Vorgefertigte DIN-konforme Schnellaktionen und freier Chat:
    - Kaltmieterhöhung (§ 558 BGB) mit automatischer Berechnung der gesetzlichen Überlegungs- und Wirksamkeitsfristen.
    - Anpassung der Betriebskostenvorauszahlung (§ 560 Abs. 4 BGB).
    - Zahlungserinnerungen & Mahnungen mit exakter Rückstands- und Fristangabe.
    - Abmahnungen wegen Zahlungsverzugs (§ 543 Abs. 2 Nr. 3 BGB) oder Hausordnungsverstößen.
    - Miet- und Mietschuldenfreiheitsbescheinigungen.
    - Handwerker- und Modernisierungsankündigungen.
    - Rundschreiben an alle Mieterinnen und Mieter einer Liegenschaft.
- 📄 **Export nach DIN 5008:2020 Form B:**
  - Zeitgleicher Download als druckfertiges **PDF** und editierbares **Word DOCX** (voll kompatibel mit Microsoft Word, LibreOffice Writer und OpenOffice).
  - Visuelle Download-Bestätigung (grünes Häkchen).
- 📊 **Betriebskosten & Finanzen:**
  - **Objektspezifische Liegenschaftsauswahl:** Filterung der gesamten Abrechnungs- und Kostenübersicht nach einzelnen Liegenschaften oder Gesamtübersicht über alle Objekte.
  - Verwaltung mehrjähriger Betriebskostenabrechnungen (Vorjahre, aktuelles Jahr).
  - Erfassung und Bearbeitung von Kostenarten mit flexiblen Umlageschlüsseln (nach Wohnfläche m², Personen oder Direkterfassung).
  - Kopierfunktion für Vorjahresdaten als Basis für neue Abrechnungsjahre (auch liegenschaftsbezogen).
  - Tabellarische Jahresabrechnungen und 1-Klick-Generierung von Einzelabrechnungs-PDFs für alle Mieter.
- 💾 **Datenbank-Backup & Wiederherstellung (Export & Import):**
  - **1-Klick-Download:** Vollständige Sicherung der lokalen SQLite-Datenbank (`prop_management.db`) inklusive aller Liegenschaften, Einheiten, Mieter, Zahlungen und Belege.
  - **Sichere Wiederherstellung:** Hochladen und Einspielen einer zuvor aus PropMAgent exportierten `.db`-Datei.
  - **Mehrstufige Schutzprüfung:** Automatische Validierung des SQLite-Headers, Integritätsprüfung (`PRAGMA integrity_check`) und Schema-Validierung (Abweisung fremder Dateien), Inhalts-Voransicht, Sicherheitsbestätigung sowie ein automatisches Sicherheitsbackup der aktuellen Datenbank vor dem Überschreiben.

---

## 🏛️ Systemarchitektur

```text
+-----------------------------------------------------------------------------------+
|                            Streamlit Web-Dashboard                                |
|  - Schnellnavigation über interaktive Menükarten                                 |
|  - Multi-Level Liegenschafts- & Einheitenverwaltung (inkl. Baujahr, Heizung)      |
|  - Dokumenten-Analyse & Auto-Fill (Zensus 2022, Mietverträge)                     |
|  - KI-Schriftverkehr mit Vorlagen & Live-Chat                                     |
|  - Betriebskosten-Management & Jahresabrechnungen                                 |
|  - Zentrale Einstellungen (Vermieterdaten, Bankverbindung, Modellwahl)            |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                         Agenten- & Logikschicht (Python)                          |
|  - Intent-Klassifizierung & strukturierte Aktionswahl (core.py)                   |
|  - Dokumentenextraktion & OCR-Parsing (doc_parser.py)                             |
|  - Deterministische Nebenkostenberechnung nach BetrKV (calculator.py)             |
|  - Datenbank-Tools für Liegenschaften, Einheiten, Mitmieter (tools.py)            |
|  - Lokales Sprachmodell via Ollama (llama3 / mistral)                             |
+-----------------------------------------+-----------------------------------------+
                                          |
                   +----------------------+----------------------+
                   v                                             v
+--------------------------------------+      +-------------------------------------+
|        Lokale Datenspeicherung       |      |         Dokumentenausgabe           |
|  - SQLite (data/prop_management.db)  |      |  - ReportLab: DIN 5008 PDF          |
|  - Automatische Schema-Migrationen   |      |  - python-docx: Word / DOCX / ODT   |
|  - Konfiguration (data/settings.json)|      +-------------------------------------+
+--------------------------------------+
```

---

## ⚙️ Voraussetzungen

- **Python 3.10** oder neuer (getestet bis Python 3.14)
- **Ollama** für lokale Modellausführung (z. B. Llama 3):
  ```bash
  ollama run llama3
  ```

---

## 🚀 Installation & Start

### 🟢 Schnellstart für Vermieter & Anwender (Ohne Programmierkenntnisse)

Für die Nutzung von PropMAgent müssen Sie **kein einziges Terminal-Kommando eingeben**. Befolgen Sie einfach diese 3 Schritte:

1. **Python installieren** (falls noch nicht auf Ihrem PC vorhanden):
   - Laden Sie [Python (Version 3.10 oder neuer)](https://www.python.org/downloads/) herunter und starten Sie die Installation.
   - ⚠️ **Sehr wichtig:** Setzen Sie ganz zu Beginn des Installationsfensters unten den Haken bei:  
     **`☑ Add python.exe to PATH`** *(oder "Python zu Umgebungsvariablen hinzufügen")*.
2. **Ollama installieren** (für das 100% lokale KI-Sprachmodell):
   - Laden Sie das kostenlose Installationsprogramm von [ollama.com/download](https://ollama.com/download) herunter und führen Sie es aus.
   - Ollama läuft anschließend vollautomatisch und datenschutzkonform im Hintergrund auf Ihrem Rechner.
3. **PropMAgent starten (1 Klick)**:
   - Laden Sie dieses Repository herunter (oben auf den grünen Button **`Code`** ➔ **`Download ZIP`** klicken und entpacken).
   - Machen Sie einfach einen **Doppelklick auf `PropMAgent_Starten.bat`** (oder `start.bat`).
   - *Das Skript richtet alles automatisch beim ersten Mal ein und öffnet das Web-Dashboard direkt in Ihrem Browser!*
   - 💡 **Modell-Tipp:** Wenn Sie noch kein KI-Modell heruntergeladen haben, können Sie **Llama 3** direkt in PropMAgent unter **`Einstellungen` ➔ `KI & Sprachmodell (Ollama)` mit einem Klick auf `Modell jetzt herunterladen`** installieren – ganz ohne Terminal!

---

<details>
<summary><b>🛠️ Für Entwickler & manuelle Installation (Terminal / Konsole)</b></summary>
<br>

#### 1. Repository klonen
```bash
git clone https://github.com/KKaradag06/PropMAgent.git
cd PropMAgent
```

#### 2. Virtuelle Umgebung erstellen und aktivieren
```bash
# Windows (PowerShell):
python -m venv venv
venv\Scripts\activate.bat   # oder: venv\Scripts\Activate.ps1

# Linux / macOS:
python3 -m venv venv
source venv/bin/activate
```

#### 3. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

#### 4. Datenbank initialisieren (optional mit Beispieldaten)
```bash
python database/seed_data.py
```

#### 5. Lokales Modell vorab laden (optional)
```bash
ollama run llama3
```

#### 6. Anwendung starten
```bash
streamlit run app.py
```

Die Anwendung öffnet sich anschließend automatisch im Browser unter `http://localhost:8501`.

</details>

---

## 📁 Projektstruktur

```text
PropMAgent/
├── PropMAgent_Starten.bat   # 1-Klick-Starter für Windows (richtet alles automatisch ein)
├── start.bat                # Kurz-Alias für den 1-Klick-Start
├── app.py                   # Streamlit Hauptanwendung, UI-Komponenten & Routing
├── README.md                # Projektdokumentation
├── requirements.txt         # Python-Abhängigkeiten
├── agent/
│   ├── calculator.py        # Deterministische Nebenkostenberechnung
│   ├── core.py              # KI-Prompting, Intent-Erkennung, Vorlagengenerierung
│   ├── doc_parser.py        # PDF-Extraktion & Analyse für Zensus-/Wohnungslisten
│   └── tools.py             # Datenbankoperationen für Liegenschaften, Einheiten, Mieter, Finanzen
├── database/
│   ├── db.py                # SQLite-Verbindungshandler & Schema-Migrationen
│   ├── schema.sql           # Tabellenschema (Properties, Units, Tenants, Expenses)
│   ├── seed_data.py         # Beispieldatensatz zur Demonstration
│   └── settings.py          # Einstellungsverwaltung (Vermieterdaten, Modellauswahl)
├── reports/
│   ├── docx_generator.py    # Erzeugung von Word-Dokumenten nach DIN 5008 Form B
│   └── pdf_generator.py     # Erzeugung von PDF-Dokumenten nach DIN 5008 Form B
└── data/                    # Lokale Datenbank (prop_management.db), automatische Backups & Exporte (Git-ignoriert)
```

---

## ⚖️ Lizenz & Datenschutz

PropMAgent wurde mit höchstem Anspruch an Datensicherheit für Vermieter entwickelt. Alle Verarbeitungen finden **vollständig offline auf deinem lokalen Computer** statt. Es werden weder Dokumente noch personenbezogene Mieterdaten an externe Cloud-Anbieter übermittelt.
