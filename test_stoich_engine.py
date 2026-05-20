import unittest

from formula_parser import parse_formula
from stoich_engine import MASS_BASIS_TARGET_FORMULA, MASS_BASIS_TOTAL_PRECURSOR, compute_recipe


class StoichEngineTests(unittest.TestCase):
    def test_fe_ti_recipe_uses_total_precursor_powder_basis(self):
        db = {
            "Fe2O3": {"elements": parse_formula("Fe2O3")},
            "TiO2": {"elements": parse_formula("TiO2")},
        }

        result = compute_recipe("Fe1.98Ti0.02O3", 15.615, db, ["Fe2O3", "TiO2"])

        self.assertIsNone(result["warning"])
        self.assertEqual(result["basis"], "cation balance")
        self.assertEqual(result["coefficients"], {"Fe2O3": 0.99, "TiO2": 0.02})
        self.assertAlmostEqual(result["recipe"]["Fe2O3"], 15.459, places=3)
        self.assertAlmostEqual(result["recipe"]["TiO2"], 0.156, places=3)
        self.assertAlmostEqual(sum(result["recipe"].values()), 15.615, places=6)
        self.assertEqual(result["mass_basis"], MASS_BASIS_TOTAL_PRECURSOR)
        self.assertAlmostEqual(result["powder_basis"], 15.615, places=6)

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
            mass_basis=MASS_BASIS_TARGET_FORMULA,
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
            mass_basis=MASS_BASIS_TARGET_FORMULA,
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
