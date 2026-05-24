import math

from .formula_parser import molar_mass, parse_formula


AVOGADRO = 6.02214076e23
ANGSTROM3_TO_CM3 = 1e-24
DEFAULT_DIE_DIAMETER_MM = 25.05


def unit_cell_volume_from_lattice(
    crystal_system,
    a_a,
    b_a=None,
    c_a=None,
    alpha_deg=None,
    beta_deg=None,
    gamma_deg=None,
):
    system = str(crystal_system).strip().lower()
    a = _positive_lattice_value(a_a, "a")

    if system == "cubic":
        b = a
        c = a
        alpha = beta = gamma = 90.0
    elif system == "tetragonal":
        b = a
        c = _positive_lattice_value(c_a, "c")
        alpha = beta = gamma = 90.0
    elif system == "orthorhombic":
        b = _positive_lattice_value(b_a, "b")
        c = _positive_lattice_value(c_a, "c")
        alpha = beta = gamma = 90.0
    elif system == "hexagonal":
        b = a
        c = _positive_lattice_value(c_a, "c")
        alpha = 90.0
        beta = 90.0
        gamma = 120.0
    elif system == "rhombohedral":
        b = a
        c = a
        alpha = _angle_value(alpha_deg, "alpha")
        beta = alpha
        gamma = alpha
    elif system == "monoclinic":
        b = _positive_lattice_value(b_a, "b")
        c = _positive_lattice_value(c_a, "c")
        alpha = 90.0
        beta = _angle_value(beta_deg, "beta")
        gamma = 90.0
    elif system == "triclinic":
        b = _positive_lattice_value(b_a, "b")
        c = _positive_lattice_value(c_a, "c")
        alpha = _angle_value(alpha_deg, "alpha")
        beta = _angle_value(beta_deg, "beta")
        gamma = _angle_value(gamma_deg, "gamma")
    else:
        raise ValueError(f"Unknown crystal system: {crystal_system}")

    return general_unit_cell_volume_a3(a, b, c, alpha, beta, gamma)


def general_unit_cell_volume_a3(a_a, b_a, c_a, alpha_deg, beta_deg, gamma_deg):
    a = _positive_lattice_value(a_a, "a")
    b = _positive_lattice_value(b_a, "b")
    c = _positive_lattice_value(c_a, "c")
    alpha = math.radians(_angle_value(alpha_deg, "alpha"))
    beta = math.radians(_angle_value(beta_deg, "beta"))
    gamma = math.radians(_angle_value(gamma_deg, "gamma"))

    cos_alpha = math.cos(alpha)
    cos_beta = math.cos(beta)
    cos_gamma = math.cos(gamma)
    volume_factor = (
        1
        + 2 * cos_alpha * cos_beta * cos_gamma
        - cos_alpha**2
        - cos_beta**2
        - cos_gamma**2
    )
    if volume_factor <= 0:
        raise ValueError("Lattice angles do not form a valid unit cell")

    return a * b * c * math.sqrt(volume_factor)


def _positive_lattice_value(value, label):
    if value is None:
        raise ValueError(f"Lattice parameter {label} is required")
    number = float(value)
    if number <= 0:
        raise ValueError(f"Lattice parameter {label} must be positive")
    return number


def _angle_value(value, label):
    if value is None:
        raise ValueError(f"Lattice angle {label} is required")
    angle = float(value)
    if angle <= 0 or angle >= 180:
        raise ValueError(f"Lattice angle {label} must be between 0 and 180 degrees")
    return angle


def cylinder_volume_cm3(diameter_mm, height_mm):
    diameter = float(diameter_mm)
    height = float(height_mm)
    if diameter <= 0:
        raise ValueError("Diameter must be positive")
    if height <= 0:
        raise ValueError("Height must be positive")

    diameter_cm = diameter / 10.0
    height_cm = height / 10.0
    radius_cm = diameter_cm / 2.0
    return math.pi * radius_cm**2 * height_cm


def theoretical_density_from_cell(formula, unit_cell_volume_a3, z):
    volume = float(unit_cell_volume_a3)
    formula_units = float(z)
    if volume <= 0:
        raise ValueError("Unit cell volume must be positive")
    if formula_units <= 0:
        raise ValueError("Z must be positive")

    mass_g_per_mol = molar_mass(parse_formula(formula))
    unit_cell_mass_g = formula_units * mass_g_per_mol / AVOGADRO
    unit_cell_volume_cm3 = volume * ANGSTROM3_TO_CM3
    return unit_cell_mass_g / unit_cell_volume_cm3


def target_mass_from_height(theoretical_density_g_cm3, height_mm, diameter_mm=DEFAULT_DIE_DIAMETER_MM):
    density = float(theoretical_density_g_cm3)
    if density <= 0:
        raise ValueError("Theoretical density must be positive")

    volume = cylinder_volume_cm3(diameter_mm, height_mm)
    return density * volume, volume


def target_height_from_mass(theoretical_density_g_cm3, target_mass_g, diameter_mm=DEFAULT_DIE_DIAMETER_MM):
    density = float(theoretical_density_g_cm3)
    mass = float(target_mass_g)
    diameter = float(diameter_mm)
    if density <= 0:
        raise ValueError("Theoretical density must be positive")
    if mass <= 0:
        raise ValueError("Target formula mass must be positive")
    if diameter <= 0:
        raise ValueError("Diameter must be positive")

    volume_cm3 = mass / density
    radius_cm = (diameter / 10.0) / 2.0
    height_cm = volume_cm3 / (math.pi * radius_cm**2)
    return height_cm * 10.0, volume_cm3


def measured_density(mass_g, diameter_mm, height_mm):
    mass = float(mass_g)
    if mass <= 0:
        raise ValueError("Measured mass must be positive")

    volume = cylinder_volume_cm3(diameter_mm, height_mm)
    return mass / volume, volume


def relative_density_percent(measured_density_g_cm3, theoretical_density_g_cm3):
    theoretical = float(theoretical_density_g_cm3)
    measured = float(measured_density_g_cm3)
    if theoretical <= 0:
        raise ValueError("Theoretical density must be positive")
    if measured <= 0:
        raise ValueError("Measured density must be positive")

    return measured / theoretical * 100.0
