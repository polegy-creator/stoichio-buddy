"""Validation and restore helpers for full app data backups."""

from stoichio.density_records import normalize_density_record, save_material_densities
from stoichio.history import save_history
from stoichio.inventory import save_inventory, save_inventory_log
from stoichio.powder_sets import normalize_powder_set_record, save_powder_sets
from stoichio.powders import normalize_powder, normalize_powder_record, save_powders


def validate_backup_data(backup):
    errors = []
    if not isinstance(backup, dict):
        return ["Backup must be a JSON object"]

    required_sections = ("powders", "inventory", "material_densities", "history")
    for section in required_sections:
        if section not in backup:
            errors.append(f"Missing section: {section}")

    powders = backup.get("powders", {})
    if not isinstance(powders, dict):
        errors.append("powders must be an object")
    else:
        for name, record in powders.items():
            if not isinstance(record, dict):
                errors.append(f"Powder {name} must be an object")
                continue
            try:
                normalize_powder(name)
                normalize_powder_record(record)
            except Exception as exc:
                errors.append(f"Powder {name}: {exc}")

    inventory = backup.get("inventory", {})
    if not isinstance(inventory, dict):
        errors.append("inventory must be an object")
    else:
        for powder, grams in inventory.items():
            try:
                normalize_powder(powder)
                float(grams)
            except Exception as exc:
                errors.append(f"Inventory {powder}: {exc}")

    material_densities = backup.get("material_densities", {})
    if not isinstance(material_densities, dict):
        errors.append("material_densities must be an object")
    else:
        for formula, record in material_densities.items():
            if not isinstance(record, dict):
                errors.append(f"Material density {formula} must be an object")
                continue
            try:
                normalize_density_record(formula, record)
            except Exception as exc:
                errors.append(f"Material density {formula}: {exc}")

    powder_sets = backup.get("powder_sets", {})
    if not isinstance(powder_sets, dict):
        errors.append("powder_sets must be an object")
    else:
        for record_id, record in powder_sets.items():
            if not isinstance(record, dict):
                errors.append(f"Powder set {record_id} must be an object")
                continue
            try:
                normalize_powder_set_record(record_id, record)
            except Exception as exc:
                errors.append(f"Powder set {record_id}: {exc}")

    history = backup.get("history", [])
    if not isinstance(history, list):
        errors.append("history must be a list")
    else:
        for index, entry in enumerate(history, start=1):
            if not isinstance(entry, dict):
                errors.append(f"History entry {index} must be an object")

    inventory_log = backup.get("inventory_log", [])
    if not isinstance(inventory_log, list):
        errors.append("inventory_log must be a list")
    else:
        for index, entry in enumerate(inventory_log, start=1):
            if not isinstance(entry, dict):
                errors.append(f"Inventory log entry {index} must be an object")

    return errors


def restore_backup_data(backup):
    errors = validate_backup_data(backup)
    if errors:
        raise ValueError("; ".join(errors))

    powders = {
        normalize_powder(name): normalize_powder_record(record)
        for name, record in backup.get("powders", {}).items()
    }
    inventory = {
        normalize_powder(powder): float(grams)
        for powder, grams in backup.get("inventory", {}).items()
    }
    material_densities = {}
    for record_key, record in backup.get("material_densities", {}).items():
        normalized_record = normalize_density_record(record_key, record)
        material_densities[normalized_record["record_id"]] = normalized_record
    powder_sets = {}
    for record_id, record in backup.get("powder_sets", {}).items():
        normalized_set = normalize_powder_set_record(record_id, record)
        powder_sets[normalized_set["record_id"]] = normalized_set
    history = [dict(entry) for entry in backup.get("history", [])]
    inventory_log = [dict(entry) for entry in backup.get("inventory_log", [])]

    save_powders(powders)
    save_inventory(inventory)
    save_inventory_log(inventory_log)
    save_material_densities(material_densities)
    save_powder_sets(powder_sets)
    save_history(history)

    return {
        "powders": len(powders),
        "inventory": len(inventory),
        "inventory_log": len(inventory_log),
        "material_densities": len(material_densities),
        "powder_sets": len(powder_sets),
        "history": len(history),
    }
