"""Powder database, powder variants, and target-relevance helpers."""

import re

from stoichio.chemistry.formula_parser import molar_mass, normalize_formula, parse_formula
from stoichio import storage

POWDER_RELEVANCE_IGNORED_ELEMENTS = {"O", "H", "C", "N"}
POWDER_VARIANT_SEPARATOR = " | "
POWDER_METADATA_FIELDS = (
    "formula",
    "casNumber",
    "purity",
    "company",
    "supplier",
    "identityStatus",
    "source",
    "casSource",
    "casSourceUrl",
    "pubchemCid",
    "pubchemFormula",
    "pubchemIupacName",
    "pubchemTitle",
    "notes",
    "msdsInventoryItemId",
)


def clean_metadata_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def clean_metadata_for_key(value):
    text = clean_metadata_text(value)
    text = text.replace("/", "-").replace("\\", "-")
    return text


def normalize_purity_label(value):
    text = clean_metadata_text(value)
    if not text:
        return ""
    numeric = re.fullmatch(r"(\d+(?:\.\d+)?)", text)
    if numeric:
        return f"{numeric.group(1)}%"
    return text


def powder_formula_from_key(powder):
    text = str(powder or "").strip()
    formula = text.split(POWDER_VARIANT_SEPARATOR, 1)[0].strip()
    return normalize_formula(formula)


def powder_key_for(formula, purity="", company=""):
    key_formula = normalize_formula(formula)
    parts = [key_formula]
    purity_label = clean_metadata_for_key(normalize_purity_label(purity))
    company_label = clean_metadata_for_key(company)
    if purity_label:
        parts.append(f"purity {purity_label}")
    if company_label:
        parts.append(f"vendor {company_label}")
    return POWDER_VARIANT_SEPARATOR.join(parts)


def normalize_powder(name):
    text = str(name or "").strip()
    if POWDER_VARIANT_SEPARATOR in text:
        formula, *metadata = [part.strip() for part in text.split(POWDER_VARIANT_SEPARATOR)]
        parts = [normalize_formula(formula)] + [clean_metadata_for_key(part) for part in metadata if part]
        return POWDER_VARIANT_SEPARATOR.join(parts)
    return normalize_formula(text)


def powder_display_name(powder, record=None):
    record = record or {}
    formula = record.get("formula") or powder_formula_from_key(powder)
    parts = [formula]
    purity = normalize_purity_label(record.get("purity"))
    company = clean_metadata_text(record.get("company") or record.get("supplier"))
    if purity:
        parts.append(purity)
    if company:
        parts.append(company)
    if len(parts) > 1:
        return " | ".join(parts)
    return powder


def formula_cation_elements(formula):
    composition = parse_formula(normalize_formula(formula))
    return {element for element in composition if element != "O"}


def powder_relevance_elements(composition):
    return {
        element
        for element, amount in composition.items()
        if float(amount) != 0.0 and element not in POWDER_RELEVANCE_IGNORED_ELEMENTS
    }


def relevant_powders_for_target(target, powders):
    powder_names = list(powders.keys())
    if not str(target or "").strip():
        return powder_names, [], set(), None

    try:
        target_elements = powder_relevance_elements(parse_formula(normalize_formula(target)))
    except ValueError as exc:
        return powder_names, [], set(), str(exc)

    if not target_elements:
        return powder_names, [], target_elements, None

    relevant = []
    hidden = []
    for powder, record in powders.items():
        powder_elements = powder_relevance_elements(record.get("elements", {}))
        if powder_elements and powder_elements <= target_elements and powder_elements & target_elements:
            relevant.append(powder)
        else:
            hidden.append(powder)

    return relevant, hidden, target_elements, None


def default_powders():
    powders = {}
    for formula in ("Fe2O3", "TiO2"):
        composition = parse_formula(formula)
        powders[normalize_formula(formula)] = {
            "formula": normalize_formula(formula),
            "molar_mass": molar_mass(composition),
            "elements": composition,
        }
    return powders


def normalize_powder_record(record, fallback_formula=None):
    raw_formula = record.get("formula") or fallback_formula
    formula = normalize_formula(raw_formula) if raw_formula else ""
    if record.get("elements"):
        elements = {element: float(amount) for element, amount in record.get("elements", {}).items()}
    else:
        elements = parse_formula(formula)
    normalized = {
        "molar_mass": molar_mass(elements),
        "elements": elements,
    }
    if formula:
        normalized["formula"] = formula
    cas_number = str(record.get("casNumber") or record.get("cas") or "").strip()
    if cas_number:
        normalized["casNumber"] = cas_number
    for field in POWDER_METADATA_FIELDS:
        if field == "casNumber":
            continue
        value = record.get(field)
        if value is not None and str(value).strip():
            normalized[field] = value if isinstance(value, (int, float)) else str(value).strip()
    return normalized


def load_powders():
    powders = storage.load_json(storage.POWDERS_FILE, None)
    if powders is None:
        powders = default_powders()
        save_powders(powders)
        return powders

    normalized = {}
    for name, record in powders.items():
        key = normalize_powder(name)
        normalized[key] = normalize_powder_record(record, fallback_formula=powder_formula_from_key(key))
    if normalized != powders:
        save_powders(normalized)
    return normalized


