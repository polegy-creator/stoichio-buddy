import json
import re
from pathlib import Path


ATOMIC_MASSES_FILE = Path(__file__).with_name("atomic_masses.json")


def load_atomic_masses(path=ATOMIC_MASSES_FILE):
    with open(path, "r") as f:
        return json.load(f)


ATOMIC_MASSES = load_atomic_masses()


def normalize_formula(formula):
    """
    Canonicalize simple chemical formulas while still accepting lower-case input.
    Examples: fe1.98ti0.02o3 -> Fe1.98Ti0.02O3, CO2 -> CO2.
    """
    if formula is None:
        raise ValueError("Formula is required")

    raw = str(formula).strip().replace(" ", "").replace("+", "")
    if not raw:
        raise ValueError("Formula is required")

    normalized = []
    i = 0
    while i < len(raw):
        ch = raw[i]

        if ch.isupper():
            if i + 1 < len(raw) and raw[i + 1].islower():
                normalized.append(ch + raw[i + 1].lower())
                i += 2
            else:
                normalized.append(ch)
                i += 1
            continue

        if ch.islower():
            first = ch.upper()
            if i + 1 < len(raw) and raw[i + 1].islower():
                candidate = first + raw[i + 1].lower()
                if candidate in ATOMIC_MASSES:
                    normalized.append(candidate)
                    i += 2
                    continue

            normalized.append(first)
            i += 1
            continue

        normalized.append(ch)
        i += 1

    return "".join(normalized)


def parse_formula(formula):
    """
    Parse a formula into an element-count dictionary.

    Supports decimal stoichiometry, grouped formulas such as Ba(NO3)2,
    and hydrate separators written as middle dot or asterisk.
    """
    formula = normalize_formula(formula)
    composition = {}

    for part in _hydrate_parts(formula):
        multiplier, body = _leading_multiplier(part)
        parsed, pos = _parse_group(body, 0, None)
        if pos != len(body):
            raise ValueError(f"Invalid formula near '{body[pos:]}'")

        for element, amount in parsed.items():
            composition[element] = composition.get(element, 0.0) + amount * multiplier

    if not composition:
        raise ValueError("Formula did not contain any elements")

    return composition


def _hydrate_parts(formula):
    parts = re.split(r"[·•*]", formula)
    if not parts or any(part == "" for part in parts):
        raise ValueError("Formula did not contain any elements")
    return parts


def _leading_multiplier(part):
    match = re.match(r"(\d+(?:\.\d*)?|\.\d+)(?=[A-Z(\[{])", part)
    if not match:
        return 1.0, part

    multiplier = float(match.group(1))
    if multiplier <= 0:
        raise ValueError("Formula multiplier must be positive")
    return multiplier, part[match.end():]


def _parse_group(text, pos, closing):
    composition = {}
    matching_close = {"(": ")", "[": "]", "{": "}"}

    while pos < len(text):
        ch = text[pos]

        if closing and ch == closing:
            return composition, pos + 1
        if ch in ")]}":
            raise ValueError(f"Unexpected closing group '{ch}'")

        if ch in matching_close:
            group_comp, pos = _parse_group(text, pos + 1, matching_close[ch])
            multiplier, pos = _read_amount(text, pos)
            _merge_composition(composition, group_comp, multiplier)
            continue

        if ch.isupper():
            element, pos = _read_element(text, pos)
            amount, pos = _read_amount(text, pos)
            composition[element] = composition.get(element, 0.0) + amount
            continue

        raise ValueError(f"Invalid formula near '{text[pos:]}'")

    if closing:
        raise ValueError(f"Missing closing group '{closing}'")
    return composition, pos


def _read_element(text, pos):
    element = text[pos]
    pos += 1
    if pos < len(text) and text[pos].islower():
        element += text[pos]
        pos += 1

    if element not in ATOMIC_MASSES:
        raise ValueError(f"Unknown element '{element}'")
    return element, pos


def _read_amount(text, pos):
    match = re.match(r"\d+(?:\.\d*)?|\.\d+", text[pos:])
    if not match:
        return 1.0, pos

    amount = float(match.group(0))
    if amount <= 0:
        raise ValueError("Formula amounts must be positive")
    return amount, pos + len(match.group(0))


def _merge_composition(destination, source, multiplier):
    for element, amount in source.items():
        destination[element] = destination.get(element, 0.0) + amount * multiplier


def molar_mass(composition):
    missing = [element for element in composition if element not in ATOMIC_MASSES]
    if missing:
        raise ValueError(f"Missing atomic masses for: {', '.join(missing)}")

    return sum(ATOMIC_MASSES[element] * amount for element, amount in composition.items())
