"""View-model and dataframe helpers for Stoichio Buddy UI pages."""

import json
from collections import defaultdict
from datetime import datetime

import pandas as pd

from stoichio.config import LOW_STOCK_THRESHOLD_G
from stoichio.chemistry.density_engine import DEFAULT_DIE_DIAMETER_MM
from stoichio.chemistry.formula_parser import normalize_formula, parse_formula
from stoichio.chemistry.stoich_engine import MASS_BASIS_TARGET_FORMULA, MASS_BASIS_TOTAL_PRECURSOR
from stoichio.powders import normalize_powder, powder_display_name


def recipe_dataframe(recipe_masses, inventory=None):
    rows = []
    for powder, grams in recipe_masses.items():
        row = {
            "Powder": powder_display_name(powder),
            "Mass (g)": round(grams, 3),
            "Exact mass (g)": grams,
        }

        if inventory is not None:
            available = inventory.get(normalize_powder(powder))
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
                "Powder": powder_display_name(powder, record),
                "Formula": record.get("formula", powder),
                "Purity": record.get("purity", ""),
                "Vendor": record.get("company") or record.get("supplier", ""),
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
        normalize_powder(powder): grams
        for powder, grams in recipe_masses.items()
    }

    for powder, grams in inventory.items():
        required = normalized_requirements.get(normalize_powder(powder), 0.0)
        remaining = grams - required

        if required > grams:
            status = f"Short for recipe by {abs(remaining):.3f} g"
        elif grams < LOW_STOCK_THRESHOLD_G:
            status = f"Low stock (<{LOW_STOCK_THRESHOLD_G:g} g)"
        else:
            status = "OK"

        row = {
            "Powder": powder_display_name(powder),
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
        "Paper title",
        "DOI",
        "COD ID",
        "Source URL",
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
                "Paper title": record.get("paper_title", ""),
                "DOI": record.get("doi", ""),
                "COD ID": record.get("cod_id", ""),
                "Source URL": record.get("source_url", ""),
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


def stock_row_class(row):
    status = str(row.get("Stock status", row.get("Status", ""))).lower()
    if "not in inventory" in status:
        return "stock-missing"
    if "short" in status:
        return "stock-short"
    if "low" in status:
        return "stock-low"
    return ""


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
