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
    delete_property,
    get_tenants_by_property,
    get_units_by_property,
    add_unit,
    update_unit,
    parse_co_tenants,
    save_imported_property_data,
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
from agent.doc_parser import extract_text_from_pdf, parse_property_document
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

@st.cache_data(ttl=10)
def get_cached_ollama_status(url: str):
    """Gibt den Status des Ollama-Servers mit kurzem Cache (10s) zurück."""
    return check_ollama_status(url)

existing_props = query_db("SELECT COUNT(*) as cnt FROM properties;")
if not existing_props or existing_props[0]["cnt"] == 0:
    seed()

# -------------------------------------------------------------
# 1. Flash-Meldungen & Toast-Feedback System
# -------------------------------------------------------------
def set_flash_message(message: str, icon: str = "✅"):
    st.session_state["flash_message"] = {"message": message, "icon": icon}

def render_flash_message_if_any():
    if "flash_message" in st.session_state and st.session_state["flash_message"]:
        msg_obj = st.session_state.pop("flash_message")
        st.toast(msg_obj["message"], icon=msg_obj.get("icon", "✅"))

# -------------------------------------------------------------
# 2. Erkennung ungespeicherter Änderungen (Dirty-Form-Tracking)
# -------------------------------------------------------------
def check_tenant_unsaved(t_data) -> bool:
    if not t_data:
        return False
    tid = t_data.get("tenant_id")
    if not tid or not any(k.startswith("te_") and k.endswith(f"_{tid}") for k in st.session_state):
        return False

    orig_sal = t_data.get("salutation", "Herr") or "Herr"
    orig_fn = t_data.get("first_name", "") or ""
    orig_ln = t_data.get("last_name", "") or ""
    orig_cr = float(t_data.get("cold_rent") or 0.0)
    orig_nk = float(t_data.get("utility_advance") or 0.0)
    orig_start = str(t_data.get("lease_start") or "")[:10]
    orig_end = str(t_data.get("lease_end") or "")
    orig_em = str(t_data.get("email") or "")
    orig_ph = str(t_data.get("phone") or "")

    co_list = parse_co_tenants(t_data.get("co_tenants"))
    co1 = co_list[0] if co_list else {}
    orig_cosal = co1.get("salutation", "Frau") or "Frau"
    orig_cofn = co1.get("first_name", "") or ""
    orig_coln = co1.get("last_name", "") or ""

    if st.session_state.get(f"te_sal_{tid}") != orig_sal:
        return True
    if str(st.session_state.get(f"te_fn_{tid}", "")).strip() != orig_fn.strip():
        return True
    if str(st.session_state.get(f"te_ln_{tid}", "")).strip() != orig_ln.strip():
        return True
    if abs(float(st.session_state.get(f"te_cr_{tid}", 0.0) or 0.0) - orig_cr) > 0.01:
        return True
    if abs(float(st.session_state.get(f"te_nk_{tid}", 0.0) or 0.0) - orig_nk) > 0.01:
        return True
    if str(st.session_state.get(f"te_em_{tid}", "")).strip() != orig_em.strip():
        return True
    if str(st.session_state.get(f"te_ph_{tid}", "")).strip() != orig_ph.strip():
        return True
    if str(st.session_state.get(f"te_end_{tid}", "")).strip() != orig_end.strip():
        return True
    if str(st.session_state.get(f"te_start_{tid}", ""))[:10] != orig_start:
        return True
    if str(st.session_state.get(f"te_cofn_{tid}", "")).strip() != orig_cofn.strip():
        return True
    if str(st.session_state.get(f"te_coln_{tid}", "")).strip() != orig_coln.strip():
        return True
    if (orig_cofn or orig_coln) and st.session_state.get(f"te_cosal_{tid}") != orig_cosal:
        return True
    return False

def check_property_unsaved(prop) -> bool:
    if not prop:
        return False
    pid = prop.get("id") or prop.get("property_id")
    if not pid or not any(k.startswith("pe_") and k.endswith(f"_{pid}") for k in st.session_state):
        return False

    if str(st.session_state.get(f"pe_name_{pid}", "")).strip() != prop["name"].strip():
        return True
    if str(st.session_state.get(f"pe_alias_{pid}", "")).strip() != str(prop.get("alias") or "").strip():
        return True
    if str(st.session_state.get(f"pe_street_{pid}", "")).strip() != prop["street"].strip():
        return True
    if str(st.session_state.get(f"pe_zip_{pid}", "")).strip() != prop["zip_code"].strip():
        return True
    if str(st.session_state.get(f"pe_city_{pid}", "")).strip() != prop["city"].strip():
        return True
    if abs(float(st.session_state.get(f"pe_area_{pid}", 0.0) or 0.0) - float(prop.get("total_area_sqm") or 0.0)) > 0.1:
        return True
    if str(st.session_state.get(f"pe_by_{pid}", "")).strip() != str(prop.get("construction_year") or "").strip():
        return True
    if str(st.session_state.get(f"pe_ht_{pid}", "")).strip() != str(prop.get("heating_type") or "").strip():
        return True
    if str(st.session_state.get(f"pe_es_{pid}", "")).strip() != str(prop.get("energy_source") or "").strip():
        return True
    return False

def check_settings_unsaved(current_settings) -> bool:
    if not current_settings:
        return False
    if "set_lname" not in st.session_state:
        return False

    cur_sel_type = st.session_state.get("settings_landlord_type_selector")
    if cur_sel_type:
        cur_type = "private" if cur_sel_type == "Privater Vermieter" else "property_management"
        if cur_type != current_settings.get("landlord_type", "private"):
            return True

    if str(st.session_state.get("set_lname", "")).strip() != str(current_settings.get("landlord_name", "")).strip():
        return True
    if str(st.session_state.get("set_lperson", "")).strip() != str(current_settings.get("landlord_contact_person", "")).strip():
        return True
    if str(st.session_state.get("set_lstreet", "")).strip() != str(current_settings.get("landlord_street", "")).strip():
        return True
    if str(st.session_state.get("set_lzip", "")).strip() != str(current_settings.get("landlord_zip", "")).strip():
        return True
    if str(st.session_state.get("set_lcity", "")).strip() != str(current_settings.get("landlord_city", "")).strip():
        return True
    if str(st.session_state.get("set_lphone", "")).strip() != str(current_settings.get("landlord_phone", "")).strip():
        return True
    if str(st.session_state.get("set_lemail", "")).strip() != str(current_settings.get("landlord_email", "")).strip():
        return True
    if str(st.session_state.get("set_liban", "")).strip() != str(current_settings.get("landlord_iban", "")).strip():
        return True
    if str(st.session_state.get("set_lbank", "")).strip() != str(current_settings.get("landlord_bank_name", "")).strip():
        return True
    return False

def has_unsaved_tenant_in_active_property() -> bool:
    pid = st.session_state.get("active_property_id")
    if not pid:
        return False
    tenants = get_tenants_by_property(pid)
    return any(check_tenant_unsaved(t) for t in tenants)

def has_unsaved_property_in_active_property() -> bool:
    pid = st.session_state.get("active_property_id")
    if not pid:
        return False
    prop = get_property_by_id(pid)
    return check_property_unsaved(prop) if prop else False

def has_unsaved_lm_changes() -> bool:
    return has_unsaved_tenant_in_active_property() or has_unsaved_property_in_active_property()

def has_unsaved_settings_changes() -> bool:
    cur_s = get_all_settings()
    return check_settings_unsaved(cur_s)

def has_any_unsaved_changes() -> bool:
    return has_unsaved_lm_changes() or has_unsaved_settings_changes()

def save_current_unsaved():
    # 1. Liegenschaftsdaten speichern falls ungespeichert
    pid = st.session_state.get("active_property_id")
    if pid:
        prop = get_property_by_id(pid)
        if prop and check_property_unsaved(prop):
            update_property(
                property_id=pid,
                name=str(st.session_state.get(f"pe_name_{pid}", prop["name"])).strip(),
                alias=str(st.session_state.get(f"pe_alias_{pid}", prop.get("alias") or "")).strip() or None,
                street=str(st.session_state.get(f"pe_street_{pid}", prop["street"])).strip(),
                zip_code=str(st.session_state.get(f"pe_zip_{pid}", prop["zip_code"])).strip(),
                city=str(st.session_state.get(f"pe_city_{pid}", prop["city"])).strip(),
                total_area_sqm=float(st.session_state.get(f"pe_area_{pid}", prop.get("total_area_sqm") or 0.0) or 0.0),
                construction_year=str(st.session_state.get(f"pe_by_{pid}", prop.get("construction_year") or "")).strip() or None,
                heating_type=str(st.session_state.get(f"pe_ht_{pid}", prop.get("heating_type") or "")).strip() or None,
                energy_source=str(st.session_state.get(f"pe_es_{pid}", prop.get("energy_source") or "")).strip() or None
            )
            for k in [f"pe_name_{pid}", f"pe_alias_{pid}", f"pe_street_{pid}", f"pe_zip_{pid}", f"pe_city_{pid}", f"pe_area_{pid}", f"pe_by_{pid}", f"pe_ht_{pid}", f"pe_es_{pid}"]:
                st.session_state.pop(k, None)

        # 2. Mieter speichern falls ungespeichert
        prop_tenants = get_tenants_by_property(pid)
        for t in prop_tenants:
            if check_tenant_unsaved(t):
                tid = t["tenant_id"]
                co_list = []
                co_fn = str(st.session_state.get(f"te_cofn_{tid}", "")).strip()
                co_ln = str(st.session_state.get(f"te_coln_{tid}", "")).strip()
                if co_fn or co_ln:
                    co_list.append({
                        "salutation": st.session_state.get(f"te_cosal_{tid}", "Frau"),
                        "first_name": co_fn,
                        "last_name": co_ln,
                        "email": "",
                        "phone": ""
                    })
                update_tenant(
                    tenant_id=tid,
                    first_name=str(st.session_state.get(f"te_fn_{tid}", t["first_name"])).strip(),
                    last_name=str(st.session_state.get(f"te_ln_{tid}", t["last_name"])).strip(),
                    salutation=st.session_state.get(f"te_sal_{tid}", t.get("salutation", "Herr")),
                    unit_id=st.session_state.get(f"te_unit_{tid}", t["unit_id"]),
                    cold_rent=float(st.session_state.get(f"te_cr_{tid}", t.get("cold_rent") or 0.0) or 0.0),
                    utility_advance=float(st.session_state.get(f"te_nk_{tid}", t.get("utility_advance") or 0.0) or 0.0),
                    lease_start=str(st.session_state.get(f"te_start_{tid}", str(t.get("lease_start") or "2025-01-01")[:10])),
                    lease_end=str(st.session_state.get(f"te_end_{tid}", t.get("lease_end") or "")).strip() or None,
                    email=str(st.session_state.get(f"te_em_{tid}", t.get("email") or "")).strip(),
                    phone=str(st.session_state.get(f"te_ph_{tid}", t.get("phone") or "")).strip(),
                    is_active=1,
                    co_tenants=co_list
                )
                for k in [f"te_sal_{tid}", f"te_fn_{tid}", f"te_ln_{tid}", f"te_unit_{tid}", f"te_cr_{tid}", f"te_nk_{tid}", f"te_start_{tid}", f"te_end_{tid}", f"te_em_{tid}", f"te_ph_{tid}", f"te_cosal_{tid}", f"te_cofn_{tid}", f"te_coln_{tid}"]:
                    st.session_state.pop(k, None)

    # 3. Einstellungen speichern falls ungespeichert
    cur_settings = get_all_settings()
    if check_settings_unsaved(cur_settings):
        is_priv = (st.session_state.get("settings_landlord_type_selector") == "Privater Vermieter")
        lname = str(st.session_state.get("set_lname", cur_settings.get("landlord_name", ""))).strip()
        save_dict = {
            "landlord_type": "private" if is_priv else "property_management",
            "landlord_name": lname,
            "landlord_contact_person": str(st.session_state.get("set_lperson", cur_settings.get("landlord_contact_person", ""))).strip(),
            "landlord_street": str(st.session_state.get("set_lstreet", cur_settings.get("landlord_street", ""))).strip(),
            "landlord_zip": str(st.session_state.get("set_lzip", cur_settings.get("landlord_zip", ""))).strip(),
            "landlord_city": str(st.session_state.get("set_lcity", cur_settings.get("landlord_city", ""))).strip(),
            "landlord_phone": str(st.session_state.get("set_lphone", cur_settings.get("landlord_phone", ""))).strip(),
            "landlord_email": str(st.session_state.get("set_lemail", cur_settings.get("landlord_email", ""))).strip(),
            "landlord_account_holder": str(st.session_state.get("set_lholder", cur_settings.get("landlord_account_holder", ""))).strip() or lname,
            "landlord_bank_name": str(st.session_state.get("set_lbank", cur_settings.get("landlord_bank_name", ""))).strip(),
            "landlord_iban": str(st.session_state.get("set_liban", cur_settings.get("landlord_iban", ""))).strip(),
            "landlord_bic": str(st.session_state.get("set_lbic", cur_settings.get("landlord_bic", ""))).strip(),
            "landlord_tax_id": str(st.session_state.get("set_ltax", cur_settings.get("landlord_tax_id", ""))).strip()
        }
        if "set_letter_city" in st.session_state:
            save_dict["letter_city"] = str(st.session_state.get("set_letter_city", "")).strip()
        save_settings(save_dict)
        for k in ["set_lname", "set_lperson", "set_lstreet", "set_lzip", "set_lcity", "set_lphone", "set_lemail", "set_lholder", "set_lbank", "set_liban", "set_lbic", "set_ltax", "set_letter_city"]:
            st.session_state.pop(k, None)

