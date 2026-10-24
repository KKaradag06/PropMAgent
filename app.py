from datetime import datetime, date
import os
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from database.db import init_db, query_db
from database.seed_data import seed
from agent.core import handle_agent_request
from agent.tools import (
    get_all_tenants, 
    get_all_units,
    get_all_properties,
    get_property_by_id,
    update_property_alias,
    update_property,
    add_property,
    get_tenants_by_property,
    get_units_by_property,
    add_unit,
    add_new_tenant,
    update_tenant,
    delete_tenant,
    get_expenses_summary, 
    get_available_expense_years,
    get_expenses_for_year,
    add_expense,
    update_expense,
    delete_expense,
    copy_expenses_from_year,
    get_annual_utility_statements,
    create_utility_statement_for_tenant
)
from database.settings import (
    init_settings,
    get_all_settings,
    get_setting,
    set_setting,
    save_settings,
    reset_settings_to_default,
    check_ollama_status,
    DEFAULT_SETTINGS
)

# Streamlit Page Config
st.set_page_config(
    page_title="PropMAgent",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Datenbank initialisieren & ggf. Beispieldaten laden
init_db()
init_settings()
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
    /* Grünes Häkchen für heruntergeladene Dateien */
    button[data-testid="stDownloadButton"] span[data-testid="stIconMaterial"] {
        color: #16a34a !important;
        font-weight: 700 !important;
        font-size: 1.25rem !important;
    }
    .prop-instant-check {
        color: #16a34a !important;
        font-weight: bold;
        display: inline-block;
    }
    /* Zentrierter Floating Scroll-to-Bottom Button */
    #prop-scroll-to-bottom-btn {
        position: fixed;
        bottom: 85px;
        left: 50%;
        transform: translate(-50%, 10px) scale(0.9);
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background-color: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.16);
        display: none;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        z-index: 9999;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.25s ease, transform 0.25s ease, background-color 0.15s ease, box-shadow 0.15s ease;
    }
    #prop-scroll-to-bottom-btn.visible {
        opacity: 1;
        pointer-events: auto;
        transform: translate(-50%, 0) scale(1);
    }
    #prop-scroll-to-bottom-btn:hover {
        background-color: #f1f5f9;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22);
        transform: translate(-50%, -2px) scale(1.06);
    }
    #prop-scroll-to-bottom-btn:active {
        transform: translate(-50%, 0) scale(0.96);
    }
    @media (prefers-color-scheme: dark) {
        #prop-scroll-to-bottom-btn {
            background-color: #1e293b;
            color: #f8fafc;
            border-color: #475569;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5);
        }
        #prop-scroll-to-bottom-btn:hover {
            background-color: #334155;
        }
    }

    /* Streamlit Ladesymbol oben rechts: Wechselnde Zeichen durch klassischen Kreis-Spinner ersetzen */
    [data-testid="stStatusWidgetRunningIcon"] {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 22px !important;
        height: 22px !important;
        position: relative !important;
    }
    [data-testid="stStatusWidgetRunningIcon"] > svg,
    [data-testid="stStatusWidgetRunningIcon"] > img,
    [data-testid="stStatusWidgetRunningIcon"] > span,
    [data-testid="stStatusWidgetRunningManIcon"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
    }
    [data-testid="stStatusWidgetRunningIcon"]::after {
        content: "" !important;
        display: block !important;
        width: 16px !important;
        height: 16px !important;
        border: 2.2px solid rgba(100, 116, 139, 0.25) !important;
        border-top-color: #2563eb !important;
        border-radius: 50% !important;
        animation: prop-stream-spin 0.75s linear infinite !important;
        box-sizing: border-box !important;
    }
    @keyframes prop-stream-spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    @media (prefers-color-scheme: dark) {
        [data-testid="stStatusWidgetRunningIcon"]::after {
            border-color: rgba(255, 255, 255, 0.2) !important;
            border-top-color: #60a5fa !important;
        }
    }

    /* Sidebar Footer fix am unteren Rand */
    [data-testid="stSidebarContent"] {
        display: flex !important;
        flex-direction: column !important;
        height: 100% !important;
    }
    .prop-sidebar-footer {
        margin-top: auto !important;
        padding-top: 2rem;
        padding-bottom: 0.8rem;
        text-align: center;
        font-size: 0.75rem;
        color: #64748b;
        border-top: 1px solid rgba(226, 232, 240, 0.8);
    }
    .prop-sidebar-footer .prop-badge-mig {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background-color: #f1f5f9;
        color: #1e293b;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 500;
        margin-bottom: 6px;
        border: 1px solid #e2e8f0;
    }
    @media (prefers-color-scheme: dark) {
        .prop-sidebar-footer {
            color: #94a3b8;
            border-top-color: rgba(51, 65, 85, 0.8);
        }
        .prop-sidebar-footer .prop-badge-mig {
            background-color: #1e293b;
            color: #f1f5f9;
            border-color: #334155;
        }
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
        ["KI-Assistent & Schriftverkehr", "Liegenschaften & Mieter", "Betriebskosten & Finanzen"],
        index=0
    )

    current_settings = get_all_settings()
    model_name = current_settings.get("ollama_model", "llama3")
    st.markdown("---")
    st.caption(f"🤖 Aktives Modell: **{model_name}**")

    current_year = datetime.now().year
    st.markdown(f"""
    <div class="prop-sidebar-footer">
        <div class="prop-badge-mig">
            🇩🇪 Made in Germany
        </div>
        <div style="margin-top: 2px; font-weight: 500;">
            © {current_year} PropMAgent
        </div>
        <div style="font-size: 0.68rem; opacity: 0.85; margin-top: 2px;">
            100% lokal & datenschutzkonform
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_settings_page():
    # 1. Zurück-Button oben links
    col_back, col_back_info = st.columns([0.18, 0.82])
    with col_back:
        if st.button("Zurück", icon=":material/arrow_back:", key="settings_top_back_btn", use_container_width=True, help="Zurück zum vorherigen Bereich"):
            st.session_state.show_settings = False
            st.rerun()
    with col_back_info:
        prev_m = st.session_state.get("previous_menu", "Hauptansicht")
        st.caption(f"Zurück zu: **{prev_m}**")

    st.header("Einstellungen")
    st.caption("Verwalte das lokale KI-Modell, deine Vermieter- und Kontaktdaten sowie Standardvorgaben für offizielle Schreiben.")

    # 100% Lokal Hinweis
    st.info("🔒 **100% Lokal:** Alle Daten und KI-Anfragen laufen vollständig auf deinem PC.")

    current_settings = get_all_settings()

    tab_vermieter, tab_ki, tab_briefe, tab_system = st.tabs([
        "Vermieterdaten & Bankverbindung",
        "KI & Sprachmodell (Ollama)",
        "Brief- & Abrechnungsvorgaben",
        "System & Datensicherung"
    ])

    with tab_vermieter:
        st.subheader("Vermieterdaten & Bankverbindung")
        st.caption("Diese Stammdaten werden als Absender für alle formellen Briefe, Mietanpassungen und Nebenkostenabrechnungen nach DIN 5008 sowie von der KI verwendet.")

        with st.form("form_landlord_settings"):
            st.markdown("##### 🏢 Absender & Verwaltung")
            col_lname, col_lperson = st.columns(2)
            with col_lname:
                new_lname = st.text_input("Name der Hausverwaltung / Vermieter *", value=current_settings.get("landlord_name", "Hausverwaltung Sonnenhang"))
            with col_lperson:
                new_lperson = st.text_input("Ansprechpartner / Unterzeichner (Druckschrift)", value=current_settings.get("landlord_contact_person", "Kirdar Karadag"))

            st.markdown("##### 📍 Anschrift (DIN 5008 Fensterkuvert)")
            col_lstreet, col_lzip, col_lcity = st.columns([2, 1, 1.5])
            with col_lstreet:
                new_lstreet = st.text_input("Straße und Hausnummer *", value=current_settings.get("landlord_street", "Lindenstraße 14"))
            with col_lzip:
                new_lzip = st.text_input("Postleitzahl *", value=current_settings.get("landlord_zip", "10115"))
            with col_lcity:
                new_lcity = st.text_input("Ort *", value=current_settings.get("landlord_city", "Berlin"))

            st.markdown("##### 📞 Kontaktdaten")
            col_lphone, col_lemail = st.columns(2)
            with col_lphone:
                new_lphone = st.text_input("Telefonnummer", value=current_settings.get("landlord_phone", "+49 30 12345678"))
            with col_lemail:
                new_lemail = st.text_input("E-Mail-Adresse", value=current_settings.get("landlord_email", "verwaltung@sonnenhang.de"))

            st.markdown("##### 💳 Bankverbindung für Mietzahlungen & Nachzahlungen")
            col_lholder, col_lbank = st.columns(2)
            with col_lholder:
                new_lholder = st.text_input("Kontoinhaber", value=current_settings.get("landlord_account_holder", current_settings.get("landlord_name", "Hausverwaltung Sonnenhang")))
            with col_lbank:
                new_lbank = st.text_input("Kreditinstitut (Bankname)", value=current_settings.get("landlord_bank_name", "Berliner Sparkasse"))

            col_liban, col_lbic, col_ltax = st.columns([2, 1.2, 1.2])
            with col_liban:
                new_liban = st.text_input("IBAN", value=current_settings.get("landlord_iban", "DE12 1005 0000 0123 4567 89"))
            with col_lbic:
                new_lbic = st.text_input("BIC", value=current_settings.get("landlord_bic", "BELADEB1XXX"))
            with col_ltax:
                new_ltax = st.text_input("Steuernummer / USt-IdNr. (optional)", value=current_settings.get("landlord_tax_id", "27/123/45678"))

            save_landlord = st.form_submit_button("Vermieterdaten speichern", type="primary", use_container_width=True)
            if save_landlord:
                save_settings({
                    "landlord_name": new_lname.strip(),
                    "landlord_contact_person": new_lperson.strip(),
                    "landlord_street": new_lstreet.strip(),
                    "landlord_zip": new_lzip.strip(),
                    "landlord_city": new_lcity.strip(),
                    "landlord_phone": new_lphone.strip(),
                    "landlord_email": new_lemail.strip(),
                    "landlord_account_holder": new_lholder.strip(),
                    "landlord_bank_name": new_lbank.strip(),
                    "landlord_iban": new_liban.strip(),
                    "landlord_bic": new_lbic.strip(),
                    "landlord_tax_id": new_ltax.strip()
                })
                st.success("Vermieterdaten wurden erfolgreich gespeichert! Alle künftigen Briefe und Abrechnungen nutzen diese Angaben.")
                st.rerun()

        # Vorschau-Box
        with st.expander("Vorschau: So erscheint dein Briefkopf auf Schreiben (DIN 5008)", expanded=False):
            v_name = current_settings.get("landlord_name", "Hausverwaltung Sonnenhang")
            v_str = current_settings.get("landlord_street", "Lindenstraße 14")
            v_city = f"{current_settings.get('landlord_zip', '10115')} {current_settings.get('landlord_city', 'Berlin')}"
            v_phone = current_settings.get("landlord_phone", "")
            v_email = current_settings.get("landlord_email", "")
            v_iban = current_settings.get("landlord_iban", "")
            v_bank = current_settings.get("landlord_bank_name", "")
            
            st.markdown(f"""
            <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 20px; font-family: Arial, sans-serif; color: #0f172a;">
                <div style="font-size: 8pt; text-decoration: underline; color: #64748b; margin-bottom: 12px;">
                    {v_name} · {v_str} · {v_city}
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <div style="font-size: 10pt; line-height: 1.4;">
                        <b>[Mieter Name]</b><br/>
                        [Mieter Straße]<br/>
                        [Mieter PLZ Ort]
                    </div>
                    <div style="text-align: right; font-size: 9pt; line-height: 1.4; color: #334155;">
                        <b>{v_name}</b><br/>
                        {v_str}<br/>
                        {v_city}<br/>
                        Tel.: {v_phone}<br/>
                        E-Mail: {v_email}<br/>
                        <span style="font-size: 8pt; color: #64748b;">Bank: {v_bank} | IBAN: {v_iban}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with tab_ki:
        st.subheader("Lokales Sprachmodell & Ollama-Verbindung")
        st.caption("PropMAgent kommuniziert direkt mit deinem lokalen Ollama-Server. Es werden zu keinem Zeitpunkt Daten ins Internet übertragen.")

        ollama_status = check_ollama_status(current_settings.get("ollama_url", "http://localhost:11434"))
        
        col_stat_info, col_stat_btn = st.columns([3, 1.2])
        with col_stat_info:
            if ollama_status["online"]:
                st.success(f"🟢 **Ollama aktiv:** {ollama_status['message']}")
            else:
                st.warning(f"🟡 **Ollama Status:** {ollama_status['message']}. Bitte stelle sicher, dass die Ollama-Anwendung läuft.")
        with col_stat_btn:
            st.write("")
            if st.button("Verbindung prüfen", icon=":material/refresh:", use_container_width=True, key="btn_check_ollama"):
                st.rerun()

        with st.form("form_ai_settings"):
            known_models = ["llama3", "llama3.1", "mistral", "qwen2.5", "phi3"]
            if ollama_status.get("models"):
                for m in ollama_status["models"]:
                    if m not in known_models:
                        known_models.append(m)
            
            cur_model = current_settings.get("ollama_model", "llama3")
            if cur_model not in known_models:
                known_models.insert(0, cur_model)
                
            col_m_sel, col_m_custom = st.columns([2, 1.5])
            with col_m_sel:
                selected_model = st.selectbox(
                    "Ollama Modell auswählen *",
                    options=known_models,
                    index=known_models.index(cur_model) if cur_model in known_models else 0,
                    help="Empfohlen: llama3 oder llama3.1 für präzise juristische Formulierungen."
                )
            with col_m_custom:
                custom_model_input = st.text_input(
                    "Oder benutzerdefiniertes Modell",
                    placeholder="z. B. llama3:8b-instruct-q8_0",
                    help="Falls du ein spezifisches Quantisierungs-Tag oder Feinabstimmung nutzt."
                )

            col_url, col_temp = st.columns([2.5, 1.5])
            with col_url:
                new_url = st.text_input(
                    "Ollama API-Endpunkt (Server-URL) *",
                    value=current_settings.get("ollama_url", "http://localhost:11434"),
                    help="Standard: http://localhost:11434. Ändere dies nur, wenn Ollama auf einem anderen Port oder in WSL läuft."
                )
            with col_temp:
                try:
                    cur_temp = float(current_settings.get("ai_temperature", "0.1"))
                except Exception:
                    cur_temp = 0.1
                new_temp = st.slider(
                    "Kreativität / Temperatur",
                    min_value=0.0,
                    max_value=0.7,
                    value=cur_temp,
                    step=0.05,
                    help="0.0 bis 0.1 liefert maximale Rechtssicherheit und Konsistenz bei Fristen und Beträgen."
                )

            save_ai = st.form_submit_button("KI-Einstellungen speichern", type="primary", use_container_width=True)
            if save_ai:
                final_model = custom_model_input.strip() if custom_model_input.strip() else selected_model
                save_settings({
                    "ollama_model": final_model,
                    "ollama_url": new_url.strip(),
                    "ai_temperature": str(new_temp)
                })
                st.success(f"KI-Konfiguration gespeichert! Aktives Modell: **{final_model}**")
                st.rerun()

    with tab_briefe:
        st.subheader("Vorgaben für Briefe, Fristen & Abrechnungen")
        st.caption("Passe Standardfristen und Formulierungen an, die in allen Schreiben und Nebenkostenabrechnungen automatisch herangezogen werden.")

        with st.form("form_letter_defaults"):
            st.markdown("##### ⏱️ Gesetzliche Fristen & Zahlungsziele")
            col_d_pay, col_d_obj = st.columns(2)
            with col_d_pay:
                new_pay_days = st.number_input(
                    "Standard-Zahlungsfrist für Mahnungen & Nachzahlungen (Tage)",
                    min_value=3,
                    max_value=90,
                    value=int(current_settings.get("default_payment_deadline_days", "14")),
                    step=1,
                    help="Frist, die in Zahlungserinnerungen und Nachzahlungsaufforderungen gesetzt wird (z. B. 14 Tage)."
                )
            with col_d_obj:
                new_obj_days = st.number_input(
                    "Einwendungsfrist für Nebenkostenabrechnungen (Tage)",
                    min_value=14,
                    max_value=365,
                    value=int(current_settings.get("default_utility_objection_days", "30")),
                    step=1,
                    help="Frist für Mieter zur Prüfung der Nebenkostenabrechnung (Standard: 30 Tage)."
                )

            st.markdown("##### ✍️ Grußformel & Unterschriftenzeile (DIN 5008)")
            col_closing, col_sig_title = st.columns(2)
            with col_closing:
                closing_opts = ["Mit freundlichen Grüßen", "Freundliche Grüße", "Mit besten Grüßen"]
                cur_closing = current_settings.get("default_closing_phrase", "Mit freundlichen Grüßen")
                idx_closing = closing_opts.index(cur_closing) if cur_closing in closing_opts else 0
                new_closing = st.selectbox("Standard-Grußformel", closing_opts, index=idx_closing)
            with col_sig_title:
                new_sig_title = st.text_input(
                    "Standard-Unterschriftenbezeichnung",
                    value=current_settings.get("default_signature_title", "Ihre Hausverwaltung"),
                    help="Wird unter den 3 Leerzeilen für die handschriftliche Unterschrift gedruckt."
                )

            st.markdown("##### 📄 Layout & Optionen")
            inc_bank = st.checkbox(
                "Bankverbindung in offiziellen Zahlungsaufforderungen und Briefen automatisch auflisten",
                value=current_settings.get("letter_include_bank_details", "true") == "true"
            )

            save_letters = st.form_submit_button("Vorgaben speichern", type="primary", use_container_width=True)
            if save_letters:
                save_settings({
                    "default_payment_deadline_days": str(new_pay_days),
                    "default_utility_objection_days": str(new_obj_days),
                    "default_closing_phrase": new_closing,
                    "default_signature_title": new_sig_title.strip(),
                    "letter_include_bank_details": "true" if inc_bank else "false"
                })
                st.success("Brief- und Abrechnungsvorgaben erfolgreich aktualisiert!")
                st.rerun()

    with tab_system:
        st.subheader("Systemstatus, Datenbank & Datensicherung")
        st.caption("Prüfe den Zustand deiner lokalen Datenbank und lade jederzeit ein vollständiges Backup herunter.")

        db_tenants = query_db("SELECT COUNT(*) as c FROM tenants;")[0]["c"]
        db_units = query_db("SELECT COUNT(*) as c FROM units;")[0]["c"]
        db_props = query_db("SELECT COUNT(*) as c FROM properties;")[0]["c"]
        db_expenses = query_db("SELECT COUNT(*) as c FROM expenses;")[0]["c"]

        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Liegenschaften", db_props)
        col_s2.metric("Wohneinheiten", db_units)
        col_s3.metric("Erfasste Mieter", db_tenants)
        col_s4.metric("Kostenbelege", db_expenses)

        st.markdown("---")
        st.markdown("##### 💾 Lokales Datenbank-Backup herunterladen")
        st.write("Deine gesamte Datenbank (`prop_management.db`) enthält alle Mieter, Verträge, Zahlungen und Betriebskosten. Sichere sie mit einem Klick:")

        from database.db import DB_PATH
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as db_file:
                db_bytes = db_file.read()
            backup_filename = f"prop_management_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            st.download_button(
                label="Datenbank-Backup herunterladen (.db)",
                data=db_bytes,
                file_name=backup_filename,
                mime="application/x-sqlite3",
                icon=":material/download:",
                use_container_width=True
            )

        st.markdown("---")
        st.markdown("##### 🔄 Auf Werkseinstellungen zurücksetzen")
        st.write("Setzt ausschließlich die Einstellungen (Vermieterdaten, Fristen, Modell) auf die Standardwerte zurück. Deine Mieterdaten und Buchungen bleiben unberührt.")
        
        with st.popover("Werkseinstellungen wiederherstellen...", use_container_width=True):
            st.warning("Möchtest du alle Einstellungen wirklich auf die Standardwerte zurücksetzen?")
            if st.button("Ja, Einstellungen zurücksetzen", type="primary", use_container_width=True):
                reset_settings_to_default()
                st.success("Einstellungen wurden auf Standardwerte zurückgesetzt.")
                st.rerun()

