"""Material-density record storage and review helpers."""

import re

from stoichio.chemistry.formula_parser import normalize_formula, parse_formula
from stoichio import storage

PREFERRED_DENSITY_STATUS = "Preferred for formula"
LAB_CHECKED_DENSITY_STATUS = "Lab checked"
LAB_UNVERIFIED_DENSITY_STATUS = "Lab entry - unverified"
CODEX_UNVERIFIED_DENSITY_STATUS = "Codex seeded - verify before use"
BLOCKED_DENSITY_STATUS = "Do not use"


def material_density_record_key(formula, phase=""):
    formula_key = normalize_formula(formula)
    phase_key = re.sub(r"[^A-Za-z0-9]+", "-", str(phase or "").strip()).strip("-").lower()
    if not phase_key:
        return formula_key
    return f"{formula_key}__{phase_key}"


def first_url(value):
    match = re.search(r"https?://[^\s<>\"]+", str(value or ""))
    return match.group(0) if match else ""


def first_doi(value):
    text = str(value or "").strip()
    doi_match = re.search(r"(10\.\d{4,9}/[^\s<>\"]+)", text, flags=re.IGNORECASE)
    if doi_match:
        return doi_match.group(1).rstrip(".,;)")

    doi_url_match = re.search(r"doi\.org/(10\.\d{4,9}/[^\s<>\"]+)", text, flags=re.IGNORECASE)
    if doi_url_match:
        return doi_url_match.group(1).rstrip(".,;)")
    return ""


