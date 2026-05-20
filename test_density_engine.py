import unittest

from density_engine import (
    AVOGADRO,
    ANGSTROM3_TO_CM3,
    cylinder_volume_cm3,
    measured_density,
    relative_density_percent,
    target_mass_from_height,
    theoretical_density_from_cell,
    unit_cell_volume_from_lattice,
)
from formula_parser import molar_mass, parse_formula


class DensityEngineTests(unittest.TestCase):
    def test_unit_cell_volume_lattice_systems(self):
        self.assertAlmostEqual(unit_cell_volume_from_lattice("Cubic", 2.0), 8.0)
        self.assertAlmostEqual(unit_cell_volume_from_lattice("Hexagonal", 2.0, c_a=4.0), 13.8564064606)

    def test_theoretical_density_from_cell(self):
        density = theoretical_density_from_cell("Fe2O3", 302.0, 6)
        expected = 6 * molar_mass(parse_formula("Fe2O3")) / AVOGADRO / (302.0 * ANGSTROM3_TO_CM3)
        self.assertAlmostEqual(density, expected, places=10)

    def test_pellet_mass_and_relative_density(self):
        volume = cylinder_volume_cm3(25.05, 1.0)
        mass, reported_volume = target_mass_from_height(5.2, 1.0, 25.05)
        self.assertAlmostEqual(reported_volume, volume, places=12)
        self.assertAlmostEqual(mass, 5.2 * volume, places=12)

        measured, measured_volume = measured_density(2.5, 25.05, 1.0)
        self.assertAlmostEqual(measured_volume, volume, places=12)
        self.assertAlmostEqual(measured, 2.5 / volume, places=12)
        self.assertAlmostEqual(relative_density_percent(measured, 5.2), measured / 5.2 * 100)


if __name__ == "__main__":
    unittest.main()
