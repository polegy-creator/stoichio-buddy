import numpy as np

from .formula_parser import molar_mass, normalize_formula, parse_formula
from stoichio.powders import purity_fraction

# =========================
# CORE STOICHIOMETRY ENGINE
# =========================

MASS_BASIS_TOTAL_PRECURSOR = "total_precursor_powder"
MASS_BASIS_TARGET_FORMULA = "target_formula_mass"
DECOMPOSITION_BYPRODUCT_ELEMENTS = {"C", "H", "N"}


def normalize_target(target):
    if isinstance(target, str):
        return normalize_formula(target), parse_formula(target)
    if isinstance(target, dict):
        return None, {element: float(amount) for element, amount in target.items()}
    raise TypeError("Target must be a formula string or an element dictionary")


def powder_molar_mass(powder_record):
    return molar_mass(powder_record["elements"])


def powder_weighed_molar_mass(powder_record):
    return powder_molar_mass(powder_record) / purity_fraction(powder_record)


def solve_elements(target_comp, selected_powders, db):
    all_elements = set(target_comp)
    for powder in selected_powders:
        all_elements.update(db[powder].get("elements", {}).keys())

    ignored = set()
    if any(element != "O" for element in target_comp):
        ignored.add("O")

    for element in all_elements - set(target_comp):
        if element in DECOMPOSITION_BYPRODUCT_ELEMENTS:
            ignored.add(element)

    elements = sorted(element for element in all_elements if element not in ignored)
    return elements, sorted(ignored)


def non_negative_least_squares(A, b, tolerance=1e-12, max_iterations=None):
    """
    Deterministic Lawson-Hanson style NNLS solver.

    Solves min ||A x - b|| with x >= 0. This keeps the chemistry engine
    constrained without relying on scipy as an extra dependency.
    """
    rows, cols = A.shape
    if cols == 0:
        return np.array([], dtype=float)

    if max_iterations is None:
        max_iterations = max(30, cols * 20)

    x = np.zeros(cols, dtype=float)
    passive = np.zeros(cols, dtype=bool)
    w = A.T @ (b - A @ x)

    iterations = 0
    while np.any((~passive) & (w > tolerance)):
        if iterations > max_iterations:
            raise np.linalg.LinAlgError("NNLS solver did not converge")
        iterations += 1

        inactive_candidates = np.where(~passive, w, -np.inf)
        passive[int(np.argmax(inactive_candidates))] = True

        while True:
            z = np.zeros(cols, dtype=float)
            if np.any(passive):
                z[passive] = np.linalg.lstsq(A[:, passive], b, rcond=None)[0]

            if np.all(z[passive] > tolerance):
                x = z
                break

            nonpositive = passive & (z <= tolerance)
            denominators = x[nonpositive] - z[nonpositive]
            valid = denominators > tolerance
            if not np.any(valid):
                x = np.where(z > tolerance, z, 0.0)
                passive &= x > tolerance
                break

            alpha = np.min(x[nonpositive][valid] / denominators[valid])
            x = x + alpha * (z - x)
            x[np.abs(x) <= tolerance] = 0.0
            passive &= x > tolerance

        w = A.T @ (b - A @ x)

    x[x < tolerance] = 0.0
    return x


