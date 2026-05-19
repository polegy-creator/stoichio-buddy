import numpy as np

from formula_parser import molar_mass, normalize_formula, parse_formula

# =========================
# CORE STOICHIOMETRY ENGINE
# =========================


def normalize_target(target):
    if isinstance(target, str):
        return normalize_formula(target), parse_formula(target)
    if isinstance(target, dict):
        return None, {element: float(amount) for element, amount in target.items()}
    raise TypeError("Target must be a formula string or an element dictionary")


def powder_molar_mass(powder_record):
    return molar_mass(powder_record["elements"])


def solve_elements(target_comp, selected_powders, db):
    all_elements = set(target_comp)
    for powder in selected_powders:
        all_elements.update(db[powder].get("elements", {}).keys())

    ignored = []
    if any(element != "O" for element in target_comp):
        ignored.append("O")

    elements = sorted(element for element in all_elements if element not in ignored)
    return elements, ignored


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


def compute_recipe(target, mass, db, selected_powders, tolerance=1e-6):
    """
    Deterministic stoichiometric solver.

    - Uses only user-selected powders
    - No subset search
    - Uses one non-negative least-squares solve: A x ~= b, x >= 0
    - Interprets x as precursor moles per mole of target
    """
    if not selected_powders:
        return {"recipe": None, "warning": "Select at least one powder"}

    if mass <= 0:
        return {"recipe": None, "warning": "Target mass must be greater than 0"}

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

    target_moles = float(mass) / target_molar_mass
    recipe = {
        powder: round(float(coefficients[i] * target_moles * powder_molar_mass(db[powder])), 6)
        for i, powder in enumerate(selected_powders)
    }

    residual_vector = A @ coefficients - b
    residual = float(np.linalg.norm(residual_vector))

    warning = None
    if residual > tolerance:
        warning = "Approximate solution (no exact stoichiometric match possible)"

    return {
        "recipe": recipe,
        "warning": warning,
        "exact": residual <= tolerance,
        "residual": residual,
        "coefficients": {
            powder: round(float(coefficients[i]), 12)
            for i, powder in enumerate(selected_powders)
        },
        "elements": elements,
        "ignored_elements": ignored_elements,
        "basis": "cation balance" if ignored_elements == ["O"] else "element balance",
        "target": target_comp,
        "normalized_target": normalized_formula,
        "target_molar_mass": round(float(target_molar_mass), 6),
    }
