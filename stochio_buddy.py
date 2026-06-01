import base64
import html
import hashlib
from datetime import datetime
from pathlib import Path

import streamlit as st

try:
    from PIL import Image
except ImportError:
    Image = None

from stoichio.app_context import AppContext
from stoichio.app_utils import (
    csv_bytes,
    recipe_input_signature,
    target_density_signature,
    truthy_secret,
    widget_key,
)
from stoichio.backup_data import restore_backup_data
from stoichio.backup_export import backup_counts, data_backup_json, parse_backup_upload
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
from stoichio.config import DATA_CACHE_TTL_SECONDS, LOW_STOCK_THRESHOLD_G
from stoichio.density_records import (
    delete_material_density,
    load_material_densities,
    related_material_density_records,
    set_preferred_material_density,
    update_material_density_review_status,
    upsert_material_density,
)
from stoichio.density_ui import density_source_control, lattice_parameter_inputs
from stoichio.history import (
    clear_history_for_target,
    clear_history_for_target_id,
    clear_target_density_history_for_person,
    delete_history_entry,
    format_target_id,
    load_history,
    log_synthesis,
    log_target_density,
)
from stoichio.inventory import (
    check_stock,
    consume_stock,
    load_inventory,
    load_inventory_log,
    set_inventory_quantity,
)
from stoichio.powders import (
    add_powder,
    delete_powder,
    load_powders,
    normalize_powder,
    powder_display_name,
    relevant_powders_for_target,
    sync_powders_from_msds_inventory,
    update_powder_notes,
)
from stoichio.lab_reports import (
    recipe_lab_summary,
    recipe_report_html,
    safe_filename,
    target_density_lab_summary,
    target_traceability_report_html,
)
from stoichio.powder_sets import (
    delete_powder_set,
    load_powder_sets,
    matching_powder_sets_for_target,
    record_powder_set_use,
    save_powder_set,
)
from stoichio.storage import (
    configure_apps_script,
    configure_google_sheets,
    storage_error,
    storage_label,
)
from stoichio.ui_pages import (
    history as history_page,
    material_density as material_density_page,
    powder_mass as powder_mass_page,
    powders_inventory as powders_inventory_page,
    target_density as target_density_page,
)
from stoichio.theme import theme_colors
from stoichio.ui_components import display_dataframe
from stoichio.ui_models import (
    database_dataframe,
    density_record_is_blocked,
    density_record_is_verified,
    density_record_label,
    density_record_sort_key,
    density_trust_status,
    filter_target_lifecycle_groups,
    format_history_time,
    grouped_history,
    grouped_target_density_history,
    history_dataframe,
    inventory_dataframe,
    inventory_log_dataframe,
    known_recipe_height_check_dataframe,
    linked_recipe_target_label,
    linked_recipe_targets,
    lookup_known_density,
    mass_basis_label,
    material_density_dataframe,
    next_target_number,
    recipe_balance_dataframe,
    recipe_basis_audit_dataframe,
    recipe_calculation_metadata,
    recipe_coefficients_dataframe,
    recipe_dataframe,
    recipe_history_summary,
    recipe_link_snapshot,
    recipe_mass_basis,
    recipe_powder_basis,
    recipe_validation_warnings,
    stock_row_class,
    synthesis_history,
    target_density_dataframe,
    target_density_history,
    target_density_history_summary,
    target_lifecycle_dataframe,
    target_lifecycle_groups,
    target_lifecycle_status,
    target_lifecycle_summary,
    unknown_inventory_items,
)
from stoichio.chemistry.stoich_engine import (
    MASS_BASIS_TARGET_FORMULA,
    MASS_BASIS_TOTAL_PRECURSOR,
    compute_recipe,
    infer_target_mass_from_recipe,
)


APP_DIR = Path(__file__).resolve().parent
APP_LOGO_PATHS = (
    APP_DIR / "assets" / "stoichio_logo_header.png",
    APP_DIR / "stochio logo.png",
    APP_DIR / "stoichio logo.png",
)
APP_ICON_PATHS = (
    APP_DIR / "assets" / "stoichio_icon_app.png",
    APP_DIR / "stoichio icon.png",
    APP_DIR / "stochio icon.png",
)


def first_existing_asset(paths):
    for path in paths:
        if path.exists():
            return path
    return None


APP_LOGO_PATH = first_existing_asset(APP_LOGO_PATHS)
APP_ICON_PATH = first_existing_asset(APP_ICON_PATHS)