def discard_current_unsaved():
    keys_to_clear = [
        k for k in list(st.session_state.keys()) 
        if k.startswith("te_") or k.startswith("pe_") or k.startswith("set_")
    ]
    for k in keys_to_clear:
        st.session_state.pop(k, None)

@st.dialog("Ungespeicherte Änderungen", width="medium")
def confirm_unsaved_dialog():
    st.warning("⚠️ **Du hast Änderungen vorgenommen, die noch nicht gespeichert wurden.**\n\nWenn du diesen Bereich verlässt, gehen deine Eingaben verloren. Was möchtest du tun?")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Änderungen speichern", type="primary", use_container_width=True, icon=":material/save:"):
            save_current_unsaved()
            set_flash_message("Änderungen wurden erfolgreich gespeichert!")
            st.session_state["show_unsaved_dialog"] = False
            pending = st.session_state.pop("pending_nav", None)
            if pending:
                if pending["type"] == "menu":
                    st.session_state["current_active_menu"] = pending["target"]
                    st.session_state["sidebar_nav_selection"] = pending["target"]
                    st.session_state["show_settings"] = False
                elif pending["type"] == "settings":
                    st.session_state["show_settings"] = True
                    st.session_state["previous_menu"] = pending.get("previous", "Liegenschaften & Mieter")
                elif pending["type"] == "back_to_properties":
                    st.session_state["active_property_id"] = None
                    st.session_state["prop_detail_tab_idx"] = 0
                    st.session_state.pop("prop_detail_active_tab", None)
                elif pending["type"] == "leave_settings":
                    st.session_state["show_settings"] = False
                elif pending["type"] == "tab":
                    st.session_state["prop_detail_tab_idx"] = pending.get("target_idx", 0)
            st.rerun()
    with c2:
        if st.button("Änderungen verwerfen", use_container_width=True, icon=":material/delete_forever:"):
            discard_current_unsaved()
            set_flash_message("Änderungen wurden verworfen.", icon="ℹ️")
            st.session_state["show_unsaved_dialog"] = False
            pending = st.session_state.pop("pending_nav", None)
            if pending:
                if pending["type"] == "menu":
                    st.session_state["current_active_menu"] = pending["target"]
                    st.session_state["sidebar_nav_selection"] = pending["target"]
                    st.session_state["show_settings"] = False
                elif pending["type"] == "settings":
                    st.session_state["show_settings"] = True
                    st.session_state["previous_menu"] = pending.get("previous", "Liegenschaften & Mieter")
                elif pending["type"] == "back_to_properties":
                    st.session_state["active_property_id"] = None
                    st.session_state["prop_detail_tab_idx"] = 0
                    st.session_state.pop("prop_detail_active_tab", None)
                elif pending["type"] == "leave_settings":
                    st.session_state["show_settings"] = False
                elif pending["type"] == "tab":
                    st.session_state["prop_detail_tab_idx"] = pending.get("target_idx", 0)
            st.rerun()
    with c3:
        if st.button("Weiter bearbeiten", use_container_width=True, icon=":material/edit:"):
            st.session_state["show_unsaved_dialog"] = False
            st.session_state.pop("pending_nav", None)
            st.session_state["sidebar_nav_selection"] = st.session_state.get("current_active_menu", "KI-Assistent & Schriftverkehr")
            st.rerun()

