"""Data backup export/import helpers."""

import json
from datetime import datetime

from stoichio.backup_data import validate_backup_data


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
