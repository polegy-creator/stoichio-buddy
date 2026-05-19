import math

from formula_parser import molar_mass, parse_formula


AVOGADRO = 6.02214076e23
ANGSTROM3_TO_CM3 = 1e-24
DEFAULT_DIE_DIAMETER_MM = 25.05


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
