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
    Parse a simple formula into an element-count dictionary.
    Supports decimal stoichiometries, but not parentheses or hydrates.
    """
    formula = normalize_formula(formula)
    pattern = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")
    composition = {}
    pos = 0

    for match in pattern.finditer(formula):
        if match.start() != pos:
            raise ValueError(f"Invalid formula near '{formula[pos:match.start()]}'")

        element, amount_text = match.groups()
        if element not in ATOMIC_MASSES:
            raise ValueError(f"Unknown element '{element}'")

        if amount_text in ("", None):
            amount = 1.0
        else:
            try:
                amount = float(amount_text)
            except ValueError as exc:
                raise ValueError(f"Invalid amount for '{element}'") from exc

        if amount <= 0:
            raise ValueError(f"Amount for '{element}' must be positive")

        composition[element] = composition.get(element, 0.0) + amount
        pos = match.end()

    if pos != len(formula):
        raise ValueError(f"Invalid formula near '{formula[pos:]}'")

    if not composition:
        raise ValueError("Formula did not contain any elements")

    return composition


def molar_mass(composition):
    missing = [element for element in composition if element not in ATOMIC_MASSES]
    if missing:
        raise ValueError(f"Missing atomic masses for: {', '.join(missing)}")

    return sum(ATOMIC_MASSES[element] * amount for element, amount in composition.items())
