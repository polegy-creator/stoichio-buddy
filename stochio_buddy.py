import json
import html
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
    clear_target_density_history_for_person,
    configure_apps_script,
    configure_google_sheets,
    consume_stock,
    delete_material_density,
    delete_powder,
    load_history,
    load_inventory,
    load_material_densities,
    load_powders,
    log_synthesis,
    log_target_density,
    set_inventory_quantity,
    storage_error,
    storage_label,
    upsert_material_density,
)
from stoich_engine import compute_recipe


st.set_page_config(
    page_title="Stoichio Buddy",
    page_icon=":material/science:",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_CACHE_TTL_SECONDS = 20


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


def recipe_dataframe(recipe_masses):
    return pd.DataFrame(
        [
            {
                "Powder": powder,
                "Mass (g)": round(grams, 3),
                "Exact mass (g)": grams,
            }
            for powder, grams in recipe_masses.items()
        ]
    )


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


def inventory_dataframe(inventory):
    return pd.DataFrame(
        [
            {"Powder": powder, "Available (g)": round(grams, 3)}
            for powder, grams in inventory.items()
        ]
    )


def material_density_dataframe(records):
    columns = [
        "Target",
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
        "Reference",
        "Notes",
    ]
    rows = []
    for formula, record in records.items():
        rows.append(
            {
                "Target": formula,
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
                "Reference": record.get("source", ""),
                "Notes": record.get("notes", ""),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def lookup_known_density(target, material_densities):
    if not target:
        return None, None, "Enter a target formula first"

    try:
        key = normalize_formula(target)
    except ValueError as exc:
        return None, None, str(exc)

    record = material_densities.get(key)
    if not record:
        return key, None, f"No saved density for {key}"

    density = record.get("theoretical_density_g_cm3")
    if density is None or density <= 0:
        return key, None, f"Saved density for {key} is missing"

    return key, float(density), None


def density_source_control(target, material_densities, key_prefix):
    source_mode = st.radio(
        "Theoretical density source",
        ["Known material density", "Use another density record", "Manual density"],
        horizontal=True,
        key=f"{key_prefix}_density_source",
    )

    if source_mode == "Known material density":
        normalized_target, density, error = lookup_known_density(target, material_densities)
        if density is not None:
            record = material_densities[normalized_target]
            st.success(f"Using {normalized_target}: {density:.4f} g/cm3")
            if record.get("source") or record.get("density_source"):
                st.caption(
                    "Source: "
                    + (record.get("source") or record.get("density_source") or "saved material density")
                )
        else:
            st.warning(error)
        return density, source_mode

    if source_mode == "Use another density record":
        source_target = st.selectbox(
            "Density record to use",
            [""] + list(material_densities.keys()),
            format_func=lambda value: value or "Choose saved material",
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
                    f"Using {source_target} unit cell for {normalized_target}: "
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


def history_dataframe(history):
    if not history:
        return pd.DataFrame()

    rows = []
    for entry in history:
        rows.append(
            {
                "Time": format_history_time(entry.get("time", entry.get("timestamp", ""))),
                "Target": entry.get("target", ""),
                "Target mass (g)": entry.get("mass", ""),
                "Recipe": json.dumps(entry.get("recipe", {}), ensure_ascii=False),
                "Inventory deducted": entry.get("inventory_deducted", False),
                "Warning": entry.get("warning") or "",
            }
        )
    return pd.DataFrame(rows).iloc[::-1]


def target_density_dataframe(history):
    if not history:
        return pd.DataFrame()

    rows = []
    for entry in history:
        rows.append(
            {
                "Time": format_history_time(entry.get("time", entry.get("timestamp", ""))),
                "Target #": entry.get("target_number", ""),
                "Target for": entry.get("target_for", ""),
                "Formula": entry.get("target", ""),
                "Measured density (g/cm3)": round(entry.get("measured_density_g_cm3", 0), 4),
                "Theoretical density (g/cm3)": round(entry.get("theoretical_density_g_cm3", 0), 4),
                "Relative density (%)": round(entry.get("relative_density_percent", 0), 2),
                "Final diameter (mm)": round(entry.get("final_diameter_mm", 0), 4),
                "Final height (mm)": round(entry.get("final_height_mm", 0), 4),
                "Final mass (g)": round(entry.get("final_mass_g", 0), 6),
                "Final volume (cm3)": round(entry.get("final_volume_cm3", 0), 6),
                "Density source": entry.get("density_source", ""),
            }
        )
    return pd.DataFrame(rows).iloc[::-1]


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


def next_target_number(history, target_for):
    person = str(target_for).strip()
    if not person:
        return 1

    used_numbers = []
    for entry in target_density_history(history):
        if str(entry.get("target_for", "")).strip() != person:
            continue
        try:
            used_numbers.append(int(entry.get("target_number")))
        except (TypeError, ValueError):
            continue

    return max(used_numbers, default=0) + 1


def csv_bytes(df):
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()


def display_dataframe(df, theme_mode, **kwargs):
    table_rows = []
    headers = "".join(f"<th>{html.escape(str(column))}</th>" for column in df.columns)
    table_rows.append(f"<tr>{headers}</tr>")

    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row)
        table_rows.append(f"<tr>{cells}</tr>")

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
):
    return {
        "target": str(target).strip(),
        "target_for": str(target_for).strip(),
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
        ["Calculate", "Powders & Inventory", "Material Density", "Target Density", "History"],
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


if page == "Calculate":
    left, right = st.columns([0.95, 1.05], gap="large")

    with left:
        st.subheader("Recipe setup")
        target = st.text_input(
            "Target formula",
            placeholder="Fe1.98Ti0.02O3",
            help="Simple formulas with decimal stoichiometry are supported.",
        )
        amount_mode = st.radio(
            "Target amount mode",
            ["Target mass", "Pellet height"],
            horizontal=True,
            help="Use pellet height to calculate target mass from theoretical density and a 25.05 mm die.",
        )

        target_mass = None
        planning_volume = None
        theoretical_density_used = None
        planning_height = None
        planning_error = None

        if amount_mode == "Target mass":
            target_mass = st.number_input(
                "Target formula mass (g)",
                min_value=0.0,
                value=15.6,
                step=0.1,
                format="%.4f",
                help="This is the intended formula batch basis. Total precursor powder can be higher.",
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
                        f"Calculated target mass: {target_mass:.4f} g "
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
                    "error": "Enter a valid target mass, or a valid height and theoretical density.",
                    "signature": current_signature,
                }
            elif planning_error:
                st.session_state.last_recipe_result = {
                    "error": planning_error,
                    "signature": current_signature,
                }
            else:
                result = compute_recipe(target, target_mass, db, selected)
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
            st.info("Enter a target formula, mass, and selected powders, then calculate.")
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
                    recipe_df = recipe_dataframe(recipe_masses)
                    total_powder = sum(recipe_masses.values())
                    displayed_target_mass = last_recipe["target_mass"]

                    metric_cols = st.columns(3)
                    metric_cols[0].metric("Target basis (g)", round(displayed_target_mass, 3))
                    metric_cols[1].metric("Precursor powder (g)", round(total_powder, 3))
                    metric_cols[2].metric("Powders used", len(recipe_masses))

                    if last_recipe["amount_mode"] == "Pellet height":
                        detail_cols = st.columns(3)
                        detail_cols[0].metric("Die diameter (mm)", round(DEFAULT_DIE_DIAMETER_MM, 3))
                        detail_cols[1].metric("Desired height (mm)", round(last_recipe["planning_height"], 3))
                        detail_cols[2].metric("Theoretical density", round(last_recipe["theoretical_density"], 4))
                        st.caption(f"Calculated planning volume: {last_recipe['planning_volume']:.6f} cm3")

                    display_dataframe(recipe_df, theme_mode, width="stretch", hide_index=True)
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

                    current_inventory = inventory
                    in_stock, stock_messages = check_stock(current_inventory, recipe_masses)
                    if stock_messages:
                        st.warning("Inventory warning: " + "; ".join(stock_messages))

                    inputs_changed = last_recipe["signature"] != current_signature
                    if inputs_changed:
                        st.warning("Inputs changed after this calculation. Recalculate before saving.")

                    save_disabled = inputs_changed or st.session_state.get("last_recipe_saved", False)
                    if st.button("Save Recipe to History", type="primary", width="stretch", disabled=save_disabled):
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

                        log_synthesis(
                            normalize_formula(last_recipe["target"]),
                            displayed_target_mass,
                            recipe_masses,
                            selected_powders=last_recipe["selected"],
                            warning=result.get("warning"),
                            inventory_deducted=inventory_deducted,
                        )
                        clear_data_cache()
                        st.session_state.last_recipe_saved = True
                        st.session_state.recipe_save_message = (
                            "Recipe saved to history"
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
            stock_df = inventory_dataframe(inventory)
            display_dataframe(stock_df, theme_mode, width="stretch", hide_index=True)
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
                st.success(f"Saved density for {normalize_formula(density_formula)}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.divider()
        st.markdown("#### Delete target density")
        density_delete_target = st.selectbox(
            "Density record to delete",
            [""] + list(material_densities.keys()),
            format_func=lambda value: value or "Choose target",
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
            display_dataframe(density_df, theme_mode, width="stretch", hide_index=True)
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
        density_target = st.text_input("Target formula", placeholder="Fe1.98Ti0.02O3")
        target_for = st.text_input("Target for", placeholder="Person or project name", key="target_density_for")

        normalized_person = target_for.strip()
        if normalized_person:
            st.caption(
                f"Next saved target for {normalized_person} will be "
                f"#{next_target_number(history, normalized_person)}."
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
        )
        calculate_density = st.button("Calculate Target Density", type="primary", width="stretch")

        if calculate_density:
            try:
                if not normalized_person:
                    raise ValueError("Enter who the target is for")
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
            current_target_number = next_target_number(history, last_density["target_for"])

            st.caption(
                f"Will save as target #{current_target_number} for "
                f"{last_density['target_for']}: {last_density['target']}"
            )
            metric_cols = st.columns(3)
            metric_cols[0].metric("Measured density", round(last_density["measured_density"], 4))
            metric_cols[1].metric("Theoretical density", round(last_density["theoretical_density"], 4))
            metric_cols[2].metric("Relative density", f"{last_density['relative_percent']:.2f}%")

            detail_cols = st.columns(3)
            detail_cols[0].metric("Final volume (cm3)", round(last_density["final_volume"], 5))
            detail_cols[1].metric("Density deficit", f"{deficit_percent:.2f}%")
            detail_cols[2].metric("Final mass (g)", round(last_density["final_mass"], 5))

            if last_density["relative_percent"] > 100:
                st.warning("Relative density is above 100%. Check dimensions, mass, or theoretical density.")
            else:
                st.success("Target density calculated.")

            inputs_changed = last_density["signature"] != current_density_signature
            if inputs_changed:
                st.warning("Inputs changed after this calculation. Recalculate before saving.")

            save_disabled = (
                inputs_changed
                or st.session_state.get("last_target_density_saved", False)
            )
            if st.button("Save Target Density to History", type="primary", width="stretch", disabled=save_disabled):
                latest_history = load_history()
                assigned_target_number = next_target_number(latest_history, last_density["target_for"])

                log_target_density(
                    last_density["target"],
                    assigned_target_number,
                    last_density["target_for"],
                    last_density["measured_density"],
                    last_density["theoretical_density"],
                    last_density["relative_percent"],
                    last_density["final_volume"],
                    last_density["final_mass"],
                    last_density["final_diameter"],
                    last_density["final_height"],
                    density_source=last_density["density_source"],
                )
                clear_data_cache()
                st.session_state.pop("last_target_density_result", None)
                st.session_state.last_target_density_saved = False
                st.session_state.target_density_save_message = (
                    f"Target density saved as #{assigned_target_number} "
                    f"for {last_density['target_for']}."
                )
                st.rerun()

            if st.session_state.get("last_target_density_saved", False):
                st.caption("This target density has already been saved. Recalculate to save a new entry.")


elif page == "History":
    st.subheader("History")

    recipe_tab, density_tab, raw_tab = st.tabs(["Recipes", "Target Density", "Raw Log"])

    with recipe_tab:
        st.markdown("#### Recipe history")
        history_df = history_dataframe(recipe_history)
        if history_df.empty:
            st.info("No saved recipes yet.")
        else:
            target_names = list(grouped_history(recipe_history).keys())
            cleanup_col, action_col = st.columns([1.25, 0.75], gap="large")
            with cleanup_col:
                target_to_clear = st.selectbox(
                    "Target history to clear",
                    [""] + target_names,
                    format_func=lambda value: value or "Choose target",
                )
            with action_col:
                st.write("")
                st.write("")
                if st.button("Clear Recipe History", width="stretch"):
                    if not target_to_clear:
                        st.error("Choose a target first.")
                    else:
                        removed_count, _ = clear_history_for_target(target_to_clear)
                        cached_load_history.clear()
                        st.success(f"Removed {removed_count} recipe(s) for {target_to_clear}.")
                        st.rerun()

            st.divider()

            for target_name, entries in grouped_history(recipe_history).items():
                target_df = history_dataframe(entries)
                with st.expander(f"{target_name} ({len(entries)})", expanded=False):
                    display_dataframe(target_df, theme_mode, width="stretch", hide_index=True)

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
            people = list(grouped_target_density_history(target_density_records).keys())
            cleanup_col, action_col = st.columns([1.25, 0.75], gap="large")
            with cleanup_col:
                person_to_clear = st.selectbox(
                    "Person target log to clear",
                    [""] + people,
                    format_func=lambda value: value or "Choose person",
                )
            with action_col:
                st.write("")
                st.write("")
                if st.button("Clear Person Target Log", width="stretch"):
                    if not person_to_clear:
                        st.error("Choose a person first.")
                    else:
                        removed_count, _ = clear_target_density_history_for_person(person_to_clear)
                        cached_load_history.clear()
                        st.success(f"Removed {removed_count} target-density record(s) for {person_to_clear}.")
                        st.rerun()

            st.divider()

            for person, entries in grouped_target_density_history(target_density_records).items():
                person_df = target_density_dataframe(entries)
                with st.expander(f"{person} ({len(entries)} target{'s' if len(entries) != 1 else ''})", expanded=True):
                    display_dataframe(person_df, theme_mode, width="stretch", hide_index=True)

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
