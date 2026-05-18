import json
import html
from collections import defaultdict
from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

from formula_parser import normalize_formula
from lab_manager import (
    add_powder,
    check_stock,
    clear_history_for_target,
    configure_apps_script,
    configure_google_sheets,
    consume_stock,
    delete_powder,
    load_history,
    load_inventory,
    load_powders,
    log_synthesis,
    set_inventory_quantity,
    storage_label,
)
from stoich_engine import compute_recipe


st.set_page_config(page_title="Stoichio Buddy", page_icon=":material/science:", layout="wide")


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


def load_app_state():
    st.session_state.db = load_powders()
    st.session_state.inventory = load_inventory()
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


def grouped_history(history):
    groups = defaultdict(list)
    for entry in history:
        target = entry.get("target") or "Unknown target"
        groups[target].append(entry)
    return dict(sorted(groups.items(), key=lambda item: item[0]))


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


def configure_app_storage():
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
db, inventory = load_app_state()
history = load_history()

with st.sidebar:
    st.markdown("### Stoichio Buddy")
    theme_mode = st.radio("Appearance", ["Dark", "Light"], horizontal=True, key="theme_mode")
    page = st.radio(
        "Navigation",
        ["Calculate", "Powders & Inventory", "History"],
        label_visibility="collapsed",
    )

    st.divider()
    st.metric("Powders", len(db))
    unknown_stock = unknown_inventory_items(inventory, db)
    st.metric("Inventory items", len(inventory))
    st.metric("Saved recipes", len(history))

    st.caption("Selected powders are always controlled by the user. The app never searches or swaps precursors automatically.")
    st.caption(f"Storage: {storage_status}")
    if unknown_stock:
        st.warning("Inventory has entries that are not in the powder database: " + ", ".join(unknown_stock))

apply_theme(theme_mode)

st.markdown('<div class="app-kicker">Solid-state synthesis</div>', unsafe_allow_html=True)
st.markdown('<div class="app-title">Stoichio Buddy</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Cation-first precursor mass calculator with powder inventory and recipe history.</div>',
    unsafe_allow_html=True,
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
        mass = st.number_input(
            "Target formula mass (g)",
            min_value=0.0,
            value=15.6,
            step=0.1,
            format="%.4f",
            help="This is the intended formula batch basis. Total precursor powder can be higher.",
        )
        selected = st.multiselect(
            "Selected powders",
            list(db.keys()),
            help="Only these powders will be used in the calculation.",
        )
        deduct_inventory = st.checkbox("Deduct from inventory after solving")

        solve = st.button("Calculate Recipe", type="primary", width="stretch")

    with right:
        st.subheader("Result")

        if not solve:
            st.info("Enter a target formula, mass, and selected powders, then calculate.")
            if db:
                display_dataframe(database_dataframe(db), theme_mode, width="stretch", hide_index=True)
        else:
            result = compute_recipe(target, mass, db, selected)

            if result is None or result.get("recipe") is None:
                st.error(result.get("warning", "No valid solution found") if result else "No valid solution found")
            else:
                recipe_masses = result["recipe"]
                recipe_df = recipe_dataframe(recipe_masses)
                total_powder = sum(recipe_masses.values())

                metric_cols = st.columns(3)
                metric_cols[0].metric("Target basis (g)", round(mass, 3))
                metric_cols[1].metric("Precursor powder (g)", round(total_powder, 3))
                metric_cols[2].metric("Powders used", len(recipe_masses))

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

                current_inventory = load_inventory()
                in_stock, stock_messages = check_stock(current_inventory, recipe_masses)
                if stock_messages:
                    st.warning("Inventory warning: " + "; ".join(stock_messages))

                inventory_deducted = False
                if deduct_inventory:
                    if in_stock:
                        st.session_state.inventory = consume_stock(current_inventory, recipe_masses)
                        inventory_deducted = True
                        st.success("Inventory deducted.")
                    else:
                        st.warning("Inventory was not deducted because stock is insufficient.")

                log_synthesis(
                    normalize_formula(target),
                    mass,
                    recipe_masses,
                    selected_powders=selected,
                    warning=result.get("warning"),
                    inventory_deducted=inventory_deducted,
                )


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
                st.session_state.db = powders
                st.session_state.inventory = load_inventory()
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
                updated_inventory = set_inventory_quantity(powder, grams)
                st.session_state.inventory = updated_inventory
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
                st.session_state.db = delete_powder(powder_to_delete, remove_inventory=remove_deleted_stock)
                st.session_state.inventory = load_inventory()
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


elif page == "History":
    st.subheader("Recipe history")

    history_df = history_dataframe(history)
    if history_df.empty:
        st.info("No saved recipes yet.")
    else:
        target_names = list(grouped_history(history).keys())
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
            if st.button("Clear Target History", width="stretch"):
                if not target_to_clear:
                    st.error("Choose a target first.")
                else:
                    removed_count, _ = clear_history_for_target(target_to_clear)
                    st.success(f"Removed {removed_count} recipe(s) for {target_to_clear}.")
                    st.rerun()

        st.divider()

        for target_name, entries in grouped_history(history).items():
            target_df = history_dataframe(entries)
            with st.expander(f"{target_name} ({len(entries)})", expanded=False):
                display_dataframe(target_df, theme_mode, width="stretch", hide_index=True)

        st.download_button(
            "Download Full History CSV",
            data=csv_bytes(history_df),
            file_name="stoichio_history.csv",
            mime="text/csv",
            width="stretch",
        )

        with st.expander("Raw history"):
            for entry in reversed(history):
                st.json(entry)
