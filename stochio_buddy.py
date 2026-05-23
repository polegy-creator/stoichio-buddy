import json
import html
import hashlib
import re
from collections import defaultdict
from datetime import datetime
from io import StringIO
from types import SimpleNamespace

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from stoichio.chemistry.density_engine import (
    DEFAULT_DIE_DIAMETER_MM,
    measured_density,
    relative_density_percent,
    target_height_from_mass,
    target_mass_from_height,
    theoretical_density_from_cell,
    unit_cell_volume_from_lattice,
)
from stoichio.chemistry.formula_parser import normalize_formula, parse_formula
from stoichio.lab_manager import (
    add_powder,
    check_stock,
    clear_history_for_target,
    clear_history_for_target_id,
    clear_target_density_history_for_person,
    configure_apps_script,
    configure_google_sheets,
    consume_stock,
    delete_history_entry,
    delete_material_density,
    delete_powder,
    delete_powder_set,
    format_target_id,
    load_history,
    load_inventory,
    load_inventory_log,
    load_material_densities,
    load_powders,
    load_powder_sets,
    log_synthesis,
    log_target_density,
    matching_powder_sets_for_target,
    related_material_density_records,
    relevant_powders_for_target,
    record_powder_set_use,
    restore_backup_data,
    save_powder_set,
    set_preferred_material_density,
    set_inventory_quantity,
    storage_error,
    storage_label,
    update_material_density_review_status,
    upsert_material_density,
    validate_backup_data,
)
from stoichio.ui_pages import (
    history as history_page,
    material_density as material_density_page,
    powder_mass as powder_mass_page,
    powders_inventory as powders_inventory_page,
    target_density as target_density_page,
)
from stoichio.chemistry.stoich_engine import (
    MASS_BASIS_TARGET_FORMULA,
    MASS_BASIS_TOTAL_PRECURSOR,
    compute_recipe,
    infer_target_mass_from_recipe,
)


