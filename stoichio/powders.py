"""Powder database and target-relevance helpers."""

from stoichio.chemistry.formula_parser import molar_mass, normalize_formula, parse_formula
from stoichio import storage

POWDER_RELEVANCE_IGNORED_ELEMENTS = {"O", "H", "C", "N"}
POWDER_METADATA_FIELDS = (
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
)


def normalize_powder(name):
    return normalize_formula(name)


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
            "molar_mass": molar_mass(composition),
            "elements": composition,
        }
    return powders


def normalize_powder_record(record):
    elements = {element: float(amount) for element, amount in record.get("elements", {}).items()}
    normalized = {
        "molar_mass": molar_mass(elements),
        "elements": elements,
    }
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
        normalized[key] = normalize_powder_record(record)
    if normalized != powders:
        save_powders(normalized)
    return normalized


def save_powders(powders):
    storage.save_json(storage.POWDERS_FILE, powders)


def add_powder(formula):
    powders = load_powders()
    key = normalize_formula(formula)
    composition = parse_formula(key)
    powders[key] = {
        "molar_mass": molar_mass(composition),
        "elements": composition,
    }
    save_powders(powders)
    return key, powders


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
