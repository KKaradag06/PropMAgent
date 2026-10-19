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

if menu == "💬 KI-Assistent & Abrechnung":
    st.header("Intelligenter Verwaltungsassistent")
    st.write("Erstelle Nebenkostenabrechnungen, stelle Fragen zu Mietern oder lass dir Auswertungen anzeigen.")

    tenants = get_all_tenants()
    tenant_options = {
        f"{t.get('salutation', 'Herr')} {t['first_name']} {t['last_name']} ({t.get('unit_number', '')})": f"{t['first_name']} {t['last_name']}"
        for t in tenants
    } if tenants else {"(Keine Mieter in Datenbank erfasst)": ""}

    # Strukturierte Vorlagen & Schnellaktionen
    with st.container(border=True):
        st.markdown("**Vorlagen & Schnellaktionen**")
        category = st.segmented_control(
            "Bereich",
            options=["Miete", "Nebenkosten", "Andere"],
            default="Miete",
            key="action_category_selector",
            label_visibility="collapsed"
        )

        if category == "Miete":
            sub_action = st.pills(
                "Miet-Aktionen",
                options=["Mietanpassung", "Zahlungserinnerung", "Mietbescheinigung", "Abmahnung Zahlungsverzug"],
                default="Mietanpassung",
                key="sub_action_miete",
                label_visibility="collapsed"
            )

            if sub_action == "Mietanpassung":
                c_t, c_inp, c_btn = st.columns([2.5, 2.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_ma")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_inp:
                    adj_val = st.text_input("Anpassung (z. B. 15% oder 50 €)", value="15%", key="act_adj_ma")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_ma"):
                        if tgt_t:
                            st.session_state.quick_prompt = f"Schreibe eine Mieterhöhung an {tgt_t} um {adj_val.strip()} zum rechtlich nächstmöglichen Zeitpunkt"
                            st.rerun()

            elif sub_action == "Zahlungserinnerung":
                c_t, c_amt, c_due, c_btn = st.columns([2, 1.5, 1.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_ze")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_amt:
                    debt_amt = st.text_input("Rückstand (€)", placeholder="z. B. 950 €", key="act_debt_amt")
                with c_due:
                    due_date = st.text_input("Zahlungsfrist", placeholder="z. B. 7 Tage", key="act_due_date")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_ze"):
                        if tgt_t:
                            amt_txt = f"über {debt_amt.strip()}" if debt_amt.strip() else ""
                            due_txt = f"mit Frist {due_date.strip()}" if due_date.strip() else ""
                            st.session_state.quick_prompt = f"Schreibe eine Zahlungserinnerung an {tgt_t} {amt_txt} {due_txt}".strip()
                            st.rerun()

            elif sub_action == "Mietbescheinigung":
                c_t, c_btn = st.columns([3.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_mb")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Bescheinigung erstellen", type="primary", use_container_width=True, key="btn_mb"):
                        if tgt_t:
                            st.session_state.quick_prompt = f"Erstelle eine Mietbescheinigung für {tgt_t}"
                            st.rerun()

            elif sub_action == "Abmahnung Zahlungsverzug":
                c_t, c_reason, c_btn = st.columns([2.5, 2.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_az")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_reason:
                    reason_txt = st.text_input("Rückstand / Details", placeholder="z. B. Miete für September und Oktober 2026", key="act_az_reason")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Abmahnung erstellen", type="primary", use_container_width=True, key="btn_az"):
                        if tgt_t:
                            detail = f": {reason_txt.strip()}" if reason_txt.strip() else ""
                            st.session_state.quick_prompt = f"Schreibe eine formelle Abmahnung an {tgt_t} wegen Zahlungsverzugs{detail}"
                            st.rerun()

        elif category == "Nebenkosten":
            sub_action = st.pills(
                "Nebenkosten-Aktionen",
                options=["Nebenkostenabrechnung", "Nebenkostensenkung", "Nebenkostenerhöhung", "Kostenübersicht"],
                default="Nebenkostenabrechnung",
                key="sub_action_nk",
                label_visibility="collapsed"
            )

            if sub_action == "Nebenkostenabrechnung":
                c_t, c_yr, c_btn = st.columns([2.5, 2.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_nka")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_yr:
                    yr_val = st.number_input("Abrechnungsjahr", min_value=2020, max_value=2030, value=2025, step=1, key="act_yr_nka")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Abrechnung generieren", type="primary", use_container_width=True, key="btn_nka"):
                        if tgt_t:
                            st.session_state.quick_prompt = f"Erstelle die Nebenkostenabrechnung {int(yr_val)} für {tgt_t}"
                            st.rerun()

            elif sub_action == "Nebenkostensenkung":
                c_t, c_inp, c_btn = st.columns([2.5, 2.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_nks")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_inp:
                    adj_val = st.text_input("Senkungsbetrag (z. B. 20 € oder 10%)", value="20 €", key="act_adj_nks")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_nks"):
                        if tgt_t:
                            st.session_state.quick_prompt = f"Schreibe einen Brief an {tgt_t} wegen Nebenkostensenkung um {adj_val.strip()} zum rechtlich nächstmöglichen Zeitpunkt"
                            st.rerun()

            elif sub_action == "Nebenkostenerhöhung":
                c_t, c_inp, c_btn = st.columns([2.5, 2.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_nke")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_inp:
                    adj_val = st.text_input("Erhöhungsbetrag (z. B. 30 € oder 15%)", value="30 €", key="act_adj_nke")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_nke"):
                        if tgt_t:
                            st.session_state.quick_prompt = f"Schreibe einen Brief an {tgt_t} wegen Nebenkostenerhöhung um {adj_val.strip()} zum rechtlich nächstmöglichen Zeitpunkt"
                            st.rerun()

            elif sub_action == "Kostenübersicht":
                c_yr, c_btn = st.columns([3.5, 1.5])
                with c_yr:
                    yr_val = st.number_input("Abrechnungsjahr", min_value=2020, max_value=2030, value=2025, step=1, key="act_yr_ko")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Kosten anzeigen", type="primary", use_container_width=True, key="btn_ko"):
                        st.session_state.quick_prompt = f"Zeige alle Betriebskosten für das Abrechnungsjahr {int(yr_val)}"
                        st.rerun()

        elif category == "Andere":
            sub_action = st.pills(
                "Weitere Aktionen",
                options=["Handwerker / Wartung", "Bankverbindung mitteilen", "Abmahnung Hausordnung", "Mieterübersicht"],
                default="Handwerker / Wartung",
                key="sub_action_andere",
                label_visibility="collapsed"
            )

            if sub_action == "Handwerker / Wartung":
                c_t, c_inp, c_btn = st.columns([2.5, 2.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_hw")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_inp:
                    work_txt = st.text_input("Grund & Termin", placeholder="z. B. Heizungswartung am 15.11. von 9-12 Uhr", key="act_hw_work")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_hw"):
                        if tgt_t:
                            st.session_state.quick_prompt = f"Schreibe ein Ankündigungsschreiben an {tgt_t} bezüglich Handwerkerarbeiten: {work_txt.strip()}"
                            st.rerun()

            elif sub_action == "Bankverbindung mitteilen":
                c_t, c_inp, c_btn = st.columns([2.5, 2.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_bv")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_inp:
                    bank_txt = st.text_input("Hinweis / Bankdaten (optional)", placeholder="z. B. Neues Mietkonto ab dem 01.11.2026", key="act_bv_hint")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_bv"):
                        if tgt_t:
                            detail = f": {bank_txt.strip()}" if bank_txt.strip() else ""
                            st.session_state.quick_prompt = f"Schreibe eine Mitteilung an {tgt_t} über die Aktualisierung der Bankverbindung für Mietzahlungen{detail}"
                            st.rerun()

            elif sub_action == "Abmahnung Hausordnung":
                c_t, c_inp, c_btn = st.columns([2.5, 2.5, 1.5])
                with c_t:
                    sel_t_lbl = st.selectbox("Mieter auswählen", list(tenant_options.keys()), key="act_t_sel_ah")
                    tgt_t = tenant_options.get(sel_t_lbl, "")
                with c_inp:
                    incident_txt = st.text_input("Pflichtverletzung", placeholder="z. B. wiederholte Ruhestörung nach 22:00 Uhr", key="act_ah_incident")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Abmahnung erstellen", type="primary", use_container_width=True, key="btn_ah"):
                        if tgt_t:
                            st.session_state.quick_prompt = f"Schreibe eine formelle Abmahnung an {tgt_t} wegen vertragswidrigen Verhaltens: {incident_txt.strip()}"
                            st.rerun()

            elif sub_action == "Mieterübersicht":
                c_txt, c_btn = st.columns([3.5, 1.5])
                with c_txt:
                    st.write("Ruft die vollständige Übersicht aller aktuell aktiven Mieter ab.")
                with c_btn:
                    if st.button("Mieterliste anzeigen", type="primary", use_container_width=True, key="btn_ml"):
                        st.session_state.quick_prompt = "Welche Mieter wohnen aktuell im Objekt?"
                        st.rerun()

    # Chat-Historie im Session-State
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Wie kann ich Ihnen helfen?"
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
                            label="PDF herunterladen (DIN 5008)",
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
                            label="Word / DOCX herunterladen",
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
                                label="PDF herunterladen (DIN 5008)",
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
                                label="Word / DOCX herunterladen",
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
                "salutation": "Anrede",
                "first_name": "Vorname",
                "last_name": "Nachname",
                "unit_number": "Wohneinheit",
                "area_sqm": "Fläche (m²)",
                "cold_rent": "Kaltmiete (€)",
                "price_per_sqm": "Miete / m² (€)",
                "utility_advance": "NK-Vorauszahlung (€)",
                "property_name": "Objekt",
                "phone": "Telefon",
                "email": "E-Mail",
                "lease_start": "Mietbeginn",
                "lease_end": "Mietende"
            })
            cols_to_show = [c for c in ["ID", "Anrede", "Vorname", "Nachname", "Wohneinheit", "Fläche (m²)", "Kaltmiete (€)", "Miete / m² (€)", "NK-Vorauszahlung (€)", "Mietbeginn", "Telefon", "E-Mail"] if c in df_display.columns]
            st.dataframe(df_display[cols_to_show], use_container_width=True, hide_index=True)
            
            # Schnell-Abrechnungsgenerator pro Mieter
            st.markdown("---")
            st.subheader("⚡ 1-Klick Abrechnungs-Erstellung")
            col_sel, col_yr, col_btn = st.columns([3, 1, 2])
            with col_sel:
                tenant_names = {f"{t.get('salutation', 'Herr')} {t['first_name']} {t['last_name']} ({t['unit_number']})": t["tenant_id"] for t in tenants}
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
            col_sal, col_fn, col_ln = st.columns([1, 2, 2])
            with col_sal:
                new_sal = st.selectbox("Anrede", ["Herr", "Frau"])
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
                        salutation=new_sal,
                        unit_id=selected_unit_id,
                        cold_rent=new_cr,
                        utility_advance=new_nk,
                        lease_start=str(new_start),
                        email=new_em,
                        phone=new_ph
                    )
                    st.success(f"✅ Mieter {new_sal} {new_fn} {new_ln} wurde erfolgreich angelegt!")
                    st.rerun()

    with tab_edit:
        st.subheader("✏️ Bestehenden Mieter bearbeiten")
        if tenants:
            tenant_dict = {f"{t.get('salutation', 'Herr')} {t['first_name']} {t['last_name']} (ID {t['tenant_id']} - {t['unit_number']})": t for t in tenants}
            selected_label = st.selectbox("Wähle einen Mieter zum Bearbeiten", list(tenant_dict.keys()), key="edit_select_tenant")
            t_data = tenant_dict[selected_label]
            
            with st.form("form_edit_tenant"):
                col_e_sal, col_e_fn, col_e_ln = st.columns([1, 2, 2])
                with col_e_sal:
                    cur_sal = t_data.get("salutation", "Herr") or "Herr"
                    sal_idx = 1 if cur_sal == "Frau" else 0
                    edit_sal = st.selectbox("Anrede", ["Herr", "Frau"], index=sal_idx)
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
                            salutation=edit_sal,
                            unit_id=edit_unit_id,
                            cold_rent=edit_cr,
                            utility_advance=edit_nk,
                            lease_start=str(edit_start),
                            lease_end=edit_end.strip() or None,
                            email=edit_em.strip(),
                            phone=edit_ph.strip(),
                            is_active=1
                        )
                        st.success(f"✅ Daten von {edit_sal} {edit_fn} {edit_ln} wurden erfolgreich aktualisiert!")
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