def first_cod_id(value):
    match = re.search(r"\bCOD\s*[:#]?\s*(\d{5,})\b", str(value or ""), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def material_density_status(record):
    status = str(record.get("verification_status", "")).strip()
    if status:
        return status
    if str(record.get("origin", "")).lower().startswith("codex"):
        return CODEX_UNVERIFIED_DENSITY_STATUS
    return LAB_UNVERIFIED_DENSITY_STATUS


def material_density_trust_rank(record):
    status = material_density_status(record).lower()
    if "do not use" in status:
        return 99
    if "preferred" in status:
        return 0
    if "checked" in status:
        return 1
    if "lab entry" in status:
        return 2
    if "codex" in status:
        return 3
    return 4


def _density_composition_profile(formula):
    composition = parse_formula(normalize_formula(formula))
    cations = {
        element: float(amount)
        for element, amount in composition.items()
        if element != "O" and float(amount) > 0
    }
    cation_total = sum(cations.values())
    if cation_total <= 0:
        return None

    return {
        "fractions": {
            element: amount / cation_total
            for element, amount in cations.items()
        },
        "elements": set(cations),
        "oxygen_per_cation": float(composition.get("O", 0.0)) / cation_total,
    }


def _density_similarity_sort_key(target_profile, record_formula, record):
    try:
        record_profile = _density_composition_profile(record_formula)
    except ValueError:
        return None
    if not record_profile:
        return None

    target_elements = target_profile["elements"]
    record_elements = record_profile["elements"]
    overlap = target_elements & record_elements
    if not overlap:
        return None

    target_fractions = target_profile["fractions"]
    record_fractions = record_profile["fractions"]
    union = target_elements | record_elements

    cation_distance = sum(
        abs(target_fractions.get(element, 0.0) - record_fractions.get(element, 0.0))
        for element in union
    )
    missing_target_fraction = sum(
        target_fractions[element]
        for element in target_elements - record_elements
    )
    extra_record_fraction = sum(
        record_fractions[element]
        for element in record_elements - target_elements
    )
    oxygen_distance = abs(
        target_profile["oxygen_per_cation"] - record_profile["oxygen_per_cation"]
    )

    extra_cation_count = len(record_elements - target_elements)

    return (
        extra_cation_count,
        round(cation_distance, 12),
        round(missing_target_fraction, 12),
        len(target_elements - record_elements),
        round(extra_record_fraction, 12),
        round(oxygen_distance, 12),
        material_density_trust_rank(record),
        record.get("formula", record_formula),
        record.get("phase", ""),
        record.get("display_name", record_formula),
    )


def related_material_density_records(target, material_densities):
    try:
        target_profile = _density_composition_profile(target)
    except ValueError:
        return []

    if not target_profile:
        return []

    matches = []
    for record_key, record in material_densities.items():
        record_formula = record.get("formula", record_key)
        similarity_key = _density_similarity_sort_key(target_profile, record_formula, record)
        if similarity_key is None:
            continue

        matches.append((*similarity_key, record_key, record))

    matches.sort()
    return [(record_key, record) for *_, record_key, record in matches]


def normalize_density_record(formula, record):
    raw_formula = record.get("formula") or str(formula).split("__", 1)[0]
    key = normalize_formula(raw_formula)
    phase = str(record.get("phase", "")).strip()
    display_name = str(record.get("display_name", "")).strip()
    if not display_name:
        display_name = f"{key} ({phase})" if phase else key
    record_id = material_density_record_key(key, phase)
    normalized = {
        "record_id": record_id,
        "formula": key,
        "phase": phase,
        "display_name": display_name,
        "unit_cell_volume_A3": None,
        "z": None,
        "theoretical_density_g_cm3": None,
        "density_source": record.get("density_source", "manual"),
        "crystal_system": str(record.get("crystal_system", "")).strip(),
        "a_A": None,
        "b_A": None,
        "c_A": None,
        "alpha_deg": None,
        "beta_deg": None,
        "gamma_deg": None,
        "reported_density_g_cm3": None,
        "density_delta_g_cm3": None,
        "density_validation": str(record.get("density_validation", "")).strip(),
        "source": str(record.get("source", "")).strip(),
        "source_url": str(record.get("source_url", "")).strip(),
        "doi": str(record.get("doi", "")).strip(),
        "cod_id": str(record.get("cod_id", "")).strip(),
        "paper_title": str(record.get("paper_title", "")).strip(),
        "notes": str(record.get("notes", "")).strip(),
        "origin": str(record.get("origin", record.get("added_by", "Lab entry"))).strip() or "Lab entry",
        "verification_status": str(record.get("verification_status", "")).strip(),
        "verified_by": str(record.get("verified_by", "")).strip(),
        "verified_date": str(record.get("verified_date", "")).strip(),
    }
    if not normalized["source_url"]:
        normalized["source_url"] = first_url(normalized["source"])
    if not normalized["doi"]:
        normalized["doi"] = first_doi(normalized["source"])
    if not normalized["cod_id"]:
        normalized["cod_id"] = first_cod_id(normalized["source"])
    if not normalized["verification_status"]:
        if normalized["origin"].lower().startswith("codex"):
            normalized["verification_status"] = "Codex seeded - verify before use"
        else:
            normalized["verification_status"] = "Lab entry - unverified"

    volume = record.get("unit_cell_volume_A3")
    if volume not in (None, ""):
        normalized["unit_cell_volume_A3"] = float(volume)

    z = record.get("z")
    if z not in (None, ""):
        normalized["z"] = float(z)

    density = record.get("theoretical_density_g_cm3")
    if density not in (None, ""):
        normalized["theoretical_density_g_cm3"] = float(density)

    reported_density = record.get("reported_density_g_cm3")
    if reported_density not in (None, ""):
        normalized["reported_density_g_cm3"] = float(reported_density)

    density_delta = record.get("density_delta_g_cm3")
    if density_delta not in (None, ""):
        normalized["density_delta_g_cm3"] = float(density_delta)

    for source_key, dest_key in (
        ("a_A", "a_A"),
        ("b_A", "b_A"),
        ("c_A", "c_A"),
        ("alpha_deg", "alpha_deg"),
        ("beta_deg", "beta_deg"),
        ("gamma_deg", "gamma_deg"),
    ):
        value = record.get(source_key)
        if value not in (None, ""):
            normalized[dest_key] = float(value)

    return normalized


def load_material_densities():
    raw_records = storage.load_json(storage.MATERIAL_DENSITIES_FILE, {})
    records = {}

    for record_key, record in raw_records.items():
        normalized = normalize_density_record(record_key, record)
        records[normalized["record_id"]] = normalized

    if records != raw_records:
        save_material_densities(records)
    return records


def save_material_densities(records):
    storage.save_json(storage.MATERIAL_DENSITIES_FILE, records)


def resolve_material_density_key(identifier, records):
    key = str(identifier).strip()
    if key not in records:
        key = material_density_record_key(identifier)
    if key not in records:
        raise ValueError(f"Material density not found: {identifier}")
    return key


def demote_other_preferred_material_densities(records, preferred_key):
    preferred_formula = records[preferred_key].get("formula")
    if not preferred_formula:
        return records

    for record_key, record in records.items():
        if record_key == preferred_key:
            continue
        if record.get("formula") != preferred_formula:
            continue
        if "preferred" in material_density_status(record).lower():
            record["verification_status"] = LAB_CHECKED_DENSITY_STATUS
    return records


def set_preferred_material_density(identifier, verified_by="", verified_date=""):
    records = load_material_densities()
    key = resolve_material_density_key(identifier, records)
    record = dict(records[key])
    record["verification_status"] = PREFERRED_DENSITY_STATUS
    record["verified_by"] = str(verified_by or record.get("verified_by", "")).strip()
    record["verified_date"] = str(verified_date or record.get("verified_date", "")).strip()
    records[key] = normalize_density_record(key, record)
    demote_other_preferred_material_densities(records, key)
    save_material_densities(records)
    return key, records


def update_material_density_review_status(identifier, verification_status, verified_by="", verified_date=""):
    status = str(verification_status or "").strip()
    if not status:
        raise ValueError("Choose a density review status")
    if "preferred" in status.lower():
        return set_preferred_material_density(identifier, verified_by, verified_date)

    records = load_material_densities()
    key = resolve_material_density_key(identifier, records)
    record = dict(records[key])
    record["verification_status"] = status
    record["verified_by"] = str(verified_by or record.get("verified_by", "")).strip()
    record["verified_date"] = str(verified_date or record.get("verified_date", "")).strip()
    records[key] = normalize_density_record(key, record)
    save_material_densities(records)
    return key, records


def upsert_material_density(
    formula,
    phase="",
    theoretical_density=None,
    unit_cell_volume=None,
    z=None,
    density_source="manual",
    crystal_system="",
    a=None,
    b=None,
    c=None,
    alpha=None,
    beta=None,
    gamma=None,
    source="",
    source_url="",
    doi="",
    cod_id="",
    paper_title="",
    notes="",
    origin="Lab entry",
    reported_density=None,
    density_delta=None,
    density_validation="",
    verification_status="Lab entry - unverified",
    verified_by="",
    verified_date="",
):
    records = load_material_densities()
    key = normalize_formula(formula)
    record = {
        "formula": key,
        "phase": phase,
        "unit_cell_volume_A3": unit_cell_volume,
        "z": z,
        "theoretical_density_g_cm3": theoretical_density,
        "density_source": density_source,
        "crystal_system": crystal_system,
        "a_A": a,
        "b_A": b,
        "c_A": c,
        "alpha_deg": alpha,
        "beta_deg": beta,
        "gamma_deg": gamma,
        "reported_density_g_cm3": reported_density,
        "density_delta_g_cm3": density_delta,
        "density_validation": density_validation,
        "source": source,
        "source_url": source_url,
        "doi": doi,
        "cod_id": cod_id,
        "paper_title": paper_title,
        "notes": notes,
        "origin": origin,
        "verification_status": verification_status,
        "verified_by": verified_by,
        "verified_date": verified_date,
    }
    normalized = normalize_density_record(key, record)
    records[normalized["record_id"]] = normalized
    if "preferred" in material_density_status(normalized).lower():
        demote_other_preferred_material_densities(records, normalized["record_id"])
    save_material_densities(records)
    return normalized["record_id"], records


def delete_material_density(identifier):
    records = load_material_densities()
    key = resolve_material_density_key(identifier, records)
    records.pop(key)
    save_material_densities(records)
    return records