# Automatisch Einstellungen verlassen, wenn der Nutzer in der Sidebar navigiert
if "last_sidebar_menu" not in st.session_state:
    st.session_state["last_sidebar_menu"] = menu
if st.session_state["last_sidebar_menu"] != menu:
    st.session_state["show_settings"] = False
    st.session_state["last_sidebar_menu"] = menu

if st.session_state.get("show_settings", False):
    render_settings_page()
elif menu == "KI-Assistent & Schriftverkehr":
    should_scroll = st.session_state.get("scroll_to_chat", False)
    if should_scroll:
        del st.session_state["scroll_to_chat"]

    def register_download(filename: str):
        st.session_state[f"downloaded_{filename}"] = True

    col_hdr_main, col_hdr_gear = st.columns([0.84, 0.16])
    with col_hdr_gear:
        st.write("")
        if st.button("Einstellungen", icon=":material/settings:", key="btn_gear_assistant", use_container_width=True, help="Einstellungen, Vermieterdaten & Modell öffnen"):
            st.session_state["previous_menu"] = "KI-Assistent & Schriftverkehr"
            st.session_state["show_settings"] = True
            st.rerun()
    with col_hdr_main:
        st.header("KI-Assistent & Schriftverkehr")
        st.write("Erstelle rechtssichere Anschreiben, Mietanpassungen und Nebenkostenabrechnungen oder stelle Fragen zu Liegenschaften und Mietern.")

    tenants = get_all_tenants()
    tenant_options = {
        f"{t.get('salutation', 'Herr')} {t['first_name']} {t['last_name']} ({t.get('unit_number', '')})": f"{t['first_name']} {t['last_name']}"
        for t in tenants
    } if tenants else {"(Keine Mieter in Datenbank erfasst)": ""}

    # Anker für sanftes Scrollen
    st.markdown('<div id="prop-quick-actions"></div>', unsafe_allow_html=True)

    # Injektion des Floating Scroll-to-Bottom Buttons und Auto-Scroll Scripts
    components.html(
        f"""
        <script>
        (function() {{
            const doc = window.parent.document || document;
            const win = window.parent || window;
            
            // Floating scroll-to-bottom button
            let btn = doc.getElementById('prop-scroll-to-bottom-btn');
            if (!btn) {{
                btn = doc.createElement('button');
                btn.id = 'prop-scroll-to-bottom-btn';
                btn.setAttribute('aria-label', 'Nach unten scrollen');
                btn.title = 'Nach unten scrollen';
                btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <polyline points="19 12 12 19 5 12"></polyline>
                </svg>`;
                doc.body.appendChild(btn);
                
                btn.addEventListener('click', function(e) {{
                    e.preventDefault();
                    e.stopPropagation();
                    const main = doc.querySelector('section.main') || doc.documentElement || doc.body;
                    if (main) {{
                        main.scrollTo({{ top: main.scrollHeight, behavior: 'smooth' }});
                    }}
                }});
            }}

            function checkScroll() {{
                const isChatActive = !!doc.getElementById('prop-quick-actions');
                if (!isChatActive) {{
                    btn.style.display = 'none';
                    btn.classList.remove('visible');
                    return;
                }}
                btn.style.display = 'flex';
                const scrollContainer = doc.querySelector('section.main') || doc.documentElement || doc.body;
                if (!scrollContainer) return;
                const distFromBottom = scrollContainer.scrollHeight - scrollContainer.clientHeight - scrollContainer.scrollTop;
                if (distFromBottom > 180) {{
                    btn.classList.add('visible');
                }} else {{
                    btn.classList.remove('visible');
                }}
            }}

            const main = doc.querySelector('section.main') || win;
            if (main && !main._propScrollBound) {{
                main.addEventListener('scroll', checkScroll, {{ passive: true }});
                main._propScrollBound = true;
            }}
            win.addEventListener('scroll', checkScroll, {{ passive: true }});
            checkScroll();

            // Sofortiges Feedback beim Klick auf Download-Buttons
            if (!doc._propDlBound) {{
                doc.addEventListener('click', function(e) {{
                    const dlBtn = e.target.closest('button[data-testid="stDownloadButton"]');
                    if (dlBtn) {{
                        let check = dlBtn.querySelector('.prop-instant-check');
                        if (!check) {{
                            check = doc.createElement('span');
                            check.className = 'prop-instant-check';
                            check.innerHTML = '&#10003;';
                            check.style.color = '#16a34a';
                            check.style.fontWeight = 'bold';
                            check.style.marginLeft = '8px';
                            check.style.fontSize = '1.15rem';
                            dlBtn.appendChild(check);
                        }}
                    }}
                }});
                doc._propDlBound = true;
            }}

            // Sanftes Scrollen beim Klick auf Aktionsbuttons (Vorlagen bleiben oben sichtbar)
            {"doAutoScroll();" if should_scroll else ""}
            function doAutoScroll() {{
                [80, 250, 500].forEach(delay => {{
                    setTimeout(function() {{
                        const preset = doc.getElementById('prop-quick-actions');
                        const scrollContainer = doc.querySelector('section.main') || doc.documentElement || doc.body;
                        if (preset && scrollContainer) {{
                            const rect = preset.getBoundingClientRect();
                            const targetScroll = scrollContainer.scrollTop + rect.top - 12;
                            scrollContainer.scrollTo({{ top: Math.max(0, targetScroll), behavior: 'smooth' }});
                        }}
                    }}, delay);
                }});
            }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )

    # Strukturierte Vorlagen & Schnellaktionen
    with st.container(border=True):
        st.markdown("**Vorlagen & Schnellaktionen**")

        # 1. Auswahl der Liegenschaft und des Mieters
        all_props = get_all_properties()
        prop_options = {}
        for p in all_props:
            alias_txt = f" ({p['alias']})" if p.get("alias") else ""
            p_lbl = f"{p['name']}{alias_txt} · {p['street']}, {p['city']}"
            prop_options[p_lbl] = p["property_id"]
        if not prop_options:
            prop_options = {"Standard-Liegenschaft": 1}

        col_prop_sel, col_tenant_sel = st.columns([1.6, 2.4])
        with col_prop_sel:
            selected_prop_label = st.selectbox(
                "Liegenschaft auswählen",
                options=list(prop_options.keys()),
                key="qa_prop_selector"
            )
            selected_prop_id = prop_options[selected_prop_label]

        # Name der gewählten Liegenschaft für treffende Prompts
        sel_prop_obj = next((p for p in all_props if p["property_id"] == selected_prop_id), None)
        sel_prop_name = sel_prop_obj["name"] if sel_prop_obj else "der Liegenschaft"

        prop_tenants = get_tenants_by_property(selected_prop_id)
        tenant_options = {}

        # Option "Alle Mieter" IMMER ganz oben an Position 1
        all_tenants_label = "👥 Alle Mieterinnen & Mieter der Liegenschaft"
        tenant_options[all_tenants_label] = {
            "type": "all",
            "name": f"alle Mieterinnen und Mieter der Liegenschaft {sel_prop_name}",
            "display": f"Alle Mieterinnen und Mieter ({sel_prop_name})"
        }

        for t in prop_tenants:
            unit_str = f" · {t['unit_number']}" if t.get("unit_number") else ""
            sal_str = t.get("salutation", "Herr")
            t_lbl = f"{t['first_name']} {t['last_name']} ({sal_str}{unit_str})"
            tenant_options[t_lbl] = {
                "type": "single",
                "name": f"{t['first_name']} {t['last_name']}",
                "display": f"{t.get('salutation', 'Herr')} {t['first_name']} {t['last_name']}"
            }

        with col_tenant_sel:
            selected_tenant_label = st.selectbox(
                "Empfänger auswählen (Alle Mieter oder Suche nach Name)",
                options=list(tenant_options.keys()),
                key="qa_tenant_selector"
            )
            tgt_entry = tenant_options.get(selected_tenant_label, {})
            tgt_t = tgt_entry.get("name", "")
            is_all = tgt_entry.get("type") == "all"

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
                c_mode, c_inp, c_btn = st.columns([2, 3, 1.5])
                with c_mode:
                    adj_mode = st.segmented_control("Art", options=["Erhöhung", "Senkung"], default="Erhöhung", key="act_mode_ma")
                with c_inp:
                    adj_val = st.text_input("Anpassung (z. B. 15% oder 50 €)", value="15%", key="act_adj_ma")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_ma"):
                        if tgt_t:
                            adj_raw = adj_val.strip()
                            if adj_raw and not any(sym in adj_raw.lower() for sym in ["%", "€", "euro"]):
                                adj_raw = f"{adj_raw} €"
                            action_word = "Mieterhöhung" if adj_mode == "Erhöhung" else "Mietsenkung"
                            st.session_state.quick_prompt = f"Schreibe eine {action_word} an {tgt_t} um {adj_raw} zum rechtlich nächstmöglichen Zeitpunkt"
                            st.session_state.scroll_to_chat = True
                            st.rerun()

            elif sub_action == "Zahlungserinnerung":
                c_amt, c_due, c_btn = st.columns([2.5, 2.5, 1.5])
                with c_amt:
                    debt_amt = st.text_input("Rückstand", value="80 €", placeholder="z. B. 80 €", key="act_debt_amt")
                with c_due:
                    due_date = st.text_input("Zahlungsfrist", value="7 Tage", placeholder="z. B. 7 Tage", key="act_due_date")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_ze"):
                        if tgt_t:
                            amt_raw = debt_amt.strip()
                            if amt_raw and not any(sym in amt_raw.lower() for sym in ["€", "euro"]):
                                amt_raw = f"{amt_raw}€"
                            due_raw = due_date.strip()
                            if due_raw and not any(unit in due_raw.lower() for unit in ["tag", "woche", "monat"]):
                                due_raw = f"{due_raw} Tagen"
                            elif "tage" in due_raw.lower() and not "tagen" in due_raw.lower():
                                due_raw = re.sub(r"\btage\b", "Tagen", due_raw, flags=re.I)

                            parts = []
                            if amt_raw:
                                parts.append(f"einem Rückstand von {amt_raw}")
                            if due_raw:
                                parts.append(f"einer Frist von {due_raw}")

                            detail_str = f" mit {' und '.join(parts)}" if parts else ""
                            st.session_state.quick_prompt = f"Schreibe eine Zahlungserinnerung an {tgt_t}{detail_str}"
                            st.session_state.scroll_to_chat = True
                            st.rerun()

            elif sub_action == "Mietbescheinigung":
                c_txt, c_btn = st.columns([4.5, 1.5])
                with c_txt:
                    display_target = f"für **{sel_prop_name}**" if is_all else f"für **{tgt_t or 'den ausgewählten Mieter'}**"
                    st.write(f"Erstellt eine offizielle Miet- und Mietschuldenfreiheitsbescheinigung {display_target}.")
                with c_btn:
                    if st.button("Bescheinigung erstellen", type="primary", use_container_width=True, key="btn_mb"):
                        if tgt_t:
                            if is_all:
                                st.session_state.quick_prompt = f"Erstelle eine Vorlage für eine Miet- und Mietschuldenfreiheitsbescheinigung für die Liegenschaft {sel_prop_name}"
                            else:
                                st.session_state.quick_prompt = f"Erstelle eine Miet- und Mietschuldenfreiheitsbescheinigung für {tgt_t}"
                            st.session_state.scroll_to_chat = True
                            st.rerun()

            elif sub_action == "Abmahnung Zahlungsverzug":
                c_reason, c_btn = st.columns([4.5, 1.5])
                with c_reason:
                    reason_txt = st.text_input("Rückstand / Details", placeholder="z. B. Miete für September und Oktober 2026", key="act_az_reason")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Abmahnung erstellen", type="primary", use_container_width=True, key="btn_az"):
                        if tgt_t:
                            detail = f" bezüglich: {reason_txt.strip()}" if reason_txt.strip() else " wegen Zahlungsverzugs der monatlichen Mietzahlungen"
                            st.session_state.quick_prompt = f"Schreibe eine formelle Abmahnung an {tgt_t}{detail}"
                            st.session_state.scroll_to_chat = True
                            st.rerun()

        elif category == "Nebenkosten":
            sub_action = st.pills(
                "Nebenkosten-Aktionen",
                options=["Nebenkostenanpassung", "Nebenkostenabrechnung", "Kostenübersicht"],
                default="Nebenkostenanpassung",
                key="sub_action_nk",
                label_visibility="collapsed"
            )

            if sub_action == "Nebenkostenanpassung":
                c_mode, c_inp, c_btn = st.columns([2, 3, 1.5])
                with c_mode:
                    adj_mode = st.segmented_control("Art", options=["Erhöhung", "Senkung"], default="Senkung", key="act_mode_nka")
                with c_inp:
                    adj_val = st.text_input("Anpassung (z. B. 20 € oder 10%)", value="20 €", key="act_adj_nka")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_nka"):
                        if tgt_t:
                            adj_raw = adj_val.strip()
                            if adj_raw and not any(sym in adj_raw.lower() for sym in ["%", "€", "euro"]):
                                adj_raw = f"{adj_raw} €"
                            action_word = "Nebenkostenerhöhung" if adj_mode == "Erhöhung" else "Nebenkostensenkung"
                            st.session_state.quick_prompt = f"Schreibe eine {action_word} an {tgt_t} um {adj_raw} zum rechtlich nächstmöglichen Zeitpunkt"
                            st.session_state.scroll_to_chat = True
                            st.rerun()

            elif sub_action == "Nebenkostenabrechnung":
                c_yr, c_btn = st.columns([4.5, 1.5])
                with c_yr:
                    yr_val = st.number_input("Abrechnungsjahr", min_value=2020, max_value=2030, value=2025, step=1, key="act_yr_nka")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Abrechnung generieren", type="primary", use_container_width=True, key="btn_nka_bill"):
                        if tgt_t:
                            if is_all:
                                st.session_state.quick_prompt = f"Erstelle die Nebenkostenabrechnung {int(yr_val)} für alle Mieter der Liegenschaft {sel_prop_name}"
                            else:
                                st.session_state.quick_prompt = f"Erstelle die Nebenkostenabrechnung {int(yr_val)} für {tgt_t}"
                            st.session_state.scroll_to_chat = True
                            st.rerun()

            elif sub_action == "Kostenübersicht":
                c_yr, c_btn = st.columns([4.5, 1.5])
                with c_yr:
                    yr_val = st.number_input("Abrechnungsjahr", min_value=2020, max_value=2030, value=2025, step=1, key="act_yr_ko")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Kosten anzeigen", type="primary", use_container_width=True, key="btn_ko"):
                        st.session_state.quick_prompt = f"Zeige alle Betriebskosten für das Abrechnungsjahr {int(yr_val)} für die Liegenschaft {sel_prop_name}"
                        st.session_state.scroll_to_chat = True
                        st.rerun()

        elif category == "Andere":
            sub_action = st.pills(
                "Weitere Aktionen",
                options=["Handwerker / Wartung", "Bankverbindung mitteilen", "Hausordnung / Rundschreiben", "Mieterübersicht"],
                default="Handwerker / Wartung",
                key="sub_action_andere",
                label_visibility="collapsed"
            )

            if sub_action == "Handwerker / Wartung":
                c_inp, c_btn = st.columns([4.5, 1.5])
                with c_inp:
                    work_txt = st.text_input("Grund & Termin", placeholder="z. B. Heizungswartung am 15.11. von 9-12 Uhr", key="act_hw_work")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_hw"):
                        if tgt_t:
                            detail = f" bezüglich: {work_txt.strip()}" if work_txt.strip() else " bezüglich anstehender Wartungs- und Handwerkerarbeiten"
                            st.session_state.quick_prompt = f"Schreibe ein Ankündigungsschreiben an {tgt_t}{detail}"
                            st.session_state.scroll_to_chat = True
                            st.rerun()

            elif sub_action == "Bankverbindung mitteilen":
                c_inp, c_btn = st.columns([4.5, 1.5])
                with c_inp:
                    bank_txt = st.text_input("Hinweis / Bankdaten (optional)", placeholder="z. B. Neues Mietkonto ab dem 01.11.2026", key="act_bv_hint")
                with c_btn:
                    st.write("")
                    st.write("")
                    if st.button("Brief erstellen", type="primary", use_container_width=True, key="btn_bv"):
                        if tgt_t:
                            detail = f" mit folgendem Hinweis: {bank_txt.strip()}" if bank_txt.strip() else ""
                            st.session_state.quick_prompt = f"Schreibe eine Mitteilung an {tgt_t} über die Aktualisierung der Bankverbindung für Mietzahlungen{detail}"
                            st.session_state.scroll_to_chat = True
                            st.rerun()

            elif sub_action == "Hausordnung / Rundschreiben":
                c_inp, c_btn = st.columns([4.5, 1.5])
                with c_inp:
                    incident_label = "Thema / Hinweis" if is_all else "Pflichtverletzung"
                    incident_placeholder = "z. B. Ruhezeiten ab 22:00 Uhr und Treppenhaus freihalten" if is_all else "z. B. wiederholte Ruhestörung nach 22:00 Uhr"
                    incident_txt = st.text_input(incident_label, placeholder=incident_placeholder, key="act_ah_incident")
                with c_btn:
                    st.write("")
                    st.write("")
                    action_label = "Rundschreiben erstellen" if is_all else "Abmahnung erstellen"
                    if st.button(action_label, type="primary", use_container_width=True, key="btn_ah"):
                        if tgt_t:
                            if is_all:
                                detail = f" bezüglich der Einhaltung der Hausordnung: {incident_txt.strip()}" if incident_txt.strip() else " bezüglich der Einhaltung der Hausordnung und des Hausfriedens"
                                st.session_state.quick_prompt = f"Schreibe ein Rundschreiben an {tgt_t}{detail}"
                            else:
                                detail = f" wegen vertragswidrigen Verhaltens: {incident_txt.strip()}" if incident_txt.strip() else " wegen wiederholter Verletzung der Hausordnung"
                                st.session_state.quick_prompt = f"Schreibe eine formelle Abmahnung an {tgt_t}{detail}"
                            st.session_state.scroll_to_chat = True
                            st.rerun()

            elif sub_action == "Mieterübersicht":
                c_txt, c_btn = st.columns([4.5, 1.5])
                with c_txt:
                    st.write(f"Ruft die vollständige Übersicht aller aktuell aktiven Mieter der Liegenschaft **{sel_prop_name}** ab.")
                with c_btn:
                    if st.button("Mieterliste anzeigen", type="primary", use_container_width=True, key="btn_ml"):
                        st.session_state.quick_prompt = f"Welche Mieter wohnen aktuell in der Liegenschaft {sel_prop_name}?"
                        st.session_state.scroll_to_chat = True
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
                col_dl1, col_dl2, _ = st.columns([1.6, 2.2, 3.2])
                if has_pdf:
                    pdf_filename = os.path.basename(msg["pdf_path"])
                    is_pdf_downloaded = st.session_state.get(f"downloaded_{pdf_filename}", False)
                    with col_dl1:
                        with open(msg["pdf_path"], "rb") as f:
                            pdf_bytes = f.read()
                        st.download_button(
                            label="PDF herunterladen",
                            data=pdf_bytes,
                            file_name=pdf_filename,
                            mime="application/pdf",
                            key=f"dl_pdf_{idx}_{pdf_filename}",
                            on_click=register_download,
                            args=(pdf_filename,),
                            icon=":material/check:" if is_pdf_downloaded else None,
                            icon_position="right",
                            use_container_width=True
                        )
                if has_docx:
                    docx_filename = os.path.basename(msg["docx_path"])
                    is_docx_downloaded = st.session_state.get(f"downloaded_{docx_filename}", False)
                    with col_dl2:
                        with open(msg["docx_path"], "rb") as f:
                            docx_bytes = f.read()
                        st.download_button(
                            label="Word / DOCX herunterladen",
                            data=docx_bytes,
                            file_name=docx_filename,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_docx_{idx}_{docx_filename}",
                            on_click=register_download,
                            args=(docx_filename,),
                            icon=":material/check:" if is_docx_downloaded else None,
                            icon_position="right",
                            use_container_width=True
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
                    col_dl1, col_dl2, _ = st.columns([1.6, 2.2, 3.2])
                    if has_pdf:
                        assistant_msg["pdf_path"] = response["pdf_path"]
                        pdf_filename = os.path.basename(response["pdf_path"])
                        is_pdf_downloaded = st.session_state.get(f"downloaded_{pdf_filename}", False)
                        with col_dl1:
                            with open(response["pdf_path"], "rb") as f:
                                pdf_bytes = f.read()
                            st.download_button(
                                label="PDF herunterladen",
                                data=pdf_bytes,
                                file_name=pdf_filename,
                                mime="application/pdf",
                                key=f"dl_new_pdf_{pdf_filename}",
                                on_click=register_download,
                                args=(pdf_filename,),
                                icon=":material/check:" if is_pdf_downloaded else None,
                                icon_position="right",
                                use_container_width=True
                            )
                    if has_docx:
                        assistant_msg["docx_path"] = response["docx_path"]
                        docx_filename = os.path.basename(response["docx_path"])
                        is_docx_downloaded = st.session_state.get(f"downloaded_{docx_filename}", False)
                        with col_dl2:
                            with open(response["docx_path"], "rb") as f:
                                docx_bytes = f.read()
                            st.download_button(
                                label="Word / DOCX herunterladen",
                                data=docx_bytes,
                                file_name=docx_filename,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_new_docx_{docx_filename}",
                                on_click=register_download,
                                args=(docx_filename,),
                                icon=":material/check:" if is_docx_downloaded else None,
                                icon_position="right",
                                use_container_width=True
                            )
                st.session_state.messages.append(assistant_msg)

# TAB 2: Liegenschaften & Mieter
elif menu == "Liegenschaften & Mieter":
    active_property_id = st.session_state.get("active_property_id", None)

    # LEVEL 1: Übersicht aller Liegenschaften
    if active_property_id is None:
        col_hdr_main, col_hdr_gear = st.columns([0.84, 0.16])
        with col_hdr_gear:
            st.write("")
            if st.button("Einstellungen", icon=":material/settings:", key="btn_gear_properties", use_container_width=True, help="Einstellungen, Vermieterdaten & Modell öffnen"):
                st.session_state["previous_menu"] = "Liegenschaften & Mieter"
                st.session_state["show_settings"] = True
                st.rerun()
        with col_hdr_main:
            st.header("Liegenschaften & Mieter")
            st.write("Verwalte alle Liegenschaften, Gebäude-Stammdaten und die zugehörigen Mietverhältnisse.")

        properties = get_all_properties()

        # Gesamtkennzahlen
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        total_units = sum(int(p.get("unit_count") or 0) for p in properties)
        total_tenants = sum(int(p.get("tenant_count") or 0) for p in properties)
        total_sqm = sum(float(p.get("total_area_sqm") or 0.0) for p in properties)
        with col_m1:
            st.metric("Liegenschaften", len(properties))
        with col_m2:
            st.metric("Wohneinheiten", total_units)
        with col_m3:
            st.metric("Gesamtfläche", f"{total_sqm:,.0f} m²".replace(",", "."))
        with col_m4:
            st.metric("Aktive Mieter", total_tenants)

        st.markdown("---")

        col_title, col_new_prop = st.columns([0.7, 0.3])
        with col_title:
            st.subheader("Verwaltete Liegenschaften")
        with col_new_prop:
            with st.popover("Neue Liegenschaft anlegen", icon=":material/add_home_work:", use_container_width=True):
                st.markdown("##### Neue Liegenschaft erfassen")
                with st.form("form_add_property", clear_on_submit=True):
                    np_name = st.text_input("Name der Liegenschaft *", placeholder="z. B. Wohnanlage Sonnenhang")
                    np_alias = st.text_input("Optionaler Alias (Kurzname)", placeholder="z. B. Sonnenhang")
                    np_street = st.text_input("Straße & Hausnummer *", placeholder="z. B. Lindenstraße 14")
                    col_np_z, np_city_col = st.columns([1, 2])
                    with col_np_z:
                        np_zip = st.text_input("PLZ *", placeholder="10115")
                    with np_city_col:
                        np_city = st.text_input("Ort *", placeholder="Berlin")
                    np_area = st.number_input("Gesamtwohnfläche (m²)", min_value=0.0, value=200.0, step=10.0)
                    submit_new_prop = st.form_submit_button("Liegenschaft anlegen", icon=":material/save:", type="primary", use_container_width=True)
                    if submit_new_prop:
                        if not np_name.strip() or not np_street.strip() or not np_zip.strip() or not np_city.strip():
                            st.error("Bitte mindestens Name, Straße, PLZ und Ort angeben!")
                        else:
                            new_p_id = add_property(
                                name=np_name.strip(),
                                alias=np_alias.strip() if np_alias.strip() else None,
                                street=np_street.strip(),
                                zip_code=np_zip.strip(),
                                city=np_city.strip(),
                                total_area_sqm=np_area
                            )
                            # Automatisch eine Standard-Wohneinheit anlegen
                            add_unit(new_p_id, "Wohnung 1", np_area, "EG")
                            st.success(f"Liegenschaft '{np_name}' erfolgreich angelegt!")
                            st.rerun()

        if not properties:
            st.info("Aktuell sind noch keine Liegenschaften erfasst. Lege jetzt die erste Liegenschaft an.")
        else:
            for p in properties:
                with st.container(border=True):
                    col_info, col_metrics, col_actions = st.columns([0.45, 0.27, 0.28])
                    with col_info:
                        alias_part = f" · Alias: **{p['alias']}**" if p.get("alias") else ""
                        st.markdown(f"#### {p['name']}{alias_part}")
                        st.caption(f":material/location_on: {p['street']}, {p['zip_code']} {p['city']}")
                    with col_metrics:
                        st.markdown(f"**Mieter:** {p['tenant_count']} &nbsp;|&nbsp; **Einheiten:** {p['unit_count']}")
                        st.caption(f"Gesamtfläche: {float(p.get('total_area_sqm') or 0.0):.1f} m²")
                    with col_actions:
                        st.write("")
                        c_open, c_alias = st.columns([1.2, 0.8])
                        with c_open:
                            if st.button("Öffnen", icon=":material/arrow_forward:", key=f"open_prop_{p['property_id']}", type="primary", use_container_width=True):
                                st.session_state["active_property_id"] = p["property_id"]
                                st.rerun()
                        with c_alias:
                            with st.popover("Alias", icon=":material/label:", use_container_width=True):
                                st.markdown(f"**Alias für {p['name']}**")
                                cur_alias = p.get("alias") or ""
                                new_alias_input = st.text_input("Alias festlegen", value=cur_alias, key=f"input_alias_{p['property_id']}")
                                if st.button("Speichern", key=f"save_alias_{p['property_id']}", icon=":material/save:", type="primary", use_container_width=True):
                                    update_property_alias(p["property_id"], new_alias_input.strip() if new_alias_input.strip() else None)
                                    st.success("Alias aktualisiert!")
                                    st.rerun()

    # LEVEL 2: Detailansicht einer ausgewählten Liegenschaft
    else:
        prop = get_property_by_id(active_property_id)
        if not prop:
            st.session_state["active_property_id"] = None
            st.rerun()

        col_back, col_space, col_gear = st.columns([0.22, 0.62, 0.16])
        with col_back:
            if st.button("Alle Liegenschaften", icon=":material/arrow_back:", key="btn_back_to_properties", use_container_width=True):
                st.session_state["active_property_id"] = None
                st.rerun()
        with col_gear:
            if st.button("Einstellungen", icon=":material/settings:", key="btn_gear_property_detail", use_container_width=True, help="Einstellungen, Vermieterdaten & Modell öffnen"):
                st.session_state["previous_menu"] = "Liegenschaften & Mieter"
                st.session_state["show_settings"] = True
                st.rerun()

        alias_display = f" · Alias: {prop['alias']}" if prop.get("alias") else ""
        st.header(f"{prop['name']}{alias_display}")
        st.caption(f":material/location_on: {prop['street']}, {prop['zip_code']} {prop['city']} · Gesamtfläche: {prop['total_area_sqm']:.1f} m² · Einheiten: {prop['unit_count']} · Mieter: {prop['tenant_count']}")

        prop_tenants = get_tenants_by_property(active_property_id)
        prop_units = get_units_by_property(active_property_id)

        tab_tenants, tab_add_t, tab_edit_t, tab_units, tab_prop_settings = st.tabs([
            "Mieterübersicht",
            "Neuen Mieter anlegen",
            "Mieter bearbeiten & löschen",
            "Wohneinheiten",
            "Liegenschaftsdaten & Alias"
        ])

        with tab_tenants:
            if prop_tenants:
                df = pd.DataFrame(prop_tenants)
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
                    "phone": "Telefon",
                    "email": "E-Mail",
                    "lease_start": "Mietbeginn",
                    "lease_end": "Mietende"
                })
                cols_to_show = [c for c in ["ID", "Anrede", "Vorname", "Nachname", "Wohneinheit", "Fläche (m²)", "Kaltmiete (€)", "Miete / m² (€)", "NK-Vorauszahlung (€)", "Mietbeginn", "Telefon", "E-Mail"] if c in df_display.columns]
                st.dataframe(df_display[cols_to_show], use_container_width=True, hide_index=True)
            else:
                st.info("In dieser Liegenschaft sind aktuell keine Mieter erfasst. Nutze den Reiter 'Neuen Mieter anlegen', um einen Mieter hinzuzufügen.")

        with tab_add_t:
            st.subheader("Neuen Mieter anlegen")
            st.caption(f"Der neue Mieter wird direkt der Liegenschaft '{prop['name']}' zugewiesen.")

            with st.form("form_add_tenant_prop", clear_on_submit=True):
                col_sal, col_fn, col_ln = st.columns([1, 2, 2])
                with col_sal:
                    new_sal = st.selectbox("Anrede", ["Herr", "Frau"])
                with col_fn:
                    new_fn = st.text_input("Vorname *", placeholder="z. B. Sabine")
                with col_ln:
                    new_ln = st.text_input("Nachname *", placeholder="z. B. Meier")

                col_u, col_cr, col_nk = st.columns(3)
                with col_u:
                    unit_options = {f"{u['unit_number']} ({u['area_sqm']:.0f} m² · {u.get('floor') or 'EG'})": u["unit_id"] for u in prop_units} if prop_units else {"Standard": 1}
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

                submitted = st.form_submit_button("Mieter speichern", icon=":material/save:", type="primary", use_container_width=True)
                if submitted:
                    if not new_fn.strip() or not new_ln.strip():
                        st.error("Bitte mindestens Vorname und Nachname ausfüllen!")
                    else:
                        add_new_tenant(
                            first_name=new_fn.strip(),
                            last_name=new_ln.strip(),
                            salutation=new_sal,
                            unit_id=selected_unit_id,
                            cold_rent=new_cr,
                            utility_advance=new_nk,
                            lease_start=str(new_start),
                            lease_end=new_end.strip() or None,
                            email=new_em,
                            phone=new_ph
                        )
                        st.success(f"Mieter {new_sal} {new_fn} {new_ln} wurde erfolgreich angelegt!")
                        st.rerun()

        with tab_edit_t:
            st.subheader("Mieter bearbeiten & löschen")
            if prop_tenants:
                tenant_dict = {f"{t.get('salutation', 'Herr')} {t['first_name']} {t['last_name']} (ID {t['tenant_id']} · {t['unit_number']})": t for t in prop_tenants}
                selected_label = st.selectbox("Wähle einen Mieter zum Bearbeiten", list(tenant_dict.keys()), key="edit_prop_select_tenant")
                t_data = tenant_dict[selected_label]

                with st.form("form_edit_tenant_prop"):
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
                        unit_options = {f"{u['unit_number']} ({u['area_sqm']:.0f} m² · {u.get('floor') or 'EG'})": u["unit_id"] for u in prop_units} if prop_units else {"Standard": 1}
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
                        save_clicked = st.form_submit_button("Änderungen speichern", icon=":material/save:", type="primary", use_container_width=True)
                    with col_del:
                        delete_clicked = st.form_submit_button("Mieter löschen", icon=":material/delete:", use_container_width=True)

                    if save_clicked:
                        if not edit_fn.strip() or not edit_ln.strip():
                            st.error("Vorname und Nachname sind Pflichtfelder!")
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
                            st.success(f"Daten von {edit_sal} {edit_fn} {edit_ln} wurden erfolgreich aktualisiert!")
                            st.rerun()

                    if delete_clicked:
                        delete_tenant(t_data["tenant_id"])
                        st.warning(f"Mieter {t_data['first_name']} {t_data['last_name']} wurde gelöscht.")
                        st.rerun()
            else:
                st.info("Keine Mieter in dieser Liegenschaft vorhanden.")

        with tab_units:
            st.subheader("Wohneinheiten dieser Liegenschaft")
            if prop_units:
                df_u = pd.DataFrame(prop_units).rename(columns={
                    "unit_id": "Einheiten-ID",
                    "unit_number": "Bezeichnung / Nummer",
                    "floor": "Etage",
                    "area_sqm": "Fläche (m²)"
                })
                cols_u = [c for c in ["Einheiten-ID", "Bezeichnung / Nummer", "Etage", "Fläche (m²)"] if c in df_u.columns]
                st.dataframe(df_u[cols_u], use_container_width=True, hide_index=True)
            else:
                st.info("Noch keine separaten Einheiten angelegt.")

            with st.popover("Neue Wohneinheit hinzufügen", icon=":material/add:", use_container_width=True):
                st.markdown("##### Neue Wohneinheit anlegen")
                with st.form("form_add_unit_to_prop", clear_on_submit=True):
                    u_num = st.text_input("Bezeichnung / Nummer *", placeholder="z. B. Wohnung 4 (2. OG)")
                    u_floor = st.text_input("Etage", value="1. OG")
                    u_area = st.number_input("Wohnfläche (m²) *", min_value=10.0, value=75.0, step=5.0)
                    submit_unit = st.form_submit_button("Einheit anlegen", icon=":material/save:", type="primary", use_container_width=True)
                    if submit_unit:
                        if not u_num.strip():
                            st.error("Bitte Bezeichnung angeben!")
                        else:
                            add_unit(active_property_id, u_num.strip(), u_area, u_floor)
                            st.success(f"Wohneinheit '{u_num}' angelegt!")
                            st.rerun()

        with tab_prop_settings:
            st.subheader("Liegenschaftsdaten & Alias")
            st.caption("Bearbeite hier den Alias oder die Stammdaten dieser Liegenschaft.")

            with st.form("form_edit_property_details"):
                ep_name = st.text_input("Name der Liegenschaft *", value=prop["name"])
                ep_alias = st.text_input("Optionaler Alias (Kurzname)", value=prop.get("alias") or "")
                ep_street = st.text_input("Straße & Hausnummer *", value=prop["street"])
                c_ep_z, c_ep_c = st.columns([1, 2])
                with c_ep_z:
                    ep_zip = st.text_input("PLZ *", value=prop["zip_code"])
                with c_ep_c:
                    ep_city = st.text_input("Ort *", value=prop["city"])
                ep_area = st.number_input("Gesamtfläche (m²) *", min_value=0.0, value=float(prop["total_area_sqm"] or 0.0), step=10.0)

                save_p_btn = st.form_submit_button("Liegenschaft speichern", icon=":material/save:", type="primary", use_container_width=True)
                if save_p_btn:
                    if not ep_name.strip() or not ep_street.strip() or not ep_zip.strip() or not ep_city.strip():
                        st.error("Bitte alle Pflichtfelder (Name, Straße, PLZ, Ort) ausfüllen!")
                    else:
                        update_property(
                            property_id=active_property_id,
                            name=ep_name.strip(),
                            alias=ep_alias.strip() if ep_alias.strip() else None,
                            street=ep_street.strip(),
                            zip_code=ep_zip.strip(),
                            city=ep_city.strip(),
                            total_area_sqm=ep_area
                        )
                        st.success("Liegenschaftsdaten erfolgreich gespeichert!")
                        st.rerun()

# TAB 3: Betriebskosten & Finanzen
elif menu == "Betriebskosten & Finanzen":
    col_hdr_main, col_hdr_gear = st.columns([0.84, 0.16])
    with col_hdr_gear:
        st.write("")
        if st.button("Einstellungen", icon=":material/settings:", key="btn_gear_finances", use_container_width=True, help="Einstellungen, Vermieterdaten & Modell öffnen"):
            st.session_state["previous_menu"] = "Betriebskosten & Finanzen"
            st.session_state["show_settings"] = True
            st.rerun()
    with col_hdr_main:
        st.header("Betriebskosten & Finanzen")
        st.caption("Umfassende Verwaltung der umlagefähigen Betriebskosten (BetrKV), mehrjähriger Kostenaufstellungen und der Jahresabrechnungen aller Mieter.")

    available_years = get_available_expense_years()
    current_year = 2026

    # Labels für die Abrechnungsjahre aufbereiten
    year_labels = {}
    for y in available_years:
        if y == current_year:
            lbl = f"{y} (Aktuelles Jahr)"
        elif y == current_year - 1:
            lbl = f"{y} (Vorjahr)"
        else:
            lbl = f"{y}"
        year_labels[lbl] = y

    col_yr_sel, col_yr_add = st.columns([3, 1])
    with col_yr_sel:
        default_lbl = list(year_labels.keys())[0]
        stored_yr = st.session_state.get("active_finance_year", current_year)
        for k, v in year_labels.items():
            if v == stored_yr:
                default_lbl = k
                break

        selected_lbl = st.segmented_control(
            "Abrechnungsjahr auswählen",
            options=list(year_labels.keys()),
            default=default_lbl,
            key="segmented_finance_year"
        )
        selected_year = year_labels.get(selected_lbl, current_year)
        st.session_state["active_finance_year"] = selected_year

    with col_yr_add:
        st.write("")
        with st.popover("Weiteres Jahr anlegen...", use_container_width=True):
            st.markdown("**Neues Abrechnungsjahr anlegen**")
            new_custom_year = st.number_input(
                "Abrechnungsjahr",
                min_value=2020,
                max_value=2035,
                value=max(available_years) + 1 if available_years else 2027,
                step=1,
                key="input_new_custom_year"
            )
            copy_source = st.selectbox(
                "Kosten als Vorlage übernehmen",
                [None] + available_years,
                format_func=lambda x: "Keine Vorlage (leer starten)" if x is None else f"Positionen aus {x} kopieren",
                key="sel_copy_source_year"
            )
            if st.button("Abrechnungsjahr anlegen", type="primary", use_container_width=True, key="btn_init_new_year"):
                target_yr = int(new_custom_year)
                if copy_source:
                    c = copy_expenses_from_year(copy_source, target_yr)
                    st.success(f"{c} Positionen aus {copy_source} für {target_yr} übernommen.")
                else:
                    st.info(f"Jahr {target_yr} ist nun aktiv. Du kannst nun Positionen anlegen.")
                st.session_state["active_finance_year"] = target_yr
                st.rerun()

    # Daten für das gewählte Jahr laden
    expenses = get_expenses_for_year(selected_year)
    statements = get_annual_utility_statements(selected_year)

    total_expenses = sum(float(e["amount"]) for e in expenses)
    total_advances = sum(float(s["prepayments_paid"]) for s in statements)
    total_tenant_share = sum(float(s["tenant_share"]) for s in statements)
    total_balance = sum(float(s["balance"]) for s in statements)

    # Kennzahlen-Leiste
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            label=f"Gesamtkosten ({selected_year})",
            value=f"{total_expenses:,.2f} €",
            help="Summe aller umlagefähigen Betriebskosten der Liegenschaft für dieses Jahr."
        )
    with m2:
        st.metric(
            label="Geleistete Vorauszahlungen",
            value=f"{total_advances:,.2f} €",
            help="Summe aller durch Mieter geleisteten bzw. vertraglich vereinbarten Jahresvorauszahlungen."
        )
    with m3:
        bal_label = "Gesamtsaldo Mieter"
        if total_balance > 0:
            bal_val = f"+{total_balance:,.2f} €"
            bal_delta = "Nachzahlung fällig"
        elif total_balance < 0:
            bal_val = f"-{abs(total_balance):,.2f} €"
            bal_delta = "Guthaben an Mieter"
        else:
            bal_val = "0,00 €"
            bal_delta = "Ausgeglichen"
        st.metric(label=bal_label, value=bal_val, delta=bal_delta, delta_color="inverse" if total_balance > 0 else "normal")
    with m4:
        st.metric(
            label="Kostenpositionen / Mieter",
            value=f"{len(expenses)} Pos. / {len(statements)} Mieter",
            help="Anzahl der verbuchten Belege und beteiligten Mietparteien."
        )
    st.markdown("---")

    # Reiter für Abrechnungen und Kostenbearbeitung
    tab_overview, tab_cost_edit, tab_cost_add = st.tabs([
        "Abrechnungsübersicht der Mieter",
        "Kostenaufstellung & Bearbeitung",
        "Neue Kostenposition erfassen"
    ])

    # 1. TAB: Abrechnungsübersicht der Mieter
    with tab_overview:
        st.subheader(f"Mieter-Abrechnungen für das Jahr {selected_year}")
        st.caption("Aufstellung aller Mieter mit Wohnfläche, Kostenanteil, Vorauszahlungen, Saldo und direktem PDF-Export.")

        if not expenses:
            st.info(f"Für das Abrechnungsjahr {selected_year} wurden noch keine Betriebskosten erfasst. Daher beträgt der berechnete Kostenanteil für alle Mieter 0,00 €.")
            if available_years:
                other_years = [y for y in available_years if y != selected_year]
                if other_years:
                    pref_copy_yr = 2025 if 2025 in other_years else other_years[0]
                    if st.button(f"Kostenpositionen aus {pref_copy_yr} als Vorlage übernehmen", type="primary", key="btn_copy_quick"):
                        count = copy_expenses_from_year(pref_copy_yr, selected_year)
                        st.success(f"{count} Positionen aus {pref_copy_yr} erfolgreich übernommen.")
                        st.rerun()

        if statements:
            df_statements = []
            for s in statements:
                bal = float(s["balance"])
                if bal > 0:
                    bal_formatted = f"+{bal:,.2f} € (Nachzahlung)"
                elif bal < 0:
                    bal_formatted = f"-{abs(bal):,.2f} € (Guthaben)"
                else:
                    bal_formatted = "0,00 € (Ausgeglichen)"

                df_statements.append({
                    "Mieter": s["full_name"],
                    "Wohneinheit": s["unit_number"],
                    "Fläche": f"{s['area_sqm']:.1f} m²",
                    "Kostenanteil": f"{s['tenant_share']:,.2f} €",
                    "Vorauszahlungen": f"{s['prepayments_paid']:,.2f} €",
                    "Abrechnungssaldo": bal_formatted,
                    "Ergebnis": s["status_label"]
                })

            st.dataframe(pd.DataFrame(df_statements), use_container_width=True, hide_index=True)

            # Einzelausdruck & Abrechnungsbrief (DIN 5008)
            st.markdown("")
            with st.container(border=True):
                st.markdown("**Einzelausdruck & Abrechnungsbrief (DIN 5008)**")
                st.caption("Wähle einen Mieter aus, um die vollständige, rechtssichere Nebenkostenabrechnung als druckfertiges PDF zu erstellen.")

                col_t_sel, col_t_btn = st.columns([3, 1.5])
                with col_t_sel:
                    tenant_map = {f"{s['full_name']} ({s['unit_number']})": s["tenant_id"] for s in statements}
                    selected_tenant_label = st.selectbox("Mieter auswählen", list(tenant_map.keys()), key=f"sel_t_bill_{selected_year}")
                    selected_tenant_id = tenant_map.get(selected_tenant_label)
                with col_t_btn:
                    st.write("")
                    st.write("")
                    btn_gen_statement = st.button("Abrechnung generieren", type="primary", use_container_width=True, key=f"btn_gen_stmt_{selected_year}")

                gen_state_key = f"generated_bill_{selected_year}_{selected_tenant_id}"
                if btn_gen_statement and selected_tenant_id:
                    with st.spinner("Erstelle DIN 5008 PDF-Abrechnung..."):
                        bill_res = create_utility_statement_for_tenant(selected_tenant_id, selected_year)
                        st.session_state[gen_state_key] = bill_res

                saved_bill = st.session_state.get(gen_state_key)
                if saved_bill and os.path.exists(saved_bill.get("pdf_path", "")):
                    with open(saved_bill["pdf_path"], "rb") as f:
                        pdf_data = f.read()
                    pdf_filename = os.path.basename(saved_bill["pdf_path"])
                    st.success(f"Abrechnung für {saved_bill['tenant']['first_name']} {saved_bill['tenant']['last_name']} ({selected_year}) erfolgreich erstellt.")
                    st.download_button(
                        label=f"PDF herunterladen ({pdf_filename})",
                        data=pdf_data,
                        file_name=pdf_filename,
                        mime="application/pdf",
                        key=f"dl_stmt_btn_{selected_year}_{selected_tenant_id}"
                    )
        else:
            st.info("Aktuell sind noch keine Mieter in der Liegenschaft erfasst.")

    # 2. TAB: Kostenaufstellung & Bearbeitung
    with tab_cost_edit:
        st.subheader(f"Kostenaufstellung für das Abrechnungsjahr {selected_year}")
        st.caption("Hier kannst du alle gebuchten Betriebskosten einsehen, Beträge und Umlageschlüssel anpassen oder Positionen entfernen.")

        if expenses:
            key_names = {"sqm": "Wohnfläche (nach m²)", "units": "Wohneinheiten (pro Einheit)", "direct": "Direktzuordnung"}
            df_exp_data = []
            for e in expenses:
                df_exp_data.append({
                    "ID": e["id"],
                    "Kostenart (BetrKV)": e["category"],
                    "Details / Beleg": e["description"] or "-",
                    "Betrag": f"{float(e['amount']):,.2f} €",
                    "Umlageschlüssel": key_names.get(e["allocation_key"], e["allocation_key"]),
                    "Belegdatum": e["receipt_date"] or "-",
                    "Liegenschaft": e["property_name"]
                })
            st.dataframe(pd.DataFrame(df_exp_data), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("Kostenposition bearbeiten oder löschen")

            exp_select_options = {
                f"#{e['id']} | {e['category']} — {float(e['amount']):,.2f} € ({e['description'] or 'Keine Details'})": e
                for e in expenses
            }
            sel_exp_label = st.selectbox(
                "Position zur Bearbeitung auswählen",
                list(exp_select_options.keys()),
                key=f"sel_edit_exp_{selected_year}"
            )
            cur_exp = exp_select_options[sel_exp_label]

            with st.form(f"form_edit_expense_{cur_exp['id']}"):
                col_ecat, col_eamt = st.columns([2, 1])
                with col_ecat:
                    betrkv_cats = [
                        "Grundsteuer", "Gebäudeversicherung", "Müllabfuhr", "Allgemeinstrom",
                        "Schornsteinfeger / Wartung", "Hausmeister / Gartenpflege", "Wasser / Abwasser",
                        "Straßenreinigung", "Aufzugswartung", "Kabelanschluss / TV", "Sonstige Betriebskosten"
                    ]
                    cat_default_idx = betrkv_cats.index(cur_exp["category"]) if cur_exp["category"] in betrkv_cats else len(betrkv_cats) - 1
                    edit_cat = st.selectbox("Kostenart (BetrKV)", betrkv_cats, index=cat_default_idx)
                with col_eamt:
                    edit_amount = st.number_input("Betrag (€)", min_value=0.0, value=float(cur_exp["amount"]), step=10.0, format="%.2f")

                col_edesc, col_ekey, col_edate = st.columns([2, 1.5, 1])
                with col_edesc:
                    edit_desc = st.text_input("Details / Belegnummer", value=str(cur_exp["description"] or ""))
                with col_ekey:
                    key_opts = {"sqm": "Wohnfläche (nach m²)", "units": "Wohneinheiten (pro Einheit)", "direct": "Direkte Zuordnung"}
                    key_keys = list(key_opts.keys())
                    key_idx = key_keys.index(cur_exp["allocation_key"]) if cur_exp["allocation_key"] in key_keys else 0
                    edit_key = st.selectbox("Umlageschlüssel", key_keys, index=key_idx, format_func=lambda x: key_opts[x])
                with col_edate:
                    cur_d_str = str(cur_exp["receipt_date"] or f"{selected_year}-01-01")[:10]
                    try:
                        parsed_d = datetime.strptime(cur_d_str, "%Y-%m-%d").date()
                    except Exception:
                        parsed_d = date(selected_year, 1, 1)
                    edit_date = st.date_input("Belegdatum", value=parsed_d)

                c_save, c_del = st.columns([3, 1])
                with c_save:
                    btn_save = st.form_submit_button("Änderungen speichern", type="primary", use_container_width=True)
                with c_del:
                    btn_del = st.form_submit_button("Position löschen", use_container_width=True)

                if btn_save:
                    update_expense(
                        expense_id=cur_exp["id"],
                        category=edit_cat,
                        amount=edit_amount,
                        allocation_key=edit_key,
                        description=edit_desc,
                        receipt_date=str(edit_date)
                    )
                    st.success(f"Kostenposition #{cur_exp['id']} ({edit_cat}) wurde erfolgreich aktualisiert.")
                    st.rerun()

                if btn_del:
                    delete_expense(cur_exp["id"])
                    st.warning(f"Kostenposition #{cur_exp['id']} ({cur_exp['category']}) wurde gelöscht.")
                    st.rerun()
        else:
            st.info(f"Für das Abrechnungsjahr {selected_year} sind noch keine Kostenpositionen erfasst.")
            if available_years:
                other_years = [y for y in available_years if y != selected_year]
                if other_years:
                    pref_copy_yr = 2025 if 2025 in other_years else other_years[0]
                    if st.button(f"Kostenpositionen aus {pref_copy_yr} als Vorlage kopieren", type="primary", key="btn_copy_template_edit"):
                        count = copy_expenses_from_year(pref_copy_yr, selected_year)
                        st.success(f"{count} Positionen aus {pref_copy_yr} für {selected_year} übernommen.")
                        st.rerun()

    # 3. TAB: Neue Kostenposition erfassen
    with tab_cost_add:
        st.subheader("Neue Betriebskostenposition erfassen")
        st.caption(f"Trage eine neue Ausgabe für das Abrechnungsjahr {selected_year} nach Maßgabe der Betriebskostenverordnung (BetrKV) ein.")

        all_props = query_db("SELECT id, name FROM properties ORDER BY name ASC;")
        prop_options = {p["name"]: p["id"] for p in all_props} if all_props else {"Liegenschaft": 1}

        with st.form("form_add_new_expense", clear_on_submit=True):
            col_aprop, col_ayr = st.columns([2, 1])
            with col_aprop:
                add_prop_label = st.selectbox("Liegenschaft", list(prop_options.keys()))
                add_prop_id = prop_options[add_prop_label]
            with col_ayr:
                add_yr = st.number_input("Abrechnungsjahr", min_value=2020, max_value=2035, value=selected_year, step=1)

            col_acat, col_aamt = st.columns([2, 1])
            with col_acat:
                betrkv_standard = [
                    "Grundsteuer", "Gebäudeversicherung", "Müllabfuhr", "Allgemeinstrom",
                    "Schornsteinfeger / Wartung", "Hausmeister / Gartenpflege", "Wasser / Abwasser",
                    "Straßenreinigung", "Aufzugswartung", "Kabelanschluss / TV", "Sonstige Betriebskosten"
                ]
                selected_cat_type = st.selectbox("Kostenart (BetrKV)", betrkv_standard + ["Eigene Kostenart eingeben..."])
                if selected_cat_type == "Eigene Kostenart eingeben...":
                    final_cat = st.text_input("Bezeichnung der Kostenart *", placeholder="z. B. Legionellenprüfung")
                else:
                    final_cat = selected_cat_type
            with col_aamt:
                add_amt = st.number_input("Rechnungsbetrag (€) *", min_value=0.01, value=100.0, step=10.0, format="%.2f")

            col_adesc, col_akey, col_adate = st.columns([2, 1.5, 1])
            with col_adesc:
                add_desc = st.text_input("Details / Rechnungsnummer", placeholder="z. B. Jahresabrechnung BSR Beleg-Nr. 2026-44")
            with col_akey:
                key_dict = {
                    "sqm": "Wohnfläche (nach m²)",
                    "units": "Wohneinheiten (pro Einheit)",
                    "direct": "Direkte Zuordnung"
                }
                add_key = st.selectbox("Umlageschlüssel", list(key_dict.keys()), format_func=lambda x: key_dict[x])
            with col_adate:
                try:
                    default_date = date(int(add_yr), date.today().month, min(date.today().day, 28))
                except Exception:
                    default_date = date(int(add_yr), 1, 1)
                add_date = st.date_input("Belegdatum", value=default_date)

            submit_expense = st.form_submit_button("Kostenposition speichern", type="primary", use_container_width=True)
            if submit_expense:
                if not final_cat or not final_cat.strip():
                    st.error("Bitte gib eine gültige Kostenart ein.")
                else:
                    add_expense(
                        property_id=add_prop_id,
                        year=int(add_yr),
                        category=final_cat.strip(),
                        amount=float(add_amt),
                        allocation_key=add_key,
                        description=add_desc.strip(),
                        receipt_date=str(add_date)
                    )
                    st.success(f"Kostenposition '{final_cat}' über {add_amt:,.2f} € erfolgreich für {int(add_yr)} gespeichert.")
                    st.session_state["active_finance_year"] = int(add_yr)
                    st.rerun()
