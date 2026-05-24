"""Saved powder-set helpers."""

import datetime
import uuid

from stoichio.chemistry.formula_parser import normalize_formula, parse_formula
from stoichio import storage
from stoichio.powders import normalize_powder, powder_relevance_elements


def powder_family_key(elements):
    return "-".join(sorted(elements))


def powder_set_family_for_target(target):
    if not str(target or "").strip():
        return "", set(), None

    try:
        normalized_target = normalize_formula(target)
        target_elements = powder_relevance_elements(parse_formula(normalized_target))
    except ValueError as exc:
        return "", set(), str(exc)

    if not target_elements:
        return "", target_elements, None
    return powder_family_key(target_elements), target_elements, None


def _unique_normalized_powders(powders):
    normalized = []
    seen = set()
    for powder in powders or []:
        key = normalize_powder(powder)
        if key not in seen:
            normalized.append(key)
            seen.add(key)
    return normalized


def normalize_powder_set_record(record_id, record):
    raw_elements = record.get("target_elements", [])
    target_elements = {
        str(element).strip()
        for element in raw_elements
        if str(element).strip()
    }

    target_formula = str(record.get("target_formula", "")).strip()
    if target_formula:
        try:
            target_formula = normalize_formula(target_formula)
            if not target_elements:
                target_elements = powder_relevance_elements(parse_formula(target_formula))
        except ValueError:
            target_formula = str(record.get("target_formula", "")).strip()

    family = str(record.get("family", "")).strip()
    if not family and target_elements:
        family = powder_family_key(target_elements)

    powders = _unique_normalized_powders(record.get("powders", []))
    name = str(record.get("name", "")).strip()
    if not name:
        name = f"{family or 'General'} powder set"

    created_at = str(record.get("created_at", "")).strip()
    updated_at = str(record.get("updated_at", "")).strip()

    return {
        "record_id": str(record.get("record_id") or record_id or uuid.uuid4().hex),
        "name": name,
        "family": family,
        "target_formula": target_formula,
        "target_elements": sorted(target_elements),
        "powders": powders,
        "notes": str(record.get("notes", "")).strip(),
        "created_at": created_at,
        "updated_at": updated_at,
        "last_used_at": str(record.get("last_used_at", "")).strip(),
        "use_count": int(record.get("use_count", 0) or 0),
    }


def load_powder_sets():
    raw_sets = storage.load_json(storage.POWDER_SETS_FILE, {})
    if not isinstance(raw_sets, dict):
        raw_sets = {}

    powder_sets = {}
    for record_id, record in raw_sets.items():
        if not isinstance(record, dict):
            continue
        normalized = normalize_powder_set_record(record_id, record)
        powder_sets[normalized["record_id"]] = normalized

    if powder_sets != raw_sets:
        save_powder_sets(powder_sets)
    return powder_sets


def save_powder_sets(powder_sets):
    storage.save_json(storage.POWDER_SETS_FILE, powder_sets)


def save_powder_set(target, powders, name="", notes="", record_id=None):
    family, target_elements, error = powder_set_family_for_target(target)
    if error:
        raise ValueError(error)
    if not target_elements:
        raise ValueError("Enter a target formula before saving a powder set")

    selected_powders = _unique_normalized_powders(powders)
    if not selected_powders:
        raise ValueError("Select at least one powder before saving a powder set")

    powder_sets = load_powder_sets()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    record_key = str(record_id or uuid.uuid4().hex)
    existing = powder_sets.get(record_key, {})
    record = {
        "record_id": record_key,
        "name": str(name or "").strip() or f"{family} powder set",
        "family": family,
        "target_formula": normalize_formula(target),
        "target_elements": sorted(target_elements),
        "powders": selected_powders,
        "notes": str(notes or "").strip(),
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "last_used_at": existing.get("last_used_at", ""),
        "use_count": existing.get("use_count", 0),
    }
    normalized = normalize_powder_set_record(record_key, record)
    powder_sets[record_key] = normalized
    save_powder_sets(powder_sets)
    return record_key, powder_sets


def matching_powder_sets_for_target(target, powder_sets):
    family, _, error = powder_set_family_for_target(target)
    if error or not family:
        return []
    matches = [
        (record_id, record)
        for record_id, record in powder_sets.items()
        if record.get("family") == family
    ]
    matches.sort(
        key=lambda item: (
            -int(item[1].get("use_count", 0) or 0),
            item[1].get("name", ""),
            item[0],
        )
    )
    return matches


def record_powder_set_use(record_id):
    powder_sets = load_powder_sets()
    key = str(record_id).strip()
    if key not in powder_sets:
        raise ValueError(f"Powder set not found: {record_id}")

    record = dict(powder_sets[key])
    record["use_count"] = int(record.get("use_count", 0) or 0) + 1
    record["last_used_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    powder_sets[key] = normalize_powder_set_record(key, record)
    save_powder_sets(powder_sets)
    return key, powder_sets


def delete_powder_set(record_id):
    powder_sets = load_powder_sets()
    key = str(record_id).strip()
    if key not in powder_sets:
        raise ValueError(f"Powder set not found: {record_id}")
    powder_sets.pop(key)
    save_powder_sets(powder_sets)
    return powder_sets