def save_powders(powders):
    storage.save_json(storage.POWDERS_FILE, powders)


def add_powder(formula, purity="", company="", cas_number="", notes=""):
    powders = load_powders()
    key = powder_key_for(formula, purity=purity, company=company)
    formula_key = powder_formula_from_key(key)
    composition = parse_formula(formula_key)
    existing = dict(powders.get(key, {}))
    powders[key] = {
        **existing,
        "formula": formula_key,
        "molar_mass": molar_mass(composition),
        "elements": composition,
    }
    purity_label = normalize_purity_label(purity)
    company_label = clean_metadata_text(company)
    if purity_label:
        powders[key]["purity"] = purity_label
    if company_label:
        powders[key]["company"] = company_label
    if cas_number:
        powders[key]["casNumber"] = str(cas_number).strip()
    elif not powders[key].get("casNumber"):
        for record in powders.values():
            if record.get("formula") == formula_key and record.get("casNumber"):
                for field in (
                    "casNumber",
                    "identityStatus",
                    "casSource",
                    "casSourceUrl",
                    "pubchemCid",
                    "pubchemFormula",
                    "pubchemIupacName",
                ):
                    if record.get(field):
                        powders[key][field] = record[field]
                break
    if notes is not None:
        note_text = str(notes or "").strip()
        if note_text:
            powders[key]["notes"] = note_text
        else:
            powders[key].pop("notes", None)
    save_powders(powders)
    return key, powders


def update_powder_notes(powder, notes=""):
    powders = load_powders()
    key = normalize_powder(powder)
    if key not in powders:
        raise ValueError(f"Powder not found: {key}")
    note_text = str(notes or "").strip()
    if note_text:
        powders[key]["notes"] = note_text
    else:
        powders[key].pop("notes", None)
    save_powders(powders)
    return key, powders


def sync_powders_from_msds_inventory(items=None):
    if items is None:
        from stoichio.msds_inventory import load_msds_inventory

        items = load_msds_inventory(include_file_data=False)

    powders = load_powders()
    created = 0
    updated = 0
    skipped = 0

    for item in items:
        if int(item.get("closetNumber") or 1) != 1:
            continue

        formula = _formula_from_msds_item(item)
        if not formula:
            skipped += 1
            continue

        purity = item.get("purity", "")
        company = item.get("company", "")
        key = powder_key_for(formula, purity=purity, company=company)
        composition = parse_formula(powder_formula_from_key(key))
        existing = dict(powders.get(key, {}))
        record = {
            **existing,
            "formula": powder_formula_from_key(key),
            "molar_mass": molar_mass(composition),
            "elements": composition,
        }

        metadata_updates = _powder_metadata_from_msds_item(item)
        for field, value in metadata_updates.items():
            if value:
                record[field] = value

        if key in powders:
            if powders[key] != record:
                updated += 1
        else:
            created += 1
        powders[key] = record

    if created or updated:
        save_powders(powders)
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "powders": powders,
    }


def _formula_from_msds_item(item):
    candidates = []
    source_id = str(item.get("sourcePowderId") or item.get("id") or "").strip()
    if source_id.startswith("powder:"):
        candidates.append(source_id.split("powder:", 1)[1])
    candidates.extend([
        item.get("nameOrFormula", ""),
        item.get("pubchemFormula", ""),
    ])

    for candidate in candidates:
        try:
            formula = normalize_formula(candidate)
            parse_formula(formula)
            return formula
        except ValueError:
            continue
    return ""


def _powder_metadata_from_msds_item(item):
    metadata = {
        "purity": normalize_purity_label(item.get("purity", "")),
        "company": clean_metadata_text(item.get("company", "")),
        "casNumber": clean_metadata_text(item.get("casNumber", "")),
        "identityStatus": clean_metadata_text(item.get("identityStatus", "")),
        "source": "MSDS inventory",
        "casSource": clean_metadata_text(item.get("casSource", "")),
        "casSourceUrl": clean_metadata_text(item.get("casSourceUrl", "")),
        "pubchemCid": clean_metadata_text(item.get("pubchemCid", "")),
        "pubchemFormula": clean_metadata_text(item.get("pubchemFormula", "")),
        "pubchemIupacName": clean_metadata_text(item.get("pubchemIupacName", "")),
        "pubchemTitle": clean_metadata_text(item.get("pubchemTitle", "")),
        "msdsInventoryItemId": clean_metadata_text(item.get("id", "")),
    }
    return {field: value for field, value in metadata.items() if value}


def delete_powder(powder, remove_inventory=True):
    from stoichio.inventory import load_inventory, log_inventory_transaction, save_inventory

    powders = load_powders()
    key = normalize_powder(powder)

    if key not in powders:
        raise ValueError(f"Powder not found: {key}")

    powders.pop(key)
    save_powders(powders)

    if remove_inventory:
        inventory = load_inventory()
        before = inventory.pop(key, None)
        save_inventory(inventory)
        if before is not None:
            log_inventory_transaction(
                key,
                -float(before),
                before_g=float(before),
                after_g=0.0,
                action="delete powder",
                reason="Powder deleted from database",
            )

    return powders
