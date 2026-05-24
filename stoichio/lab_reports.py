"""Printable reports and lab-summary text builders."""

import html
from datetime import datetime

from stoichio.chemistry.density_engine import DEFAULT_DIE_DIAMETER_MM
from stoichio.chemistry.stoich_engine import MASS_BASIS_TARGET_FORMULA
from stoichio.ui_models import (
    format_history_time,
    mass_basis_label,
    recipe_mass_basis,
    recipe_powder_basis,
    target_lifecycle_status,
)


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
