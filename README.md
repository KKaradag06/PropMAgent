# PropMAgent 🏢🤖

**PropMAgent** ist ein lokaler, datenschutzfreundlicher KI-Agent für private Vermieter und Immobilienverwalter.
Das System kombiniert deterministische Rechen- und Datenbanklogik (Python & SQLite) mit lokaler KI (Ollama / Llama 3) und einem interaktiven Web-Dashboard (Streamlit).

---

## 🌟 Highlights

- **100% Lokaler Datenschutz:** Alle Mieterdaten, Verträge und Abrechnungen verbleiben in einer lokalen SQLite-Datenbank (`data/prop_management.db`) auf deinem Rechner.
- **Keine KI-Rechenfehler:** Finanzmathematik (Kostenumlage nach $m^2$, Abrechnungsguthaben / Nachzahlungen) wird deterministisch in Python berechnet. Das Sprachmodell übernimmt Formulierung und Intent-Erkennung.
- **Druckfertige PDFs:** Generierung formeller Anschreiben und Nebenkostenabrechnungen nach DIN-Standard per Mausklick.
- **Keine API-Kosten:** Nutzt lokale Open-Source LLMs über Ollama.

---

## 🏗️ Architektur

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Streamlit Dashboard (app.py)                             │
│    - Übersicht Tabellen (Mieter, Wohnungen, Belege)         │
│    - Chat-Assistent & PDF-Download                          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Agent & Berechnungslogik (agent/)                        │
│    - core.py: Ollama / Llama 3 Absichtserkennung            │
│    - calculator.py: Exakte Berechnung nach Umlageschlüsseln │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌─────────────────────────────┐ ┌─────────────────────────────┐
│ 3. Lokale SQLite-Datenbank  │ │ 4. PDF-Engine (ReportLab)   │
│    data/prop_management.db  │ │    Druckfertige Abrechnung  │
└─────────────────────────────┘ └─────────────────────────────┘
```

---

## 🚀 Schnellstart

### 1. Voraussetzungen
- **Python 3.10+**
- **Ollama** ([ollama.com](https://ollama.com)) mit geladenem Modell:
  ```powershell
  ollama run llama3
  ```

### 2. Installation
```powershell
# Virtuelle Umgebung (optional, empfohlen)
python -m venv venv
venv\Scripts\activate

# Pakete installieren
pip install -r requirements.txt
```

### 3. Datenbank initialisieren (mit Beispieldaten)
```powershell
python database/seed_data.py
```

### 4. Dashboard starten
```powershell
streamlit run app.py
```
Das Dashboard öffnet sich automatisch in deinem Browser unter `http://localhost:8501`.
