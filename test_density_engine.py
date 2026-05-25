import json
from pathlib import Path
import unittest

from stoichio.chemistry.density_engine import (
    AVOGADRO,
    ANGSTROM3_TO_CM3,
    cylinder_volume_cm3,
    measured_density,
    relative_density_percent,
    target_height_from_mass,
    target_mass_from_height,
    theoretical_density_from_cell,
    unit_cell_volume_from_lattice,
)
from stoichio.chemistry.formula_parser import molar_mass, parse_formula


MATERIAL_DENSITIES_FILE = Path(__file__).with_name("material_densities.json")


LITERATURE_DENSITY_CASES = [
    {
        "name": "hematite Fe2O3, Blake et al. 1966, COD 9000139",
        "formula": "Fe2O3",
        "system": "Hexagonal",
        "a": 5.038,
        "c": 13.772,
        "z": 6,
        "published_volume": 302.722,
        "published_density": 5.256,
    },
    {
        "name": "rutile TiO2, Howard et al. 1991, COD 9015662",
        "formula": "TiO2",
        "system": "Tetragonal",
        "a": 4.5937,
        "c": 2.9587,
        "z": 2,
        "published_volume": 62.435,
        "published_density": 4.249,
    },
    {
        "name": "zincite ZnO, Schreyer et al. 2014, COD 2300450",
        "formula": "ZnO",
        "system": "Hexagonal",
        "a": 3.249308,
        "c": 5.205709,
        "z": 2,
        "published_volume": 47.5984,
        "published_density": 5.67848,
    },
    {
        "name": "baddeleyite ZrO2, Smith and Newkirk 1965, COD 9007485",
        "formula": "ZrO2",
        "system": "Monoclinic",
        "a": 5.145,
        "b": 5.2075,
        "c": 5.3107,
        "beta": 99.23,
        "z": 4,
        "published_volume": 140.445,
        "published_density": 5.828,
    },
    {
        "name": "spinel Co3O4, Kotousova and Polyakov 1972, COD 1526734",
        "formula": "Co3O4",
        "system": "Cubic",
        "a": 8.065,
        "z": 8,
        "published_volume": 524.582,
        "published_density": None,
    },
]


class DensityEngineTests(unittest.TestCase):
    def test_unit_cell_volume_lattice_systems(self):
        self.assertAlmostEqual(unit_cell_volume_from_lattice("Cubic", 2.0), 8.0)
        self.assertAlmostEqual(unit_cell_volume_from_lattice("Hexagonal", 2.0, c_a=4.0), 13.8564064606)

    def test_missing_lattice_a_is_clear_user_error(self):
        with self.assertRaisesRegex(ValueError, "Lattice parameter a is required"):
            unit_cell_volume_from_lattice("Cubic", None)

    def test_theoretical_density_from_cell(self):
        density = theoretical_density_from_cell("Fe2O3", 302.0, 6)
        expected = 6 * molar_mass(parse_formula("Fe2O3")) / AVOGADRO / (302.0 * ANGSTROM3_TO_CM3)
        self.assertAlmostEqual(density, expected, places=10)

    def test_theoretical_density_matches_literature_cells(self):
        for case in LITERATURE_DENSITY_CASES:
            with self.subTest(case=case["name"]):
                volume = unit_cell_volume_from_lattice(
                    case["system"],
                    case["a"],
                    b_a=case.get("b"),
                    c_a=case.get("c"),
                    beta_deg=case.get("beta"),
                )
                density = theoretical_density_from_cell(case["formula"], volume, case["z"])

                self.assertAlmostEqual(volume, case["published_volume"], delta=0.001)
                if case["published_density"] is not None:
                    self.assertAlmostEqual(density, case["published_density"], delta=0.001)

    def test_codex_seeded_reported_densities_match_calculated_values(self):
        records = json.loads(MATERIAL_DENSITIES_FILE.read_text())
        checked_records = 0

        for record_key, record in records.items():
            if record.get("origin") != "Codex literature seed":
                continue

            reported_density = record.get("reported_density_g_cm3")
            if reported_density is None:
                continue

            checked_records += 1
            calculated_density = theoretical_density_from_cell(
                record["formula"],
                record["unit_cell_volume_A3"],
                record["z"],
            )

            with self.subTest(record=record_key):
                self.assertAlmostEqual(
                    calculated_density,
                    record["theoretical_density_g_cm3"],
                    places=10,
                )
                self.assertAlmostEqual(calculated_density, reported_density, delta=0.01)

        self.assertGreater(checked_records, 0)

    def test_pellet_mass_and_relative_density(self):
        volume = cylinder_volume_cm3(25.05, 1.0)
        mass, reported_volume = target_mass_from_height(5.2, 1.0, 25.05)
        self.assertAlmostEqual(reported_volume, volume, places=12)
        self.assertAlmostEqual(mass, 5.2 * volume, places=12)

        height, height_volume = target_height_from_mass(5.2, mass, 25.05)
        self.assertAlmostEqual(height_volume, volume, places=12)
        self.assertAlmostEqual(height, 1.0, places=12)

        measured, measured_volume = measured_density(2.5, 25.05, 1.0)
        self.assertAlmostEqual(measured_volume, volume, places=12)
        self.assertAlmostEqual(measured, 2.5 / volume, places=12)
        self.assertAlmostEqual(relative_density_percent(measured, 5.2), measured / 5.2 * 100)

    def test_height_mass_matches_excel_porosity_workflow(self):
        mass, solid_volume = target_mass_from_height(
            theoretical_density_g_cm3=5.27,
            height_mm=6.35,
            diameter_mm=25.0,
            target_porosity_percent=5.0,
        )

        self.assertAlmostEqual(cylinder_volume_cm3(25.0, 6.35), 3.1170489609836225)
        self.assertAlmostEqual(solid_volume, 2.9611965129344413)
        self.assertAlmostEqual(mass, 15.605505623164504)


if __name__ == "__main__":
    unittest.main()
