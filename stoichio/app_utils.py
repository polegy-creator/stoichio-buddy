"""Small app-level utility helpers."""

import hashlib
from io import StringIO


def widget_key(prefix, value):
    digest = hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def csv_bytes(df):
    buffer = StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()


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