def compute_recipe(
    target,
    mass,
    db,
    selected_powders,
    tolerance=1e-6,
    mass_basis=MASS_BASIS_TOTAL_PRECURSOR,
):
    """
    Deterministic stoichiometric solver.

    - Uses only user-selected powders
    - No subset search
    - Uses one non-negative least-squares solve: A x ~= b, x >= 0
    - Interprets x as precursor moles per mole of target
    - Defaults to the lab weighing workflow: the input mass is the powder mixture mass
    - Keeps the legacy target-formula basis available for stored-history checks
    """
    if not selected_powders:
        return {"recipe": None, "warning": "Select at least one powder"}

    if mass <= 0:
        return {"recipe": None, "warning": "Input mass must be greater than 0"}

    if mass_basis not in {MASS_BASIS_TOTAL_PRECURSOR, MASS_BASIS_TARGET_FORMULA}:
        return {"recipe": None, "warning": f"Unknown mass basis: {mass_basis}"}

    try:
        normalized_formula, target_comp = normalize_target(target)
    except (TypeError, ValueError) as exc:
        return {"recipe": None, "warning": str(exc)}

    missing_powders = [powder for powder in selected_powders if powder not in db]
    if missing_powders:
        return {"recipe": None, "warning": f"Powder not found: {', '.join(missing_powders)}"}

    elements, ignored_elements = solve_elements(target_comp, selected_powders, db)

    missing_elements = [
        element for element in sorted(target_comp)
        if element in elements
        if all(db[powder].get("elements", {}).get(element, 0.0) == 0.0 for powder in selected_powders)
    ]
    if missing_elements:
        return {
            "recipe": None,
            "warning": f"Selected powders do not provide: {', '.join(missing_elements)}",
        }

    if not elements:
        return {"recipe": None, "warning": "No balanceable elements found"}

    b = np.array([target_comp.get(element, 0.0) for element in elements], dtype=float)
    A = np.array(
        [
            [db[powder].get("elements", {}).get(element, 0.0) for powder in selected_powders]
            for element in elements
        ],
        dtype=float,
    )

    try:
        coefficients = non_negative_least_squares(A, b)
    except np.linalg.LinAlgError:
        return {"recipe": None, "warning": "Solver failed"}

    if np.sum(coefficients) == 0:
        return {"recipe": None, "warning": "No physically valid contribution from selected powders"}

    try:
        target_molar_mass = molar_mass(target_comp)
    except ValueError as exc:
        return {"recipe": None, "warning": str(exc)}

    precursor_formula_mass = sum(
        float(coefficients[i]) * powder_weighed_molar_mass(db[powder])
        for i, powder in enumerate(selected_powders)
    )
    if precursor_formula_mass <= tolerance:
        return {"recipe": None, "warning": "No physically valid precursor mass from selected powders"}

    if mass_basis == MASS_BASIS_TARGET_FORMULA:
        formula_units = float(mass) / target_molar_mass
    else:
        formula_units = float(mass) / precursor_formula_mass

    recipe = {
        powder: round(float(coefficients[i] * formula_units * powder_weighed_molar_mass(db[powder])), 6)
        for i, powder in enumerate(selected_powders)
    }
    powder_basis = sum(recipe.values())

    residual_vector = A @ coefficients - b
    residual = float(np.linalg.norm(residual_vector))

    warning = None
    if residual > tolerance:
        warning = "Approximate solution (no exact stoichiometric match possible)"

    chemical_target_mass = formula_units * target_molar_mass
    displayed_target_mass = powder_basis if mass_basis == MASS_BASIS_TOTAL_PRECURSOR else chemical_target_mass

    return {
        "recipe": recipe,
        "warning": warning,
        "exact": residual <= tolerance,
        "residual": residual,
        "coefficients": {
            powder: round(float(coefficients[i]), 12)
            for i, powder in enumerate(selected_powders)
        },
        "purity_factors": {
            powder: round(float(purity_fraction(db[powder])), 8)
            for powder in selected_powders
        },
        "elements": elements,
        "ignored_elements": ignored_elements,
        "basis": "cation balance" if ignored_elements else "element balance",
        "target": target_comp,
        "normalized_target": normalized_formula,
        "input_mass": round(float(mass), 6),
        "mass_basis": mass_basis,
        "powder_basis": round(float(powder_basis), 6),
        "target_molar_mass": round(float(target_molar_mass), 6),
        "precursor_formula_mass": round(float(precursor_formula_mass), 6),
        "formula_units": round(float(formula_units), 12),
        "estimated_target_mass": round(float(displayed_target_mass), 6),
        "stoichiometric_target_mass": round(float(chemical_target_mass), 6),
    }


def infer_target_mass_from_recipe(
    target,
    recipe_masses,
    db,
    selected_powders,
    tolerance=1e-3,
    mass_basis=MASS_BASIS_TOTAL_PRECURSOR,
):
    """
    Infer the recipe mass represented by known precursor masses.

    By default this follows the lab weighing workflow, so the inferred target
    mass is the total powder mass. The legacy target-formula basis is still
    available for old saved-history checks.
    """
    if not selected_powders:
        return {"target_mass": None, "warning": "Select at least one powder"}

    actual_masses = {}
    for powder in selected_powders:
        try:
            grams = float(recipe_masses.get(powder, 0.0))
        except (TypeError, ValueError):
            return {"target_mass": None, "warning": f"Enter a valid mass for {powder}"}
        if grams < 0:
            return {"target_mass": None, "warning": f"Mass for {powder} cannot be negative"}
        actual_masses[powder] = grams

    total_actual_mass = sum(actual_masses.values())
    if total_actual_mass <= 0:
        return {"target_mass": None, "warning": "Enter at least one known powder mass"}

    reference = compute_recipe(
        target,
        1.0,
        db,
        selected_powders,
        tolerance=tolerance,
        mass_basis=mass_basis,
    )
    if reference.get("recipe") is None:
        return {"target_mass": None, "warning": reference.get("warning", "No valid solution found")}

    coefficients = reference["coefficients"]
    precursor_formula_mass = sum(
        float(coefficients[powder]) * powder_molar_mass(db[powder])
        for powder in selected_powders
    )
    if precursor_formula_mass <= 0:
        return {"target_mass": None, "warning": "No physically valid precursor mass from selected powders"}

    formula_units = total_actual_mass / precursor_formula_mass
    if mass_basis == MASS_BASIS_TARGET_FORMULA:
        target_molar_mass = molar_mass(reference["target"])
        target_mass = formula_units * target_molar_mass
    else:
        target_mass = total_actual_mass

    expected_recipe = {
        powder: float(coefficients[powder]) * formula_units * powder_molar_mass(db[powder])
        for powder in selected_powders
    }
    deviations = {
        powder: actual_masses[powder] - expected_recipe[powder]
        for powder in selected_powders
    }
    max_abs_deviation = max(abs(value) for value in deviations.values())

    warning = reference.get("warning")
    if warning is None and max_abs_deviation > tolerance:
        warning = "Known powder masses do not match the target stoichiometric ratio"

    return {
        "target_mass": float(target_mass),
        "formula_units": float(formula_units),
        "actual_recipe": actual_masses,
        "expected_recipe": expected_recipe,
        "deviations": deviations,
        "max_abs_deviation": float(max_abs_deviation),
        "warning": warning,
        "reference": reference,
    }
