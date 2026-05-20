import json
import html
import hashlib
from collections import defaultdict
from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

from density_engine import (
    DEFAULT_DIE_DIAMETER_MM,
    measured_density,
    relative_density_percent,
    target_mass_from_height,
    theoretical_density_from_cell,
    unit_cell_volume_from_lattice,
)
from formula_parser import normalize_formula
from lab_manager import (
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
    format_target_id,
    load_history,
    load_inventory,
    load_material_densities,
    load_powders,
    log_synthesis,
    log_target_density,
    restore_backup_data,
    set_inventory_quantity,
    storage_error,
    storage_label,
    upsert_material_density,
    validate_backup_data,
)
from stoich_engine import MASS_BASIS_TARGET_FORMULA, MASS_BASIS_TOTAL_PRECURSOR, compute_recipe


st.set_page_config(
    page_title="Stoichio Buddy",
    page_icon=":material/science:",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_CACHE_TTL_SECONDS = 20
LOW_STOCK_THRESHOLD_G = 10.0


def apply_theme(mode):
    if mode == "Dark":
        colors = {
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
    else:
        colors = {
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
        overflow-x: auto;
        border: 1px solid var(--sb-border);
        border-radius: 8px;
        background: var(--sb-table-bg);
        margin-bottom: 0.75rem;
    }

    .sb-table {
        width: 100%;
        border-collapse: collapse;
        background: var(--sb-table-bg);
        color: var(--sb-text);
        font-size: 0.92rem;
    }

    .sb-table th {
        background: var(--sb-table-header);
        color: var(--sb-text);
        font-weight: 750;
        text-align: left;
        padding: 0.65rem 0.75rem;
        border-bottom: 1px solid var(--sb-border);
    }

    .sb-table td {
        background: var(--sb-table-bg);
        color: var(--sb-text);
        padding: 0.6rem 0.75rem;
        border-bottom: 1px solid var(--sb-border);
    }

    .sb-table tr:last-child td {
        border-bottom: 0;
    }

    .sb-table tr.stock-low td {
        background: color-mix(in srgb, var(--sb-accent) 18%, var(--sb-table-bg)) !important;
        border-left: 3px solid var(--sb-accent);
    }

    .sb-table tr.stock-short td,
    .sb-table tr.stock-empty td,
    .sb-table tr.stock-missing td {
        background: color-mix(in srgb, #d64a4a 22%, var(--sb-table-bg)) !important;
        border-left: 3px solid #d64a4a;
    }

    .sb-table tr.codex-seeded td {
        background: color-mix(in srgb, #2f80ed 18%, var(--sb-table-bg)) !important;
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
def cached_load_history(storage_status):
    return load_history()


@st.cache_data(ttl=DATA_CACHE_TTL_SECONDS, show_spinner=False)
def cached_load_material_densities(storage_status):
    return load_material_densities()


def clear_data_cache():
    cached_load_powders.clear()
    cached_load_inventory.clear()
    cached_load_history.clear()
    cached_load_material_densities.clear()


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

    return pd.DataFrame(rows)


def material_density_dataframe(records):
    columns = [
        "Record",
        "Formula",
        "Phase",
        "Theoretical density (g/cm3)",
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
        key=lambda item: (
            item[1].get("formula", item[0]),
            item[1].get("phase", ""),
            item[1].get("display_name", item[0]),
        ),
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


def density_record_label(record_key, record, include_density=True):
    label = record.get("display_name") or record.get("formula") or record_key
    density = record.get("theoretical_density_g_cm3")
    if include_density and density:
        return f"{label} - {float(density):.4f} g/cm3"
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
    records.sort(key=lambda item: (item[1].get("phase", ""), item[1].get("display_name", item[0])))

    if not records:
        return key, [], f"No saved density for {key}"

    return key, records, None


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
            if record.get("source") or record.get("density_source"):
                st.caption(
                    "Source: "
                    + (record.get("source") or record.get("density_source") or "saved material density")
                )
            return density, f"Known material density: {density_record_label(selected_record_key, record, False)}"
        else:
            st.warning(error)
        return None, source_mode

    if source_mode == "Use another density record":
        source_target = st.selectbox(
            "Density record to use",
            [""] + list(material_densities.keys()),
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
                return density, source_mode
            except ValueError as exc:
                st.warning(str(exc))
                return None, source_mode

        density = source_record.get("theoretical_density_g_cm3")
        if density:
            st.warning(
                f"{source_target} has no saved unit cell volume and Z. "
                "Using its stored density directly."
            )
            return float(density), source_mode

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


def data_backup_json(powders, inventory, material_densities, history):
    backup = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "app": "Stoichio Buddy",
        "powders": powders,
        "inventory": inventory,
        "material_densities": material_densities,
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
        "material_densities": len(backup.get("material_densities", {})),
        "history": len(backup.get("history", [])),
    }


def display_dataframe(df, theme_mode, row_class_func=None, **kwargs):
    table_rows = []
    headers = "".join(f"<th>{html.escape(str(column))}</th>" for column in df.columns)
    table_rows.append(f"<tr>{headers}</tr>")

    for _, row in df.iterrows():
        row_class = row_class_func(row) if row_class_func else ""
        class_attr = f' class="{html.escape(row_class)}"' if row_class else ""
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
        table_rows.append(f"<tr{class_attr}>{cells}</tr>")

    st.markdown(
        '<div class="sb-table-wrap"><table class="sb-table">'
        + "".join(table_rows)
        + "</table></div>",
        unsafe_allow_html=True,
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
history = cached_load_history(storage_status)
recipe_history = synthesis_history(history)
target_density_records = target_density_history(history)
material_densities = cached_load_material_densities(storage_status)
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
    st.metric("Material densities", len(material_densities))
    st.metric("Saved recipes", len(recipe_history))
    st.metric("Target density logs", len(target_density_records))

    st.caption("Selected powders are always controlled by the user. The app never searches or swaps precursors automatically.")
    st.caption(f"Storage: {storage_status}")
    if st.button("Refresh Data", width="stretch"):
        clear_data_cache()
        st.rerun()
    st.download_button(
        "Download Data Backup JSON",
        data=data_backup_json(db, inventory, material_densities, history),
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
                    f"{counts['material_densities']} material densities, and "
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
                            f"{restored_counts['material_densities']} material densities, "
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


if page == "Powder Mass Calculation":
    left, right = st.columns([0.95, 1.05], gap="large")

    with left:
        st.subheader("Powder mass setup")
        target = st.text_input(
            "Target formula",
            placeholder="Fe1.98Ti0.02O3",
            help="Supports decimals, parentheses, and hydrates with middle dot or asterisk.",
        )
        recipe_target_for = st.text_input(
            "Target for (optional)",
            placeholder="Person or project name",
            key="recipe_target_for",
        )
        recipe_target_owner = recipe_target_for.strip()
        if recipe_target_owner:
            preview_number = next_target_number(history, recipe_target_owner)
            st.caption(
                f"This recipe will be the before-sintering record for "
                f"{format_target_id(recipe_target_owner, preview_number)}."
            )
        amount_mode = st.radio(
            "Target amount mode",
            ["Target formula mass", "Pellet height"],
            horizontal=True,
            help="This uses the original lab math. Powder totals may be slightly higher or lower than the target formula mass.",
        )

        target_mass = None
        planning_volume = None
        theoretical_density_used = None
        planning_height = None
        planning_error = None

        if amount_mode == "Target formula mass":
            target_mass = st.number_input(
                "Target formula mass (g)",
                min_value=0.0,
                value=15.6,
                step=0.1,
                format="%.4f",
                help="Original basis: the target compound/formula is scaled to this mass.",
            )
        else:
            st.caption(f"Fixed die diameter: {DEFAULT_DIE_DIAMETER_MM:.2f} mm")
            planning_height = st.number_input(
                "Desired target height (mm)",
                min_value=0.0,
                value=1.0,
                step=0.1,
                format="%.4f",
            )
            theoretical_density_used, _ = density_source_control(
                target,
                material_densities,
                key_prefix="recipe_height",
            )
            if theoretical_density_used is not None and planning_height > 0:
                try:
                    target_mass, planning_volume = target_mass_from_height(
                        theoretical_density_used,
                        planning_height,
                        DEFAULT_DIE_DIAMETER_MM,
                    )
                    st.info(
                        f"Calculated target formula mass: {target_mass:.4f} g "
                        f"from {planning_volume:.4f} cm3."
                    )
                except ValueError as exc:
                    planning_error = str(exc)
                    st.error(planning_error)

        selected = st.multiselect(
            "Selected powders",
            list(db.keys()),
            help="Only these powders will be used in the calculation.",
        )
        deduct_inventory = st.checkbox("Deduct inventory when saving recipe")

        solve = st.button("Calculate Recipe", type="primary", width="stretch")
        current_signature = recipe_input_signature(target, target_mass, selected, amount_mode)

        if solve:
            if target_mass is None or target_mass <= 0:
                st.session_state.last_recipe_result = {
                    "error": "Enter a valid target formula mass, or a valid height and theoretical density.",
                    "signature": current_signature,
                }
            elif planning_error:
                st.session_state.last_recipe_result = {
                    "error": planning_error,
                    "signature": current_signature,
                }
            else:
                result = compute_recipe(
                    target,
                    target_mass,
                    db,
                    selected,
                    mass_basis=MASS_BASIS_TARGET_FORMULA,
                )
                st.session_state.last_recipe_result = {
                    "result": result,
                    "target": target,
                    "target_mass": target_mass,
                    "selected": selected,
                    "amount_mode": amount_mode,
                    "planning_height": planning_height,
                    "planning_volume": planning_volume,
                    "theoretical_density": theoretical_density_used,
                    "signature": current_signature,
                }
                st.session_state.last_recipe_saved = False

    with right:
        st.subheader("Result")
        save_message = st.session_state.pop("recipe_save_message", None)
        if save_message:
            st.success(save_message)

        last_recipe = st.session_state.get("last_recipe_result")
        if not last_recipe:
            st.info("Enter a target formula, target mass, and selected powders, then calculate.")
            if db:
                display_dataframe(database_dataframe(db), theme_mode, width="stretch", hide_index=True)
        else:
            if last_recipe.get("error"):
                st.error(last_recipe["error"])
            else:
                result = last_recipe["result"]

                if result is None or result.get("recipe") is None:
                    st.error(result.get("warning", "No valid solution found") if result else "No valid solution found")
                else:
                    recipe_masses = result["recipe"]
                    current_inventory = inventory
                    in_stock, stock_messages = check_stock(current_inventory, recipe_masses)
                    recipe_df = recipe_dataframe(recipe_masses, current_inventory)
                    total_powder = sum(recipe_masses.values())
                    displayed_target_mass = last_recipe["target_mass"]

                    metric_cols = st.columns(3)
                    metric_cols[0].metric("Target formula mass (g)", round(displayed_target_mass, 3))
                    metric_cols[1].metric("Precursor powder total (g)", round(total_powder, 3))
                    metric_cols[2].metric("Powders used", len(recipe_masses))

                    if last_recipe["amount_mode"] == "Pellet height":
                        detail_cols = st.columns(3)
                        detail_cols[0].metric("Die diameter (mm)", round(DEFAULT_DIE_DIAMETER_MM, 3))
                        detail_cols[1].metric("Desired height (mm)", round(last_recipe["planning_height"], 3))
                        detail_cols[2].metric("Theoretical density", round(last_recipe["theoretical_density"], 4))
                        st.caption(f"Calculated planning volume: {last_recipe['planning_volume']:.6f} cm3")

                    display_dataframe(
                        recipe_df,
                        theme_mode,
                        row_class_func=stock_row_class,
                        width="stretch",
                        hide_index=True,
                    )
                    st.download_button(
                        "Download Recipe CSV",
                        data=csv_bytes(recipe_df),
                        file_name="stoichio_recipe.csv",
                        mime="text/csv",
                        width="stretch",
                    )

                    if result.get("warning"):
                        st.warning(result["warning"])
                        st.caption(f"Residual: {result['residual']:.6g}")
                    else:
                        st.success("Exact cation-balance solution computed.")

                    if result.get("ignored_elements"):
                        st.caption(
                            "Solve basis: "
                            + result.get("basis", "element balance")
                            + "; ignored in balance: "
                            + ", ".join(result["ignored_elements"])
                        )

                    with st.expander("Stoichiometry audit", expanded=False):
                        audit_cols = st.columns(4)
                        audit_cols[0].metric("Solve basis", result.get("basis", "element balance"))
                        audit_cols[1].metric("Precursor formula mass", result.get("precursor_formula_mass", ""))
                        audit_cols[2].metric("Target molar mass", result.get("target_molar_mass", ""))
                        audit_cols[3].metric("Residual", f"{result.get('residual', 0):.3g}")

                        coeff_df = recipe_coefficients_dataframe(result, recipe_masses)
                        balance_df = recipe_balance_dataframe(result, db)

                        st.markdown("##### Precursor coefficients")
                        display_dataframe(coeff_df, theme_mode, width="stretch", hide_index=True)
                        st.download_button(
                            "Download Coefficients CSV",
                            data=csv_bytes(coeff_df),
                            file_name="stoichio_recipe_coefficients.csv",
                            mime="text/csv",
                            width="stretch",
                        )

                        st.markdown("##### Element balance")
                        display_dataframe(balance_df, theme_mode, width="stretch", hide_index=True)
                        st.download_button(
                            "Download Element Balance CSV",
                            data=csv_bytes(balance_df),
                            file_name="stoichio_element_balance.csv",
                            mime="text/csv",
                            width="stretch",
                        )

                    low_after_recipe = [
                        row["Powder"]
                        for _, row in recipe_df.iterrows()
                        if "Low after recipe" in str(row.get("Stock status", ""))
                    ]

                    if stock_messages:
                        st.error("Inventory shortage: " + "; ".join(stock_messages))
                    else:
                        if low_after_recipe:
                            st.warning(
                                "Low inventory after this recipe: "
                                + ", ".join(low_after_recipe)
                                + f" will be below {LOW_STOCK_THRESHOLD_G:g} g."
                            )

                    inputs_changed = last_recipe["signature"] != current_signature
                    if inputs_changed:
                        st.warning("Inputs changed after this calculation. Recalculate before saving.")

                    recipe_target_owner = recipe_target_for.strip()
                    recipe_target_id = None
                    if recipe_target_owner:
                        recipe_target_number = next_target_number(history, recipe_target_owner)
                        recipe_target_id = format_target_id(recipe_target_owner, recipe_target_number)
                        st.caption(
                            f"Will save before-sintering recipe as {recipe_target_id} "
                            f"for {recipe_target_owner}."
                        )
                    else:
                        st.caption("No target owner set. This can still be saved as a quick recipe record.")

                    recipe_notes = st.text_area(
                        "Recipe notes",
                        placeholder="Example: calcination plan, pressing force, operator notes",
                        key=widget_key("recipe_save_notes", last_recipe["signature"]),
                    )
                    st.markdown("#### Lab notebook summary")
                    recipe_summary_text = recipe_lab_summary(
                        normalize_formula(last_recipe["target"]),
                        displayed_target_mass,
                        recipe_masses,
                        target_for=recipe_target_owner,
                        target_id=recipe_target_id,
                        notes=recipe_notes,
                        result=result,
                    )
                    st.code(recipe_summary_text, language="text")
                    st.download_button(
                        "Download Recipe Summary TXT",
                        data=recipe_summary_text,
                        file_name="stoichio_recipe_summary.txt",
                        mime="text/plain",
                        width="stretch",
                    )
                    recipe_report = recipe_report_html(
                        normalize_formula(last_recipe["target"]),
                        displayed_target_mass,
                        recipe_masses,
                        target_for=recipe_target_owner,
                        target_id=recipe_target_id,
                        notes=recipe_notes,
                        result=result,
                        stock_messages=stock_messages,
                        low_after_recipe=low_after_recipe,
                        planning_context=last_recipe,
                    )
                    st.download_button(
                        "Download Printable Recipe Report HTML",
                        data=recipe_report,
                        file_name=f"{safe_filename(recipe_target_id or last_recipe['target'])}_recipe_report.html",
                        mime="text/html",
                        width="stretch",
                    )
                    save_disabled = (
                        inputs_changed
                        or st.session_state.get("last_recipe_saved", False)
                    )
                    if st.button("Save Recipe to History", type="primary", width="stretch", disabled=save_disabled):
                        latest_history = load_history()
                        assigned_target_number = (
                            next_target_number(latest_history, recipe_target_owner)
                            if recipe_target_owner
                            else None
                        )
                        latest_inventory = load_inventory()
                        latest_in_stock, latest_stock_messages = check_stock(latest_inventory, recipe_masses)

                        inventory_deducted = False
                        if deduct_inventory:
                            if latest_in_stock:
                                consume_stock(latest_inventory, recipe_masses)
                                inventory_deducted = True
                            else:
                                st.error(
                                    "Recipe was not saved because inventory is insufficient: "
                                    + "; ".join(latest_stock_messages)
                                )
                                st.stop()

                        saved_history = log_synthesis(
                            normalize_formula(last_recipe["target"]),
                            displayed_target_mass,
                            recipe_masses,
                            selected_powders=last_recipe["selected"],
                            warning=result.get("warning"),
                            inventory_deducted=inventory_deducted,
                            notes=recipe_notes,
                            target_for=recipe_target_owner or None,
                            target_number=assigned_target_number,
                            calculation=recipe_calculation_metadata(result),
                        )
                        saved_recipe = saved_history[-1] if saved_history else {}
                        recipe_id = saved_recipe.get("target_id") or saved_recipe.get("recipe_id", "Recipe")
                        clear_data_cache()
                        st.session_state.last_recipe_saved = True
                        st.session_state.recipe_save_message = (
                            f"{recipe_id} saved to history"
                            + (" and inventory deducted." if inventory_deducted else ".")
                        )
                        st.rerun()

                    if st.session_state.get("last_recipe_saved", False):
                        st.caption("This recipe has already been saved. Recalculate to save a new entry.")


elif page == "Powders & Inventory":
    st.subheader("Powders & inventory")

    unknown_stock = unknown_inventory_items(inventory, db)
    if unknown_stock:
        st.warning(
            "These inventory entries are not in the powder database: "
            + ", ".join(unknown_stock)
            + ". Select one below and set it to 0 g to remove it."
        )

    add_col, edit_col, delete_col = st.columns([1, 1, 0.9], gap="large")

    with add_col:
        st.markdown("#### Add powder")
        new_formula = st.text_input("Powder formula", placeholder="Fe2O3")
        new_grams = st.number_input(
            "Initial inventory grams",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.4f",
        )

        if st.button("Add Powder & Stock", type="primary", width="stretch"):
            try:
                powder_name, powders = add_powder(new_formula)
                if new_grams > 0:
                    set_inventory_quantity(powder_name, new_grams)
                clear_data_cache()
                if new_grams > 0:
                    st.success(f"Added {powder_name} with {new_grams:g} g in inventory.")
                else:
                    st.success(f"Added {powder_name}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Molar masses are recalculated from atomic_masses.json every time the database is loaded.")

    with edit_col:
        st.markdown("#### Set quantity")
        powder_options = [""] + list(db.keys()) + [powder for powder in unknown_stock if powder not in db]
        powder = st.selectbox("Powder", powder_options, format_func=lambda value: value or "Choose powder")
        grams = st.number_input("Available grams", min_value=0.0, value=0.0, step=1.0, format="%.4f")

        if st.button("Save Quantity", type="primary", width="stretch"):
            try:
                if not powder:
                    raise ValueError("Choose a powder")
                set_inventory_quantity(powder, grams)
                clear_data_cache()
                st.success(f"Updated {normalize_formula(powder)} to {grams:g} g.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Set quantity to 0 to remove a powder from inventory.")

    with delete_col:
        st.markdown("#### Delete powder")
        powder_to_delete = st.selectbox(
            "Powder to delete",
            [""] + list(db.keys()),
            format_func=lambda value: value or "Choose powder",
        )
        remove_deleted_stock = st.checkbox("Also remove its inventory entry", value=True)

        if st.button("Delete Powder", width="stretch"):
            try:
                if not powder_to_delete:
                    raise ValueError("Choose a powder")
                delete_powder(powder_to_delete, remove_inventory=remove_deleted_stock)
                clear_data_cache()
                st.success(f"Deleted {powder_to_delete}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Deleting a powder removes it from future calculations. History entries are kept unchanged.")

    st.divider()

    powder_table_col, stock_table_col = st.columns(2, gap="large")
    with powder_table_col:
        st.markdown("#### Powder database")
        powder_df = database_dataframe(db)
        display_dataframe(powder_df, theme_mode, width="stretch", hide_index=True)
        st.download_button(
            "Download Powder Database CSV",
            data=csv_bytes(powder_df),
            file_name="powders.csv",
            mime="text/csv",
            width="stretch",
        )

    with stock_table_col:
        st.markdown("#### Current inventory")
        if inventory:
            comparison_recipe = active_recipe_masses()
            if comparison_recipe:
                in_stock, stock_messages = check_stock(inventory, comparison_recipe)
                st.caption("Compared with the last calculated recipe.")
                if stock_messages:
                    st.error("Last recipe needs more powder than inventory: " + "; ".join(stock_messages))

            low_stock_powders = [
                powder
                for powder, grams in inventory.items()
                if grams < LOW_STOCK_THRESHOLD_G
            ]
            if low_stock_powders:
                st.warning(
                    f"Low inventory below {LOW_STOCK_THRESHOLD_G:g} g: "
                    + ", ".join(low_stock_powders)
                )

            stock_df = inventory_dataframe(inventory, comparison_recipe)
            display_dataframe(
                stock_df,
                theme_mode,
                row_class_func=stock_row_class,
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "Download Inventory CSV",
                data=csv_bytes(stock_df),
                file_name="inventory.csv",
                mime="text/csv",
                width="stretch",
            )
        else:
            st.info("Inventory is empty.")


elif page == "Material Density":
    st.subheader("Material density database")
    st.caption("Known target densities are used for pellet-height planning and post-sintering relative density.")

    entry_col, table_col = st.columns([0.95, 1.05], gap="large")

    with entry_col:
        st.markdown("#### Add or update target")
        density_formula = st.text_input("Target formula", placeholder="Fe1.98Ti0.02O3")
        density_phase = st.text_input("Phase / polymorph (optional)", placeholder="rutile, anatase, hematite")
        density_entry_mode = st.radio(
            "Density entry mode",
            ["From lattice parameters", "From unit cell volume", "Manual theoretical density"],
        )

        unit_cell_volume = None
        z_value = None
        theoretical_density = None
        density_source = "manual"
        crystal_system = ""
        lattice_params = {
            "a": None,
            "b": None,
            "c": None,
            "alpha": None,
            "beta": None,
            "gamma": None,
        }

        if density_entry_mode == "From lattice parameters":
            crystal_system = st.selectbox(
                "Crystal system",
                ["Cubic", "Tetragonal", "Orthorhombic", "Hexagonal", "Rhombohedral", "Monoclinic", "Triclinic"],
            )
            lattice_params = lattice_parameter_inputs(crystal_system)
            z_value = st.number_input(
                "Z, formula units per unit cell",
                min_value=0.0,
                value=1.0,
                step=1.0,
                format="%.6f",
                help="Z is not atoms per unit cell. It is how many target formula units are in one unit cell.",
            )
            if density_formula and z_value > 0:
                try:
                    unit_cell_volume = unit_cell_volume_from_lattice(
                        crystal_system,
                        lattice_params["a"],
                        lattice_params["b"],
                        lattice_params["c"],
                        lattice_params["alpha"],
                        lattice_params["beta"],
                        lattice_params["gamma"],
                    )
                    theoretical_density = theoretical_density_from_cell(
                        density_formula,
                        unit_cell_volume,
                        z_value,
                    )
                    st.info(
                        f"Unit cell volume: {unit_cell_volume:.5f} A3; "
                        f"theoretical density: {theoretical_density:.5f} g/cm3"
                    )
                    density_source = "lattice parameters"
                except ValueError as exc:
                    st.warning(str(exc))
        elif density_entry_mode == "From unit cell volume":
            unit_cell_volume = st.number_input(
                "Unit cell volume (A3)",
                min_value=0.0,
                value=0.0,
                step=1.0,
                format="%.6f",
                help="Use Angstrom cubed. The app converts A3 to cm3.",
            )
            z_value = st.number_input(
                "Z, formula units per unit cell",
                min_value=0.0,
                value=1.0,
                step=1.0,
                format="%.6f",
                help="Z is not atoms per unit cell. It is how many target formula units are in one unit cell.",
            )
            if density_formula and unit_cell_volume > 0 and z_value > 0:
                try:
                    theoretical_density = theoretical_density_from_cell(
                        density_formula,
                        unit_cell_volume,
                        z_value,
                    )
                    st.info(f"Calculated theoretical density: {theoretical_density:.5f} g/cm3")
                    density_source = "unit cell"
                except ValueError as exc:
                    st.warning(str(exc))
        else:
            theoretical_density = st.number_input(
                "Manual theoretical density (g/cm3)",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.6f",
            )
            density_source = "manual"

        reference = st.text_input("Source / reference", placeholder="XRD refinement, paper, manual")
        notes = st.text_area("Notes", height=90)

        save_density = st.button("Save Material Density", type="primary", width="stretch")
        if save_density:
            try:
                if not density_formula:
                    raise ValueError("Enter a target formula")
                if theoretical_density is None or theoretical_density <= 0:
                    raise ValueError("Enter enough density information")
                upsert_material_density(
                    density_formula,
                    phase=density_phase,
                    theoretical_density=theoretical_density,
                    unit_cell_volume=unit_cell_volume if unit_cell_volume and unit_cell_volume > 0 else None,
                    z=z_value if z_value and z_value > 0 else None,
                    density_source=density_source,
                    crystal_system=crystal_system,
                    a=lattice_params["a"],
                    b=lattice_params["b"],
                    c=lattice_params["c"],
                    alpha=lattice_params["alpha"],
                    beta=lattice_params["beta"],
                    gamma=lattice_params["gamma"],
                    source=reference,
                    notes=notes,
                )
                clear_data_cache()
                saved_label = normalize_formula(density_formula)
                if density_phase.strip():
                    saved_label = f"{saved_label} ({density_phase.strip()})"
                st.success(f"Saved density for {saved_label}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.divider()
        st.markdown("#### Delete target density")
        density_delete_target = st.selectbox(
            "Density record to delete",
            [""] + list(material_densities.keys()),
            format_func=lambda value: density_record_label(value, material_densities[value]) if value else "Choose target",
        )
        if st.button("Delete Density Record", width="stretch"):
            try:
                if not density_delete_target:
                    raise ValueError("Choose a target")
                delete_material_density(density_delete_target)
                clear_data_cache()
                st.success(f"Deleted density for {density_delete_target}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    with table_col:
        st.markdown("#### Known densities")
        density_df = material_density_dataframe(material_densities)
        if density_df.empty:
            st.info("No material densities saved yet.")
        else:
            st.caption("Blue rows were seeded by Codex from COD/paper literature and should be source-checked before lab use.")
            display_dataframe(
                density_df,
                theme_mode,
                row_class_func=lambda row: (
                    "codex-seeded"
                    if str(row.get("Origin", "")).lower().startswith("codex")
                    else ""
                ),
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "Download Material Density CSV",
                data=csv_bytes(density_df),
                file_name="material_densities.csv",
                mime="text/csv",
                width="stretch",
            )


elif page == "Target Density":
    st.subheader("Target density after sintering")
    st.caption("Use the final measured dimensions after sintering, not the 25.05 mm die diameter.")

    density_left, density_right = st.columns([0.95, 1.05], gap="large")

    with density_left:
        linked_targets = linked_recipe_targets(history)
        linked_target_lookup = {entry["entry_id"]: entry for entry in linked_targets}
        linked_target_key = st.selectbox(
            "Saved recipe target",
            [""] + list(linked_target_lookup.keys()),
            format_func=lambda key: (
                "New target not linked to a recipe"
                if not key
                else linked_recipe_target_label(linked_target_lookup[key])
            ),
            help="Choose the before-sintering recipe target when this density measurement belongs to it.",
        )
        linked_target = linked_target_lookup.get(linked_target_key)

        if linked_target:
            density_target = linked_target.get("target", "")
            target_for = str(linked_target.get("target_for", "")).strip()
            linked_target_number = int(linked_target.get("target_number", 0) or 0)
            linked_target_id = linked_target.get("target_id") or format_target_id(
                target_for,
                linked_target_number,
            )
            st.info(
                f"After-sintering density will be linked to {linked_target_id}"
                + (f" for {target_for}." if target_for else ".")
            )
            st.caption(
                "Linked before-sintering recipe: "
                + (linked_target.get("recipe_id") or linked_target.get("entry_id", "saved recipe"))
            )
            st.text_input(
                "Target formula",
                value=density_target,
                disabled=True,
                key=widget_key("linked_density_target", linked_target_key),
            )
        else:
            density_target = st.text_input("Target formula", placeholder="Fe1.98Ti0.02O3")
            target_for = st.text_input(
                "Target for (optional)",
                placeholder="Person or project name",
                key="target_density_for",
            )
            linked_target_number = None
            linked_target_id = None

        normalized_person = target_for.strip()
        if normalized_person:
            if linked_target_id:
                st.caption(f"This is the after-sintering record for {linked_target_id}.")
            else:
                preview_number = next_target_number(history, normalized_person)
                st.caption(
                    f"Next saved target for {normalized_person} will be "
                    f"{format_target_id(normalized_person, preview_number)}."
                )

        sintered_diameter = st.number_input(
            "Measured final diameter (mm)",
            min_value=0.0,
            value=0.0,
            step=0.1,
            format="%.4f",
        )
        sintered_height = st.number_input(
            "Measured final height (mm)",
            min_value=0.0,
            value=0.0,
            step=0.1,
            format="%.4f",
        )
        sintered_mass = st.number_input(
            "Measured final mass (g)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.6f",
        )
        relative_theoretical_density, density_source_mode = density_source_control(
            density_target,
            material_densities,
            key_prefix="relative_density",
        )
        current_density_signature = target_density_signature(
            density_target,
            target_for,
            sintered_diameter,
            sintered_height,
            sintered_mass,
            relative_theoretical_density,
            density_source_mode,
            target_id=linked_target_id,
            linked_recipe_entry_id=linked_target.get("entry_id") if linked_target else None,
        )
        calculate_density = st.button("Calculate Target Density", type="primary", width="stretch")

        if calculate_density:
            try:
                if relative_theoretical_density is None:
                    raise ValueError("Choose a saved density or enter a manual theoretical density")

                normalized_density_target = normalize_formula(density_target)
                pellet_measured_density, final_volume = measured_density(
                    sintered_mass,
                    sintered_diameter,
                    sintered_height,
                )
                relative_percent = relative_density_percent(
                    pellet_measured_density,
                    relative_theoretical_density,
                )
                st.session_state.last_target_density_result = {
                    "target": normalized_density_target,
                    "target_for": normalized_person,
                    "measured_density": pellet_measured_density,
                    "theoretical_density": relative_theoretical_density,
                    "relative_percent": relative_percent,
                    "final_volume": final_volume,
                    "final_mass": sintered_mass,
                    "final_diameter": sintered_diameter,
                    "final_height": sintered_height,
                    "density_source": density_source_mode,
                    "target_number": linked_target_number,
                    "target_id": linked_target_id,
                    "linked_recipe": recipe_link_snapshot(linked_target),
                    "signature": current_density_signature,
                }
                st.session_state.last_target_density_saved = False
            except ValueError as exc:
                st.session_state.last_target_density_result = {
                    "error": str(exc),
                    "signature": current_density_signature,
                }

    with density_right:
        st.markdown("#### Result")
        save_message = st.session_state.pop("target_density_save_message", None)
        if save_message:
            st.success(save_message)

        last_density = st.session_state.get("last_target_density_result")
        if not last_density:
            st.info("Enter final sintered dimensions, final mass, and a theoretical density.")
        elif last_density.get("error"):
            st.error(last_density["error"])
        else:
            deficit_percent = 100.0 - last_density["relative_percent"]
            current_target_owner = str(last_density.get("target_for", "")).strip()
            current_target_number = last_density.get("target_number")
            if not current_target_number and current_target_owner:
                current_target_number = next_target_number(history, current_target_owner)
            current_target_id = last_density.get("target_id")
            if not current_target_id and current_target_owner:
                current_target_id = format_target_id(current_target_owner, current_target_number)

            if current_target_id:
                st.caption(
                    f"Will save after-sintering density as {current_target_id} for "
                    f"{current_target_owner}: {last_density['target']}"
                )
            else:
                st.caption("This can be saved as a quick unassigned density record.")
            metric_cols = st.columns(3)
            metric_cols[0].metric("Measured density", round(last_density["measured_density"], 4))
            metric_cols[1].metric("Theoretical density", round(last_density["theoretical_density"], 4))
            metric_cols[2].metric("Relative density", f"{last_density['relative_percent']:.2f}%")

            detail_cols = st.columns(3)
            detail_cols[0].metric("Final volume (cm3)", round(last_density["final_volume"], 5))
            detail_cols[1].metric("Density deficit", f"{deficit_percent:.2f}%")
            detail_cols[2].metric("Final mass (g)", round(last_density["final_mass"], 5))

            linked_recipe = last_density.get("linked_recipe")
            if linked_recipe:
                linked_recipe_label = linked_recipe.get("recipe_id") or linked_recipe.get("entry_id", "saved recipe")
                st.info(f"Linked to before-sintering recipe {linked_recipe_label}.")
                with st.expander("Linked recipe details", expanded=False):
                    st.markdown(
                        f"**Input basis:** {linked_recipe.get('input_basis_g', '')} g "
                        f"({mass_basis_label(linked_recipe.get('input_basis_type'))})"
                    )
                    st.markdown(f"**Powder basis:** {linked_recipe.get('powder_basis_g', '')} g")
                    st.markdown(
                        "**Powders:** "
                        + ", ".join(linked_recipe.get("selected_powders") or [])
                    )
                    linked_recipe_masses = linked_recipe.get("recipe") or {}
                    if linked_recipe_masses:
                        display_dataframe(
                            recipe_dataframe(linked_recipe_masses),
                            theme_mode,
                            width="stretch",
                            hide_index=True,
                        )
                    if linked_recipe.get("notes"):
                        st.markdown(f"**Recipe notes:** {linked_recipe['notes']}")

            if last_density["relative_percent"] > 100:
                st.warning("Relative density is above 100%. Check dimensions, mass, or theoretical density.")
            else:
                st.success("Target density calculated.")

            inputs_changed = last_density["signature"] != current_density_signature
            if inputs_changed:
                st.warning("Inputs changed after this calculation. Recalculate before saving.")

            target_density_notes = st.text_area(
                "Target density notes",
                placeholder="Example: sintering temperature, cracks, polish state, measurement notes",
                key=widget_key("target_density_save_notes", last_density["signature"]),
            )
            st.markdown("#### Lab notebook summary")
            density_summary_text = target_density_lab_summary(last_density, target_id=current_target_id)
            st.code(density_summary_text, language="text")
            st.download_button(
                "Download Density Summary TXT",
                data=density_summary_text,
                file_name="stoichio_density_summary.txt",
                mime="text/plain",
                width="stretch",
            )
            save_disabled = (
                inputs_changed
                or st.session_state.get("last_target_density_saved", False)
            )
            if st.button("Save Target Density to History", type="primary", width="stretch", disabled=save_disabled):
                assigned_target_number = last_density.get("target_number")
                if not assigned_target_number and current_target_owner:
                    latest_history = load_history()
                    assigned_target_number = next_target_number(latest_history, current_target_owner)
                assigned_target_id = last_density.get("target_id")
                if not assigned_target_id and current_target_owner:
                    assigned_target_id = format_target_id(current_target_owner, assigned_target_number)

                saved_history = log_target_density(
                    last_density["target"],
                    assigned_target_number,
                    current_target_owner or None,
                    last_density["measured_density"],
                    last_density["theoretical_density"],
                    last_density["relative_percent"],
                    last_density["final_volume"],
                    last_density["final_mass"],
                    last_density["final_diameter"],
                    last_density["final_height"],
                    density_source=last_density["density_source"],
                    notes=target_density_notes,
                    target_id=assigned_target_id,
                    linked_recipe=last_density.get("linked_recipe"),
                )
                saved_target = saved_history[-1] if saved_history else {}
                target_id = saved_target.get("target_id") or "quick density record"
                clear_data_cache()
                st.session_state.pop("last_target_density_result", None)
                st.session_state.last_target_density_saved = False
                if current_target_owner:
                    st.session_state.target_density_save_message = (
                        f"Target density saved as {target_id} for {current_target_owner}."
                    )
                else:
                    st.session_state.target_density_save_message = "Target density saved as a quick record."
                st.rerun()

            if st.session_state.get("last_target_density_saved", False):
                st.caption("This target density has already been saved. Recalculate to save a new entry.")


elif page == "History":
    st.subheader("History")

    target_tab, recipe_tab, density_tab, raw_tab = st.tabs(["Targets", "Recipes", "Target Density", "Raw Log"])

    with target_tab:
        st.markdown("#### Target lifecycle")
        lifecycle_groups = target_lifecycle_groups(history)
        if not lifecycle_groups:
            st.info("No saved target records yet.")
        else:
            search_col, owner_col, status_col = st.columns([1.45, 0.9, 0.85], gap="small")
            lifecycle_search = search_col.text_input(
                "Search targets",
                placeholder="Target ID, person, formula, powder, notes",
            )
            owner_options = ["All"] + sorted({group_key[0] for group_key, _ in lifecycle_groups})
            owner_filter = owner_col.selectbox("Target for", owner_options)
            status_filter = status_col.selectbox(
                "Status",
                ["All", "Complete", "Needs density", "Needs recipe"],
            )
            filtered_lifecycle_groups = filter_target_lifecycle_groups(
                lifecycle_groups,
                search_text=lifecycle_search,
                owner_filter=owner_filter,
                status_filter=status_filter,
            )
            lifecycle_df = target_lifecycle_dataframe(lifecycle_groups=filtered_lifecycle_groups)
            st.caption(f"Showing {len(filtered_lifecycle_groups)} of {len(lifecycle_groups)} target groups.")

            if not filtered_lifecycle_groups:
                st.info("No target records match these filters.")

            for group_key, entries in filtered_lifecycle_groups:
                summary = target_lifecycle_summary(group_key, entries)
                target_id = summary["target_id"]
                can_clear_group = any(entry.get("target_id") for entry in entries)
                group_col, group_delete_col = st.columns([0.94, 0.06], gap="small")
                with group_col:
                    with st.expander(summary["title"], expanded=True):
                        st.markdown(
                            '<div class="history-item-meta">'
                            f'{html.escape(summary["meta"])}'
                            "</div>",
                            unsafe_allow_html=True,
                        )
                        st.download_button(
                            "Download Target Report HTML",
                            data=target_traceability_report_html(group_key, summary),
                            file_name=f"{safe_filename(target_id)}_target_report.html",
                            mime="text/html",
                            key=widget_key("target_report_html", target_id),
                            width="stretch",
                        )

                        if summary["recipes"]:
                            st.markdown("##### Before sintering")
                            for entry in summary["recipes"]:
                                entry_id = entry.get("entry_id")
                                item_summary = recipe_history_summary(entry)
                                item_col, item_delete_col = st.columns([0.94, 0.06], gap="small")
                                with item_col:
                                    st.markdown(
                                        '<div class="history-item">'
                                        f'<div class="history-item-title">{html.escape(item_summary["title"])}</div>'
                                        f'<div class="history-item-meta">{html.escape(item_summary["meta"])}</div>'
                                        "</div>",
                                        unsafe_allow_html=True,
                                    )
                                with item_delete_col:
                                    st.write("")
                                    if entry_id and trash_button(
                                        widget_key("delete_lifecycle_recipe", entry_id),
                                        "Delete this before-sintering recipe",
                                    ):
                                        removed_count, _ = delete_history_entry(entry_id)
                                        cached_load_history.clear()
                                        st.success(f"Deleted {removed_count} recipe item.")
                                        st.rerun()
                        else:
                            st.caption("No before-sintering recipe saved for this target.")

                        if summary["densities"]:
                            st.markdown("##### After sintering")
                            for entry in summary["densities"]:
                                entry_id = entry.get("entry_id")
                                item_summary = target_density_history_summary(entry)
                                item_col, item_delete_col = st.columns([0.94, 0.06], gap="small")
                                with item_col:
                                    st.markdown(
                                        '<div class="history-item">'
                                        f'<div class="history-item-title">{html.escape(item_summary["title"])}</div>'
                                        f'<div class="history-item-meta">{html.escape(item_summary["meta"])}</div>'
                                        "</div>",
                                        unsafe_allow_html=True,
                                    )
                                with item_delete_col:
                                    st.write("")
                                    if entry_id and trash_button(
                                        widget_key("delete_lifecycle_density", entry_id),
                                        "Delete this after-sintering density record",
                                    ):
                                        removed_count, _ = delete_history_entry(entry_id)
                                        cached_load_history.clear()
                                        st.success(f"Deleted {removed_count} target-density item.")
                                        st.rerun()
                        else:
                            st.caption("No after-sintering density saved for this target yet.")
                with group_delete_col:
                    st.write("")
                    if can_clear_group and trash_button(
                        widget_key("clear_lifecycle_group", target_id),
                        f"Clear all history for {target_id}",
                    ):
                        removed_count, _ = clear_history_for_target_id(target_id)
                        cached_load_history.clear()
                        st.success(f"Removed {removed_count} item(s) for {target_id}.")
                        st.rerun()

            if not lifecycle_df.empty:
                st.download_button(
                    "Download Filtered Target Lifecycle CSV",
                    data=csv_bytes(lifecycle_df),
                    file_name="stoichio_target_lifecycle.csv",
                    mime="text/csv",
                    width="stretch",
                )

    with recipe_tab:
        st.markdown("#### Recipe history")
        history_df = history_dataframe(recipe_history)
        if history_df.empty:
            st.info("No saved recipes yet.")
        else:
            for target_name, entries in grouped_history(recipe_history).items():
                group_col, group_delete_col = st.columns([0.94, 0.06], gap="small")
                with group_col:
                    with st.expander(f"{target_name} ({len(entries)})", expanded=False):
                        for entry in reversed(entries):
                            entry_id = entry.get("entry_id")
                            summary = recipe_history_summary(entry)
                            item_col, item_delete_col = st.columns([0.94, 0.06], gap="small")
                            with item_col:
                                st.markdown(
                                    '<div class="history-item">'
                                    f'<div class="history-item-title">{html.escape(summary["title"])}</div>'
                                    f'<div class="history-item-meta">{html.escape(summary["meta"])}</div>'
                                    "</div>",
                                    unsafe_allow_html=True,
                                )
                            with item_delete_col:
                                st.write("")
                                if entry_id and trash_button(
                                    widget_key("delete_recipe", entry_id),
                                    "Delete this saved recipe",
                                ):
                                    removed_count, _ = delete_history_entry(entry_id)
                                    cached_load_history.clear()
                                    st.success(f"Deleted {removed_count} recipe item.")
                                    st.rerun()
                with group_delete_col:
                    st.write("")
                    if trash_button(
                        widget_key("clear_recipe_group", target_name),
                        f"Clear all recipe history for {target_name}",
                    ):
                        removed_count, _ = clear_history_for_target(target_name)
                        cached_load_history.clear()
                        st.success(f"Removed {removed_count} recipe(s) for {target_name}.")
                        st.rerun()

            st.download_button(
                "Download Recipe History CSV",
                data=csv_bytes(history_df),
                file_name="stoichio_recipe_history.csv",
                mime="text/csv",
                width="stretch",
            )

    with density_tab:
        st.markdown("#### Target density log")
        density_history_df = target_density_dataframe(target_density_records)
        if density_history_df.empty:
            st.info("No saved target-density records yet.")
        else:
            for person, entries in grouped_target_density_history(target_density_records).items():
                group_col, group_delete_col = st.columns([0.94, 0.06], gap="small")
                with group_col:
                    with st.expander(f"{person} ({len(entries)} target{'s' if len(entries) != 1 else ''})", expanded=True):
                        for entry in sorted(entries, key=lambda item: item.get("target_number", 0), reverse=True):
                            entry_id = entry.get("entry_id")
                            summary = target_density_history_summary(entry)
                            item_col, item_delete_col = st.columns([0.94, 0.06], gap="small")
                            with item_col:
                                st.markdown(
                                    '<div class="history-item">'
                                    f'<div class="history-item-title">{html.escape(summary["title"])}</div>'
                                    f'<div class="history-item-meta">{html.escape(summary["meta"])}</div>'
                                    "</div>",
                                    unsafe_allow_html=True,
                                )
                            with item_delete_col:
                                st.write("")
                                if entry_id and trash_button(
                                    widget_key("delete_target_density", entry_id),
                                    "Delete this saved target-density record",
                                ):
                                    removed_count, _ = delete_history_entry(entry_id)
                                    cached_load_history.clear()
                                    st.success(f"Deleted {removed_count} target-density item.")
                                    st.rerun()
                with group_delete_col:
                    st.write("")
                    if trash_button(
                        widget_key("clear_target_density_group", person),
                        f"Clear all target-density records for {person}",
                    ):
                        removed_count, _ = clear_target_density_history_for_person(person)
                        cached_load_history.clear()
                        st.success(f"Removed {removed_count} target-density record(s) for {person}.")
                        st.rerun()

            st.download_button(
                "Download Target Density CSV",
                data=csv_bytes(density_history_df),
                file_name="stoichio_target_density_history.csv",
                mime="text/csv",
                width="stretch",
            )

    with raw_tab:
        if not history:
            st.info("No saved history yet.")
        else:
            for entry in reversed(history):
                st.json(entry)
