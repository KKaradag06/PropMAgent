import os
import streamlit as st
import pandas as pd
from database.db import init_db, query_db
from database.seed_data import seed
from agent.core import handle_agent_request
from agent.tools import get_all_tenants, get_expenses_summary, create_utility_statement_for_tenant

# Streamlit Page Config
st.set_page_config(
    page_title="PropMAgent - Smarte Immobilienverwaltung",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Datenbank initialisieren & ggf. Beispieldaten laden
init_db()
existing_props = query_db("SELECT COUNT(*) as cnt FROM properties;")
if not existing_props or existing_props[0]["cnt"] == 0:
    seed()

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .stChatMessage {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("🏢 PropMAgent")
    st.caption("Lokaler KI-Immobilienassistent")
    st.markdown("---")
    
    menu = st.radio(
        "Navigation",
        ["💬 KI-Assistent & Abrechnung", "👥 Mieter & Einheiten", "📊 Betriebskosten & Finanzen"],
        index=0
    )
    
    st.markdown("---")
    st.subheader("⚙️ Einstellungen")
    model_name = st.selectbox("Ollama Modell", ["llama3", "mistral", "llama3.1"], index=0)
    st.info("🔒 **100% Lokal:** Alle Daten und KI-Anfragen laufen vollständig auf deinem PC.")

# TAB 1: Chat & Nebenkosten-Erstellung
if menu == "💬 KI-Assistent & Abrechnung":
    st.header("💬 Intelligenter Verwaltungsassistent")
    st.write("Erstelle Nebenkostenabrechnungen, stelle Fragen zu Mietern oder lass dir Auswertungen anzeigen.")

    # Schnellaktionen
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📄 Abrechnung Schmidt 2025 erstellen", use_container_width=True):
            st.session_state.quick_prompt = "Erstelle die Nebenkostenabrechnung 2025 für Mieter Schmidt"
    with col2:
        if st.button("📄 Abrechnung Mustermann 2025 erstellen", use_container_width=True):
            st.session_state.quick_prompt = "Erstelle die Nebenkostenabrechnung 2025 für Mieter Mustermann"
    with col3:
        if st.button("📋 Alle aktuellen Mieter auflisten", use_container_width=True):
            st.session_state.quick_prompt = "Welche Mieter wohnen aktuell im Objekt?"

    # Chat-Historie im Session-State
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hallo! Ich bin dein lokaler PropMAgent. Wie kann ich dich heute unterstützen? Du kannst mich z. B. bitten: *'Erstelle die Nebenkostenabrechnung 2025 für Mieter Schmidt'*."
            }
        ]

    # Nachrichten anzeigen
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "pdf_path" in msg and os.path.exists(msg["pdf_path"]):
                with open(msg["pdf_path"], "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="📥 Fertiges PDF herunterladen",
                    data=pdf_bytes,
                    file_name=os.path.basename(msg["pdf_path"]),
                    mime="application/pdf",
                    key=f"dl_{os.path.basename(msg['pdf_path'])}"
                )

    # Chat-Eingabe
    prompt = st.chat_input("Nachricht oder Befehl eingeben...")
    if "quick_prompt" in st.session_state and st.session_state.quick_prompt:
        prompt = st.session_state.quick_prompt
        del st.session_state.quick_prompt

    if prompt:
        # Nutzereingabe anzeigen
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Agent ausführen
        with st.chat_message("assistant"):
            with st.spinner("Analysiere Anfrage und berechne Daten..."):
                response = handle_agent_request(prompt, model=model_name)
                st.markdown(response["message"])

                assistant_msg = {"role": "assistant", "content": response["message"]}
                if "pdf_path" in response and os.path.exists(response["pdf_path"]):
                    assistant_msg["pdf_path"] = response["pdf_path"]
                    with open(response["pdf_path"], "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        label="📥 Fertiges PDF herunterladen",
                        data=pdf_bytes,
                        file_name=os.path.basename(response["pdf_path"]),
                        mime="application/pdf",
                        key=f"dl_new_{os.path.basename(response['pdf_path'])}"
                    )
                st.session_state.messages.append(assistant_msg)

# TAB 2: Mieter & Einheiten
elif menu == "👥 Mieter & Einheiten":
    st.header("👥 Mieter- und Einheitenübersicht")
    tenants = get_all_tenants()
    
    if tenants:
        df = pd.DataFrame(tenants)
        # Schönere Spaltenbezeichnungen
        df_display = df.rename(columns={
            "tenant_id": "ID",
            "first_name": "Vorname",
            "last_name": "Nachname",
            "unit_number": "Wohneinheit",
            "area_sqm": "Fläche (m²)",
            "cold_rent": "Kaltmiete (€)",
            "utility_advance": "NK-Vorauszahlung (€)",
            "property_name": "Objekt",
            "phone": "Telefon",
            "email": "E-Mail"
        })
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Schnell-Abrechnungsgenerator pro Mieter
        st.subheader("⚡ 1-Klick Abrechnungs-Erstellung")
        col_sel, col_yr, col_btn = st.columns([3, 1, 2])
        with col_sel:
            tenant_names = {f"{t['first_name']} {t['last_name']} ({t['unit_number']})": t["tenant_id"] for t in tenants}
            selected_t_name = st.selectbox("Mieter auswählen", list(tenant_names.keys()))
        with col_yr:
            year_val = st.number_input("Abrechnungsjahr", min_value=2020, max_value=2030, value=2025)
        with col_btn:
            st.write("")
            st.write("")
            if st.button("📄 PDF jetzt generieren", type="primary", use_container_width=True):
                t_id = tenant_names[selected_t_name]
                bill = create_utility_statement_for_tenant(t_id, int(year_val))
                st.success(f"Abrechnung für {selected_t_name} erfolgreich erstellt!")
                with open(bill["pdf_path"], "rb") as f:
                    pdf_data = f.read()
                st.download_button(
                    label=f"📥 Download {os.path.basename(bill['pdf_path'])}",
                    data=pdf_data,
                    file_name=os.path.basename(bill["pdf_path"]),
                    mime="application/pdf"
                )
    else:
        st.info("Keine Mieterdaten vorhanden.")

# TAB 3: Betriebskosten & Finanzen
elif menu == "📊 Betriebskosten & Finanzen":
    st.header("📊 Betriebskosten für das Abrechnungsjahr 2025")
    expenses = get_expenses_summary(2025)
    
    if expenses:
        total_sum = sum(e["amount"] for e in expenses)
        col1, col2 = st.columns(2)
        col1.metric("Gesamte Betriebskosten (2025)", f"{total_sum:,.2f} €")
        col2.metric("Anzahl Positionen", len(expenses))

        st.markdown("---")
        df_exp = pd.DataFrame(expenses)
        df_exp_display = df_exp.rename(columns={
            "category": "Kostenart",
            "description": "Details / Beleg",
            "amount": "Betrag (€)",
            "allocation_key": "Umlageschlüssel",
            "receipt_date": "Datum",
            "property_name": "Objekt"
        })
        st.dataframe(df_exp_display, use_container_width=True, hide_index=True)
    else:
        st.info("Keine Betriebskosten für 2025 erfasst.")
