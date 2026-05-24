"""Synthesis and target-density history helpers."""

import datetime
import re
import uuid

from stoichio import storage


def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _history_name_code(value, fallback):
    cleaned = "".join(character for character in str(value or "").strip() if character.isalnum())
    return cleaned[:24] or fallback


def _next_unused_number(used_numbers):
    number = max(used_numbers, default=0) + 1
    while number in used_numbers:
        number += 1
    return number


def format_recipe_id(recipe_number):
    number = _positive_int(recipe_number) or 1
    return f"R{number:03d}"


def format_target_id(target_for, target_number):
    number = _positive_int(target_number) or 1
    return f"{_history_name_code(target_for, 'Target')}-T{number:03d}"


def _recipe_number_from_entry(entry):
    number = _positive_int(entry.get("recipe_number"))
    if number is not None:
        return number

    recipe_id = str(entry.get("recipe_id", ""))
    match = re.fullmatch(r"R0*(\d+)", recipe_id, flags=re.IGNORECASE)
    if match:
        return _positive_int(match.group(1))
    return None


def _target_number_from_entry(entry):
    number = _positive_int(entry.get("target_number"))
    if number is not None:
        return number

    target_id = str(entry.get("target_id", ""))
    match = re.search(r"-T0*(\d+)$", target_id, flags=re.IGNORECASE)
    if match:
        return _positive_int(match.group(1))
    return None


def next_recipe_number(history):
    used_numbers = {
        number
        for entry in history
        if isinstance(entry, dict) and history_entry_type(entry) == "synthesis"
        for number in [_recipe_number_from_entry(entry)]
        if number is not None
    }
    return _next_unused_number(used_numbers)


def next_target_number(history, target_for):
    person = str(target_for).strip()
    if not person:
        return 1

    used_numbers = {
        number
        for entry in history
        if isinstance(entry, dict) and str(entry.get("target_for", "")).strip() == person
        for number in [_target_number_from_entry(entry)]
        if number is not None
    }
    return _next_unused_number(used_numbers)


def load_history():
    history = storage.load_json(storage.HISTORY_FILE, [])
    if not isinstance(history, list):
        return []

    changed = False
    used_recipe_numbers = {
        number
        for entry in history
        if isinstance(entry, dict) and history_entry_type(entry) == "synthesis"
        for number in [_recipe_number_from_entry(entry)]
        if number is not None
    }
    used_target_numbers = {}

    for entry in history:
        if not isinstance(entry, dict):
            continue
        person = str(entry.get("target_for", "")).strip()
        if not person:
            continue
        number = _target_number_from_entry(entry)
        if number is not None:
            used_target_numbers.setdefault(person, set()).add(number)

    for entry in history:
        if not isinstance(entry, dict):
            continue

        if not entry.get("entry_id"):
            entry["entry_id"] = uuid.uuid4().hex
            changed = True

        entry_type = history_entry_type(entry)
        if entry_type == "synthesis":
            recipe_number = _recipe_number_from_entry(entry)
            if recipe_number is None:
                recipe_number = _next_unused_number(used_recipe_numbers)
                used_recipe_numbers.add(recipe_number)
                entry["recipe_number"] = recipe_number
                entry["recipe_id"] = format_recipe_id(recipe_number)
                changed = True
            else:
                used_recipe_numbers.add(recipe_number)
                if entry.get("recipe_number") != recipe_number:
                    entry["recipe_number"] = recipe_number
                    changed = True
                if not entry.get("recipe_id"):
                    entry["recipe_id"] = format_recipe_id(recipe_number)
                    changed = True

            person = str(entry.get("target_for", "")).strip()
            if person:
                used_for_person = used_target_numbers.setdefault(person, set())
                target_number = _target_number_from_entry(entry)

                if target_number is None:
                    target_number = _next_unused_number(used_for_person)
                    used_for_person.add(target_number)
                    entry["target_number"] = target_number
                    entry["target_id"] = format_target_id(person, target_number)
                    changed = True
                else:
                    used_for_person.add(target_number)
                    if entry.get("target_number") != target_number:
                        entry["target_number"] = target_number
                        changed = True
                    if not entry.get("target_id"):
                        entry["target_id"] = format_target_id(person, target_number)
                        changed = True

        if entry_type == "target_density":
            person = str(entry.get("target_for", "")).strip()
            target_number = _target_number_from_entry(entry)
            if not person:
                if target_number is not None and entry.get("target_number") != target_number:
                    entry["target_number"] = target_number
                    changed = True
                continue

            used_for_person = used_target_numbers.setdefault(person, set())

            if target_number is None:
                target_number = _next_unused_number(used_for_person)
                used_for_person.add(target_number)
                entry["target_number"] = target_number
                entry["target_id"] = format_target_id(person, target_number)
                changed = True
            else:
                used_for_person.add(target_number)
                if entry.get("target_number") != target_number:
                    entry["target_number"] = target_number
                    changed = True
                if not entry.get("target_id"):
                    entry["target_id"] = format_target_id(person, target_number)
                    changed = True

    if changed:
        save_history(history)

    return history