# Flash-Toast anzeigen falls vorhanden
render_flash_message_if_any()

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

    /* Sidebar Navigation als moderne, großflächige Bereiche (Kacheln/Cards) */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] {
        width: 100% !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] > div {
        gap: 12px !important;
        width: 100% !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label {
        display: flex !important;
        flex-direction: column !important;
        align-items: flex-start !important;
        width: 100% !important;
        padding: 13px 15px !important;
        margin: 0 !important;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: #ffffff !important;
        cursor: pointer !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    }
    /* Kleinen Radio-Punkt ausblenden */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:first-child {
        display: none !important;
    }
    /* Titel des Bereichs */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:nth-child(2) {
        width: 100% !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        color: #0f172a !important;
        line-height: 1.35 !important;
    }
    /* Caption / Unterzeile des Bereichs */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:nth-child(3),
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label [data-testid="stCaptionContainer"] {
        font-size: 0.74rem !important;
        font-weight: 400 !important;
        color: #64748b !important;
        margin-top: 3px !important;
        line-height: 1.25 !important;
    }
    /* Hover-Effekt */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
        background-color: #f8fafc !important;
        border-color: #94a3b8 !important;
        transform: translateY(-1.5px) !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.07) !important;
    }
    /* Aktiver ausgewählter Bereich */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {
        background-color: #eff6ff !important;
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 1.5px #3b82f6, 0 4px 12px rgba(37, 99, 235, 0.12) !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) > div:nth-child(2) {
        color: #1d4ed8 !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) [data-testid="stCaptionContainer"] {
        color: #2563eb !important;
    }
    @media (prefers-color-scheme: dark) {
        div[data-testid="stSidebar"] div[data-testid="stRadio"] label {
            background-color: #1e293b !important;
            border-color: #334155 !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3) !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:nth-child(2) {
            color: #f1f5f9 !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stRadio"] label [data-testid="stCaptionContainer"] {
            color: #94a3b8 !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
            background-color: #263349 !important;
            border-color: #64748b !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35) !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {
            background-color: #1e3a5f !important;
            border-color: #60a5fa !important;
            box-shadow: 0 0 0 1.5px #60a5fa, 0 4px 14px rgba(37, 99, 235, 0.25) !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) > div:nth-child(2) {
            color: #93c5fd !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) [data-testid="stCaptionContainer"] {
            color: #bfdbfe !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("🏢 PropMAgent")
    st.caption("Lokaler KI-Immobilienassistent")
    st.markdown("---")
    
    has_unsaved_lm = has_unsaved_lm_changes()
    has_unsaved_set = has_unsaved_settings_changes()
    has_any_unsaved = has_unsaved_lm or has_unsaved_set

    if "current_active_menu" not in st.session_state:
        st.session_state["current_active_menu"] = "KI-Assistent & Schriftverkehr"
    if "sidebar_nav_selection" not in st.session_state:
        st.session_state["sidebar_nav_selection"] = st.session_state["current_active_menu"]

    options_list = ["KI-Assistent & Schriftverkehr", "Liegenschaften & Mieter", "Betriebskosten & Finanzen"]
    try:
        def_idx = options_list.index(st.session_state["sidebar_nav_selection"])
    except ValueError:
        def_idx = 0

    def nav_format_func(x):
        icons = {
            "KI-Assistent & Schriftverkehr": "🤖  KI-Assistent & Schriftverkehr",
            "Liegenschaften & Mieter": "🏢  Liegenschaften & Mieter",
            "Betriebskosten & Finanzen": "📊  Betriebskosten & Finanzen"
        }
        base = icons.get(x, x)
        if x == "Liegenschaften & Mieter" and has_unsaved_lm:
            return f"{base}  🔴"
        return base

    selected_menu = st.radio(
        "Navigation",
        options=options_list,
        index=def_idx,
        captions=["Briefe, Vorlagen & KI-Chat", "Objekte, Einheiten & Mietverträge", "Kostenaufstellung & Abrechnungen"],
        format_func=nav_format_func,
        label_visibility="collapsed",
        key="main_sidebar_radio"
    )

    if selected_menu != st.session_state["current_active_menu"]:
        if has_any_unsaved:
            st.session_state["pending_nav"] = {"type": "menu", "target": selected_menu}
            st.session_state["show_unsaved_dialog"] = True
            st.session_state["sidebar_nav_selection"] = st.session_state["current_active_menu"]
            st.rerun()
        else:
            st.session_state["current_active_menu"] = selected_menu
            st.session_state["sidebar_nav_selection"] = selected_menu
            st.session_state["show_settings"] = False

    menu = st.session_state["current_active_menu"]

    current_settings = get_all_settings()
    model_name = current_settings.get("ollama_model", "llama3")
    ollama_url_cfg = current_settings.get("ollama_url", "http://localhost:11434")
    sb_status = get_cached_ollama_status(ollama_url_cfg)
    sb_models = [m.lower() for m in sb_status.get("models", [])]
    sb_clean = model_name.strip().lower()
    is_sb_ready = any(
        sb_clean == m or
        f"{sb_clean}:latest" == m or
        m.startswith(f"{sb_clean}:") or
        sb_clean.startswith(m.split(":")[0])
        for m in sb_models
    )

    st.markdown("---")
    if sb_status["online"] and is_sb_ready:
        st.caption(f"🟢 KI aktiv: **{model_name}** (lokal)")
    elif sb_status["online"]:
        st.caption(f"🟡 Modell: **{model_name}** (Download ausstehend)")
    else:
        st.caption(f"⚪ KI-Modus: **Vorlagen-Fallback** (Ollama offline)")

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
        back_btn_label = f"Zurück{' 🔴' if has_unsaved_settings_changes() else ''}"
        if st.button(back_btn_label, icon=":material/arrow_back:", key="settings_top_back_btn", use_container_width=True, help="Zurück zum vorherigen Bereich"):
            if has_unsaved_settings_changes():
                st.session_state["pending_nav"] = {"type": "leave_settings"}
                st.session_state["show_unsaved_dialog"] = True
                st.rerun()
            else:
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
    cur_model = current_settings.get("ollama_model", "llama3")
    ollama_url = current_settings.get("ollama_url", "http://localhost:11434")
    ollama_status = get_cached_ollama_status(ollama_url)
    installed_models = ollama_status.get("models", [])
    installed_lower = [m.lower() for m in installed_models]
    cur_model_clean = cur_model.strip().lower()
    is_model_installed = any(
        cur_model_clean == m or
        f"{cur_model_clean}:latest" == m or
        m.startswith(f"{cur_model_clean}:") or
        cur_model_clean.startswith(m.split(":")[0])
        for m in installed_lower
    )

    has_set_dirty = has_unsaved_settings_changes()
    set_tab_label = f"Vermieterdaten & Bankverbindung{' 🔴' if has_set_dirty else ''}"
    set_tabs_list = [
        set_tab_label,
        "KI & Sprachmodell (Ollama)",
        "Brief- & Abrechnungsvorgaben",
        "System & Datensicherung"
    ]

    prev_set_idx = st.session_state.get("settings_tab_idx", 0)
    new_set_idx = prev_set_idx
    if "settings_active_tab" in st.session_state:
        cur_set_lbl = st.session_state["settings_active_tab"]
        if "Vermieterdaten" in cur_set_lbl or "Bankverbindung" in cur_set_lbl:
            new_set_idx = 0
        elif "KI" in cur_set_lbl:
            new_set_idx = 1
        elif "Brief" in cur_set_lbl:
            new_set_idx = 2
        elif "System" in cur_set_lbl:
            new_set_idx = 3

    st.session_state["settings_tab_idx"] = new_set_idx
    active_set_label = set_tabs_list[new_set_idx]
    st.session_state["settings_active_tab"] = active_set_label

    tab_vermieter, tab_ki, tab_briefe, tab_system = st.tabs(
        set_tabs_list,
        default=active_set_label,
        key="settings_active_tab",
        on_change="rerun"
    )

    with tab_vermieter:
        st.subheader("Vermieterdaten & Bankverbindung")
        st.caption("Diese Stammdaten werden als Absender für alle formellen Briefe, Mietanpassungen und Nebenkostenabrechnungen nach DIN 5008 sowie von der KI verwendet.")

        cur_type = current_settings.get("landlord_type", "private")
        type_options = ["Privater Vermieter", "Hausverwaltung"]
        type_idx = 1 if cur_type in ["property_management", "Hausverwaltung"] else 0

        with st.container(border=True):
            st.markdown("##### 👤 Organisationsform / Vermieter-Typ")
            selected_type = st.segmented_control(
                "Typ auswählen",
                type_options,
                default=type_options[type_idx],
                key="settings_landlord_type_selector",
                label_visibility="collapsed"
            )
            is_private = (selected_type == "Privater Vermieter")

            if is_private:
                st.info("ℹ️ **Privater Vermieter ausgewählt:** In all deinen Anschreiben, Abrechnungen und KI-Briefen wird ausschließlich dein persönlicher Name als Vermieter verwendet. Begriffe wie 'Hausverwaltung' werden vollständig weggelassen.")
            else:
                st.info("ℹ️ **Hausverwaltung ausgewählt:** In Schreiben wird der Firmenname der Hausverwaltung sowie optional der zuständige Ansprechpartner genannt.")

            st.markdown("##### 🏢 Absender & Verwaltung")
            col_lname, col_lperson = st.columns(2)
            with col_lname:
                name_label = "Vollständiger Name des Vermieters *" if is_private else "Name der Hausverwaltung / Firma *"
                name_placeholder = "z. B. Kirdar Karadag" if is_private else "z. B. Hausverwaltung Sonnenhang"
                def_name = current_settings.get("landlord_name", "Kirdar Karadag" if is_private else "Hausverwaltung Sonnenhang")
                if is_private and def_name == "Hausverwaltung Sonnenhang":
                    def_name = current_settings.get("landlord_contact_person") or "Kirdar Karadag"
                new_lname = st.text_input(name_label, value=def_name, placeholder=name_placeholder, key="set_lname")

            with col_lperson:
                if is_private:
                    new_lperson = st.text_input(
                        "Zusatz zur Unterschrift (optional)",
                        value=current_settings.get("landlord_contact_person", "") if current_settings.get("landlord_contact_person") != "Hausverwaltung Sonnenhang" else "",
                        placeholder="z. B. Vermieter (oder leer lassen)",
                        help="Wird unter deinem Namen bei der Unterschrift aufgeführt.",
                        key="set_lperson"
                    )
                else:
                    new_lperson = st.text_input(
                        "Ansprechpartner / Sachbearbeiter",
                        value=current_settings.get("landlord_contact_person", "Kirdar Karadag"),
                        placeholder="z. B. Sabine Meier",
                        key="set_lperson"
                    )

            st.markdown("##### 📍 Anschrift (DIN 5008 Fensterkuvert)")
            col_lstreet, col_lzip, col_lcity = st.columns([2, 1, 1.5])
            with col_lstreet:
                new_lstreet = st.text_input("Straße und Hausnummer *", value=current_settings.get("landlord_street", "Lindenstraße 14"), key="set_lstreet")
            with col_lzip:
                new_lzip = st.text_input("Postleitzahl *", value=current_settings.get("landlord_zip", "10115"), key="set_lzip")
            with col_lcity:
                new_lcity = st.text_input("Ort *", value=current_settings.get("landlord_city", "Berlin"), key="set_lcity")

            st.markdown("##### 📞 Kontaktdaten")
            col_lphone, col_lemail = st.columns(2)
            with col_lphone:
                new_lphone = st.text_input("Telefonnummer", value=current_settings.get("landlord_phone", "+49 30 12345678"), key="set_lphone")
            with col_lemail:
                new_lemail = st.text_input("E-Mail-Adresse", value=current_settings.get("landlord_email", "kirdar@karadag.de" if is_private else "verwaltung@sonnenhang.de"), key="set_lemail")

            st.markdown("##### 💳 Bankverbindung für Mietzahlungen & Nachzahlungen")
            col_lholder, col_lbank = st.columns(2)
            with col_lholder:
                def_holder = current_settings.get("landlord_account_holder", def_name)
                if is_private and def_holder == "Hausverwaltung Sonnenhang":
                    def_holder = def_name
                new_lholder = st.text_input("Kontoinhaber", value=def_holder, key="set_lholder")
            with col_lbank:
                new_lbank = st.text_input("Kreditinstitut (Bankname)", value=current_settings.get("landlord_bank_name", "Berliner Sparkasse"), key="set_lbank")

            col_liban, col_lbic, col_ltax = st.columns([2, 1.2, 1.2])
            with col_liban:
                new_liban = st.text_input("IBAN", value=current_settings.get("landlord_iban", "DE12 1005 0000 0123 4567 89"), key="set_liban")
            with col_lbic:
                new_lbic = st.text_input("BIC", value=current_settings.get("landlord_bic", "BELADEB1XXX"), key="set_lbic")
            with col_ltax:
                new_ltax = st.text_input("Steuernummer / USt-IdNr. (optional)", value=current_settings.get("landlord_tax_id", "27/123/45678"), key="set_ltax")

            save_landlord = st.button("Vermieterdaten speichern", type="primary", use_container_width=True, key="btn_save_landlord_settings")
            if save_landlord:
                new_sig_title = new_lname.strip() if is_private else (current_settings.get("default_signature_title") or "Ihre Hausverwaltung")
                if is_private and "hausverwaltung" in new_sig_title.lower():
                    new_sig_title = new_lname.strip()
                elif not is_private and "vermieter" in new_sig_title.lower():
                    new_sig_title = "Ihre Hausverwaltung"

                save_settings({
                    "landlord_type": "private" if is_private else "property_management",
                    "landlord_name": new_lname.strip(),
                    "landlord_contact_person": new_lperson.strip(),
                    "landlord_street": new_lstreet.strip(),
                    "landlord_zip": new_lzip.strip(),
                    "landlord_city": new_lcity.strip(),
                    "landlord_phone": new_lphone.strip(),
                    "landlord_email": new_lemail.strip(),
                    "landlord_account_holder": new_lholder.strip() if new_lholder.strip() else new_lname.strip(),
                    "landlord_bank_name": new_lbank.strip(),
                    "landlord_iban": new_liban.strip(),
                    "landlord_bic": new_lbic.strip(),
                    "landlord_tax_id": new_ltax.strip(),
                    "default_signature_title": new_sig_title
                })
                for k in ["set_lname", "set_lperson", "set_lstreet", "set_lzip", "set_lcity", "set_lphone", "set_lemail", "set_lholder", "set_lbank", "set_liban", "set_lbic", "set_ltax"]:
                    st.session_state.pop(k, None)
                set_flash_message(f"{'Vermieterdaten' if is_private else 'Hausverwaltungsdaten'} wurden erfolgreich gespeichert!")
                st.rerun()

        # Vorschau-Box
        with st.expander("Vorschau: So erscheint dein Briefkopf auf Schreiben (DIN 5008)", expanded=False):
            v_type_is_priv = current_settings.get("landlord_type", "private") == "private"
            v_name = current_settings.get("landlord_name", "Kirdar Karadag" if v_type_is_priv else "Hausverwaltung Sonnenhang")
            v_str = current_settings.get("landlord_street", "Lindenstraße 14")
            v_city = f"{current_settings.get('landlord_zip', '10115')} {current_settings.get('landlord_city', 'Berlin')}"
            v_phone = current_settings.get("landlord_phone", "")
            v_email = current_settings.get("landlord_email", "")
            v_iban = current_settings.get("landlord_iban", "")
            v_bank = current_settings.get("landlord_bank_name", "")
            v_person = current_settings.get("landlord_contact_person", "")

            title_badge = " (Vermieter)" if v_type_is_priv else ""
            person_line = f"<br/>Ansprechpartner: {v_person}" if (not v_type_is_priv and v_person) else ""

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
                        <b>{v_name}</b>{title_badge}{person_line}<br/>
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

        col_stat_info, col_stat_btn = st.columns([3, 1.2])
        with col_stat_info:
            if ollama_status["online"]:
                st.success(f"🟢 **Ollama aktiv:** {ollama_status['message']}")
            else:
                st.warning(f"🟡 **Ollama Status:** {ollama_status['message']}")
        with col_stat_btn:
            st.write("")
            if st.button("Verbindung prüfen", icon=":material/refresh:", use_container_width=True, key="btn_check_ollama"):
                get_cached_ollama_status.clear()
                st.rerun()

        if not ollama_status["online"]:
            with st.container(border=True):
                st.markdown("##### 🔌 Ollama nicht verbunden oder nicht gestartet")
                st.write("PropMAgent führt alle Sprachmodelle 100% lokal über die kostenlose Software **Ollama** aus. Es werden zu keinem Zeitpunkt Daten oder Dokumente ins Internet übertragen.")
                c_inst1, c_inst2 = st.columns([1.6, 2.4])
                with c_inst1:
                    st.link_button("Ollama herunterladen (ollama.com)", "https://ollama.com/download", icon=":material/download:", use_container_width=True)
                with c_inst2:
                    st.info("💡 **Bereits installiert?** Starte einfach das Ollama-Symbol im Windows-Startmenü oder der Taskleiste und klicke oben auf **'Verbindung prüfen'**.")
        else:
            if not is_model_installed:
                with st.container(border=True):
                    st.markdown(f"##### 📥 Modell '{cur_model}' noch nicht auf dem PC")
                    st.write(f"Ollama ist aktiv, aber das ausgewählte Sprachmodell **{cur_model}** wurde noch nicht lokal gespeichert. Klicke unten auf den Button, um das Modell direkt in PropMAgent herunterzuladen (Größe ca. 4.7 GB) – ganz ohne Terminal!")
                    if st.button(f"Modell '{cur_model}' jetzt herunterladen", icon=":material/cloud_download:", type="primary", use_container_width=True, key=f"btn_dl_active_{cur_model}"):
                        with st.status(f"Lade '{cur_model}' über Ollama herunter... Bitte das Browserfenster geöffnet lassen.", expanded=True) as status_box:
                            try:
                                import ollama
                                prog_bar = st.progress(0, text="Verbindung herstellen...")
                                for step in ollama.pull(cur_model, stream=True):
                                    s_msg = step.get("status", "")
                                    c_bytes = step.get("completed", 0)
                                    t_bytes = step.get("total", 0)
                                    if t_bytes > 0:
                                        pct = min(1.0, max(0.0, float(c_bytes) / float(t_bytes)))
                                        mb_c = c_bytes / (1024 * 1024)
                                        mb_t = t_bytes / (1024 * 1024)
                                        prog_bar.progress(pct, text=f"{s_msg} ({int(pct*100)}% - {mb_c:.1f} MB / {mb_t:.1f} MB)")
                                    else:
                                        prog_bar.progress(0, text=s_msg)
                                prog_bar.progress(1.0, text="Download abgeschlossen!")
                                status_box.update(label=f"✅ Modell '{cur_model}' erfolgreich installiert!", state="complete", expanded=False)
                                get_cached_ollama_status.clear()
                                set_flash_message(f"Modell '{cur_model}' wurde erfolgreich installiert und ist sofort einsatzbereit!", icon="🎉")
                                st.rerun()
                            except Exception as err:
                                status_box.update(label=f"Fehler beim Download: {err}", state="error")
                                st.error(f"Download fehlgeschlagen: {err}")
            else:
                st.info(f"✅ **Aktives Modell bereit:** `{cur_model}` ist vollständig lokal auf deinem PC installiert und einsatzbereit.")

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
                get_cached_ollama_status.clear()
                set_flash_message(f"KI-Konfiguration gespeichert! Aktives Modell: **{final_model}**")
                st.rerun()

    with tab_briefe:
        st.subheader("Vorgaben für Briefe, Fristen & Abrechnungen")
        st.caption("Passe Standardfristen und Formulierungen an, die in allen Schreiben und Nebenkostenabrechnungen automatisch herangezogen werden.")

        with st.form("form_letter_defaults"):
            st.markdown("##### 📍 Datumszeile & Ausstellungsort (DIN 5008)")
            cur_letter_city = current_settings.get("letter_city", "")
            def_landlord_city = current_settings.get("landlord_city", "Berlin")
            col_d_city, col_d_city_prev = st.columns([1.2, 1.8])
            with col_d_city:
                new_letter_city = st.text_input(
                    "Ausstellungsort für Datumszeile (Ort und Datum)",
                    value=cur_letter_city,
                    placeholder=f"Standard: {def_landlord_city}",
                    help="Ort, der in der Datumszeile oben rechts auf allen Briefen und Nebenkostenabrechnungen gedruckt wird (z. B. 'Aachen, den 26.10.2026'). Bleibt dieses Feld leer, wird automatisch der Wohnort aus den Vermieterdaten verwendet."
                )
            with col_d_city_prev:
                preview_city = (new_letter_city.strip() or def_landlord_city or "Berlin")
                st.caption(
                    "ℹ️ **Vorschau der Datumszeile:**\n\n"
                    f"`{preview_city}, den {datetime.now().strftime('%d.%m.%Y')}`\n\n"
                    "Wird in allen offiziellen Schreiben, Mahnungen, Mieterhöhungen sowie Nebenkostenabrechnungen eingesetzt."
                )

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
                default_sig_fallback = "Ihr Vermieter" if current_settings.get("landlord_type", "private") == "private" else "Ihre Hausverwaltung"
                cur_sig_val = current_settings.get("default_signature_title", default_sig_fallback)
                if current_settings.get("landlord_type", "private") == "private" and cur_sig_val == "Ihre Hausverwaltung":
                    cur_sig_val = "Ihr Vermieter"
                new_sig_title = st.text_input(
                    "Standard-Unterschriftenbezeichnung",
                    value=cur_sig_val,
                    help="Wird unter den 3 Leerzeilen für die handschriftliche Unterschrift gedruckt (z. B. 'Ihr Vermieter' oder 'Ihre Hausverwaltung')."
                )

            st.markdown("##### 📄 Layout & Optionen")
            inc_bank = st.checkbox(
                "Bankverbindung in offiziellen Zahlungsaufforderungen und Briefen automatisch auflisten",
                value=current_settings.get("letter_include_bank_details", "true") == "true"
            )

            save_letters = st.form_submit_button("Vorgaben speichern", type="primary", use_container_width=True)
            if save_letters:
                save_settings({
                    "letter_city": new_letter_city.strip(),
                    "default_payment_deadline_days": str(new_pay_days),
                    "default_utility_objection_days": str(new_obj_days),
                    "default_closing_phrase": new_closing,
                    "default_signature_title": new_sig_title.strip(),
                    "letter_include_bank_details": "true" if inc_bank else "false"
                })
                set_flash_message("Brief- und Abrechnungsvorgaben erfolgreich aktualisiert!")
                st.rerun()

    with tab_system:
        st.subheader("Systemstatus, Datenbank & Datensicherung")
        st.caption("Prüfe den Zustand deiner lokalen Datenbank und lade jederzeit ein vollständiges Backup herunter.")

        st.markdown("##### 🔍 Systembereitschaft & Komponenten-Status")
        col_cs1, col_cs2, col_cs3 = st.columns(3)
        with col_cs1:
            st.markdown("**Lokale Datenbank (SQLite):**")
            st.markdown("🟢 Bereit & verbunden (`prop_management.db`)")
        with col_cs2:
            st.markdown("**Ollama KI-Server:**")
            if ollama_status["online"]:
                st.markdown(f"🟢 Verbunden (`{ollama_url}`)")
            else:
                st.markdown("🔴 Nicht erreichbar ([Ollama starten / laden](https://ollama.com/download))")
        with col_cs3:
            st.markdown("**Aktives Sprachmodell:**")
            if is_model_installed:
                st.markdown(f"🟢 **{cur_model}** einsatzbereit")
            elif ollama_status["online"]:
                st.markdown(f"🟡 **{cur_model}** (Download in 'KI & Sprachmodell')")
            else:
                st.markdown("⚪ Status ausstehend")

        st.markdown("---")

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
        st.markdown("##### 💾 Datenbank-Backup & Datensicherung")
        st.caption("Sichere deinen gesamten Datenbestand als `.db`-Datei oder stelle ein zuvor heruntergeladenes Backup wieder her.")

        col_bak_dl, col_bak_up = st.columns(2, gap="medium")

        from database.db import DB_PATH, validate_backup_file, restore_backup_file

        with col_bak_dl:
            with st.container(border=True):
                st.markdown("###### 📥 Backup herunterladen")
                st.write("Deine gesamte Datenbank (`prop_management.db`) enthält alle Liegenschaften, Einheiten, Mieter, Verträge, Zahlungen und Betriebskosten. Sichere sie mit einem Klick:")
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
                else:
                    st.warning("Keine aktive Datenbankdatei gefunden.")

        with col_bak_up:
            with st.container(border=True):
                st.markdown("###### 📤 Backup wiederherstellen / DB hochladen")
                st.write("Stelle einen früheren Datenbestand aus einer PropMAgent-Backup-Datei wieder her:")

                st.info(
                    "⚠️ **Wichtiger Hinweis:**\n\n"
                    "Lade hier ausschließlich **.db-Dateien** hoch, die zuvor als Backup aus **PropMAgent** heruntergeladen wurden. "
                    "Fremde Datenbanken besitzen eine andere Tabellenstruktur und werden zum Schutz deiner Daten abgewiesen.",
                    icon="ℹ️"
                )

                uploaded_backup = st.file_uploader(
                    "Backup-Datei auswählen (.db)",
                    type=["db", "sqlite", "sqlite3"],
                    key="uploader_db_backup",
                    help="Wähle eine zuvor aus PropMAgent exportierte .db-Backup-Datei aus."
                )

                if uploaded_backup is not None:
                    b_bytes = uploaded_backup.getvalue()
                    is_valid, val_msg, b_stats = validate_backup_file(b_bytes)
                    if not is_valid:
                        st.error(f"❌ **Ungültige Backup-Datei:** {val_msg}")
                    else:
                        st.success(
                            f"✅ **Gültiges PropMAgent-Backup erkannt!**\n\n"
                            f"• **Liegenschaften:** {b_stats.get('properties', 0)}  \n"
                            f"• **Wohneinheiten:** {b_stats.get('units', 0)}  \n"
                            f"• **Erfasste Mieter:** {b_stats.get('tenants', 0)}  \n"
                            f"• **Kostenbelege:** {b_stats.get('expenses', 0)}  \n"
                            f"• **Zahlungen:** {b_stats.get('payments', 0)}"
                        )

                        st.warning(
                            "⚠️ **Achtung:** Durch das Wiederherstellen wird der aktuelle Datenbestand in PropMAgent durch diese Datei ersetzt.\n\n"
                            "*(Vor dem Überschreiben wird automatisch eine Sicherheitskopie deiner aktuellen Datenbank im Ordner `data/backups/` gespeichert.)*"
                        )

                        with st.popover("⚠️ Jetzt Wiederherstellung bestätigen...", use_container_width=True):
                            st.write("Bist du sicher? Alle aktuellen Daten werden durch das Backup ersetzt.")
                            if st.button("Ja, Backup endgültig einspielen", type="primary", icon=":material/restore:", use_container_width=True, key="btn_confirm_restore_db"):
                                success, rest_msg, rest_stats = restore_backup_file(b_bytes)
                                if success:
                                    for k in list(st.session_state.keys()):
                                        if k.startswith("active_") or k.startswith("pe_") or k.startswith("te_") or k.startswith("set_"):
                                            st.session_state.pop(k, None)
                                    set_flash_message(
                                        f"Datenbank erfolgreich wiederhergestellt! ({rest_stats.get('properties', 0)} Liegenschaften, {rest_stats.get('tenants', 0)} Mieter geladen)",
                                        icon="✅"
                                    )
                                    st.rerun()
                                else:
                                    st.error(f"Wiederherstellung fehlgeschlagen: {rest_msg}")

        st.markdown("---")
        st.markdown("##### 🔄 Auf Werkseinstellungen zurücksetzen")
        st.write("Setzt ausschließlich die Einstellungen (Vermieterdaten, Fristen, Modell) auf die Standardwerte zurück. Deine Mieterdaten und Buchungen bleiben unberührt.")
        
        with st.popover("Werkseinstellungen wiederherstellen...", use_container_width=True):
            st.warning("Möchtest du alle Einstellungen wirklich auf die Standardwerte zurücksetzen?")
            if st.button("Ja, Einstellungen zurücksetzen", type="primary", use_container_width=True):
                reset_settings_to_default()
                set_flash_message("Einstellungen wurden auf Standardwerte zurückgesetzt.", icon="ℹ️")
                st.rerun()

def render_document_import_view():
    """Rendert die Ansicht zur Dokumentenanalyse & automatischen Liegenschafts-/Einheitenerfassung."""
    # 1. Obere Navigationsleiste mit Zurück-Button
    col_back, col_space, col_gear = st.columns([0.24, 0.60, 0.16])
    with col_back:
        if st.button("Zurück zu Liegenschaften", icon=":material/arrow_back:", key="btn_doc_import_top_back", use_container_width=True):
            st.session_state["doc_import_active"] = False
            st.session_state["doc_import_parsed_data"] = None
            st.session_state["doc_import_target_prop_id"] = None
            st.rerun()
    with col_gear:
        if st.button("Einstellungen", icon=":material/settings:", key="btn_gear_doc_import", use_container_width=True, help="Einstellungen öffnen"):
            st.session_state["previous_menu"] = "Liegenschaften & Mieter"
            st.session_state["show_settings"] = True
            st.rerun()

    # Titel & Beschreibung
    st.header("Liegenschaft & Einheiten aus Dokument erfassen")
    st.write("Lade ein PDF-Dokument (z. B. **Zensus 2022 Gebäude- und Wohnungszählung**, Teilungserklärung, Mietverträge oder Wohnungsliste) hoch. Die Daten werden automatisch analysiert und dir übersichtlich zur Prüfung angezeigt, bevor sie in deiner Liegenschaft gespeichert werden.")

    # Datenschutz & Lokalitäts-Hinweis
    st.info("🔒 **100% Lokale Verarbeitung:** Dein Dokument wird ausschließlich lokal auf deinem PC ausgelesen und durch dein lokales Ollama-Modell verarbeitet. Es werden zu keinem Zeitpunkt Daten oder Dokumente ins Internet übertragen.")

    current_settings = get_all_settings()
    model_name = current_settings.get("ollama_model", "llama3")

    # Upload-Bereich
    with st.container(border=True):
        st.markdown("##### 📁 Dokument auswählen")
        uploaded_file = st.file_uploader(
            "PDF-Dokument hochladen",
            type=["pdf"],
            key="prop_doc_upload_input",
            help="Wähle eine PDF-Datei aus (z. B. Zensus 2022 Erfassungsbogen, Wohnungsübersicht etc.)"
        )

        if uploaded_file is not None:
            col_f_info, col_f_btn = st.columns([0.65, 0.35])
            with col_f_info:
                file_size_kb = len(uploaded_file.getvalue()) / 1024
                st.caption(f"Ausgewählte Datei: **{uploaded_file.name}** ({file_size_kb:.1f} KB)")
            with col_f_btn:
                start_analysis = st.button("Dokument jetzt analysieren", icon=":material/document_scanner:", type="primary", use_container_width=True, key="btn_start_doc_analysis")

            if start_analysis:
                with st.spinner("Extrahiere Dokumentdaten und analysiere Wohnungen mit lokalem Modell..."):
                    try:
                        raw_text = extract_text_from_pdf(uploaded_file)
                        if not raw_text.strip():
                            st.error("In diesem PDF konnte kein lesbarer Text gefunden werden (möglicherweise handelt es sich um einen reinen Bild-Scan ohne OCR-Textebene).")
                        else:
                            parsed = parse_property_document(raw_text, model=model_name)
                            st.session_state["doc_import_parsed_data"] = parsed
                            st.session_state["doc_import_raw_text"] = raw_text
                            st.session_state["doc_import_file_name"] = uploaded_file.name
                            st.success(f"Dokument erfolgreich analysiert! {len(parsed.get('units', []))} Wohneinheiten erkannt.")
                    except Exception as ex:
                        st.error(f"Fehler bei der Analyse: {ex}")

    # Wenn Daten analysiert wurden: Prüf- und Bearbeitungsmaske
    parsed_data = st.session_state.get("doc_import_parsed_data")
    if parsed_data:
        st.markdown("---")
        st.markdown("### 📋 Erfasste Daten prüfen & anpassen")
        st.caption("Prüfe die erkannten Liegenschafts- und Wohnungsdaten. Du kannst jedes Feld vor der Übernahme frei anpassen.")

        existing_props = get_all_properties()
        target_prop_preset = st.session_state.get("doc_import_target_prop_id")

        # 1. Liegenschafts-Zuordnung
        st.markdown("##### 1. Liegenschaftszuordnung")
        target_options = ["Neue Liegenschaft anlegen"]
        if existing_props:
            target_options.append("Zu bestehender Liegenschaft hinzufügen / aktualisieren")

        default_target_idx = 1 if (target_prop_preset and existing_props) else 0
        dest_mode = st.radio(
            "Wohin sollen die erfassten Einheiten gespeichert werden?",
            options=target_options,
            index=default_target_idx,
            horizontal=True
        )

        selected_existing_prop_id = None
        if dest_mode == "Neue Liegenschaft anlegen":
            col_pn, col_pa = st.columns([1.5, 1])
            with col_pn:
                def_p_name = parsed_data.get("property_name") or "Neue Liegenschaft"
                prop_name_input = st.text_input("Name der Liegenschaft *", value=def_p_name, key="import_p_name", placeholder="z. B. Wohnanlage Sonnenhang")
            with col_pa:
                def_p_alias = parsed_data.get("alias") or ""
                prop_alias_input = st.text_input("Optionaler Alias (Kurzname)", value=def_p_alias, key="import_p_alias", placeholder="z. B. Sonnenhang")

            col_str, col_z, col_c = st.columns([2, 1, 1.5])
            with col_str:
                def_str = parsed_data.get("street") or ""
                prop_street_input = st.text_input("Straße & Hausnummer *", value=def_str, key="import_p_street", placeholder="z. B. Lindenstraße 14")
            with col_z:
                def_zip = parsed_data.get("zip_code") or ""
                prop_zip_input = st.text_input("PLZ *", value=def_zip, key="import_p_zip", placeholder="10115")
            with col_c:
                def_city = parsed_data.get("city") or ""
                prop_city_input = st.text_input("Ort *", value=def_city, key="import_p_city", placeholder="Berlin")

            col_by, col_ht, col_es = st.columns(3)
            with col_by:
                def_by = parsed_data.get("construction_year") or ""
                prop_by_input = st.text_input("Baujahr (optional)", value=str(def_by), key="import_p_by", placeholder="z. B. 1998")
            with col_ht:
                def_ht = parsed_data.get("heating_type") or ""
                ht_options = ["", "Zentralheizung", "Etagenheizung", "Fernwärme", "Wärmepumpe", "Einzelöfen", "Sonstige"]
                ht_idx = ht_options.index(def_ht) if def_ht in ht_options else (len(ht_options) - 1 if def_ht else 0)
                prop_ht_input = st.selectbox("Heizungsart (optional)", ht_options, index=ht_idx, key="import_p_ht")
            with col_es:
                def_es = parsed_data.get("energy_source") or ""
                es_options = ["", "Erdgas", "Heizöl", "Fernwärme", "Strom / Umweltwärme", "Holzpellets", "Sonstige"]
                es_idx = es_options.index(def_es) if def_es in es_options else (len(es_options) - 1 if def_es else 0)
                prop_es_input = st.selectbox("Energieträger (optional)", es_options, index=es_idx, key="import_p_es")
        else:
            prop_map = {f"{p['name']} ({p['street']}, {p['zip_code']} {p['city']})": p["property_id"] for p in existing_props}
            default_p_idx = 0
            if target_prop_preset:
                for idx, (lbl, pid) in enumerate(prop_map.items()):
                    if pid == target_prop_preset:
                        default_p_idx = idx
                        break
            sel_label = st.selectbox("Bestehende Liegenschaft auswählen *", list(prop_map.keys()), index=default_p_idx)
            selected_existing_prop_id = prop_map[sel_label]
            prop_name_input = ""
            prop_alias_input = ""
            prop_street_input = ""
            prop_zip_input = ""
            prop_city_input = ""
            prop_by_input = ""
            prop_ht_input = ""
            prop_es_input = ""

        st.markdown("##### 2. Erkannte Wohneinheiten & Mieter")
        st.caption("Passe Werte direkt in der Tabelle an. Du kannst Zeilen bearbeiten, löschen oder über das '+' am Tabellenende neue hinzufügen.")

        units_list = parsed_data.get("units", [])
        if not units_list:
            units_list = [{
                "unit_number": "Wohnung 1",
                "floor": "EG",
                "area_sqm": 65.0,
                "rooms": 2.0,
                "person_count": 1,
                "salutation": "Herr",
                "first_name": "",
                "last_name": "",
                "co_tenants": "",
                "cold_rent": 0.0,
                "utility_advance": 0.0
            }]

        df_editor_data = pd.DataFrame(units_list)
        for col_name in ["unit_number", "floor", "area_sqm", "rooms", "person_count", "salutation", "first_name", "last_name", "co_tenants", "cold_rent", "utility_advance"]:
            if col_name not in df_editor_data.columns:
                df_editor_data[col_name] = 1 if col_name == "person_count" else (2.0 if col_name == "rooms" else "")

        edited_df = st.data_editor(
            df_editor_data,
            column_config={
                "unit_number": st.column_config.TextColumn("Wohnung / Einheit *", required=True, width="medium"),
                "floor": st.column_config.TextColumn("Etage / Lage", width="small"),
                "area_sqm": st.column_config.NumberColumn("Wohnfläche (m²) *", min_value=1.0, max_value=3000.0, step=0.5, format="%.1f m²", required=True),
                "rooms": st.column_config.NumberColumn("Zimmer", min_value=1.0, max_value=25.0, step=0.5, format="%.1f"),
                "person_count": st.column_config.NumberColumn("Personen (Anzahl)", min_value=1, max_value=20, step=1, format="%d"),
                "salutation": st.column_config.SelectboxColumn("Anrede", options=["Herr", "Frau"], width="small"),
                "first_name": st.column_config.TextColumn("Mieter Vorname (opt.)", width="medium"),
                "last_name": st.column_config.TextColumn("Mieter Nachname (opt.)", width="medium"),
                "co_tenants": st.column_config.TextColumn("Weitere Mieter / Mitmieter (opt.)", width="large", help="z. B. Laura Schmidt (falls Mietvertrag auf mehrere Personen)"),
                "cold_rent": st.column_config.NumberColumn("Kaltmiete (€)", min_value=0.0, step=50.0, format="%.2f €"),
                "utility_advance": st.column_config.NumberColumn("NK-Vorauszahlung (€)", min_value=0.0, step=10.0, format="%.2f €")
            },
            num_rows="dynamic",
            use_container_width=True,
            key="table_doc_import_editor"
        )

        calc_units_cnt = len(edited_df)
        try:
            calc_total_area = float(edited_df["area_sqm"].sum())
        except Exception:
            calc_total_area = 0.0

        col_met1, col_met2, col_met3 = st.columns([1, 1, 2])
        with col_met1:
            st.metric("Erfasste Einheiten", calc_units_cnt)
        with col_met2:
            st.metric("Gesamtwohnfläche", f"{calc_total_area:,.1f} m²".replace(",", "."))

        # Optional: Extrahierter Text zur Kontrolle
        raw_t = st.session_state.get("doc_import_raw_text", "")
        if raw_t:
            with st.expander("Extrahierter Originaltext aus dem PDF (zur Einsicht)", expanded=False):
                st.text_area("PDF-Rohtext", raw_t, height=180, disabled=True)

        st.markdown("---")
        col_btn_save, col_btn_cancel = st.columns([1.5, 1])
        with col_btn_save:
            save_import_btn = st.button("Liegenschaft & Einheiten jetzt speichern", icon=":material/save:", type="primary", use_container_width=True, key="btn_commit_doc_import")
        with col_btn_cancel:
            cancel_import_btn = st.button("Abbrechen & Verwerfen", icon=":material/close:", use_container_width=True, key="btn_abort_doc_import")

        if save_import_btn:
            if dest_mode == "Neue Liegenschaft anlegen":
                if not prop_name_input.strip() or not prop_street_input.strip() or not prop_zip_input.strip() or not prop_city_input.strip():
                    st.error("Bitte mindestens Name, Straße, PLZ und Ort der Liegenschaft angeben!")
                    return
            if edited_df.empty:
                st.error("Bitte mindestens eine Wohneinheit in der Tabelle belassen oder hinzufügen!")
                return

            records = edited_df.to_dict(orient="records")
            prop_payload = {
                "name": prop_name_input.strip() if dest_mode == "Neue Liegenschaft anlegen" else "",
                "alias": prop_alias_input.strip() if dest_mode == "Neue Liegenschaft anlegen" else "",
                "street": prop_street_input.strip() if dest_mode == "Neue Liegenschaft anlegen" else "",
                "zip_code": prop_zip_input.strip() if dest_mode == "Neue Liegenschaft anlegen" else "",
                "city": prop_city_input.strip() if dest_mode == "Neue Liegenschaft anlegen" else "",
                "total_area_sqm": calc_total_area,
                "construction_year": prop_by_input.strip() if dest_mode == "Neue Liegenschaft anlegen" else "",
                "heating_type": prop_ht_input.strip() if dest_mode == "Neue Liegenschaft anlegen" else "",
                "energy_source": prop_es_input.strip() if dest_mode == "Neue Liegenschaft anlegen" else ""
            }

            try:
                saved_id = save_imported_property_data(
                    prop_data=prop_payload,
                    units=records,
                    existing_property_id=selected_existing_prop_id
                )
                st.session_state["active_property_id"] = saved_id
                st.session_state["doc_import_active"] = False
                st.session_state["doc_import_parsed_data"] = None
                st.session_state["doc_import_raw_text"] = None
                st.session_state["doc_import_target_prop_id"] = None
                set_flash_message("Liegenschaft und Einheiten wurden erfolgreich gespeichert!")
                st.rerun()
            except Exception as e_save:
                st.error(f"Fehler beim Speichern in die Datenbank: {e_save}")

        if cancel_import_btn:
            st.session_state["doc_import_active"] = False
            st.session_state["doc_import_parsed_data"] = None
            st.session_state["doc_import_raw_text"] = None
            st.session_state["doc_import_target_prop_id"] = None
            st.rerun()

# Prüfen ob Dialog für ungespeicherte Änderungen geöffnet werden muss
if st.session_state.get("show_unsaved_dialog", False):
    confirm_unsaved_dialog()

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
        gear_lbl_a = f"Einstellungen{' 🔴' if has_unsaved_settings_changes() else ''}"
        if st.button(gear_lbl_a, icon=":material/settings:", key="btn_gear_assistant", use_container_width=True, help="Einstellungen, Vermieterdaten & Modell öffnen"):
            if has_any_unsaved_changes():
                st.session_state["pending_nav"] = {"type": "settings", "previous": "KI-Assistent & Schriftverkehr"}
                st.session_state["show_unsaved_dialog"] = True
                st.rerun()
            else:
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
    if st.session_state.get("doc_import_active", False):
        render_document_import_view()

    # LEVEL 1: Übersicht aller Liegenschaften
    elif active_property_id is None:
        col_hdr_main, col_hdr_gear = st.columns([0.84, 0.16])
        with col_hdr_gear:
            st.write("")
            gear_lbl_p = f"Einstellungen{' 🔴' if has_unsaved_settings_changes() else ''}"
            if st.button(gear_lbl_p, icon=":material/settings:", key="btn_gear_properties", use_container_width=True, help="Einstellungen, Vermieterdaten & Modell öffnen"):
                if has_any_unsaved_changes():
                    st.session_state["pending_nav"] = {"type": "settings", "previous": "Liegenschaften & Mieter"}
                    st.session_state["show_unsaved_dialog"] = True
                    st.rerun()
                else:
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

        col_title, col_new_prop = st.columns([0.48, 0.52])
        with col_title:
            st.subheader("Verwaltete Liegenschaften")
        with col_new_prop:
            col_doc_btn, col_manual_btn = st.columns(2)
            with col_doc_btn:
                if st.button("Dokument hochladen", icon=":material/upload_file:", type="primary", use_container_width=True, help="Liegenschaft & Einheiten automatisch aus Zensus-Bogen oder Wohnungsliste erfassen"):
                    st.session_state["doc_import_active"] = True
                    st.session_state["doc_import_target_prop_id"] = None
                    st.session_state["doc_import_parsed_data"] = None
                    st.rerun()
            with col_manual_btn:
                with st.popover("Manuell anlegen", icon=":material/add_home_work:", use_container_width=True):
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
                        np_by = st.text_input("Baujahr (optional)", placeholder="z. B. 1995")
                        col_np_h1, col_np_h2 = st.columns(2)
                        with col_np_h1:
                            np_heat = st.selectbox("Heizungsart (optional)", ["", "Zentralheizung", "Etagenheizung", "Fernwärme", "Wärmepumpe", "Einzelöfen", "Sonstige"])
                        with col_np_h2:
                            np_energy = st.selectbox("Energieträger (optional)", ["", "Erdgas", "Heizöl", "Fernwärme", "Strom / Wärmepumpe", "Holzpellets", "Sonstige"])
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
                                    total_area_sqm=np_area,
                                    construction_year=np_by.strip() or None,
                                    heating_type=np_heat.strip() or None,
                                    energy_source=np_energy.strip() or None
                                )
                                # Automatisch eine Standard-Wohneinheit anlegen
                                add_unit(new_p_id, "Wohnung 1", np_area, "EG", rooms=2.0, person_count=1)
                                set_flash_message(f"Liegenschaft '{np_name}' erfolgreich angelegt!")
                                st.rerun()

        if not properties:
            st.info("Aktuell sind noch keine Liegenschaften erfasst. Lege jetzt die erste Liegenschaft an.")
        else:
            for p in properties:
                with st.container(border=True):
                    col_info, col_metrics, col_actions = st.columns([0.43, 0.25, 0.32])
                    with col_info:
                        alias_part = f" · Alias: **{p['alias']}**" if p.get("alias") else ""
                        st.markdown(f"#### {p['name']}{alias_part}")
                        meta_details = []
                        if p.get("construction_year"):
                            meta_details.append(f"Baujahr: {p['construction_year']}")
                        if p.get("heating_type"):
                            ht_str = p['heating_type']
                            if p.get("energy_source"):
                                ht_str += f" ({p['energy_source']})"
                            meta_details.append(ht_str)
                        meta_str = (" · " + " · ".join(meta_details)) if meta_details else ""
                        st.caption(f":material/location_on: {p['street']}, {p['zip_code']} {p['city']}{meta_str}")
                    with col_metrics:
                        st.markdown(f"**Mieter:** {p['tenant_count']} &nbsp;|&nbsp; **Einheiten:** {p['unit_count']}")
                        st.caption(f"Gesamtfläche: {float(p.get('total_area_sqm') or 0.0):.1f} m²")
                    with col_actions:
                        st.write("")
                        c_open, c_alias, c_del = st.columns([1.1, 0.8, 0.8])
                        with c_open:
                            if st.button("Öffnen", icon=":material/arrow_forward:", key=f"open_prop_{p['property_id']}", type="primary", use_container_width=True):
                                st.session_state["active_property_id"] = p["property_id"]
                                st.session_state["prop_detail_tab_idx"] = 0
                                st.session_state.pop("prop_detail_active_tab", None)
                                st.rerun()
                        with c_alias:
                            with st.popover("Alias", icon=":material/label:", use_container_width=True):
                                st.markdown(f"**Alias für {p['name']}**")
                                cur_alias = p.get("alias") or ""
                                new_alias_input = st.text_input("Alias festlegen", value=cur_alias, key=f"input_alias_{p['property_id']}")
                                if st.button("Speichern", key=f"save_alias_{p['property_id']}", icon=":material/save:", type="primary", use_container_width=True):
                                    update_property_alias(p["property_id"], new_alias_input.strip() if new_alias_input.strip() else None)
                                    set_flash_message(f"Alias für '{p['name']}' gespeichert!")
                                    st.rerun()
                        with c_del:
                            with st.popover("Löschen", icon=":material/delete:", use_container_width=True):
                                st.error(f"**Liegenschaft '{p['name']}' wirklich löschen?**\n\nAlle Einheiten, Mieter und Nebenkostenabrechnungen werden unwiderruflich gelöscht.")
                                if st.button("Endgültig löschen", type="primary", key=f"del_prop_btn_{p['property_id']}", use_container_width=True):
                                    delete_property(p["property_id"])
                                    set_flash_message(f"Liegenschaft '{p['name']}' wurde gelöscht.", icon="🗑️")
                                    st.rerun()

    # LEVEL 2: Detailansicht einer ausgewählten Liegenschaft
    else:
        prop = get_property_by_id(active_property_id)
        if not prop:
            st.session_state["active_property_id"] = None
            st.session_state["prop_detail_tab_idx"] = 0
            st.session_state.pop("prop_detail_active_tab", None)
            st.rerun()

        col_back, col_space, col_gear = st.columns([0.24, 0.60, 0.16])
        with col_back:
            back_lbl_p = f"Alle Liegenschaften{' 🔴' if has_unsaved_lm_changes() else ''}"
            if st.button(back_lbl_p, icon=":material/arrow_back:", key="btn_back_to_properties", use_container_width=True):
                if has_unsaved_lm_changes():
                    st.session_state["pending_nav"] = {"type": "back_to_properties"}
                    st.session_state["show_unsaved_dialog"] = True
                    st.rerun()
                else:
                    st.session_state["active_property_id"] = None
                    st.session_state["prop_detail_tab_idx"] = 0
                    st.session_state.pop("prop_detail_active_tab", None)
                    st.rerun()
        with col_gear:
            gear_lbl_pd = f"Einstellungen{' 🔴' if has_unsaved_settings_changes() else ''}"
            if st.button(gear_lbl_pd, icon=":material/settings:", key="btn_gear_property_detail", use_container_width=True, help="Einstellungen, Vermieterdaten & Modell öffnen"):
                if has_unsaved_lm_changes():
                    st.session_state["pending_nav"] = {"type": "settings", "previous": "Liegenschaften & Mieter"}
                    st.session_state["show_unsaved_dialog"] = True
                    st.rerun()
                else:
                    st.session_state["previous_menu"] = "Liegenschaften & Mieter"
                    st.session_state["show_settings"] = True
                    st.rerun()

        alias_display = f" · Alias: {prop['alias']}" if prop.get("alias") else ""
        st.header(f"{prop['name']}{alias_display}")
        meta_details = []
        if prop.get("construction_year"):
            meta_details.append(f"Baujahr: {prop['construction_year']}")
        if prop.get("heating_type"):
            ht_str = f"Heizung: {prop['heating_type']}"
            if prop.get("energy_source"):
                ht_str += f" ({prop['energy_source']})"
            meta_details.append(ht_str)
        meta_str = (" · " + " · ".join(meta_details)) if meta_details else ""
        st.caption(f":material/location_on: {prop['street']}, {prop['zip_code']} {prop['city']} · Gesamtfläche: {prop['total_area_sqm']:.1f} m² · Einheiten: {prop['unit_count']} · Mieter: {prop['tenant_count']}{meta_str}")

        prop_tenants = get_tenants_by_property(active_property_id)
        prop_units = get_units_by_property(active_property_id)

        has_t_dirty = has_unsaved_tenant_in_active_property()
        has_p_dirty = has_unsaved_property_in_active_property()

        tab_label_edit = f"Mieter bearbeiten & löschen{' 🔴' if has_t_dirty else ''}"
        tab_label_prop = f"Liegenschaftsdaten & Alias{' 🔴' if has_p_dirty else ''}"
        tabs_list = [
            "Mieterübersicht",
            "Neuen Mieter anlegen",
            tab_label_edit,
            "Wohneinheiten",
            tab_label_prop
        ]

        prev_idx = st.session_state.get("prop_detail_tab_idx", 0)
        new_idx = prev_idx

        # Falls ein Tab angeklickt wurde oder im Widget-State steht:
        if "prop_detail_active_tab" in st.session_state:
            cur_lbl = st.session_state["prop_detail_active_tab"]
            if "bearbeiten" in cur_lbl:
                new_idx = 2
            elif "Liegenschaftsdaten" in cur_lbl or "Alias" in cur_lbl:
                new_idx = 4
            elif "anlegen" in cur_lbl:
                new_idx = 1
            elif "Wohneinheiten" in cur_lbl:
                new_idx = 3
            else:
                new_idx = 0

        # Wenn der Nutzer absichtlich von einem schmutzigen Tab wegklickt:
        is_leaving_dirty_t = (prev_idx == 2 and new_idx != 2 and has_t_dirty)
        is_leaving_dirty_p = (prev_idx == 4 and new_idx != 4 and has_p_dirty)

        if is_leaving_dirty_t or is_leaving_dirty_p:
            st.session_state["pending_nav"] = {"type": "tab", "target_idx": new_idx}
            st.session_state["show_unsaved_dialog"] = True
            new_idx = prev_idx  # Bleibe bis zur Bestätigung auf dem aktuellen Tab!

        st.session_state["prop_detail_tab_idx"] = new_idx
        active_tab_label = tabs_list[new_idx]
        st.session_state["prop_detail_active_tab"] = active_tab_label

        tab_tenants, tab_add_t, tab_edit_t, tab_units, tab_prop_settings = st.tabs(
            tabs_list,
            default=active_tab_label,
            key="prop_detail_active_tab",
            on_change="rerun"
        )

        with tab_tenants:
            if prop_tenants:
                df = pd.DataFrame(prop_tenants)
                df["Mieter / Vertragspartner"] = [t.get("display_name") or f"{t.get('first_name', '')} {t.get('last_name', '')}" for t in prop_tenants]
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
                cols_to_show = [c for c in ["ID", "Anrede", "Mieter / Vertragspartner", "Wohneinheit", "Fläche (m²)", "Kaltmiete (€)", "Miete / m² (€)", "NK-Vorauszahlung (€)", "Mietbeginn", "Telefon", "E-Mail"] if c in df_display.columns]
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

                st.markdown("##### 👥 Weitere Personen auf dem Mietvertrag (Gemeinschaftlicher Mietvertrag)")
                st.caption("Optional: Trage hier einen zweiten Mieter/Vertragspartner ein (z. B. Ehepartner oder Mitbewohner).")
                col_co_sal, col_co_fn, col_co_ln = st.columns([1, 2, 2])
                with col_co_sal:
                    new_co_sal = st.selectbox("Anrede (2. Mieter)", ["Frau", "Herr"], key="new_add_co_sal")
                with col_co_fn:
                    new_co_fn = st.text_input("Vorname (2. Mieter)", key="new_add_co_fn", placeholder="z. B. Laura")
                with col_co_ln:
                    new_co_ln = st.text_input("Nachname (2. Mieter)", key="new_add_co_ln", placeholder="z. B. Schmidt")

                submitted = st.form_submit_button("Mieter speichern", icon=":material/save:", type="primary", use_container_width=True)
                if submitted:
                    if not new_fn.strip() or not new_ln.strip():
                        st.error("Bitte mindestens Vorname und Nachname ausfüllen!")
                    else:
                        co_list = []
                        if new_co_fn.strip() or new_co_ln.strip():
                            co_list.append({
                                "salutation": new_co_sal,
                                "first_name": new_co_fn.strip(),
                                "last_name": new_co_ln.strip(),
                                "email": "",
                                "phone": ""
                            })
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
                            phone=new_ph,
                            co_tenants=co_list
                        )
                        set_flash_message(f"Mieter {new_sal} {new_fn} {new_ln} wurde erfolgreich angelegt!")
                        st.rerun()

        with tab_edit_t:
            st.subheader("Mieter bearbeiten & löschen")
            if prop_tenants:
                tenant_dict = {f"{t.get('salutation', 'Herr')} {t['display_name']} (ID {t['tenant_id']} · {t['unit_number']})": t for t in prop_tenants}
                selected_label = st.selectbox("Wähle einen Mieter zum Bearbeiten", list(tenant_dict.keys()), key="edit_prop_select_tenant")
                t_data = tenant_dict[selected_label]
                tid = t_data["tenant_id"]

                with st.container(border=True):
                    col_e_sal, col_e_fn, col_e_ln = st.columns([1, 2, 2])
                    with col_e_sal:
                        cur_sal = t_data.get("salutation", "Herr") or "Herr"
                        sal_idx = 1 if cur_sal == "Frau" else 0
                        edit_sal = st.selectbox("Anrede", ["Herr", "Frau"], index=sal_idx, key=f"te_sal_{tid}")
                    with col_e_fn:
                        edit_fn = st.text_input("Vorname *", value=t_data.get("first_name", ""), key=f"te_fn_{tid}")
                    with col_e_ln:
                        edit_ln = st.text_input("Nachname *", value=t_data.get("last_name", ""), key=f"te_ln_{tid}")

                    col_e_u, col_e_cr, col_e_nk = st.columns(3)
                    with col_e_u:
                        unit_options = {f"{u['unit_number']} ({u['area_sqm']:.0f} m² · {u.get('floor') or 'EG'})": u["unit_id"] for u in prop_units} if prop_units else {"Standard": 1}
                        unit_keys = list(unit_options.keys())
                        curr_idx = 0
                        for idx, key in enumerate(unit_keys):
                            if unit_options[key] == t_data.get("unit_id"):
                                curr_idx = idx
                                break
                        edit_unit_label = st.selectbox("Wohneinheit", unit_keys, index=curr_idx, key=f"te_unit_lbl_{tid}")
                        edit_unit_id = unit_options[edit_unit_label]
                        st.session_state[f"te_unit_{tid}"] = edit_unit_id
                    with col_e_cr:
                        edit_cr = st.number_input("Kaltmiete (€)", min_value=0.0, value=float(t_data.get("cold_rent") or 0.0), step=50.0, key=f"te_cr_{tid}")
                    with col_e_nk:
                        edit_nk = st.number_input("NK-Vorauszahlung (€)", min_value=0.0, value=float(t_data.get("utility_advance") or 0.0), step=10.0, key=f"te_nk_{tid}")

                    col_e_start, col_e_end = st.columns(2)
                    with col_e_start:
                        try:
                            parsed_start = datetime.strptime(str(t_data.get("lease_start") or "2025-01-01")[:10], "%Y-%m-%d").date()
                        except Exception:
                            parsed_start = date.today()
                        edit_start = st.date_input("Mietbeginn", value=parsed_start, key=f"te_start_{tid}")
                    with col_e_end:
                        edit_end = st.text_input("Mietende (optional)", value=str(t_data.get("lease_end") or ""), key=f"te_end_{tid}")

                    col_e_em, col_e_ph = st.columns(2)
                    with col_e_em:
                        edit_em = st.text_input("E-Mail-Adresse", value=str(t_data.get("email") or ""), key=f"te_em_{tid}")
                    with col_e_ph:
                        edit_ph = st.text_input("Telefonnummer", value=str(t_data.get("phone") or ""), key=f"te_ph_{tid}")

                    existing_co = parse_co_tenants(t_data.get("co_tenants"))
                    co1 = existing_co[0] if existing_co else {}
                    st.markdown("##### 👥 Weitere Personen auf dem Mietvertrag (Gemeinschaftlicher Mietvertrag)")
                    st.caption("Optional: Bearbeite hier den zweiten Mieter/Vertragspartner.")
                    col_eco_sal, col_eco_fn, col_eco_ln = st.columns([1, 2, 2])
                    with col_eco_sal:
                        co_cur_sal = co1.get("salutation", "Frau")
                        co_sal_idx = 1 if co_cur_sal == "Herr" else 0
                        edit_co_sal = st.selectbox("Anrede (2. Mieter)", ["Frau", "Herr"], index=co_sal_idx, key=f"te_cosal_{tid}")
                    with col_eco_fn:
                        edit_co_fn = st.text_input("Vorname (2. Mieter)", value=co1.get("first_name", ""), key=f"te_cofn_{tid}", placeholder="z. B. Laura")
                    with col_eco_ln:
                        edit_co_ln = st.text_input("Nachname (2. Mieter)", value=co1.get("last_name", ""), key=f"te_coln_{tid}", placeholder="z. B. Schmidt")

                    col_save, col_del = st.columns([3, 1])
                    confirm_del = False
                    with col_save:
                        save_clicked = st.button("Änderungen speichern", icon=":material/save:", type="primary", use_container_width=True, key=f"btn_save_t_{tid}")
                    with col_del:
                        with st.popover("Mieter löschen", icon=":material/delete:", use_container_width=True):
                            st.error(f"**Mieter '{t_data['first_name']} {t_data['last_name']}' wirklich löschen?**")
                            confirm_del = st.button("Endgültig löschen", type="primary", key=f"btn_confirm_del_t_{tid}", use_container_width=True)

                    if save_clicked:
                        if not edit_fn.strip() or not edit_ln.strip():
                            st.error("Vorname und Nachname sind Pflichtfelder!")
                        else:
                            upd_co_list = []
                            if edit_co_fn.strip() or edit_co_ln.strip():
                                upd_co_list.append({
                                    "salutation": edit_co_sal,
                                    "first_name": edit_co_fn.strip(),
                                    "last_name": edit_co_ln.strip(),
                                    "email": "",
                                    "phone": ""
                                })
                            update_tenant(
                                tenant_id=tid,
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
                                is_active=1,
                                co_tenants=upd_co_list
                            )
                            for k in [f"te_sal_{tid}", f"te_fn_{tid}", f"te_ln_{tid}", f"te_unit_{tid}", f"te_unit_lbl_{tid}", f"te_cr_{tid}", f"te_nk_{tid}", f"te_start_{tid}", f"te_end_{tid}", f"te_em_{tid}", f"te_ph_{tid}", f"te_cosal_{tid}", f"te_cofn_{tid}", f"te_coln_{tid}"]:
                                st.session_state.pop(k, None)
                            st.session_state["prop_detail_tab_idx"] = 2
                            set_flash_message(f"Änderungen an Mieter {edit_fn} {edit_ln} erfolgreich gespeichert!")
                            st.rerun()

                    if confirm_del:
                        for k in [f"te_sal_{tid}", f"te_fn_{tid}", f"te_ln_{tid}", f"te_unit_{tid}", f"te_unit_lbl_{tid}", f"te_cr_{tid}", f"te_nk_{tid}", f"te_start_{tid}", f"te_end_{tid}", f"te_em_{tid}", f"te_ph_{tid}", f"te_cosal_{tid}", f"te_cofn_{tid}", f"te_coln_{tid}"]:
                            st.session_state.pop(k, None)
                        delete_tenant(tid)
                        st.session_state["prop_detail_tab_idx"] = 0
                        set_flash_message(f"Mieter {t_data['first_name']} {t_data['last_name']} wurde gelöscht.", icon="🗑️")
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
                    "area_sqm": "Fläche (m²)",
                    "rooms": "Zimmer",
                    "person_count": "Personen (Anzahl)"
                })
                cols_u = [c for c in ["Einheiten-ID", "Bezeichnung / Nummer", "Etage", "Fläche (m²)", "Zimmer", "Personen (Anzahl)"] if c in df_u.columns]
                st.dataframe(df_u[cols_u], use_container_width=True, hide_index=True)
            else:
                st.info("Noch keine separaten Einheiten angelegt.")

            col_u_doc, col_u_man = st.columns(2)
            with col_u_doc:
                if st.button("Einheiten aus Dokument importieren", icon=":material/upload_file:", type="primary", use_container_width=True, help="Wohneinheiten aus Zensus-Bogen oder Liste direkt in diese Liegenschaft importieren"):
                    st.session_state["doc_import_active"] = True
                    st.session_state["doc_import_target_prop_id"] = active_property_id
                    st.session_state["doc_import_parsed_data"] = None
                    st.rerun()
            with col_u_man:
                with st.popover("Neue Wohneinheit manuell hinzufügen", icon=":material/add:", use_container_width=True):
                    st.markdown("##### Neue Wohneinheit anlegen")
                    with st.form("form_add_unit_to_prop", clear_on_submit=True):
                        u_num = st.text_input("Bezeichnung / Nummer *", placeholder="z. B. Wohnung 4 (2. OG)")
                        col_uf, col_ua = st.columns(2)
                        with col_uf:
                            u_floor = st.text_input("Etage", value="1. OG")
                        with col_ua:
                            u_area = st.number_input("Wohnfläche (m²) *", min_value=10.0, value=75.0, step=5.0)
                        col_ur, col_up = st.columns(2)
                        with col_ur:
                            u_rooms = st.number_input("Zimmer", min_value=1.0, value=2.0, step=0.5)
                        with col_up:
                            u_persons = st.number_input("Anzahl der lebenden Personen", min_value=1, value=1, step=1)
                        submit_unit = st.form_submit_button("Einheit anlegen", icon=":material/save:", type="primary", use_container_width=True)
                        if submit_unit:
                            if not u_num.strip():
                                st.error("Bitte Bezeichnung angeben!")
                            else:
                                add_unit(active_property_id, u_num.strip(), u_area, u_floor, rooms=u_rooms, person_count=u_persons)
                                set_flash_message(f"Wohneinheit '{u_num}' angelegt!")
                                st.rerun()

            if prop_units:
                with st.expander("✏️ Bestehende Wohneinheit bearbeiten", expanded=False):
                    unit_edit_map = {f"{u['unit_number']} ({u['area_sqm']:.0f} m² · {u.get('floor') or 'EG'})": u for u in prop_units}
                    sel_u_lbl = st.selectbox("Wohneinheit auswählen", list(unit_edit_map.keys()), key="sel_u_edit_box")
                    target_u = unit_edit_map[sel_u_lbl]
                    with st.form("form_edit_existing_unit"):
                        col_eu1, col_eu2 = st.columns(2)
                        with col_eu1:
                            eu_num = st.text_input("Bezeichnung / Nummer *", value=target_u["unit_number"])
                            eu_floor = st.text_input("Etage", value=target_u.get("floor") or "EG")
                        with col_eu2:
                            eu_area = st.number_input("Wohnfläche (m²) *", min_value=1.0, value=float(target_u.get("area_sqm") or 50.0), step=1.0)
                            eu_rooms = st.number_input("Zimmer", min_value=1.0, value=float(target_u.get("rooms") or 2.0), step=0.5)
                        eu_persons = st.number_input("Anzahl der lebenden Personen", min_value=1, value=int(target_u.get("person_count") or 1), step=1)
                        if st.form_submit_button("Wohneinheit aktualisieren", icon=":material/save:", type="primary", use_container_width=True):
                            update_unit(target_u["unit_id"], eu_num.strip(), eu_area, eu_floor.strip(), rooms=eu_rooms, person_count=eu_persons)
                            set_flash_message(f"Wohneinheit '{eu_num}' erfolgreich aktualisiert!")
                            st.rerun()

        with tab_prop_settings:
            st.subheader("Liegenschaftsdaten & Alias")
            st.caption("Bearbeite hier den Alias oder die Stammdaten dieser Liegenschaft.")
            pid = active_property_id

            with st.container(border=True):
                ep_name = st.text_input("Name der Liegenschaft *", value=prop["name"], key=f"pe_name_{pid}")
                ep_alias = st.text_input("Optionaler Alias (Kurzname)", value=prop.get("alias") or "", key=f"pe_alias_{pid}")
                ep_street = st.text_input("Straße & Hausnummer *", value=prop["street"], key=f"pe_street_{pid}")
                c_ep_z, c_ep_c = st.columns([1, 2])
                with c_ep_z:
                    ep_zip = st.text_input("PLZ *", value=prop["zip_code"], key=f"pe_zip_{pid}")
                with c_ep_c:
                    ep_city = st.text_input("Ort *", value=prop["city"], key=f"pe_city_{pid}")
                ep_area = st.number_input("Gesamtfläche (m²) *", min_value=0.0, value=float(prop["total_area_sqm"] or 0.0), step=10.0, key=f"pe_area_{pid}")

                col_ep_by, col_ep_ht, col_ep_es = st.columns(3)
                with col_ep_by:
                    ep_by = st.text_input("Baujahr (optional)", value=str(prop.get("construction_year") or ""), key=f"pe_by_{pid}")
                with col_ep_ht:
                    cur_ht = prop.get("heating_type") or ""
                    ht_opts = ["", "Zentralheizung", "Etagenheizung", "Fernwärme", "Wärmepumpe", "Einzelöfen", "Sonstige"]
                    ht_idx = ht_opts.index(cur_ht) if cur_ht in ht_opts else (len(ht_opts) - 1 if cur_ht else 0)
                    ep_ht = st.selectbox("Heizungsart (optional)", ht_opts, index=ht_idx, key=f"pe_ht_{pid}")
                with col_ep_es:
                    cur_es = prop.get("energy_source") or ""
                    es_opts = ["", "Erdgas", "Heizöl", "Fernwärme", "Strom / Umweltwärme", "Holzpellets", "Sonstige"]
                    es_idx = es_opts.index(cur_es) if cur_es in es_opts else (len(es_opts) - 1 if cur_es else 0)
                    ep_es = st.selectbox("Energieträger (optional)", es_opts, index=es_idx, key=f"pe_es_{pid}")

                save_p_btn = st.button("Liegenschaft speichern", icon=":material/save:", type="primary", use_container_width=True, key=f"btn_save_prop_{pid}")
                if save_p_btn:
                    if not ep_name.strip() or not ep_street.strip() or not ep_zip.strip() or not ep_city.strip():
                        st.error("Bitte alle Pflichtfelder (Name, Straße, PLZ, Ort) ausfüllen!")
                    else:
                        update_property(
                            property_id=pid,
                            name=ep_name.strip(),
                            alias=ep_alias.strip() if ep_alias.strip() else None,
                            street=ep_street.strip(),
                            zip_code=ep_zip.strip(),
                            city=ep_city.strip(),
                            total_area_sqm=ep_area,
                            construction_year=ep_by.strip() or None,
                            heating_type=ep_ht.strip() or None,
                            energy_source=ep_es.strip() or None
                        )
                        for k in [f"pe_name_{pid}", f"pe_alias_{pid}", f"pe_street_{pid}", f"pe_zip_{pid}", f"pe_city_{pid}", f"pe_area_{pid}", f"pe_by_{pid}", f"pe_ht_{pid}", f"pe_es_{pid}"]:
                            st.session_state.pop(k, None)
                        st.session_state["prop_detail_tab_idx"] = 4
                        set_flash_message(f"Liegenschaftsdaten für '{ep_name}' erfolgreich gespeichert!")
                        st.rerun()

            st.markdown("---")
            with st.container(border=True):
                st.markdown("##### ⚠️ Gefahrenbereich")
                st.caption("Das Löschen dieser Liegenschaft entfernt auch alle zugehörigen Wohneinheiten, Mietverhältnisse und Betriebskostenabrechnungen unwiderruflich.")
                with st.popover("Liegenschaft endgültig löschen", icon=":material/delete_forever:", use_container_width=True):
                    st.error(f"**Bist du absolut sicher?**\n\nDie Liegenschaft '{prop['name']}' und alle dazugehörigen Daten werden unwiderruflich gelöscht.")
                    if st.button("Ja, Liegenschaft jetzt löschen", type="primary", key=f"btn_delete_prop_detail_{pid}", use_container_width=True):
                        delete_property(pid)
                        st.session_state["active_property_id"] = None
                        set_flash_message(f"Liegenschaft '{prop['name']}' wurde gelöscht.", icon="🗑️")
                        st.rerun()

