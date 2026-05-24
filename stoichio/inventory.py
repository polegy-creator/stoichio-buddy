"""Inventory quantities and inventory transaction log helpers."""

import datetime
import uuid

from stoichio.powders import normalize_powder
from stoichio import storage


def load_inventory():
    raw_inventory = storage.load_json(storage.INVENTORY_FILE, {})
    inventory = {}

    for powder, grams in raw_inventory.items():
        try:
            key = normalize_powder(powder)
        except ValueError:
            key = powder.strip()
        inventory[key] = inventory.get(key, 0.0) + float(grams)

    return inventory


def save_inventory(inventory):
    storage.save_json(storage.INVENTORY_FILE, inventory)


def load_inventory_log():
    raw_log = storage.load_json(storage.INVENTORY_LOG_FILE, [])
    if not isinstance(raw_log, list):
        return []
    return [dict(entry) for entry in raw_log if isinstance(entry, dict)]


def save_inventory_log(log_entries):
    storage.save_json(storage.INVENTORY_LOG_FILE, log_entries)


def log_inventory_transaction(
    powder,
    change_g,
    before_g=None,
    after_g=None,
    action="manual update",
    reason="",
    recipe_id="",
    notes="",
):
    key = normalize_powder(powder)
    entry = {
        "entry_id": uuid.uuid4().hex,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "powder": key,
        "change_g": round(float(change_g), 6),
        "before_g": None if before_g is None else round(float(before_g), 6),
        "after_g": None if after_g is None else round(float(after_g), 6),
        "action": str(action or "").strip(),
        "reason": str(reason or "").strip(),
        "recipe_id": str(recipe_id or "").strip(),
        "notes": str(notes or "").strip(),
    }
    log_entries = load_inventory_log()
    log_entries.append(entry)
    save_inventory_log(log_entries)
    return entry


def add_to_inventory(powder, grams):
    inventory = load_inventory()
    key = normalize_powder(powder)
    before = inventory.get(key, 0.0)
    inventory[key] = before + float(grams)

    save_inventory(inventory)
    log_inventory_transaction(
        key,
        float(grams),
        before_g=before,
        after_g=inventory[key],
        action="add inventory",
    )
    return inventory


def set_inventory_quantity(powder, grams, reason="manual quantity set"):
    inventory = load_inventory()
    key = normalize_powder(powder)
    before = inventory.get(key, 0.0)

    if grams <= 0:
        inventory.pop(key, None)
        after = 0.0
    else:
        inventory[key] = float(grams)
        after = float(grams)

    save_inventory(inventory)
    if round(after - before, 6) != 0:
        log_inventory_transaction(
            key,
            after - before,
            before_g=before,
            after_g=after,
            action="set quantity",
            reason=reason,
        )
    return inventory


def check_stock(inventory, recipe):
    missing = []

    for powder, required in recipe.items():
        key = normalize_powder(powder)
        available = inventory.get(key)

        if available is None:
            missing.append(f"{powder} (not in inventory)")
        elif required > available:
            missing.append(f"{powder} (need {required:.3f} g, have {available:.3f} g)")

    return len(missing) == 0, missing


def consume_stock(inventory, recipe, reason="recipe deduction", recipe_id=""):
    transactions = []
    for powder, amount in recipe.items():
        key = normalize_powder(powder)

        if key in inventory:
            before = float(inventory[key])
            inventory[key] -= amount
            if inventory[key] < 0:
                inventory[key] = 0
            transactions.append((key, -float(amount), before, float(inventory[key])))

    save_inventory(inventory)
    for key, change, before, after in transactions:
        log_inventory_transaction(
            key,
            change,
            before_g=before,
            after_g=after,
            action="recipe deduction",
            reason=reason,
            recipe_id=recipe_id,
        )
    return inventory