def save_history(history):
    storage.save_json(storage.HISTORY_FILE, history)


def history_entry_type(entry):
    return entry.get("entry_type", "synthesis")


def clear_history_for_target(target):
    history = load_history()
    remaining = [
        entry
        for entry in history
        if not (history_entry_type(entry) == "synthesis" and entry.get("target") == target)
    ]
    removed_count = len(history) - len(remaining)
    save_history(remaining)
    return removed_count, remaining


def delete_history_entry(entry_id):
    history = load_history()
    entry_key = str(entry_id)
    remaining = [
        entry
        for entry in history
        if str(entry.get("entry_id", "")) != entry_key
    ]
    removed_count = len(history) - len(remaining)
    if removed_count:
        save_history(remaining)
    return removed_count, remaining


def clear_target_density_history_for_person(target_for):
    history = load_history()
    person = str(target_for).strip()
    remaining = [
        entry
        for entry in history
        if not (
            history_entry_type(entry) == "target_density"
            and str(entry.get("target_for", "")).strip() == person
        )
    ]
    removed_count = len(history) - len(remaining)
    save_history(remaining)
    return removed_count, remaining


def clear_history_for_target_id(target_id):
    history = load_history()
    target_key = str(target_id).strip()
    remaining = [
        entry
        for entry in history
        if str(entry.get("target_id", "")).strip() != target_key
    ]
    removed_count = len(history) - len(remaining)
    if removed_count:
        save_history(remaining)
    return removed_count, remaining


def log_synthesis(
    target,
    mass,
    recipe,
    selected_powders=None,
    warning=None,
    inventory_deducted=False,
    notes=None,
    target_for=None,
    target_number=None,
    target_id=None,
    calculation=None,
):
    history = load_history()
    recipe_number = next_recipe_number(history)
    target_for = str(target_for or "").strip()
    if target_for:
        target_number = int(target_number or next_target_number(history, target_for))
        target_id = target_id or format_target_id(target_for, target_number)

    entry = {
        "entry_id": uuid.uuid4().hex,
        "entry_type": "synthesis",
        "recipe_id": format_recipe_id(recipe_number),
        "recipe_number": recipe_number,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "target": target,
        "mass": mass,
        "selected_powders": selected_powders or [],
        "recipe": recipe,
        "warning": warning,
        "inventory_deducted": inventory_deducted,
        "notes": str(notes or "").strip(),
    }
    if calculation:
        entry["calculation"] = calculation
    if target_for:
        entry.update(
            {
                "target_id": target_id,
                "target_number": target_number,
                "target_for": target_for,
            }
        )

    history.append(entry)
    save_history(history)
    return history


def log_target_density(
    target,
    target_number,
    target_for,
    measured_density,
    theoretical_density,
    relative_density,
    final_volume,
    final_mass,
    final_diameter,
    final_height,
    density_source=None,
    notes=None,
    target_id=None,
    linked_recipe=None,
):
    history = load_history()
    target_for = str(target_for or "").strip()
    target_number = _positive_int(target_number)
    target_id = str(target_id or "").strip()

    if target_for and target_number is None:
        target_number = next_target_number(history, target_for)
    if target_for and not target_id:
        target_id = format_target_id(target_for, target_number)

    entry = {
        "entry_id": uuid.uuid4().hex,
        "entry_type": "target_density",
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "target": target,
        "measured_density_g_cm3": float(measured_density),
        "theoretical_density_g_cm3": float(theoretical_density),
        "relative_density_percent": float(relative_density),
        "final_volume_cm3": float(final_volume),
        "final_mass_g": float(final_mass),
        "final_diameter_mm": float(final_diameter),
        "final_height_mm": float(final_height),
        "density_source": density_source or "",
        "notes": str(notes or "").strip(),
    }
    if linked_recipe:
        entry["linked_recipe"] = linked_recipe
    if target_id:
        entry["target_id"] = target_id
    if target_number is not None:
        entry["target_number"] = target_number
    if target_for:
        entry["target_for"] = target_for

    history.append(entry)
    save_history(history)
    return history
