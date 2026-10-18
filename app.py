from datetime import datetime, date
import os
import streamlit as st
import pandas as pd
from database.db import init_db, query_db
from database.seed_data import seed
from agent.core import handle_agent_request
from agent.tools import (
    get_all_tenants, 
    get_all_units,
    add_new_tenant,
    update_tenant,
    delete_tenant,
    get_expenses_summary, 
    create_utility_statement_for_tenant
)

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
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            has_pdf = "pdf_path" in msg and os.path.exists(msg["pdf_path"])
            has_docx = "docx_path" in msg and os.path.exists(msg["docx_path"])
            if has_pdf or has_docx:
                col_dl1, col_dl2 = st.columns(2)
                if has_pdf:
                    with col_dl1:
                        with open(msg["pdf_path"], "rb") as f:
                            pdf_bytes = f.read()
                        st.download_button(
                            label="📥 PDF herunterladen",
                            data=pdf_bytes,
                            file_name=os.path.basename(msg["pdf_path"]),
                            mime="application/pdf",
                            key=f"dl_pdf_{idx}_{os.path.basename(msg['pdf_path'])}"
                        )
                if has_docx:
                    with col_dl2:
                        with open(msg["docx_path"], "rb") as f:
                            docx_bytes = f.read()
                        st.download_button(
                            label="📝 Word/ODT (DOCX) herunterladen",
                            data=docx_bytes,
                            file_name=os.path.basename(msg["docx_path"]),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_docx_{idx}_{os.path.basename(msg['docx_path'])}"
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
            with st.spinner("Analysiere Anfrage und erstelle Dokument..."):
                response = handle_agent_request(prompt, model=model_name)
                st.markdown(response["message"])

                assistant_msg = {"role": "assistant", "content": response["message"]}
                has_pdf = "pdf_path" in response and os.path.exists(response["pdf_path"])
                has_docx = "docx_path" in response and os.path.exists(response["docx_path"])

                if has_pdf or has_docx:
                    col_dl1, col_dl2 = st.columns(2)
                    if has_pdf:
                        assistant_msg["pdf_path"] = response["pdf_path"]
                        with col_dl1:
                            with open(response["pdf_path"], "rb") as f:
                                pdf_bytes = f.read()
                            st.download_button(
                                label="📥 PDF herunterladen",
                                data=pdf_bytes,
                                file_name=os.path.basename(response["pdf_path"]),
                                mime="application/pdf",
                                key=f"dl_new_pdf_{os.path.basename(response['pdf_path'])}"
                            )
                    if has_docx:
                        assistant_msg["docx_path"] = response["docx_path"]
                        with col_dl2:
                            with open(response["docx_path"], "rb") as f:
                                docx_bytes = f.read()
                            st.download_button(
                                label="📝 Word/ODT (DOCX) herunterladen",
                                data=docx_bytes,
                                file_name=os.path.basename(response["docx_path"]),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_new_docx_{os.path.basename(response['docx_path'])}"
                            )
                st.session_state.messages.append(assistant_msg)

# TAB 2: Mieter & Einheiten
elif menu == "👥 Mieter & Einheiten":
    st.header("👥 Mieter- und Einheitenverwaltung")
    
    tenants = get_all_tenants()
    all_units = get_all_units()
    
    tab_list, tab_add, tab_edit = st.tabs([
        "📋 Mieterübersicht & Abrechnung", 
        "➕ Neuen Mieter anlegen", 
        "✏️ Mieterdaten bearbeiten"
    ])
    
    with tab_list:
        if tenants:
            df = pd.DataFrame(tenants)
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
                "email": "E-Mail",
                "lease_start": "Mietbeginn",
                "lease_end": "Mietende"
            })
            cols_to_show = [c for c in ["ID", "Vorname", "Nachname", "Wohneinheit", "Fläche (m²)", "Kaltmiete (€)", "NK-Vorauszahlung (€)", "Mietbeginn", "Telefon", "E-Mail"] if c in df_display.columns]
            st.dataframe(df_display[cols_to_show], use_container_width=True, hide_index=True)
            
            # Schnell-Abrechnungsgenerator pro Mieter
            st.markdown("---")
            st.subheader("⚡ 1-Klick Abrechnungs-Erstellung")
            col_sel, col_yr, col_btn = st.columns([3, 1, 2])
            with col_sel:
                tenant_names = {f"{t['first_name']} {t['last_name']} ({t['unit_number']})": t["tenant_id"] for t in tenants}
                selected_t_name = st.selectbox("Mieter auswählen", list(tenant_names.keys()), key="bill_tenant_select")
            with col_yr:
                year_val = st.number_input("Abrechnungsjahr", min_value=2020, max_value=2030, value=2025, key="bill_year_input")
            with col_btn:
                st.write("")
                st.write("")
                if st.button("📄 PDF jetzt generieren", type="primary", use_container_width=True, key="btn_gen_pdf"):
                    t_id = tenant_names[selected_t_name]
                    bill = create_utility_statement_for_tenant(t_id, int(year_val))
                    st.success(f"Abrechnung für {selected_t_name} erfolgreich erstellt!")
                    with open(bill["pdf_path"], "rb") as f:
                        pdf_data = f.read()
                    st.download_button(
                        label=f"📥 Download {os.path.basename(bill['pdf_path'])}",
                        data=pdf_data,
                        file_name=os.path.basename(bill["pdf_path"]),
                        mime="application/pdf",
                        key="btn_download_bill"
                    )
        else:
            st.info("Aktuell sind noch keine Mieter erfasst. Nutze den Reiter '➕ Neuen Mieter anlegen', um den ersten Mieter hinzuzufügen.")

    with tab_add:
        st.subheader("➕ Neuen Mieter manuell anlegen")
        st.caption("Pflichtfelder sind nur Vor- und Nachname. Alle anderen Felder können frei bleiben oder später ergänzt werden.")
        
        with st.form("form_add_tenant", clear_on_submit=True):
            col_fn, col_ln = st.columns(2)
            with col_fn:
                new_fn = st.text_input("Vorname *", placeholder="z. B. Sabine")
            with col_ln:
                new_ln = st.text_input("Nachname *", placeholder="z. B. Meier")
                
            col_u, col_cr, col_nk = st.columns(3)
            with col_u:
                unit_options = {f"{u['unit_number']} ({u['area_sqm']:.0f} m² - {u['property_name']})": u["unit_id"] for u in all_units} if all_units else {"Standard": 1}
                selected_unit_label = st.selectbox("Wohneinheit", list(unit_options.keys()))
                selected_unit_id = unit_options[selected_unit_label]
            with col_cr:
                new_cr = st.number_input("Kaltmiete (€)", min_value=0.0, value=0.0, step=50.0)
            with col_nk:
                new_nk = st.number_input("NK-Vorauszahlung (€)", min_value=0.0, value=0.0, step=10.0)
                
            col_start, col_end = st.columns(2)
            with col_start:
                new_start = st.date_input("Mietbeginn", value=date.today())
            with col_end:
                new_end = st.text_input("Mietende (optional)", placeholder="z. B. 2026-12-31 oder leer lassen")
                
            col_em, col_ph = st.columns(2)
            with col_em:
                new_em = st.text_input("E-Mail-Adresse (optional)", placeholder="mieter@beispiel.de")
            with col_ph:
                new_ph = st.text_input("Telefonnummer (optional)", placeholder="+49 170 1234567")
                
            submitted = st.form_submit_button("💾 Mieter speichern", type="primary", use_container_width=True)
            if submitted:
                if not new_fn.strip() or not new_ln.strip():
                    st.error("⚠️ Bitte mindestens Vorname und Nachname ausfüllen!")
                else:
                    add_new_tenant(
                        first_name=new_fn.strip(),
                        last_name=new_ln.strip(),
                        unit_id=selected_unit_id,
                        cold_rent=new_cr,
                        utility_advance=new_nk,
                        lease_start=str(new_start),
                        email=new_em,
                        phone=new_ph
                    )
                    st.success(f"✅ Mieter {new_fn} {new_ln} wurde erfolgreich angelegt!")
                    st.rerun()

    with tab_edit:
        st.subheader("✏️ Bestehenden Mieter bearbeiten")
        if tenants:
            tenant_dict = {f"{t['first_name']} {t['last_name']} (ID {t['tenant_id']} - {t['unit_number']})": t for t in tenants}
            selected_label = st.selectbox("Wähle einen Mieter zum Bearbeiten", list(tenant_dict.keys()), key="edit_select_tenant")
            t_data = tenant_dict[selected_label]
            
            with st.form("form_edit_tenant"):
                col_e_fn, col_e_ln = st.columns(2)
                with col_e_fn:
                    edit_fn = st.text_input("Vorname *", value=t_data.get("first_name", ""))
                with col_e_ln:
                    edit_ln = st.text_input("Nachname *", value=t_data.get("last_name", ""))
                    
                col_e_u, col_e_cr, col_e_nk = st.columns(3)
                with col_e_u:
                    unit_options = {f"{u['unit_number']} ({u['area_sqm']:.0f} m² - {u['property_name']})": u["unit_id"] for u in all_units} if all_units else {"Standard": 1}
                    unit_keys = list(unit_options.keys())
                    curr_idx = 0
                    for idx, key in enumerate(unit_keys):
                        if unit_options[key] == t_data.get("unit_id"):
                            curr_idx = idx
                            break
                    edit_unit_label = st.selectbox("Wohneinheit", unit_keys, index=curr_idx)
                    edit_unit_id = unit_options[edit_unit_label]
                with col_e_cr:
                    edit_cr = st.number_input("Kaltmiete (€)", min_value=0.0, value=float(t_data.get("cold_rent") or 0.0), step=50.0)
                with col_e_nk:
                    edit_nk = st.number_input("NK-Vorauszahlung (€)", min_value=0.0, value=float(t_data.get("utility_advance") or 0.0), step=10.0)
                    
                col_e_start, col_e_end = st.columns(2)
                with col_e_start:
                    try:
                        parsed_start = datetime.strptime(str(t_data.get("lease_start") or "2025-01-01")[:10], "%Y-%m-%d").date()
                    except Exception:
                        parsed_start = date.today()
                    edit_start = st.date_input("Mietbeginn", value=parsed_start)
                with col_e_end:
                    edit_end = st.text_input("Mietende (optional)", value=str(t_data.get("lease_end") or ""))
                    
                col_e_em, col_e_ph = st.columns(2)
                with col_e_em:
                    edit_em = st.text_input("E-Mail-Adresse", value=str(t_data.get("email") or ""))
                with col_e_ph:
                    edit_ph = st.text_input("Telefonnummer", value=str(t_data.get("phone") or ""))
                    
                col_save, col_del = st.columns([3, 1])
                with col_save:
                    save_clicked = st.form_submit_button("💾 Änderungen speichern", type="primary", use_container_width=True)
                with col_del:
                    delete_clicked = st.form_submit_button("🗑️ Mieter löschen", use_container_width=True)
                    
                if save_clicked:
                    if not edit_fn.strip() or not edit_ln.strip():
                        st.error("⚠️ Vorname und Nachname sind Pflichtfelder!")
                    else:
                        update_tenant(
                            tenant_id=t_data["tenant_id"],
                            first_name=edit_fn.strip(),
                            last_name=edit_ln.strip(),
                            unit_id=edit_unit_id,
                            cold_rent=edit_cr,
                            utility_advance=edit_nk,
                            lease_start=str(edit_start),
                            lease_end=edit_end.strip() or None,
                            email=edit_em.strip(),
                            phone=edit_ph.strip(),
                            is_active=1
                        )
                        st.success(f"✅ Daten von {edit_fn} {edit_ln} wurden erfolgreich aktualisiert!")
                        st.rerun()
                        
                if delete_clicked:
                    delete_tenant(t_data["tenant_id"])
                    st.warning(f"Mieter {t_data['first_name']} {t_data['last_name']} wurde gelöscht.")
                    st.rerun()
        else:
            st.info("Keine Mieter vorhanden zum Bearbeiten.")

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
