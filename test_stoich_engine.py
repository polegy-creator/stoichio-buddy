import unittest

from formula_parser import parse_formula
from stoich_engine import compute_recipe


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

    def test_missing_cation_source_warns(self):
        db = {
            "Fe2O3": {"elements": parse_formula("Fe2O3")},
        }

        result = compute_recipe("FeTiO3", 10.0, db, ["Fe2O3"])

        self.assertIsNone(result["recipe"])
        self.assertIn("Ti", result["warning"])


if __name__ == "__main__":
    unittest.main()
