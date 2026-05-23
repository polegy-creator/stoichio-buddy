import unittest

from stoichio.chemistry.density_engine import target_height_from_mass, target_mass_from_height, theoretical_density_from_cell
from stoichio.chemistry.formula_parser import parse_formula
from stoichio.chemistry.stoich_engine import (
    MASS_BASIS_TARGET_FORMULA,
    MASS_BASIS_TOTAL_PRECURSOR,
    compute_recipe,
    infer_target_mass_from_recipe,
)


class StoichEngineTests(unittest.TestCase):
    def test_fe_ti_recipe_uses_original_target_formula_basis_by_default(self):
        db = {
            "Fe2O3": {"elements": parse_formula("Fe2O3")},
            "TiO2": {"elements": parse_formula("TiO2")},
        }

        result = compute_recipe("Fe1.98Ti0.02O3", 15.615, db, ["Fe2O3", "TiO2"])

        self.assertIsNone(result["warning"])
        self.assertEqual(result["basis"], "cation balance")
        self.assertEqual(result["coefficients"], {"Fe2O3": 0.99, "TiO2": 0.02})
        self.assertAlmostEqual(result["recipe"]["Fe2O3"], 15.474312, places=6)
        self.assertAlmostEqual(result["recipe"]["TiO2"], 0.156348, places=6)
        self.assertAlmostEqual(sum(result["recipe"].values()), 15.63066, places=6)
        self.assertEqual(result["mass_basis"], MASS_BASIS_TARGET_FORMULA)
        self.assertAlmostEqual(result["estimated_target_mass"], 15.615, places=6)

    def test_fe_ti_recipe_can_still_use_total_precursor_powder_basis(self):
        db = {
            "Fe2O3": {"elements": parse_formula("Fe2O3")},
            "TiO2": {"elements": parse_formula("TiO2")},
        }

        result = compute_recipe(
            "Fe1.98Ti0.02O3",
            15.615,
            db,
            ["Fe2O3", "TiO2"],
            mass_basis=MASS_BASIS_TOTAL_PRECURSOR,
        )

        self.assertAlmostEqual(result["recipe"]["Fe2O3"], 15.459, places=3)
        self.assertAlmostEqual(result["recipe"]["TiO2"], 0.156, places=3)
        self.assertAlmostEqual(sum(result["recipe"].values()), 15.615, places=6)
        self.assertEqual(result["mass_basis"], MASS_BASIS_TOTAL_PRECURSOR)

    def test_fe_ti_known_powder_masses_round_trip_through_pellet_height(self):
        db = {
            "Fe2O3": {"elements": parse_formula("Fe2O3")},
            "TiO2": {"elements": parse_formula("TiO2")},
        }

        trusted_recipe = compute_recipe("Fe1.98Ti0.02O3", 15.615, db, ["Fe2O3", "TiO2"])
        inferred = infer_target_mass_from_recipe(
            "Fe1.98Ti0.02O3",
            trusted_recipe["recipe"],
            db,
            ["Fe2O3", "TiO2"],
        )
        hematite_cell_density_for_target = theoretical_density_from_cell("Fe1.98Ti0.02O3", 302.722, 6)
        height, _ = target_height_from_mass(
            hematite_cell_density_for_target,
            inferred["target_mass"],
            25.05,
        )
        height_target_mass, _ = target_mass_from_height(hematite_cell_density_for_target, height, 25.05)
        roundtrip = compute_recipe("Fe1.98Ti0.02O3", height_target_mass, db, ["Fe2O3", "TiO2"])

        self.assertAlmostEqual(inferred["target_mass"], 15.615, places=6)
        self.assertAlmostEqual(height, 6.03455, places=6)
        self.assertAlmostEqual(roundtrip["recipe"]["Fe2O3"], trusted_recipe["recipe"]["Fe2O3"], places=6)
        self.assertAlmostEqual(roundtrip["recipe"]["TiO2"], trusted_recipe["recipe"]["TiO2"], places=6)

    def test_fe_ti_total_powder_recipe_round_trips_through_pellet_height(self):
        db = {
            "Fe2O3": {"elements": parse_formula("Fe2O3")},
            "TiO2": {"elements": parse_formula("TiO2")},
        }

        trusted_recipe = compute_recipe(
            "Fe1.98Ti0.02O3",
            15.615,
            db,
            ["Fe2O3", "TiO2"],
            mass_basis=MASS_BASIS_TOTAL_PRECURSOR,
        )
        inferred = infer_target_mass_from_recipe(
            "Fe1.98Ti0.02O3",
            trusted_recipe["recipe"],
            db,
            ["Fe2O3", "TiO2"],
        )
        hematite_cell_density_for_target = theoretical_density_from_cell("Fe1.98Ti0.02O3", 302.722, 6)
        height, _ = target_height_from_mass(
            hematite_cell_density_for_target,
            inferred["target_mass"],
            25.05,
        )
        height_target_mass, _ = target_mass_from_height(hematite_cell_density_for_target, height, 25.05)
        roundtrip = compute_recipe("Fe1.98Ti0.02O3", height_target_mass, db, ["Fe2O3", "TiO2"])

        self.assertAlmostEqual(inferred["target_mass"], trusted_recipe["estimated_target_mass"], places=6)
        self.assertAlmostEqual(height, 6.028504, places=6)
        self.assertAlmostEqual(roundtrip["recipe"]["Fe2O3"], trusted_recipe["recipe"]["Fe2O3"], places=6)
        self.assertAlmostEqual(roundtrip["recipe"]["TiO2"], trusted_recipe["recipe"]["TiO2"], places=6)

    def test_legacy_target_formula_basis_reproduces_saved_zn_recipe(self):
        db = {
            "Fe2O3": {"elements": parse_formula("Fe2O3")},
            "ZnO": {"elements": parse_formula("ZnO")},
        }

        result = compute_recipe(
            "Fe1.96Zn0.04O3",
            15.6,
            db,
            ["ZnO", "Fe2O3"],
        )

        self.assertEqual(result["coefficients"], {"ZnO": 0.04, "Fe2O3": 0.98})
        self.assertAlmostEqual(result["recipe"]["ZnO"], 0.317242, places=6)
        self.assertAlmostEqual(result["recipe"]["Fe2O3"], 15.251573, places=6)
        self.assertAlmostEqual(sum(result["recipe"].values()), 15.568815, places=6)

    def test_legacy_target_formula_basis_reproduces_saved_co_ti_recipe(self):
        db = {
            "Fe2O3": {"elements": parse_formula("Fe2O3")},
            "TiO2": {"elements": parse_formula("TiO2")},
            "Co3O4": {"elements": parse_formula("Co3O4")},
        }

        result = compute_recipe(
            "CoFe1.99Ti0.01O4",
            15.485,
            db,
            ["Fe2O3", "TiO2", "Co3O4"],
        )

        self.assertEqual(
            result["coefficients"],
            {"Fe2O3": 0.995, "TiO2": 0.01, "Co3O4": 0.333333333333},
        )
        self.assertAlmostEqual(result["recipe"]["Fe2O3"], 10.490311, places=6)
        self.assertAlmostEqual(result["recipe"]["TiO2"], 0.052729, places=6)
        self.assertAlmostEqual(result["recipe"]["Co3O4"], 5.299342, places=6)
        self.assertAlmostEqual(sum(result["recipe"].values()), 15.842382, places=6)

    def test_missing_cation_source_warns(self):
        db = {
            "Fe2O3": {"elements": parse_formula("Fe2O3")},
        }

        result = compute_recipe("FeTiO3", 10.0, db, ["Fe2O3"])

        self.assertIsNone(result["recipe"])
        self.assertIn("Ti", result["warning"])


if __name__ == "__main__":
    unittest.main()