def load_page_icon():
    if Image is not None and APP_ICON_PATH:
        try:
            return Image.open(APP_ICON_PATH)
        except OSError:
            pass
    return ":material/science:"


def image_data_uri(path):
    if not path:
        return ""
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/png;base64,{encoded}"


st.set_page_config(
    page_title="Stoichio Buddy",
    page_icon=load_page_icon(),
    layout="wide",
    initial_sidebar_state="expanded",
)


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

    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        margin: 0.15rem 0 0.9rem;
    }

    .sidebar-brand img {
        width: 42px;
        height: 42px;
        object-fit: cover;
        border-radius: 10px;
        flex: 0 0 auto;
    }

    .sidebar-brand span {
        color: var(--sb-text);
        font-size: 1.05rem;
        font-weight: 760;
        line-height: 1.1;
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

    .brand-header {
        margin: 0.05rem 0 0.45rem;
        max-width: 760px;
    }

    .brand-logo {
        display: block;
        width: min(620px, 100%);
        height: auto;
        object-fit: contain;
        border-radius: 0;
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

    @media (max-width: 700px) {
        .brand-logo {
            width: 100%;
        }
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

    .sb-table th.sb-cell-full,
    .sb-table td.sb-cell-full {
        min-width: 260px;
        max-width: none;
        white-space: nowrap;
        overflow-wrap: normal;
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

    .sb-table td.sb-cell-full .sb-cell-content {
        display: block;
        max-height: none;
        overflow: visible;
        -webkit-line-clamp: unset;
    }

    .sb-table td.sb-cell-full a {
        white-space: nowrap;
        overflow-wrap: normal;
    }

    .sb-table td.sb-cell-wrap a {
        overflow-wrap: anywhere;
    }

    .sb-table td:first-child,
    .sb-table th:first-child {
        padding-left: 1rem;
    }

    .sb-table td:last-child,
    .sb-table th:last-child {
        padding-right: 1rem;
    }

    .sb-table tr:last-child td {
        border-bottom: 0;
    }

    .sb-table tr.stock-low td {
        background: color-mix(in srgb, var(--sb-accent) 18%, var(--sb-table-bg)) !important;
    }

    .sb-table tr.stock-short td,
    .sb-table tr.stock-empty td,
    .sb-table tr.stock-missing td {
        background: color-mix(in srgb, #d64a4a 22%, var(--sb-table-bg)) !important;
    }

    .sb-table tr.codex-seeded td {
        background: color-mix(in srgb, #2f80ed 18%, var(--sb-table-bg)) !important;
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


def render_sidebar_brand():
    icon_uri = image_data_uri(APP_ICON_PATH)
    if not icon_uri:
        st.markdown("### Stoichio Buddy")
        return

    st.markdown(
        f"""
        <div class="sidebar-brand">
            <img src="{icon_uri}" alt="Stoichio Buddy icon">
            <span>Stoichio Buddy</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_app_brand():
    logo_uri = image_data_uri(APP_LOGO_PATH)
    st.markdown('<div class="app-kicker">Solid-state synthesis</div>', unsafe_allow_html=True)
    if logo_uri:
        st.markdown(
            f"""
            <div class="brand-header">
                <img class="brand-logo" src="{logo_uri}" alt="Stoichio Buddy">
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="app-title">Stoichio Buddy</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">Cation-first precursor mass calculator with powder database and recipe history.</div>',
        unsafe_allow_html=True,
    )


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
    render_sidebar_brand()
    theme_mode = st.radio("Appearance", ["Dark", "Light"], horizontal=True, key="theme_mode")
    page = st.radio(
        "Navigation",
        [
            "Powder Mass Calculation",
            "Target Density %",
            "Powder Database",
            "Theoretical Density",
            "History",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.metric("Powders", len(db))
    st.metric("Theoretical densities", len(material_densities))
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

apply_theme(theme_mode)

render_app_brand()

if storage_problem:
    st.warning(
        "Google Sheets storage did not connect. Check the Apps Script web app URL, deployment access, "
        f"and token. Details: {storage_problem}"
    )


PAGE_RENDERERS = {
    "Powder Mass Calculation": powder_mass_page,
    "Target Density %": target_density_page,
    "Powder Database": powders_inventory_page,
    "Theoretical Density": material_density_page,
    "History": history_page,
}

page_context = AppContext(
    **{
        name: value
        for name, value in globals().items()
        if not name.startswith("__")
    }
)
PAGE_RENDERERS[page].render(page_context)