# TAB 3: Betriebskosten & Finanzen
elif menu == "Betriebskosten & Finanzen":
    col_hdr_main, col_hdr_gear = st.columns([0.84, 0.16])
    with col_hdr_gear:
        st.write("")
        gear_lbl_f = f"Einstellungen{' 🔴' if has_unsaved_settings_changes() else ''}"
        if st.button(gear_lbl_f, icon=":material/settings:", key="btn_gear_finances", use_container_width=True, help="Einstellungen, Vermieterdaten & Modell öffnen"):
            if has_any_unsaved_changes():
                st.session_state["pending_nav"] = {"type": "settings", "previous": "Betriebskosten & Finanzen"}
                st.session_state["show_unsaved_dialog"] = True
                st.rerun()
            else:
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

    # Liegenschaften für Filter vorbereiten
    all_properties = get_all_properties()
    prop_filter_options = {"🏢 Alle Liegenschaften (Gesamtübersicht)": None}
    for p in all_properties:
        p_name = p["name"]
        if p.get("alias"):
            p_name += f" ({p['alias']})"
        prop_filter_options[f"🏢 {p_name}"] = p["property_id"]

    col_prop_sel, col_yr_sel, col_yr_add = st.columns([1.7, 1.4, 0.9])
    with col_prop_sel:
        saved_prop_id = st.session_state.get("active_finance_property_id", None)
        prop_labels = list(prop_filter_options.keys())
        default_prop_idx = 0
        for idx, (lbl, pid) in enumerate(prop_filter_options.items()):
            if pid == saved_prop_id:
                default_prop_idx = idx
                break

        selected_prop_label = st.selectbox(
            "Liegenschaft auswählen",
            options=prop_labels,
            index=default_prop_idx,
            key="finance_property_selector",
            help="Wähle eine bestimmte Liegenschaft aus, um nur deren Mieter und Kosten zu sehen, oder wähle die Gesamtübersicht aller Liegenschaften."
        )
        selected_property_id = prop_filter_options[selected_prop_label]
        st.session_state["active_finance_property_id"] = selected_property_id

    with col_yr_sel:
        default_lbl = list(year_labels.keys())[0]
        stored_yr = st.session_state.get("active_finance_year", current_year)
        for k, v in year_labels.items():
            if v == stored_yr:
                default_lbl = k
                break
        yr_idx = list(year_labels.keys()).index(default_lbl) if default_lbl in year_labels else 0

        selected_lbl = st.selectbox(
            "Abrechnungsjahr",
            options=list(year_labels.keys()),
            index=yr_idx,
            key="finance_year_selector"
        )
        selected_year = year_labels.get(selected_lbl, current_year)
        st.session_state["active_finance_year"] = selected_year

    with col_yr_add:
        st.write("")
        st.write("")
        with st.popover("Neues Jahr...", use_container_width=True):
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
                    c = copy_expenses_from_year(copy_source, target_yr, property_id=selected_property_id)
                    set_flash_message(f"{c} Positionen aus {copy_source} für {target_yr} übernommen.")
                else:
                    set_flash_message(f"Abrechnungsjahr {target_yr} ist nun aktiv.")
                st.session_state["active_finance_year"] = target_yr
                st.rerun()

    # Daten für das gewählte Jahr und die gewählte Liegenschaft laden
    expenses = get_expenses_for_year(selected_year, selected_property_id)
    statements = get_annual_utility_statements(selected_year, selected_property_id)

    total_expenses = sum(float(e["amount"]) for e in expenses)
    total_advances = sum(float(s["prepayments_paid"]) for s in statements)
    total_tenant_share = sum(float(s["tenant_share"]) for s in statements)
    total_balance = sum(float(s["balance"]) for s in statements)

    # Kennzahlen-Leiste
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        cost_metric_label = f"Kosten Liegenschaft ({selected_year})" if selected_property_id else f"Gesamtkosten ({selected_year})"
        st.metric(
            label=cost_metric_label,
            value=f"{total_expenses:,.2f} €",
            help="Summe aller umlagefähigen Betriebskosten für die getroffene Liegenschaftsauswahl in diesem Jahr."
        )
    with m2:
        st.metric(
            label="Geleistete Vorauszahlungen",
            value=f"{total_advances:,.2f} €",
            help="Summe aller durch die Mieter dieser Liegenschaft geleisteten bzw. vertraglich vereinbarten Jahresvorauszahlungen."
        )
    with m3:
        bal_label = "Saldo Liegenschaft" if selected_property_id else "Gesamtsaldo Mieter"
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
            help="Anzahl der verbuchten Belege und beteiligten Mietparteien in der getroffenen Auswahl."
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
        header_text = f"Mieter-Abrechnungen für {selected_prop_label.replace('🏢 ', '')} ({selected_year})" if selected_property_id else f"Mieter-Abrechnungen aller Liegenschaften ({selected_year})"
        st.subheader(header_text)
        st.caption("Aufstellung aller Mieter mit Wohnfläche, Kostenanteil, Vorauszahlungen, Saldo und direktem PDF-Export.")

        if not expenses:
            scope_desc = f"für '{selected_prop_label.replace('🏢 ', '')}'" if selected_property_id else "in diesem Abrechnungsjahr"
            st.info(f"Für das Abrechnungsjahr {selected_year} wurden {scope_desc} noch keine Betriebskosten erfasst. Daher beträgt der berechnete Kostenanteil für die Mieter 0,00 €.")
            if available_years:
                other_years = [y for y in available_years if y != selected_year]
                if other_years:
                    pref_copy_yr = 2025 if 2025 in other_years else other_years[0]
                    if st.button(f"Kostenpositionen aus {pref_copy_yr} als Vorlage übernehmen", type="primary", key="btn_copy_quick"):
                        count = copy_expenses_from_year(pref_copy_yr, selected_year, property_id=selected_property_id)
                        set_flash_message(f"{count} Positionen aus {pref_copy_yr} erfolgreich übernommen.")
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

                row_dict = {
                    "Mieter": s["full_name"],
                    "Wohneinheit": s["unit_number"]
                }
                if not selected_property_id:
                    row_dict["Liegenschaft"] = s.get("property_name") or "-"
                row_dict.update({
                    "Fläche": f"{s['area_sqm']:.1f} m²",
                    "Kostenanteil": f"{s['tenant_share']:,.2f} €",
                    "Vorauszahlungen": f"{s['prepayments_paid']:,.2f} €",
                    "Abrechnungssaldo": bal_formatted,
                    "Ergebnis": s["status_label"]
                })
                df_statements.append(row_dict)

            st.dataframe(pd.DataFrame(df_statements), use_container_width=True, hide_index=True)

            # Einzelausdruck & Abrechnungsbrief (DIN 5008)
            st.markdown("")
            with st.container(border=True):
                st.markdown("**Einzelausdruck & Abrechnungsbrief (DIN 5008)**")
                scope_info = f"der Liegenschaft '{selected_prop_label.replace('🏢 ', '')}'" if selected_property_id else ""
                st.caption(f"Wähle einen Mieter {scope_info} aus, um die vollständige, rechtssichere Nebenkostenabrechnung als druckfertiges PDF zu erstellen.")

                col_t_sel, col_t_btn = st.columns([3, 1.5])
                with col_t_sel:
                    tenant_map = {
                        f"{s['full_name']} ({s['unit_number']}{' · ' + s['property_name'] if not selected_property_id else ''})": s["tenant_id"] 
                        for s in statements
                    }
                    selected_tenant_label = st.selectbox(
                        "Mieter auswählen", 
                        list(tenant_map.keys()), 
                        key=f"sel_t_bill_{selected_year}_{selected_property_id}"
                    )
                    selected_tenant_id = tenant_map.get(selected_tenant_label)
                with col_t_btn:
                    st.write("")
                    st.write("")
                    btn_gen_statement = st.button("Abrechnung generieren", type="primary", use_container_width=True, key=f"btn_gen_stmt_{selected_year}_{selected_property_id}")

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
            if selected_property_id:
                st.info(f"In der Liegenschaft '{selected_prop_label.replace('🏢 ', '')}' sind aktuell keine Mieter erfasst.")
            else:
                st.info("Aktuell sind noch keine Mieter im System erfasst.")

    # 2. TAB: Kostenaufstellung & Bearbeitung
    with tab_cost_edit:
        cost_edit_header = f"Kostenaufstellung für {selected_prop_label.replace('🏢 ', '')} ({selected_year})" if selected_property_id else f"Kostenaufstellung aller Liegenschaften ({selected_year})"
        st.subheader(cost_edit_header)
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
                    set_flash_message(f"Kostenposition #{cur_exp['id']} ({edit_cat}) wurde erfolgreich aktualisiert.")
                    st.rerun()

                if btn_del:
                    delete_expense(cur_exp["id"])
                    set_flash_message(f"Kostenposition #{cur_exp['id']} ({cur_exp['category']}) wurde gelöscht.", icon="🗑️")
                    st.rerun()
        else:
            scope_no_exp = f"für die Liegenschaft '{selected_prop_label.replace('🏢 ', '')}'" if selected_property_id else "in diesem Abrechnungsjahr"
            st.info(f"Für das Abrechnungsjahr {selected_year} sind {scope_no_exp} noch keine Kostenpositionen erfasst.")
            if available_years:
                other_years = [y for y in available_years if y != selected_year]
                if other_years:
                    pref_copy_yr = 2025 if 2025 in other_years else other_years[0]
                    if st.button(f"Kostenpositionen aus {pref_copy_yr} als Vorlage kopieren", type="primary", key="btn_copy_template_edit"):
                        count = copy_expenses_from_year(pref_copy_yr, selected_year, property_id=selected_property_id)
                        set_flash_message(f"{count} Positionen aus {pref_copy_yr} für {selected_year} übernommen.")
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
                def_prop_idx = 0
                if selected_property_id:
                    for idx, (p_name, p_id) in enumerate(prop_options.items()):
                        if p_id == selected_property_id:
                            def_prop_idx = idx
                            break
                add_prop_label = st.selectbox("Liegenschaft", list(prop_options.keys()), index=def_prop_idx)
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
                    set_flash_message(f"Kostenposition '{final_cat}' über {add_amt:,.2f} € erfolgreich für {int(add_yr)} gespeichert.")
                    st.session_state["active_finance_year"] = int(add_yr)
                    st.rerun()