st.set_page_config(
    page_title="Stoichio Buddy",
    page_icon=":material/science:",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_CACHE_TTL_SECONDS = 20
LOW_STOCK_THRESHOLD_G = 10.0


def theme_colors(mode):
    if mode == "Dark":
        return {
            "accent": "#f59f3a",
            "accent_soft": "#3a2a17",
            "background": "#0d151b",
            "surface": "#111f28",
            "panel": "#152834",
            "sidebar": "#0a1218",
            "border": "#2d4655",
            "text": "#ecf5f8",
            "muted": "#9eb1bc",
            "input": "#132532",
            "control_bg": "#132532",
            "control_text": "#edf8fb",
            "control_border": "#416171",
            "button_bg": "#f59f3a",
            "button_text": "#1f1308",
            "primary_text": "#1f1308",
            "table_bg": "#10212c",
            "table_header": "#183442",
        }

    return {
        "accent": "#f59f3a",
        "accent_soft": "#fff2df",
        "background": "#ffffff",
        "surface": "#ffffff",
        "panel": "#f7fafb",
        "sidebar": "#f7fafb",
        "border": "#d7dee4",
        "text": "#16232e",
        "muted": "#5d6b78",
        "input": "#ffffff",
        "control_bg": "#ffffff",
        "control_text": "#16232e",
        "control_border": "#d7dee4",
        "button_bg": "#f59f3a",
        "button_text": "#1f1308",
        "primary_text": "#1f1308",
        "table_bg": "#edf7fb",
        "table_header": "#d5eaf2",
    }


def apply_theme(mode):
    colors = theme_colors(mode)

    css = """
    <style>
    :root {
        --sb-accent: __ACCENT__;
        --sb-accent-soft: __ACCENT_SOFT__;
        --sb-bg: __BACKGROUND__;
        --sb-surface: __SURFACE__;
        --sb-border: __BORDER__;
        --sb-muted: __MUTED__;
        --sb-panel: __PANEL__;
        --sb-sidebar: __SIDEBAR__;
        --sb-text: __TEXT__;
        --sb-input: __INPUT__;
        --sb-control-bg: __CONTROL_BG__;
        --sb-control-text: __CONTROL_TEXT__;
        --sb-control-border: __CONTROL_BORDER__;
        --sb-button-bg: __BUTTON_BG__;
        --sb-button-text: __BUTTON_TEXT__;
        --sb-primary-text: __PRIMARY_TEXT__;
        --sb-table-bg: __TABLE_BG__;
        --sb-table-header: __TABLE_HEADER__;
    }

    .stApp,
    [data-testid="stAppViewContainer"] {
        background: var(--sb-bg);
        color: var(--sb-text);
    }

    html,
    body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stSidebarContent"],
    .sb-table-wrap {
        scrollbar-width: thin;
        scrollbar-color: color-mix(in srgb, var(--sb-accent) 42%, transparent) transparent;
        scrollbar-gutter: stable;
    }

    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: transparent;
        border-radius: 999px;
    }

    ::-webkit-scrollbar-thumb {
        background: color-mix(in srgb, var(--sb-accent) 36%, transparent);
        border: 2px solid transparent;
        background-clip: padding-box;
        border-radius: 999px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: color-mix(in srgb, var(--sb-accent) 72%, transparent);
        background-clip: padding-box;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stSidebarContent"] {
        overflow-y: auto;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 1.6rem;
        padding-bottom: 3rem;
    }

    [data-testid="stHeader"],
    header {
        background: var(--sb-bg);
        color: var(--sb-text);
        box-shadow: none;
    }

    [data-testid="stHeader"] *,
    header * {
        color: var(--sb-text);
    }

    [data-testid="stToolbar"],
    [data-testid="stToolbar"] *,
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"] {
        background: transparent;
        color: var(--sb-text);
    }

    [data-testid="stSidebar"] {
        background: var(--sb-sidebar);
        border-right: 1px solid var(--sb-border);
    }

    [data-testid="stSidebar"] * {
        color: var(--sb-text);
    }

    h1, h2, h3, h4, h5, h6,
    label,
    p,
    [data-testid="stMarkdownContainer"],
    [data-testid="stWidgetLabel"] {
        color: var(--sb-text);
    }

    .app-kicker {
        color: var(--sb-muted);
        font-size: 0.9rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.15rem;
    }

    .app-title {
        color: var(--sb-text);
        font-size: 2.15rem;
        font-weight: 760;
        line-height: 1.12;
        margin-bottom: 0.25rem;
    }

    .app-subtitle {
        color: var(--sb-muted);
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }

    .section-card {
        border: 1px solid var(--sb-border);
        border-radius: 8px;
        background: var(--sb-surface);
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
    }

    .hint {
        color: var(--sb-muted);
        font-size: 0.9rem;
    }

    div[data-testid="stMetric"] {
        border: 1px solid var(--sb-border);
        border-radius: 8px;
        padding: 0.8rem 0.9rem;
        background: var(--sb-panel);
    }

    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--sb-text);
    }

    [data-testid="stExpander"] details {
        border: 1px solid var(--sb-border) !important;
        border-radius: 8px !important;
        background: var(--sb-surface) !important;
        overflow: hidden;
    }

    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary:hover,
    [data-testid="stExpander"] summary:focus,
    [data-testid="stExpander"] summary:focus-visible,
    [data-testid="stExpander"] details[open] > summary {
        background: var(--sb-panel) !important;
        color: var(--sb-text) !important;
        box-shadow: none !important;
        outline: none !important;
    }

    [data-testid="stExpander"] summary *,
    [data-testid="stExpander"] details[open] > summary * {
        color: var(--sb-text) !important;
    }

    [data-testid="stExpander"] summary:hover {
        box-shadow: inset 3px 0 0 var(--sb-accent) !important;
    }

    [data-baseweb="tab-list"] {
        gap: 0.35rem;
        border-bottom: 1px solid var(--sb-border);
    }

    [data-baseweb="tab"] {
        background: transparent !important;
        color: var(--sb-muted) !important;
        border-radius: 7px 7px 0 0 !important;
        border: 1px solid transparent !important;
    }

    [data-baseweb="tab"] *,
    [data-baseweb="tab"][aria-selected="true"] * {
        color: inherit !important;
    }

    [data-baseweb="tab"]:hover,
    [data-baseweb="tab"][aria-selected="true"],
    [data-baseweb="tab"][aria-selected="true"]:focus {
        background: var(--sb-panel) !important;
        color: var(--sb-text) !important;
        border-color: var(--sb-border) !important;
        box-shadow: inset 0 -3px 0 var(--sb-accent) !important;
    }

    [data-testid="stAlert"] {
        border-radius: 8px;
        border: 1px solid var(--sb-border);
    }

    .stTextInput input,
    .stNumberInput input,
    textarea,
    [data-baseweb="select"] > div,
    [data-baseweb="input"] {
        background-color: var(--sb-control-bg);
        color: var(--sb-control-text);
        border-color: var(--sb-control-border);
    }

    .stTextInput input::placeholder,
    textarea::placeholder {
        color: var(--sb-muted);
        opacity: 1;
    }

    [data-baseweb="select"] span,
    [data-baseweb="select"] input,
    [data-baseweb="popover"] * {
        color: var(--sb-control-text);
    }

    [data-baseweb="popover"] {
        background: var(--sb-control-bg);
    }

    [data-baseweb="popover"] [role="listbox"],
    [data-baseweb="menu"],
    ul[role="listbox"] {
        background: var(--sb-control-bg) !important;
        color: var(--sb-control-text) !important;
        border: 1px solid var(--sb-accent) !important;
        border-radius: 8px !important;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.38) !important;
        padding: 0.25rem !important;
    }

    [role="option"],
    [data-baseweb="menu"] li,
    [data-baseweb="popover"] li {
        background: var(--sb-control-bg) !important;
        color: var(--sb-control-text) !important;
        border-radius: 6px !important;
    }

    [role="option"] *,
    [data-baseweb="menu"] li *,
    [data-baseweb="popover"] li * {
        color: var(--sb-control-text) !important;
    }

    [role="option"]:hover,
    [role="option"][aria-selected="true"],
    [data-baseweb="menu"] li:hover,
    [data-baseweb="popover"] li:hover {
        background: var(--sb-accent) !important;
        color: var(--sb-button-text) !important;
    }

    [role="option"]:hover *,
    [role="option"][aria-selected="true"] *,
    [data-baseweb="menu"] li:hover *,
    [data-baseweb="popover"] li:hover * {
        color: var(--sb-button-text) !important;
    }

    [role="tooltip"],
    [data-baseweb="tooltip"],
    [data-baseweb="popover"] [role="tooltip"],
    div[data-testid="stTooltipContent"] {
        background: var(--sb-control-bg) !important;
        color: var(--sb-control-text) !important;
        border: 1px solid var(--sb-accent) !important;
        border-radius: 8px !important;
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35) !important;
    }

    [role="tooltip"] *,
    [data-baseweb="tooltip"] *,
    [data-baseweb="popover"] [role="tooltip"] *,
    div[data-testid="stTooltipContent"] * {
        color: var(--sb-control-text) !important;
        background: transparent !important;
    }

    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
        background: var(--sb-table-bg);
        border: 1px solid var(--sb-border);
        border-radius: 8px;
        overflow: hidden;
    }

    [data-testid="stDataFrame"] canvas,
    [data-testid="stDataFrame"] [role="grid"],
    [data-testid="stDataFrame"] div {
        background-color: var(--sb-table-bg);
    }

    .sb-table-wrap {
        width: 100%;
        max-height: min(72vh, 720px);
        overflow: auto;
        overscroll-behavior: contain;
        border: 1px solid var(--sb-border);
        border-radius: 8px;
        background: var(--sb-table-bg);
        margin-bottom: 0.75rem;
    }

    .sb-table {
        min-width: 100%;
        border-collapse: collapse;
        background: var(--sb-table-bg);
        color: var(--sb-text);
        font-size: 0.94rem;
    }

    .sb-table th {
        background: var(--sb-table-header);
        color: var(--sb-text);
        font-weight: 750;
        text-align: left;
        position: sticky;
        top: 0;
        z-index: 2;
        padding: 0.8rem 0.95rem;
        border-bottom: 1px solid var(--sb-border);
        line-height: 1.35;
        vertical-align: top;
        white-space: nowrap;
    }

    .sb-table td {
        background: var(--sb-table-bg);
        color: var(--sb-text);
        padding: 0.85rem 0.95rem;
        border-bottom: 1px solid var(--sb-border);
        line-height: 1.45;
        vertical-align: top;
        white-space: nowrap;
    }

    .sb-table th.sb-cell-wrap,
    .sb-table td.sb-cell-wrap {
        min-width: 180px;
        max-width: 520px;
        white-space: normal;
        overflow-wrap: anywhere;
    }

    .sb-table td .sb-cell-content {
        display: block;
    }

    .sb-table td.sb-cell-wrap .sb-cell-content {
        display: -webkit-box;
        max-height: 4.35em;
        overflow: hidden;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 3;
    }

    .sb-table td.sb-cell-wrap a {
        overflow-wrap: anywhere;
    }

    .sb-table td:first-child,
    .sb-table th:first-child {
        padding-left: 2.1rem;
    }

    .sb-table td:last-child,
    .sb-table th:last-child {
        padding-right: 2.1rem;
    }

    .sb-table tr:last-child td {
        border-bottom: 0;
    }

    .sb-table tr.stock-low td {
        background: color-mix(in srgb, var(--sb-accent) 18%, var(--sb-table-bg)) !important;
    }

    .sb-table tr.stock-low td:first-child {
        border-left: 3px solid var(--sb-accent);
    }

    .sb-table tr.stock-short td,
    .sb-table tr.stock-empty td,
    .sb-table tr.stock-missing td {
        background: color-mix(in srgb, #d64a4a 22%, var(--sb-table-bg)) !important;
    }

    .sb-table tr.stock-short td:first-child,
    .sb-table tr.stock-empty td:first-child,
    .sb-table tr.stock-missing td:first-child {
        border-left: 3px solid #d64a4a;
    }

    .sb-table tr.codex-seeded td {
        background: color-mix(in srgb, #2f80ed 18%, var(--sb-table-bg)) !important;
    }

    .sb-table tr.codex-seeded td:first-child {
        border-left: 3px solid #2f80ed;
    }

    .history-item {
        border: 1px solid var(--sb-border);
        border-radius: 8px;
        background: var(--sb-panel);
        padding: 0.65rem 0.75rem;
        margin-bottom: 0.45rem;
    }

    .history-item-title {
        color: var(--sb-text);
        font-weight: 750;
        margin-bottom: 0.15rem;
    }

    .history-item-meta {
        color: var(--sb-muted);
        font-size: 0.9rem;
    }

    button,
    .stButton > button,
    .stDownloadButton > button,
    [data-testid="baseButton-secondary"],
    [data-testid="baseButton-minimal"],
    [data-testid="baseButton-header"] {
        border-radius: 7px;
        font-weight: 700;
        background: var(--sb-button-bg) !important;
        color: var(--sb-button-text) !important;
        border: 1px solid var(--sb-accent) !important;
        transition: filter 120ms ease, box-shadow 120ms ease, transform 120ms ease;
    }

    button *,
    .stButton > button *,
    .stDownloadButton > button *,
    [data-testid="baseButton-secondary"] *,
    [data-testid="baseButton-minimal"] *,
    [data-testid="baseButton-header"] * {
        color: inherit !important;
    }

    button:hover,
    .stButton > button:hover,
    .stDownloadButton > button:hover,
    [data-testid="baseButton-secondary"]:hover,
    [data-testid="baseButton-minimal"]:hover,
    [data-testid="baseButton-header"]:hover {
        background: var(--sb-button-bg) !important;
        color: var(--sb-button-text) !important;
        border-color: var(--sb-accent) !important;
        filter: brightness(1.14) saturate(1.08);
        box-shadow: 0 0 0 2px rgba(245, 159, 58, 0.22), 0 6px 16px rgba(245, 159, 58, 0.18);
        transform: translateY(-1px);
    }

    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {
        background: var(--sb-accent) !important;
        color: var(--sb-primary-text) !important;
        border-color: var(--sb-accent) !important;
    }

    .stButton > button[kind="primary"] *,
    [data-testid="baseButton-primary"] * {
        color: inherit !important;
    }

    .stButton > button[kind="primary"]:hover,
    [data-testid="baseButton-primary"]:hover {
        filter: brightness(1.14) saturate(1.08);
        color: var(--sb-primary-text) !important;
    }

    .stButton > button[kind="tertiary"] {
        min-width: 2.1rem;
        min-height: 2.1rem;
        padding: 0.25rem 0.45rem;
        background: color-mix(in srgb, var(--sb-accent) 14%, transparent) !important;
        color: var(--sb-accent) !important;
        border-color: color-mix(in srgb, var(--sb-accent) 55%, var(--sb-border)) !important;
    }

    .stButton > button[kind="tertiary"]:hover {
        background: color-mix(in srgb, var(--sb-accent) 28%, transparent) !important;
        color: var(--sb-accent) !important;
    }
    </style>
    """

    for key, value in colors.items():
        css = css.replace("__" + key.upper() + "__", value)

    st.markdown(css, unsafe_allow_html=True)


@st.cache_data(ttl=DATA_CACHE_TTL_SECONDS, show_spinner=False)
def cached_load_powders(storage_status):
    return load_powders()


@st.cache_data(ttl=DATA_CACHE_TTL_SECONDS, show_spinner=False)
def cached_load_inventory(storage_status):
    return load_inventory()


@st.cache_data(ttl=DATA_CACHE_TTL_SECONDS, show_spinner=False)
def cached_load_inventory_log(storage_status):
    return load_inventory_log()


@st.cache_data(ttl=DATA_CACHE_TTL_SECONDS, show_spinner=False)
def cached_load_history(storage_status):
    return load_history()


@st.cache_data(ttl=DATA_CACHE_TTL_SECONDS, show_spinner=False)
def cached_load_material_densities(storage_status):
    return load_material_densities()


@st.cache_data(ttl=DATA_CACHE_TTL_SECONDS, show_spinner=False)
def cached_load_powder_sets(storage_status):
    return load_powder_sets()


def clear_data_cache():
    cached_load_powders.clear()
    cached_load_inventory.clear()
    cached_load_inventory_log.clear()
    cached_load_history.clear()
    cached_load_material_densities.clear()
    cached_load_powder_sets.clear()


def load_app_state(storage_status):
    st.session_state.db = cached_load_powders(storage_status)
    st.session_state.inventory = cached_load_inventory(storage_status)
    return st.session_state.db, st.session_state.inventory


def recipe_dataframe(recipe_masses, inventory=None):
    rows = []
    for powder, grams in recipe_masses.items():
        row = {
            "Powder": powder,
            "Mass (g)": round(grams, 3),
            "Exact mass (g)": grams,
        }

        if inventory is not None:
            available = inventory.get(normalize_formula(powder))
            if available is None:
                row.update(
                    {
                        "Available (g)": "",
                        "After recipe (g)": "",
                        "Stock status": "Not in inventory",
                    }
                )
            else:
                remaining = available - grams
                if remaining < 0:
                    status = f"Short by {abs(remaining):.3f} g"
                elif remaining < LOW_STOCK_THRESHOLD_G:
                    status = f"Low after recipe (<{LOW_STOCK_THRESHOLD_G:g} g)"
                else:
                    status = "OK"

                row.update(
                    {
                        "Available (g)": round(available, 3),
                        "After recipe (g)": round(remaining, 3),
                        "Stock status": status,
                    }
                )

        rows.append(row)

    rows.sort(
        key=lambda row: (
            0 if "short" in str(row.get("Stock status", "")).lower() else 1,
            0 if "low" in str(row.get("Stock status", "")).lower() else 1,
            row.get("Powder", ""),
        )
    )
    return pd.DataFrame(rows)


def database_dataframe(db):
    return pd.DataFrame(
        [
            {
                "Powder": powder,
                "Molar mass (g/mol)": round(record["molar_mass"], 3),
                "Composition": ", ".join(
                    f"{element}{amount:g}" for element, amount in record["elements"].items()
                ),
            }
            for powder, record in db.items()
        ]
    )


def inventory_dataframe(inventory, recipe_masses=None):
    rows = []
    recipe_masses = recipe_masses or {}
    normalized_requirements = {
        normalize_formula(powder): grams
        for powder, grams in recipe_masses.items()
    }

    for powder, grams in inventory.items():
        required = normalized_requirements.get(normalize_formula(powder), 0.0)
        remaining = grams - required

        if required > grams:
            status = f"Short for recipe by {abs(remaining):.3f} g"
        elif grams < LOW_STOCK_THRESHOLD_G:
            status = f"Low stock (<{LOW_STOCK_THRESHOLD_G:g} g)"
        else:
            status = "OK"

        row = {
            "Powder": powder,
            "Available (g)": round(grams, 3),
            "Status": status,
        }
        if recipe_masses:
            row["Needed for last recipe (g)"] = round(required, 3) if required else ""
            row["After last recipe (g)"] = round(remaining, 3) if required else round(grams, 3)
        rows.append(row)

    rows.sort(
        key=lambda row: (
            0 if "short" in str(row.get("Status", "")).lower() else 1,
            0 if "low" in str(row.get("Status", "")).lower() else 1,
            row.get("Powder", ""),
        )
    )
    return pd.DataFrame(rows)


def inventory_log_dataframe(log_entries, limit=50):
    rows = []
    for entry in reversed(log_entries[-limit:]):
        rows.append(
            {
                "Time": format_history_time(entry.get("time", "")),
                "Powder": entry.get("powder", ""),
                "Action": entry.get("action", ""),
                "Change (g)": entry.get("change_g", ""),
                "Before (g)": entry.get("before_g", ""),
                "After (g)": entry.get("after_g", ""),
                "Recipe": entry.get("recipe_id", ""),
                "Reason": entry.get("reason", ""),
            }
        )
    return pd.DataFrame(rows)


def material_density_dataframe(records):
    columns = [
        "Record",
        "Formula",
        "Phase",
        "Theoretical density (g/cm3)",
        "Reported density (g/cm3)",
        "Delta vs reported (g/cm3)",
        "Density check",
        "Trust status",
        "Verified by",
        "Verified date",
        "Unit cell volume (A3)",
        "Z",
        "Crystal system",
        "a (A)",
        "b (A)",
        "c (A)",
        "alpha",
        "beta",
        "gamma",
        "Density source",
        "Origin",
        "Reference",
        "Notes",
    ]
    rows = []
    sorted_records = sorted(
        records.items(),
        key=lambda item: density_record_sort_key(item[0], item[1]),
    )
    for formula, record in sorted_records:
        rows.append(
            {
                "Record": record.get("display_name", formula),
                "Formula": record.get("formula", formula),
                "Phase": record.get("phase", ""),
                "Theoretical density (g/cm3)": (
                    round(record["theoretical_density_g_cm3"], 4)
                    if record.get("theoretical_density_g_cm3") is not None
                    else ""
                ),
                "Reported density (g/cm3)": (
                    round(record["reported_density_g_cm3"], 4)
                    if record.get("reported_density_g_cm3") is not None
                    else ""
                ),
                "Delta vs reported (g/cm3)": (
                    round(record["density_delta_g_cm3"], 5)
                    if record.get("density_delta_g_cm3") is not None
                    else ""
                ),
                "Density check": record.get("density_validation", ""),
                "Trust status": density_trust_status(record),
                "Verified by": record.get("verified_by", ""),
                "Verified date": record.get("verified_date", ""),
                "Unit cell volume (A3)": (
                    round(record["unit_cell_volume_A3"], 4)
                    if record.get("unit_cell_volume_A3") is not None
                    else ""
                ),
                "Z": record.get("z") if record.get("z") is not None else "",
                "Crystal system": record.get("crystal_system", ""),
                "a (A)": record.get("a_A") if record.get("a_A") is not None else "",
                "b (A)": record.get("b_A") if record.get("b_A") is not None else "",
                "c (A)": record.get("c_A") if record.get("c_A") is not None else "",
                "alpha": record.get("alpha_deg") if record.get("alpha_deg") is not None else "",
                "beta": record.get("beta_deg") if record.get("beta_deg") is not None else "",
                "gamma": record.get("gamma_deg") if record.get("gamma_deg") is not None else "",
                "Density source": record.get("density_source", ""),
                "Origin": record.get("origin", "Lab entry"),
                "Reference": record.get("source", ""),
                "Notes": record.get("notes", ""),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def density_trust_status(record):
    status = str(record.get("verification_status", "")).strip()
    if status:
        return status
    if str(record.get("origin", "")).lower().startswith("codex"):
        return "Codex seeded - verify before use"
    return "Lab entry - unverified"


def density_record_is_verified(record):
    status = density_trust_status(record).lower()
    return "preferred" in status or "checked" in status


def density_record_is_blocked(record):
    return "do not use" in density_trust_status(record).lower()


def density_record_sort_key(record_key, record):
    status = density_trust_status(record).lower()
    if "do not use" in status:
        trust_rank = 99
    elif "preferred" in status:
        trust_rank = 0
    elif "checked" in status:
        trust_rank = 1
    elif "lab entry" in status:
        trust_rank = 2
    elif "codex" in status:
        trust_rank = 3
    else:
        trust_rank = 4
    return (
        trust_rank,
        record.get("formula", record_key),
        record.get("phase", ""),
        record.get("display_name", record_key),
    )


def density_record_label(record_key, record, include_density=True):
    label = record.get("display_name") or record.get("formula") or record_key
    density = record.get("theoretical_density_g_cm3")
    if include_density and density:
        return f"{label} - {float(density):.4f} g/cm3 [{density_trust_status(record)}]"
    return label


def density_records_for_formula(target, material_densities):
    if not target:
        return None, [], "Enter a target formula first"

    try:
        key = normalize_formula(target)
    except ValueError as exc:
        return None, [], str(exc)

    records = [
        (record_key, record)
        for record_key, record in material_densities.items()
        if record.get("formula", record_key) == key or record_key == key
    ]
    records.sort(key=lambda item: density_record_sort_key(item[0], item[1]))

    if not records:
        return key, [], f"No saved density for {key}"

    return key, records, None


def target_cation_label(target):
    try:
        elements = sorted(element for element in parse_formula(normalize_formula(target)) if element != "O")
    except ValueError:
        return ""
    return ", ".join(elements)


def lookup_known_density(target, material_densities):
    key, records, error = density_records_for_formula(target, material_densities)
    if error:
        return key, None, error

    record_key, record = records[0]
    density = record.get("theoretical_density_g_cm3")
    if density is None or density <= 0:
        return key, None, f"Saved density for {density_record_label(record_key, record, False)} is missing"

    return record_key, float(density), None


def density_source_control(target, material_densities, key_prefix):
    source_mode = st.radio(
        "Theoretical density source",
        ["Known material density", "Use another density record", "Manual density"],
        horizontal=True,
        key=f"{key_prefix}_density_source",
    )

    if source_mode == "Known material density":
        normalized_target, density_records, error = density_records_for_formula(target, material_densities)
        if density_records:
            if len(density_records) > 1:
                selected_record_key = st.selectbox(
                    "Known density phase",
                    [record_key for record_key, _ in density_records],
                    format_func=lambda value: density_record_label(value, material_densities[value]),
                    key=f"{key_prefix}_known_density_phase",
                )
            else:
                selected_record_key = density_records[0][0]

            record = material_densities[selected_record_key]
            density = record.get("theoretical_density_g_cm3")
            if density is None or density <= 0:
                st.warning(f"Saved density for {density_record_label(selected_record_key, record, False)} is missing")
                return None, source_mode

            density = float(density)
            st.success(f"Using {density_record_label(selected_record_key, record)}")
            if not density_record_is_verified(record):
                st.warning(
                    "This density record is not lab-verified yet. "
                    "Check the source before using it for final planning."
                )
            if density_record_is_blocked(record):
                st.error("This density record is marked Do not use.")
                return None, source_mode
            if record.get("source") or record.get("density_source"):
                st.caption(
                    "Source: "
                    + (record.get("source") or record.get("density_source") or "saved material density")
                )
            st.session_state[f"{key_prefix}_density_verified"] = density_record_is_verified(record)
            st.session_state[f"{key_prefix}_density_record_key"] = selected_record_key
            return density, f"Known material density: {density_record_label(selected_record_key, record, False)}"
        else:
            related_records = related_material_density_records(target, material_densities)
            if related_records and normalized_target:
                cation_text = target_cation_label(target)
                st.warning(f"No exact density for {normalized_target}. Choose a related cation-containing record.")
                if cation_text:
                    st.caption(
                        f"Showing {len(related_records)} records that contain target cation(s): {cation_text}."
                    )
                selected_record_key = st.selectbox(
                    "Related density record",
                    [record_key for record_key, _ in related_records],
                    format_func=lambda value: density_record_label(value, material_densities[value]),
                    key=f"{key_prefix}_related_known_density",
                )
                source_record = material_densities[selected_record_key]
                if density_record_is_blocked(source_record):
                    st.error("This density record is marked Do not use.")
                    return None, source_mode
                volume = source_record.get("unit_cell_volume_A3")
                z_value = source_record.get("z")
                if volume and z_value:
                    try:
                        density = theoretical_density_from_cell(normalized_target, volume, z_value)
                        st.success(
                            f"Using {density_record_label(selected_record_key, source_record, False)} unit cell "
                            f"for {normalized_target}: {density:.4f} g/cm3"
                        )
                        st.caption(
                            f"Recalculated from V={volume:g} A3 and Z={z_value:g}; "
                            "molar mass comes from the current target formula."
                        )
                        st.session_state[f"{key_prefix}_density_verified"] = density_record_is_verified(source_record)
                        st.session_state[f"{key_prefix}_density_record_key"] = selected_record_key
                        return (
                            density,
                            f"Related material density: {density_record_label(selected_record_key, source_record, False)}",
                        )
                    except ValueError as exc:
                        st.warning(str(exc))
                else:
                    st.warning(f"{density_record_label(selected_record_key, source_record, False)} has no unit cell data.")
            else:
                st.warning(error)
        return None, source_mode

    if source_mode == "Use another density record":
        related_records = related_material_density_records(target, material_densities)
        all_records = sorted(
            material_densities.items(),
            key=lambda item: density_record_sort_key(item[0], item[1]),
        )
        show_all_density_records = False
        if related_records:
            cation_text = target_cation_label(target)
            if cation_text:
                st.caption(
                    f"Showing {len(related_records)} records that contain target cation(s): {cation_text}."
                )
            show_all_density_records = st.checkbox(
                "Show all density records",
                value=False,
                key=f"{key_prefix}_show_all_density_records",
            )
            record_choices = all_records if show_all_density_records else related_records
        else:
            record_choices = all_records
            if target:
                st.warning("No density records share cations with this target. Showing all records.")

        source_target = st.selectbox(
            "Density record to use",
            [""] + [record_key for record_key, _ in record_choices],
            format_func=lambda value: density_record_label(value, material_densities[value]) if value else "Choose saved material",
            key=f"{key_prefix}_density_record",
        )
        if not source_target:
            st.warning("Choose a saved material density record")
            return None, source_mode

        try:
            normalized_target = normalize_formula(target)
        except ValueError as exc:
            st.warning(str(exc))
            return None, source_mode

        source_record = material_densities[source_target]
        if not density_record_is_verified(source_record):
            st.warning(
                "This density record is not lab-verified yet. "
                "Check the source before using it for final planning."
            )
        if density_record_is_blocked(source_record):
            st.error("This density record is marked Do not use.")
            return None, source_mode
        volume = source_record.get("unit_cell_volume_A3")
        z_value = source_record.get("z")
        if volume and z_value:
            try:
                density = theoretical_density_from_cell(normalized_target, volume, z_value)
                st.success(
                    f"Using {density_record_label(source_target, source_record, False)} unit cell "
                    f"for {normalized_target}: "
                    f"{density:.4f} g/cm3"
                )
                st.caption(
                    f"Recalculated from V={volume:g} A3 and Z={z_value:g}; "
                    "molar mass comes from the current target formula."
                )
                st.session_state[f"{key_prefix}_density_verified"] = density_record_is_verified(source_record)
                st.session_state[f"{key_prefix}_density_record_key"] = source_target
                return density, f"Related/manual density record: {density_record_label(source_target, source_record, False)}"
            except ValueError as exc:
                st.warning(str(exc))
                return None, source_mode

        density = source_record.get("theoretical_density_g_cm3")
        if density:
            st.warning(
                f"{source_target} has no saved unit cell volume and Z. "
                "Using its stored density directly."
            )
            st.session_state[f"{key_prefix}_density_verified"] = density_record_is_verified(source_record)
            st.session_state[f"{key_prefix}_density_record_key"] = source_target
            return float(density), f"Stored density record: {density_record_label(source_target, source_record, False)}"

        st.warning(f"{source_target} has no usable density data")
        return None, source_mode

    density = st.number_input(
        "Manual theoretical density (g/cm3)",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.5f",
        key=f"{key_prefix}_manual_density",
    )
    st.session_state[f"{key_prefix}_density_verified"] = False
    st.session_state[f"{key_prefix}_density_record_key"] = ""
    return density if density > 0 else None, source_mode


def lattice_parameter_inputs(crystal_system):
    system = crystal_system.lower()
    a = b = c = alpha = beta = gamma = None

    if system == "cubic":
        a = st.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = c = a
        alpha = beta = gamma = 90.0
    elif system == "tetragonal":
        col_a, col_c = st.columns(2)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = a
        alpha = beta = gamma = 90.0
    elif system == "orthorhombic":
        col_a, col_b, col_c = st.columns(3)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = col_b.number_input("b (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        alpha = beta = gamma = 90.0
    elif system == "hexagonal":
        col_a, col_c = st.columns(2)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = a
        alpha = beta = 90.0
        gamma = 120.0
    elif system == "rhombohedral":
        col_a, col_alpha = st.columns(2)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        alpha = col_alpha.number_input(
            "alpha = beta = gamma (deg)",
            min_value=0.0,
            value=90.0,
            step=0.1,
            format="%.6f",
        )
        b = c = a
        beta = gamma = alpha
    elif system == "monoclinic":
        col_a, col_b, col_c = st.columns(3)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = col_b.number_input("b (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        beta = st.number_input("beta (deg)", min_value=0.0, value=90.0, step=0.1, format="%.6f")
        alpha = gamma = 90.0
    else:
        col_a, col_b, col_c = st.columns(3)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = col_b.number_input("b (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        col_alpha, col_beta, col_gamma = st.columns(3)
        alpha = col_alpha.number_input("alpha (deg)", min_value=0.0, value=90.0, step=0.1, format="%.6f")
        beta = col_beta.number_input("beta (deg)", min_value=0.0, value=90.0, step=0.1, format="%.6f")
        gamma = col_gamma.number_input("gamma (deg)", min_value=0.0, value=90.0, step=0.1, format="%.6f")

    return {
        "a": a,
        "b": b,
        "c": c,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
    }


def unknown_inventory_items(inventory, db):
    return sorted(powder for powder in inventory if powder not in db)


def format_history_time(value):
    if not value:
        return ""

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value).split(".")[0]

    return parsed.strftime("D-%d.%m.%y T-%H:%M:%S")


def history_entry_type(entry):
    return entry.get("entry_type", "synthesis")


def synthesis_history(history):
    return [entry for entry in history if history_entry_type(entry) == "synthesis"]


def target_density_history(history):
    return [entry for entry in history if history_entry_type(entry) == "target_density"]


def recipe_mass_basis(entry):
    calculation = entry.get("calculation") or {}
    if calculation.get("mass_basis"):
        return calculation["mass_basis"]
    if entry.get("mass_basis"):
        return entry["mass_basis"]
    if calculation:
        return MASS_BASIS_TOTAL_PRECURSOR
    return MASS_BASIS_TARGET_FORMULA


def mass_basis_label(mass_basis):
    if mass_basis == MASS_BASIS_TOTAL_PRECURSOR:
        return "Total precursor powder"
    if mass_basis == MASS_BASIS_TARGET_FORMULA:
        return "Target formula mass"
    return str(mass_basis or "")


def recipe_powder_basis(entry):
    calculation = entry.get("calculation") or {}
    if calculation.get("powder_basis") not in (None, ""):
        return calculation["powder_basis"]

    recipe = entry.get("recipe") or {}
    if recipe:
        return sum(float(grams) for grams in recipe.values())

    return entry.get("mass", "")


def history_dataframe(history):
    if not history:
        return pd.DataFrame()

    rows = []
    for entry in history:
        calculation = entry.get("calculation") or {}
        mass_basis = recipe_mass_basis(entry)
        rows.append(
            {
                "Target ID": entry.get("target_id", ""),
                "Target for": entry.get("target_for", ""),
                "Recipe ID": entry.get("recipe_id", ""),
                "Time": format_history_time(entry.get("time", entry.get("timestamp", ""))),
                "Target": entry.get("target", ""),
                "Input basis (g)": entry.get("mass", ""),
                "Input basis type": mass_basis_label(mass_basis),
                "Powder basis (g)": round(recipe_powder_basis(entry), 6),
                "Estimated target mass (g)": calculation.get("estimated_target_mass", ""),
                "Solve basis": calculation.get("basis", ""),
                "Residual": calculation.get("residual", ""),
                "Recipe": json.dumps(entry.get("recipe", {}), ensure_ascii=False),
                "Inventory deducted": entry.get("inventory_deducted", False),
                "Warning": entry.get("warning") or "",
                "Notes": entry.get("notes", ""),
            }
        )
    return pd.DataFrame(rows).iloc[::-1]


def target_density_dataframe(history):
    if not history:
        return pd.DataFrame()

    rows = []
    for entry in history:
        linked_recipe = entry.get("linked_recipe") or {}
        rows.append(
            {
                "Target ID": entry.get("target_id", ""),
                "Time": format_history_time(entry.get("time", entry.get("timestamp", ""))),
                "Target #": entry.get("target_number", ""),
                "Target for": entry.get("target_for", ""),
                "Formula": entry.get("target", ""),
                "Linked recipe": linked_recipe.get("recipe_id", ""),
                "Linked recipe entry": linked_recipe.get("entry_id", ""),
                "Measured density (g/cm3)": round(entry.get("measured_density_g_cm3", 0), 4),
                "Theoretical density (g/cm3)": round(entry.get("theoretical_density_g_cm3", 0), 4),
                "Relative density (%)": round(entry.get("relative_density_percent", 0), 2),
                "Final diameter (mm)": round(entry.get("final_diameter_mm", 0), 4),
                "Final height (mm)": round(entry.get("final_height_mm", 0), 4),
                "Final mass (g)": round(entry.get("final_mass_g", 0), 6),
                "Final volume (cm3)": round(entry.get("final_volume_cm3", 0), 6),
                "Density source": entry.get("density_source", ""),
                "Notes": entry.get("notes", ""),
            }
        )
    return pd.DataFrame(rows).iloc[::-1]


def recipe_coefficients_dataframe(result, recipe_masses):
    rows = []
    coefficients = result.get("coefficients", {})
    for powder, grams in recipe_masses.items():
        rows.append(
            {
                "Powder": powder,
                "Moles per target formula": coefficients.get(powder, ""),
                "Mass (g)": round(grams, 6),
            }
        )
    return pd.DataFrame(rows)


def known_recipe_height_check_dataframe(check_result):
    rows = []
    actual = check_result.get("actual_recipe", {})
    expected = check_result.get("expected_recipe", {})
    deviations = check_result.get("deviations", {})
    for powder in actual:
        rows.append(
            {
                "Powder": powder,
                "Known mass (g)": round(actual[powder], 6),
                "Round-trip mass (g)": round(expected.get(powder, 0.0), 6),
                "Difference (g)": round(deviations.get(powder, 0.0), 6),
            }
        )
    return pd.DataFrame(rows)


def recipe_balance_dataframe(result, powder_db):
    rows = []
    target = result.get("target", {})
    elements = result.get("elements", [])
    coefficients = result.get("coefficients", {})
    selected = list(coefficients.keys())

    for element in elements:
        delivered = 0.0
        for powder in selected:
            # The engine already solved these coefficients; this table is an audit
            # of the selected precursor contribution to each balanced element.
            delivered += coefficients.get(powder, 0.0) * powder_db[powder]["elements"].get(element, 0.0)
        target_amount = float(target.get(element, 0.0))
        rows.append(
            {
                "Element": element,
                "Target amount": round(target_amount, 8),
                "Delivered amount": round(delivered, 8),
                "Difference": round(delivered - target_amount, 10),
            }
        )

    return pd.DataFrame(rows)


def recipe_stoich_ratio_text(result):
    coefficients = result.get("coefficients", {}) if result else {}
    if not coefficients:
        return ""
    return ", ".join(f"{powder}: {amount:g}" for powder, amount in coefficients.items())


def recipe_basis_audit_dataframe(result, recipe_masses, planning_context=None):
    planning_context = planning_context or {}
    rows = [
        ["Calculation mode", planning_context.get("amount_mode", "Target formula mass")],
        ["Input mass basis", mass_basis_label(result.get("mass_basis", MASS_BASIS_TARGET_FORMULA))],
        ["Target formula mass (g)", result.get("estimated_target_mass", "")],
        ["Precursor powder total (g)", round(sum(recipe_masses.values()), 6)],
        ["Stoich ratio coefficients", recipe_stoich_ratio_text(result)],
        ["Solve basis", result.get("basis", "")],
        ["Ignored elements", ", ".join(result.get("ignored_elements") or [])],
        ["Residual", result.get("residual", "")],
    ]
    if planning_context.get("amount_mode") == "Pellet height":
        rows.extend(
            [
                ["Desired target height (mm)", planning_context.get("planning_height", "")],
                ["Die diameter (mm)", DEFAULT_DIE_DIAMETER_MM],
                ["Planning volume (cm3)", planning_context.get("planning_volume", "")],
                ["Theoretical density (g/cm3)", planning_context.get("theoretical_density", "")],
                ["Density source", planning_context.get("density_source", "")],
            ]
        )
    return pd.DataFrame(rows, columns=["Field", "Value"])


def recipe_validation_warnings(result, recipe_masses, stock_messages=None, planning_context=None):
    warnings = []
    if not result.get("exact", False):
        warnings.append("Stoichiometry is approximate; inspect the residual and element balance.")
    if stock_messages:
        warnings.append("Inventory is not enough for this recipe: " + "; ".join(stock_messages))
    if planning_context and planning_context.get("amount_mode") == "Pellet height":
        density_source = str(planning_context.get("density_source", ""))
        if density_source.startswith("Related"):
            warnings.append(
                "Pellet-height mode is using a related density record, not an exact density for this formula."
            )
        if not planning_context.get("density_verified", False):
            warnings.append("Pellet-height density source is not marked as lab-checked or preferred.")
    if any(mass <= 0 for mass in recipe_masses.values()):
        warnings.append("One or more selected powders calculated to zero mass; check the selected powder set.")
    return warnings


def recipe_calculation_metadata(result):
    if not result:
        return {}

    keys = (
        "basis",
        "residual",
        "exact",
        "coefficients",
        "elements",
        "ignored_elements",
        "input_mass",
        "mass_basis",
        "powder_basis",
        "target_molar_mass",
        "precursor_formula_mass",
        "formula_units",
        "estimated_target_mass",
    )
    return {key: result[key] for key in keys if key in result}


def target_lifecycle_dataframe(history=None, lifecycle_groups=None):
    if lifecycle_groups is None:
        lifecycle_groups = target_lifecycle_groups(history or [])
    rows = []
    for group_key, entries in lifecycle_groups:
        summary = target_lifecycle_summary(group_key, entries)
        latest_recipe = summary["recipes"][0] if summary["recipes"] else {}
        latest_density = summary["densities"][0] if summary["densities"] else {}
        recipe = latest_recipe.get("recipe", {})
        calculation = latest_recipe.get("calculation", {})
        linked_recipe = latest_density.get("linked_recipe", {}) if latest_density else {}
        mass_basis = recipe_mass_basis(latest_recipe) if latest_recipe else ""

        rows.append(
            {
                "Target ID": summary["target_id"],
                "Target for": group_key[0],
                "Formula": group_key[2],
                "Status": (
                    "Recipe + density"
                    if latest_recipe and latest_density
                    else "Recipe only"
                    if latest_recipe
                    else "Density only"
                    if latest_density
                    else ""
                ),
                "Recipe time": format_history_time(
                    latest_recipe.get("time", latest_recipe.get("timestamp", ""))
                ) if latest_recipe else "",
                "Recipe input basis (g)": latest_recipe.get("mass", ""),
                "Recipe input basis type": mass_basis_label(mass_basis),
                "Recipe powder basis (g)": (
                    round(recipe_powder_basis(latest_recipe), 6)
                    if latest_recipe
                    else ""
                ),
                "Estimated target mass (g)": calculation.get("estimated_target_mass", ""),
                "Recipe solve basis": calculation.get("basis", ""),
                "Recipe powders": ", ".join(
                    f"{powder}: {grams:.3f} g" for powder, grams in recipe.items()
                ),
                "Recipe notes": latest_recipe.get("notes", ""),
                "Density time": format_history_time(
                    latest_density.get("time", latest_density.get("timestamp", ""))
                ) if latest_density else "",
                "Density linked recipe": linked_recipe.get("recipe_id", ""),
                "Relative density (%)": (
                    round(latest_density.get("relative_density_percent", 0), 2)
                    if latest_density
                    else ""
                ),
                "Measured density (g/cm3)": (
                    round(latest_density.get("measured_density_g_cm3", 0), 4)
                    if latest_density
                    else ""
                ),
                "Theoretical density (g/cm3)": (
                    round(latest_density.get("theoretical_density_g_cm3", 0), 4)
                    if latest_density
                    else ""
                ),
                "Final diameter (mm)": (
                    round(latest_density.get("final_diameter_mm", 0), 4)
                    if latest_density
                    else ""
                ),
                "Final height (mm)": (
                    round(latest_density.get("final_height_mm", 0), 4)
                    if latest_density
                    else ""
                ),
                "Final mass (g)": (
                    round(latest_density.get("final_mass_g", 0), 6)
                    if latest_density
                    else ""
                ),
                "Density notes": latest_density.get("notes", ""),
            }
        )

    return pd.DataFrame(rows)


def target_lifecycle_status(summary):
    has_recipe = bool(summary["recipes"])
    has_density = bool(summary["densities"])
    if has_recipe and has_density:
        return "Complete"
    if has_recipe:
        return "Needs density"
    if has_density:
        return "Needs recipe"
    return "Empty"


def target_lifecycle_search_text(group_key, entries, summary):
    recipe_text = []
    for entry in summary["recipes"]:
        recipe_text.extend(entry.get("selected_powders") or [])
        recipe_text.extend(entry.get("recipe", {}).keys())
        recipe_text.append(str(entry.get("notes", "")))

    density_text = [
        str(entry.get("density_source", ""))
        + " "
        + str(entry.get("notes", ""))
        + " "
        + str((entry.get("linked_recipe") or {}).get("recipe_id", ""))
        + " "
        + " ".join((entry.get("linked_recipe") or {}).get("selected_powders") or [])
        for entry in summary["densities"]
    ]

    return " ".join(
        str(part)
        for part in [
            group_key[0],
            group_key[1],
            group_key[2],
            summary["title"],
            summary["meta"],
            *recipe_text,
            *density_text,
        ]
    ).lower()


def filter_target_lifecycle_groups(lifecycle_groups, search_text="", owner_filter="All", status_filter="All"):
    query = str(search_text or "").strip().lower()
    filtered = []

    for group_key, entries in lifecycle_groups:
        summary = target_lifecycle_summary(group_key, entries)
        owner = group_key[0]
        status = target_lifecycle_status(summary)

        if owner_filter != "All" and owner != owner_filter:
            continue
        if status_filter != "All" and status != status_filter:
            continue
        if query and query not in target_lifecycle_search_text(group_key, entries, summary):
            continue

        filtered.append((group_key, entries))

    return filtered


def grouped_history(history):
    groups = defaultdict(list)
    for entry in history:
        target = entry.get("target") or "Unknown target"
        groups[target].append(entry)
    return dict(sorted(groups.items(), key=lambda item: item[0]))


def grouped_target_density_history(history):
    groups = defaultdict(list)
    for entry in history:
        target_for = str(entry.get("target_for", "")).strip() or "Unassigned"
        groups[target_for].append(entry)
    return dict(sorted(groups.items(), key=lambda item: item[0].lower()))


def target_lifecycle_groups(history):
    groups = defaultdict(list)
    for entry in history:
        entry_type = history_entry_type(entry)
        if entry_type not in {"synthesis", "target_density"}:
            continue

        target_id = str(entry.get("target_id") or entry.get("recipe_id") or "Unassigned").strip()
        target_for = str(entry.get("target_for", "")).strip() or "Unassigned"
        target = entry.get("target") or "Unknown target"
        groups[(target_for, target_id, target)].append(entry)

    def sort_key(item):
        (_, target_id, _), entries = item
        latest_time = max(str(entry.get("time", entry.get("timestamp", ""))) for entry in entries)
        target_number = max(
            (
                int(entry.get("target_number"))
                for entry in entries
                if str(entry.get("target_number", "")).isdigit()
            ),
            default=0,
        )
        return (latest_time, str(item[0][0]).lower(), target_number, target_id)

    return sorted(groups.items(), key=sort_key, reverse=True)


def target_lifecycle_summary(group_key, entries):
    target_for, target_id, target = group_key
    recipes = [entry for entry in entries if history_entry_type(entry) == "synthesis"]
    densities = [entry for entry in entries if history_entry_type(entry) == "target_density"]
    latest_entry = max(
        entries,
        key=lambda entry: str(entry.get("time", entry.get("timestamp", ""))),
    )
    latest_time = format_history_time(latest_entry.get("time", latest_entry.get("timestamp", "")))
    status_parts = []
    status_parts.append(f"{len(recipes)} before-sintering recipe{'s' if len(recipes) != 1 else ''}")
    status_parts.append(f"{len(densities)} after-sintering density log{'s' if len(densities) != 1 else ''}")
    if not recipes:
        status_parts.append("recipe missing")
    if not densities:
        status_parts.append("density pending")

    return {
        "target_id": target_id,
        "title": f"{target_id} | {target} | {target_for}",
        "meta": " | ".join([latest_time] + status_parts),
        "recipes": sorted(recipes, key=lambda entry: str(entry.get("time", "")), reverse=True),
        "densities": sorted(densities, key=lambda entry: str(entry.get("time", "")), reverse=True),
    }


def next_target_number(history, target_for):
    person = str(target_for).strip()
    if not person:
        return 1

    used_numbers = []
    for entry in history:
        if str(entry.get("target_for", "")).strip() != person:
            continue
        try:
            used_numbers.append(int(entry.get("target_number")))
        except (TypeError, ValueError):
            continue

    return max(used_numbers, default=0) + 1


def linked_recipe_targets(history):
    entries = [
        entry
        for entry in synthesis_history(history)
        if entry.get("entry_id") and entry.get("target_id") and entry.get("target_for")
    ]
    return sorted(
        entries,
        key=lambda entry: (
            str(entry.get("target_for", "")).lower(),
            int(entry.get("target_number", 0) or 0),
            str(entry.get("time", "")),
        ),
        reverse=True,
    )


def linked_recipe_target_label(entry):
    mass = entry.get("mass", "")
    mass_basis = recipe_mass_basis(entry)
    mass_label = "powder" if mass_basis == MASS_BASIS_TOTAL_PRECURSOR else "target"
    mass_text = f"{mass:g} g {mass_label}" if isinstance(mass, (int, float)) else str(mass)
    time_text = format_history_time(entry.get("time", entry.get("timestamp", "")))
    return " | ".join(
        part
        for part in [
            entry.get("target_id", ""),
            entry.get("target", ""),
            entry.get("target_for", ""),
            mass_text,
            time_text,
        ]
        if part
    )


def recipe_link_snapshot(entry):
    if not entry:
        return None

    return {
        "entry_id": entry.get("entry_id", ""),
        "recipe_id": entry.get("recipe_id", ""),
        "target_id": entry.get("target_id", ""),
        "target": entry.get("target", ""),
        "time": entry.get("time", entry.get("timestamp", "")),
        "input_basis_g": entry.get("mass", ""),
        "input_basis_type": recipe_mass_basis(entry),
        "powder_basis_g": recipe_powder_basis(entry),
        "selected_powders": entry.get("selected_powders") or [],
        "recipe": entry.get("recipe") or {},
        "notes": entry.get("notes", ""),
        "inventory_deducted": entry.get("inventory_deducted", False),
        "calculation": entry.get("calculation") or {},
    }


def widget_key(prefix, value):
    digest = hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def stock_row_class(row):
    status = str(row.get("Stock status", row.get("Status", ""))).lower()
    if "not in inventory" in status:
        return "stock-missing"
    if "short" in status:
        return "stock-short"
    if "low" in status:
        return "stock-low"
    return ""


def active_recipe_masses():
    last_recipe = st.session_state.get("last_recipe_result")
    if not last_recipe or last_recipe.get("error"):
        return None
    result = last_recipe.get("result") or {}
    return result.get("recipe")


def trash_button(key, help_text):
    return st.button(
        " ",
        key=key,
        help=help_text,
        icon=":material/delete:",
        type="tertiary",
        width="content",
    )


def recipe_history_summary(entry):
    time_text = format_history_time(entry.get("time", entry.get("timestamp", "")))
    mass = entry.get("mass", "")
    mass_basis = recipe_mass_basis(entry)
    mass_label = "powder" if mass_basis == MASS_BASIS_TOTAL_PRECURSOR else "target"
    mass_text = f"{mass:g} g {mass_label}" if isinstance(mass, (int, float)) else str(mass)
    powders = ", ".join(entry.get("selected_powders") or [])
    recipe = entry.get("recipe") or {}
    recipe_text = ", ".join(f"{powder}: {grams:.3f} g" for powder, grams in recipe.items())
    calculation = entry.get("calculation") or {}
    residual = calculation.get("residual")
    if isinstance(residual, (int, float)):
        residual_text = f"residual {residual:.3g}"
    else:
        residual_text = f"residual {residual}" if residual not in ("", None) else ""
    calculation_text = "; ".join(
        part
        for part in [
            calculation.get("basis", ""),
            residual_text,
        ]
        if part
    )
    notes = entry.get("notes", "")
    recipe_id = entry.get("recipe_id") or "Recipe"
    target_id = entry.get("target_id") or recipe_id
    target_for = entry.get("target_for", "")
    return {
        "title": f"{target_id} | {entry.get('target', 'Unknown target')} | {mass_text}",
        "meta": " | ".join(
            part
            for part in [
                time_text,
                f"For {target_for}" if target_for else "",
                recipe_id if entry.get("target_id") else "",
                calculation_text,
                powders,
                recipe_text,
                notes,
            ]
            if part
        ),
    }


def target_density_history_summary(entry):
    time_text = format_history_time(entry.get("time", entry.get("timestamp", "")))
    relative_density = entry.get("relative_density_percent") or 0
    measured_density_value = entry.get("measured_density_g_cm3") or 0
    theoretical_density_value = entry.get("theoretical_density_g_cm3") or 0
    diameter_value = entry.get("final_diameter_mm") or 0
    height_value = entry.get("final_height_mm") or 0
    mass_value = entry.get("final_mass_g") or 0
    linked_recipe = entry.get("linked_recipe") or {}
    linked_recipe_text = (
        f"from {linked_recipe.get('recipe_id')}"
        if linked_recipe.get("recipe_id")
        else ""
    )
    notes = entry.get("notes", "")
    target_id = entry.get("target_id") or f"#{entry.get('target_number', '')}"
    return {
        "title": (
            f"{target_id} | "
            f"{entry.get('target', 'Unknown target')} | "
            f"{relative_density:.2f}%"
        ),
        "meta": " | ".join(part for part in [
            linked_recipe_text,
            f"{time_text} | measured {measured_density_value:.4f} g/cm3 | "
            f"theoretical {theoretical_density_value:.4f} g/cm3 | "
            f"{diameter_value:.3f} mm x {height_value:.3f} mm | "
            f"{mass_value:.5f} g",
            notes,
        ] if part),
    }


def recipe_lab_summary(target, target_mass, recipe_masses, target_for="", target_id=None, notes="", result=None):
    lines = [
        "Stoichio Buddy recipe",
        f"Target: {target}",
        f"Target formula mass: {target_mass:.4f} g",
    ]
    if result:
        lines.append(f"Solve basis: {result.get('basis', 'element balance')}")
        lines.append(f"Target molar mass: {result.get('target_molar_mass', '')} g/mol")
        lines.append(f"Precursor formula mass: {result.get('precursor_formula_mass', '')} g")
        lines.append(f"Estimated target mass: {result.get('estimated_target_mass', '')} g")
        lines.append(f"Residual: {result.get('residual', '')}")
    if target_id:
        lines.append(f"Target ID: {target_id}")
    if target_for:
        lines.append(f"Target for: {target_for}")

    lines.append("Precursors:")
    for powder, grams in recipe_masses.items():
        lines.append(f"- {powder}: {grams:.6f} g")

    total_powder = sum(recipe_masses.values())
    lines.append(f"Total precursor powder: {total_powder:.6f} g")
    if notes:
        lines.append(f"Notes: {notes}")
    return "\n".join(lines)


def target_density_lab_summary(result, target_id=None):
    target_for = str(result.get("target_for", "")).strip()
    lines = [
        "Stoichio Buddy target density",
        f"Target: {result['target']}",
    ]
    if target_id:
        lines.append(f"Target ID: {target_id}")
    if target_for:
        lines.append(f"Target for: {target_for}")
    linked_recipe = result.get("linked_recipe") or {}
    if linked_recipe.get("recipe_id"):
        lines.append(f"Linked recipe: {linked_recipe['recipe_id']}")

    lines.extend(
        [
            f"Measured density: {result['measured_density']:.6f} g/cm3",
            f"Theoretical density: {result['theoretical_density']:.6f} g/cm3",
            f"Relative density: {result['relative_percent']:.2f}%",
            f"Final diameter: {result['final_diameter']:.4f} mm",
            f"Final height: {result['final_height']:.4f} mm",
            f"Final mass: {result['final_mass']:.6f} g",
            f"Final volume: {result['final_volume']:.6f} cm3",
            f"Density source: {result.get('density_source', '')}",
        ]
    )
    return "\n".join(lines)


def safe_filename(value, fallback="stoichio_report"):
    cleaned = "".join(
        character.lower() if character.isalnum() else "-"
        for character in str(value or "").strip()
    ).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or fallback


def report_html_document(title, body_html):
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{
      color: #18242b;
      font-family: Arial, sans-serif;
      line-height: 1.45;
      margin: 36px;
    }}
    h1, h2, h3 {{ color: #12313f; margin-bottom: 8px; }}
    .meta {{ color: #536975; margin-bottom: 18px; }}
    .panel {{ border: 1px solid #ccd9df; padding: 14px; margin: 14px 0; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0 16px; }}
    th, td {{ border: 1px solid #ccd9df; padding: 8px; text-align: left; }}
    th {{ background: #e8f1f5; }}
    .warning {{ color: #8a3f00; font-weight: 700; }}
    @media print {{ body {{ margin: 18mm; }} }}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""


def html_table(headers, rows):
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    row_html = []
    for row in rows:
        row_html.append(
            "<tr>"
            + "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
            + "</tr>"
        )
    return f"<table><tr>{header_html}</tr>{''.join(row_html)}</table>"


def recipe_report_html(
    target,
    powder_basis,
    recipe_masses,
    target_for="",
    target_id=None,
    notes="",
    result=None,
    stock_messages=None,
    low_after_recipe=None,
    planning_context=None,
):
    result = result or {}
    stock_messages = stock_messages or []
    low_after_recipe = low_after_recipe or []
    planning_context = planning_context or {}
    title = f"Recipe report {target_id or target}"

    recipe_rows = [
        [powder, f"{grams:.6f}"]
        for powder, grams in recipe_masses.items()
    ]
    detail_rows = [
        ["Target", target],
        ["Target ID", target_id or ""],
        ["Target for", target_for or ""],
        ["Generated", datetime.now().strftime("D-%d.%m.%y T-%H:%M:%S")],
        ["Input basis", mass_basis_label(result.get("mass_basis", MASS_BASIS_TARGET_FORMULA))],
        ["Input mass (g)", f"{powder_basis:.6f}"],
        ["Estimated target mass (g)", result.get("estimated_target_mass", "")],
        ["Total precursor powder (g)", f"{sum(recipe_masses.values()):.6f}"],
        ["Solve basis", result.get("basis", "")],
        ["Residual", result.get("residual", "")],
        ["Target molar mass (g/mol)", result.get("target_molar_mass", "")],
        ["Precursor formula mass (g)", result.get("precursor_formula_mass", "")],
    ]

    if planning_context.get("amount_mode") == "Pellet height":
        detail_rows.extend(
            [
                ["Desired height (mm)", planning_context.get("planning_height", "")],
                ["Die diameter (mm)", DEFAULT_DIE_DIAMETER_MM],
                ["Planning volume (cm3)", planning_context.get("planning_volume", "")],
                ["Theoretical density (g/cm3)", planning_context.get("theoretical_density", "")],
                ["Density source", planning_context.get("density_source", "")],
                ["Density lab checked/preferred", planning_context.get("density_verified", "")],
            ]
        )

    inventory_warning = ""
    if stock_messages:
        inventory_warning = (
            '<p class="warning">Inventory shortage: '
            + html.escape("; ".join(stock_messages))
            + "</p>"
        )
    elif low_after_recipe:
        inventory_warning = (
            '<p class="warning">Low inventory after recipe: '
            + html.escape(", ".join(low_after_recipe))
            + "</p>"
        )

    notes_html = f"<p>{html.escape(notes)}</p>" if notes else "<p></p>"
    body = (
        f"<h1>{html.escape(title)}</h1>"
        '<div class="meta">Stoichio Buddy printable lab report</div>'
        '<div class="panel"><h2>Recipe details</h2>'
        + html_table(["Field", "Value"], detail_rows)
        + "</div>"
        '<div class="panel"><h2>Powder masses</h2>'
        + html_table(["Powder", "Mass (g)"], recipe_rows)
        + inventory_warning
        + "</div>"
        '<div class="panel"><h2>Notes</h2>'
        + notes_html
        + "</div>"
    )
    return report_html_document(title, body)


def target_traceability_report_html(group_key, summary):
    target_for, target_id, target = group_key
    title = f"Target report {target_id}"
    body = [
        f"<h1>{html.escape(title)}</h1>",
        '<div class="meta">Stoichio Buddy target traceability report</div>',
        '<div class="panel"><h2>Target</h2>',
        html_table(
            ["Field", "Value"],
            [
                ["Target ID", target_id],
                ["Target for", target_for],
                ["Formula", target],
                ["Generated", datetime.now().strftime("D-%d.%m.%y T-%H:%M:%S")],
                ["Status", target_lifecycle_status(summary)],
            ],
        ),
        "</div>",
    ]

    body.append('<div class="panel"><h2>Before sintering recipes</h2>')
    if summary["recipes"]:
        for recipe_entry in summary["recipes"]:
            recipe_rows = [
                [powder, f"{grams:.6f}"]
                for powder, grams in (recipe_entry.get("recipe") or {}).items()
            ]
            calculation = recipe_entry.get("calculation") or {}
            mass_basis = recipe_mass_basis(recipe_entry)
            body.append(f"<h3>{html.escape(recipe_entry.get('recipe_id', 'Recipe'))}</h3>")
            body.append(
                html_table(
                    ["Field", "Value"],
                    [
                        ["Time", format_history_time(recipe_entry.get("time", ""))],
                        ["Input basis (g)", recipe_entry.get("mass", "")],
                        ["Input basis type", mass_basis_label(mass_basis)],
                        ["Powder basis (g)", recipe_powder_basis(recipe_entry)],
                        ["Inventory deducted", recipe_entry.get("inventory_deducted", False)],
                        ["Solve basis", calculation.get("basis", "")],
                        ["Residual", calculation.get("residual", "")],
                        ["Notes", recipe_entry.get("notes", "")],
                    ],
                )
            )
            body.append(html_table(["Powder", "Mass (g)"], recipe_rows))
    else:
        body.append("<p>No before-sintering recipe saved.</p>")
    body.append("</div>")

    body.append('<div class="panel"><h2>After sintering density records</h2>')
    if summary["densities"]:
        for density_entry in summary["densities"]:
            linked_recipe = density_entry.get("linked_recipe") or {}
            body.append(f"<h3>{html.escape(format_history_time(density_entry.get('time', '')))}</h3>")
            body.append(
                html_table(
                    ["Field", "Value"],
                    [
                        ["Linked recipe", linked_recipe.get("recipe_id", "")],
                        ["Measured density (g/cm3)", density_entry.get("measured_density_g_cm3", "")],
                        ["Theoretical density (g/cm3)", density_entry.get("theoretical_density_g_cm3", "")],
                        ["Relative density (%)", density_entry.get("relative_density_percent", "")],
                        ["Final diameter (mm)", density_entry.get("final_diameter_mm", "")],
                        ["Final height (mm)", density_entry.get("final_height_mm", "")],
                        ["Final mass (g)", density_entry.get("final_mass_g", "")],
                        ["Density source", density_entry.get("density_source", "")],
                        ["Notes", density_entry.get("notes", "")],
                    ],
                )
            )
    else:
        body.append("<p>No after-sintering density record saved.</p>")
    body.append("</div>")

    return report_html_document(title, "".join(body))


def csv_bytes(df):
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()


def data_backup_json(powders, inventory, material_densities, history, inventory_log=None, powder_sets=None):
    backup = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "app": "Stoichio Buddy",
        "powders": powders,
        "inventory": inventory,
        "inventory_log": inventory_log or [],
        "material_densities": material_densities,
        "powder_sets": powder_sets or {},
        "history": history,
    }
    return json.dumps(backup, indent=2, ensure_ascii=False)


def parse_backup_upload(uploaded_file):
    try:
        backup = json.loads(uploaded_file.getvalue().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"Could not read backup JSON: {exc}"]

    return backup, validate_backup_data(backup)


def backup_counts(backup):
    return {
        "powders": len(backup.get("powders", {})),
        "inventory": len(backup.get("inventory", {})),
        "inventory_log": len(backup.get("inventory_log", [])),
        "material_densities": len(backup.get("material_densities", {})),
        "powder_sets": len(backup.get("powder_sets", {})),
        "history": len(backup.get("history", [])),
    }


def display_dataframe(df, theme_mode, row_class_func=None, **kwargs):
    colors = theme_colors(theme_mode)
    row_count = len(df.index)
    content_height = 74 * (row_count + 1) + 28
    frame_height = min(9000, max(220, content_height))
    wrap_column_terms = (
        "check",
        "composition",
        "density source",
        "note",
        "origin",
        "phase",
        "reason",
        "record",
        "reference",
        "source",
        "status",
        "warning",
    )

    def column_class(column):
        column_text = str(column).strip().lower()
        if any(term in column_text for term in wrap_column_terms):
            return "sb-cell-wrap"
        return "sb-cell-compact"

    def linkify_text(text):
        parts = []
        position = 0
        for match in re.finditer(r"https?://[^\s<>\"]+", text):
            url = match.group(0)
            parts.append(html.escape(text[position:match.start()]))
            parts.append(
                f'<a href="{html.escape(url, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">{html.escape(url)}</a>'
            )
            position = match.end()
        parts.append(html.escape(text[position:]))
        return "".join(parts)

    def cell_html(column, value):
        text = str(value)
        title = html.escape(text, quote=True)
        cell_class = column_class(column)
        escaped = (
            linkify_text(text)
            if column in {"Reference", "Source"} or "http://" in text or "https://" in text
            else html.escape(text)
        )

        return f'<td class="{cell_class}" title="{title}"><span class="sb-cell-content">{escaped}</span></td>'

    table_rows = []
    headers = "".join(
        f'<th class="{column_class(column)}" title="{html.escape(str(column), quote=True)}">'
        f'{html.escape(str(column))}</th>'
        for column in df.columns
    )
    table_rows.append(f"<tr>{headers}</tr>")

    for _, row in df.iterrows():
        row_class = row_class_func(row) if row_class_func else ""
        class_attr = f' class="{html.escape(row_class)}"' if row_class else ""
        cells = "".join(
            cell_html(column, row[column])
            for column in df.columns
        )
        table_rows.append(f"<tr{class_attr}>{cells}</tr>")

    table_html = "".join(table_rows)
    components.html(
        f"""
        <!doctype html>
        <html>
        <head>
        <style>
            :root {{
                --sb-accent: {colors["accent"]};
                --sb-bg: {colors["background"]};
                --sb-border: {colors["border"]};
                --sb-panel: {colors["panel"]};
                --sb-table-bg: {colors["table_bg"]};
                --sb-table-header: {colors["table_header"]};
                --sb-text: {colors["text"]};
            }}

            html,
            body {{
                margin: 0;
                padding: 0;
                background: transparent;
                color: var(--sb-text);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                overflow: hidden;
            }}

            .sb-table-shell {{
                position: relative;
                width: 100%;
            }}

            .sb-table-wrap {{
                width: 100%;
                max-height: none;
                overflow: auto;
                overscroll-behavior: contain;
                border: 1px solid var(--sb-border);
                border-radius: 8px;
                background: var(--sb-table-bg);
                scrollbar-width: thin;
                scrollbar-color: color-mix(in srgb, var(--sb-accent) 42%, transparent) transparent;
                scrollbar-gutter: stable;
                box-sizing: border-box;
            }}

            .sb-table-drag-edge {{
                position: absolute;
                top: 1px;
                bottom: 9px;
                width: 32px;
                z-index: 10;
                cursor: grab;
                background: transparent;
                border-radius: 7px;
                transition: background 120ms ease, box-shadow 120ms ease;
            }}

            .sb-table-drag-edge.left {{
                left: 1px;
                box-shadow: inset 3px 0 0 color-mix(in srgb, var(--sb-accent) 55%, transparent);
            }}

            .sb-table-drag-edge.right {{
                right: 9px;
                box-shadow: inset -3px 0 0 color-mix(in srgb, var(--sb-accent) 55%, transparent);
            }}

            .sb-table-drag-edge:hover,
            .sb-table-drag-edge.dragging {{
                background: color-mix(in srgb, var(--sb-accent) 16%, transparent);
                box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--sb-accent) 35%, transparent);
            }}

            .sb-table-drag-edge.left:hover,
            .sb-table-drag-edge.left.dragging {{
                box-shadow:
                    inset 0 0 0 1px color-mix(in srgb, var(--sb-accent) 35%, transparent),
                    inset 4px 0 0 var(--sb-accent);
            }}

            .sb-table-drag-edge.right:hover,
            .sb-table-drag-edge.right.dragging {{
                box-shadow:
                    inset 0 0 0 1px color-mix(in srgb, var(--sb-accent) 35%, transparent),
                    inset -4px 0 0 var(--sb-accent);
            }}

            .sb-table-drag-edge::before {{
                content: "";
                position: absolute;
                top: 50%;
                width: 4px;
                height: min(72px, 32%);
                min-height: 42px;
                transform: translateY(-50%);
                border-radius: 999px;
                background: var(--sb-accent);
                opacity: 0.48;
                box-shadow: 0 0 0 1px color-mix(in srgb, var(--sb-bg) 45%, transparent);
            }}

            .sb-table-drag-edge.left::before {{
                left: 11px;
            }}

            .sb-table-drag-edge.right::before {{
                right: 11px;
            }}

            .sb-table-drag-edge:hover::before,
            .sb-table-drag-edge.dragging::before {{
                opacity: 0.92;
            }}

            .sb-table-drag-edge.dragging {{
                cursor: grabbing !important;
                user-select: none !important;
                -webkit-user-select: none !important;
            }}

            .sb-table-wrap::-webkit-scrollbar {{
                width: 8px;
                height: 8px;
            }}

            .sb-table-wrap::-webkit-scrollbar-track {{
                background: transparent;
                border-radius: 999px;
            }}

            .sb-table-wrap::-webkit-scrollbar-thumb {{
                background: color-mix(in srgb, var(--sb-accent) 38%, transparent);
                border: 2px solid transparent;
                background-clip: padding-box;
                border-radius: 999px;
            }}

            .sb-table-wrap::-webkit-scrollbar-thumb:hover {{
                background: color-mix(in srgb, var(--sb-accent) 76%, transparent);
                background-clip: padding-box;
            }}

            .sb-table {{
                min-width: 100%;
                border-collapse: collapse;
                background: var(--sb-table-bg);
                color: var(--sb-text);
                font-size: 0.94rem;
            }}

            .sb-table a {{
                color: var(--sb-accent);
                font-weight: 700;
                text-decoration: underline;
                text-underline-offset: 2px;
            }}

            .sb-table th {{
                background: var(--sb-table-header);
                color: var(--sb-text);
                font-weight: 750;
                text-align: left;
                position: sticky;
                top: 0;
                z-index: 2;
                padding: 0.8rem 0.95rem;
                border-bottom: 1px solid var(--sb-border);
                line-height: 1.35;
                vertical-align: top;
                white-space: nowrap;
            }}

            .sb-table td {{
                background: var(--sb-table-bg);
                color: var(--sb-text);
                padding: 0.85rem 0.95rem;
                border-bottom: 1px solid var(--sb-border);
                line-height: 1.45;
                vertical-align: top;
                white-space: nowrap;
            }}

            .sb-table th.sb-cell-wrap,
            .sb-table td.sb-cell-wrap {{
                min-width: 180px;
                max-width: 520px;
                white-space: normal;
                overflow-wrap: anywhere;
            }}

            .sb-table td .sb-cell-content {{
                display: block;
            }}

            .sb-table td.sb-cell-wrap .sb-cell-content {{
                display: -webkit-box;
                max-height: 4.35em;
                overflow: hidden;
                -webkit-box-orient: vertical;
                -webkit-line-clamp: 3;
            }}

            .sb-table td.sb-cell-wrap a {{
                overflow-wrap: anywhere;
            }}

            .sb-table td:first-child,
            .sb-table th:first-child {{
                padding-left: 2.2rem;
            }}

            .sb-table td:last-child,
            .sb-table th:last-child {{
                padding-right: 2.2rem;
            }}

            .sb-table tr:last-child td {{
                border-bottom: 0;
            }}

            .sb-table tr.stock-low td {{
                background: color-mix(in srgb, var(--sb-accent) 18%, var(--sb-table-bg)) !important;
            }}

            .sb-table tr.stock-low td:first-child {{
                border-left: 3px solid var(--sb-accent);
            }}

            .sb-table tr.stock-short td,
            .sb-table tr.stock-empty td,
            .sb-table tr.stock-missing td {{
                background: color-mix(in srgb, #d64a4a 22%, var(--sb-table-bg)) !important;
            }}

            .sb-table tr.stock-short td:first-child,
            .sb-table tr.stock-empty td:first-child,
            .sb-table tr.stock-missing td:first-child {{
                border-left: 3px solid #d64a4a;
            }}

            .sb-table tr.codex-seeded td {{
                background: color-mix(in srgb, #2f80ed 18%, var(--sb-table-bg)) !important;
            }}

            .sb-table tr.codex-seeded td:first-child {{
                border-left: 3px solid #2f80ed;
            }}
        </style>
        </head>
        <body>
            <div class="sb-table-shell">
                <div class="sb-table-wrap" aria-label="Scrollable data table">
                    <table class="sb-table">{table_html}</table>
                </div>
                <div class="sb-table-drag-edge left" title="Drag the table edge to move" aria-label="Drag table left edge"></div>
                <div class="sb-table-drag-edge right" title="Drag the table edge to move" aria-label="Drag table right edge"></div>
            </div>
            <script>
            (() => {{
                const wrap = document.querySelector(".sb-table-wrap");
                const dragEdges = document.querySelectorAll(".sb-table-drag-edge");
                let drag = null;
                let suppressClick = false;

                dragEdges.forEach((dragEdge) => dragEdge.addEventListener("mousedown", (event) => {{
                    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey) {{
                        return;
                    }}
                    drag = {{
                        startX: event.clientX,
                        startY: event.clientY,
                        scrollLeft: wrap.scrollLeft,
                        scrollTop: wrap.scrollTop,
                        moved: false,
                        dragEdge
                    }};
                    dragEdge.classList.add("dragging");
                    event.preventDefault();
                }}));

                window.addEventListener("mousemove", (event) => {{
                    if (!drag) {{
                        return;
                    }}
                    const dx = event.clientX - drag.startX;
                    const dy = event.clientY - drag.startY;
                    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {{
                        drag.moved = true;
                        suppressClick = true;
                    }}
                    wrap.scrollLeft = drag.scrollLeft - dx;
                    wrap.scrollTop = drag.scrollTop - dy;
                    event.preventDefault();
                }});

                function endDrag() {{
                    if (drag && drag.dragEdge) {{
                        drag.dragEdge.classList.remove("dragging");
                    }}
                    drag = null;
                    setTimeout(() => {{
                        suppressClick = false;
                    }}, 0);
                }}

                window.addEventListener("mouseup", endDrag);
                window.addEventListener("mouseleave", endDrag);
                dragEdges.forEach((dragEdge) => dragEdge.addEventListener("click", (event) => {{
                    if (!suppressClick) {{
                        return;
                    }}
                    suppressClick = false;
                    event.preventDefault();
                    event.stopPropagation();
                }}, true));
            }})();
            </script>
        </body>
        </html>
        """,
        height=frame_height,
        scrolling=False,
    )


def recipe_input_signature(target, target_mass, selected, amount_mode):
    return {
        "target": str(target).strip(),
        "target_mass": round(float(target_mass), 8) if target_mass is not None else None,
        "selected": tuple(selected),
        "amount_mode": amount_mode,
    }


def target_density_signature(
    target,
    target_for,
    final_diameter,
    final_height,
    final_mass,
    theoretical_density,
    density_source,
    target_id=None,
    linked_recipe_entry_id=None,
):
    return {
        "target": str(target).strip(),
        "target_for": str(target_for).strip(),
        "target_id": str(target_id or "").strip(),
        "linked_recipe_entry_id": str(linked_recipe_entry_id or "").strip(),
        "final_diameter": round(float(final_diameter), 8),
        "final_height": round(float(final_height), 8),
        "final_mass": round(float(final_mass), 8),
        "theoretical_density": (
            round(float(theoretical_density), 8) if theoretical_density is not None else None
        ),
        "density_source": density_source,
    }


def truthy_secret(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def configure_app_storage():
    try:
        shared_storage_enabled = truthy_secret(st.secrets.get("enable_shared_storage", False))
    except (FileNotFoundError, KeyError, AttributeError):
        shared_storage_enabled = False

    if not shared_storage_enabled:
        return "Local JSON files"

    try:
        apps_script_url = st.secrets.get("apps_script_url")
        apps_script_token = st.secrets.get("apps_script_token")
    except (FileNotFoundError, KeyError, AttributeError):
        apps_script_url = None
        apps_script_token = None

    if apps_script_url and apps_script_token:
        try:
            configure_apps_script(apps_script_url, apps_script_token)
        except Exception as exc:
            st.warning(f"Apps Script storage is not connected, using local JSON files. Details: {exc}")
        return storage_label()

    try:
        credentials = st.secrets.get("gcp_service_account")
    except (FileNotFoundError, KeyError, AttributeError):
        return "Local JSON files"

    if not credentials:
        return "Local JSON files"

    try:
        configure_google_sheets(
            credentials_info=credentials,
            spreadsheet_id=st.secrets.get("google_sheet_id"),
            spreadsheet_name=st.secrets.get("google_sheet_name", "Stoichio Buddy Data"),
        )
    except Exception as exc:
        st.warning(f"Google Sheets storage is not connected, using local JSON files. Details: {exc}")

    return storage_label()


storage_status = configure_app_storage()
db, inventory = load_app_state(storage_status)
inventory_log = cached_load_inventory_log(storage_status)
history = cached_load_history(storage_status)
recipe_history = synthesis_history(history)
target_density_records = target_density_history(history)
material_densities = cached_load_material_densities(storage_status)
powder_sets = cached_load_powder_sets(storage_status)
storage_status = storage_label()
storage_problem = storage_error()

with st.sidebar:
    st.markdown("### Stoichio Buddy")
    theme_mode = st.radio("Appearance", ["Dark", "Light"], horizontal=True, key="theme_mode")
    page = st.radio(
        "Navigation",
        [
            "Powder Mass Calculation",
            "Target Density",
            "Powders & Inventory",
            "Material Density",
            "History",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.metric("Powders", len(db))
    unknown_stock = unknown_inventory_items(inventory, db)
    st.metric("Inventory items", len(inventory))
    st.metric("Inventory log", len(inventory_log))
    st.metric("Material densities", len(material_densities))
    st.metric("Powder sets", len(powder_sets))
    st.metric("Saved recipes", len(recipe_history))
    st.metric("Target density logs", len(target_density_records))

    st.caption("Selected powders are always controlled by the user. The app never searches or swaps precursors automatically.")
    st.caption(f"Storage: {storage_status}")
    if st.button("Refresh Data", width="stretch"):
        clear_data_cache()
        st.rerun()
    st.download_button(
        "Download Data Backup JSON",
        data=data_backup_json(db, inventory, material_densities, history, inventory_log, powder_sets),
        file_name=f"stoichio_buddy_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        width="stretch",
    )
    with st.expander("Restore Data Backup", expanded=False):
        backup_file = st.file_uploader(
            "Backup JSON file",
            type=["json"],
            key="restore_backup_json",
        )
        if backup_file is not None:
            backup_data, backup_errors = parse_backup_upload(backup_file)
            if backup_errors:
                st.error("Backup cannot be restored: " + "; ".join(backup_errors[:4]))
            else:
                counts = backup_counts(backup_data)
                st.caption(
                    "Backup contains "
                    f"{counts['powders']} powders, "
                    f"{counts['inventory']} inventory entries, "
                    f"{counts['inventory_log']} inventory log entries, "
                    f"{counts['material_densities']} material densities, "
                    f"{counts['powder_sets']} powder sets, and "
                    f"{counts['history']} history entries."
                )
                confirm_restore = st.checkbox(
                    "Replace current app data with this backup",
                    key="confirm_restore_backup",
                )
                if st.button(
                    "Restore Backup",
                    disabled=not confirm_restore,
                    width="stretch",
                ):
                    try:
                        restored_counts = restore_backup_data(backup_data)
                        clear_data_cache()
                        st.success(
                            "Backup restored: "
                            f"{restored_counts['powders']} powders, "
                            f"{restored_counts['inventory']} inventory entries, "
                            f"{restored_counts['inventory_log']} inventory log entries, "
                            f"{restored_counts['material_densities']} material densities, "
                            f"{restored_counts['powder_sets']} powder sets, "
                            f"{restored_counts['history']} history entries."
                        )
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
    if storage_problem:
        st.warning("Shared storage is not connected. The app is using local JSON files for now.")
    if unknown_stock:
        st.warning("Inventory has entries that are not in the powder database: " + ", ".join(unknown_stock))

apply_theme(theme_mode)

st.markdown('<div class="app-kicker">Solid-state synthesis</div>', unsafe_allow_html=True)
st.markdown('<div class="app-title">Stoichio Buddy</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Cation-first precursor mass calculator with powder inventory and recipe history.</div>',
    unsafe_allow_html=True,
)

if storage_problem:
    st.warning(
        "Google Sheets storage did not connect. Check the Apps Script web app URL, deployment access, "
        f"and token. Details: {storage_problem}"
    )


PAGE_RENDERERS = {
    "Powder Mass Calculation": powder_mass_page,
    "Target Density": target_density_page,
    "Powders & Inventory": powders_inventory_page,
    "Material Density": material_density_page,
    "History": history_page,
}

page_context = SimpleNamespace(
    **{
        name: value
        for name, value in globals().items()
        if not name.startswith("__")
    }
)
PAGE_RENDERERS[page].render(page_context)
