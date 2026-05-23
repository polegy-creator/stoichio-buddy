import unittest

from stoichio.chemistry.density_engine import target_height_from_mass, target_mass_from_height
from stoichio.chemistry.formula_parser import parse_formula
from stoichio.chemistry.stoich_engine import (
    MASS_BASIS_TARGET_FORMULA,
    compute_recipe,
    infer_target_mass_from_recipe,
)


TEST_DENSITY_G_CM3 = 5.0

GOLDEN_HISTORY_RECIPES = [
    {
        "recipe_id": "R001",
        "target": "Fe1.96Zn0.04O3",
        "mass": 15.6,
        "selected_powders": ["ZnO", "Fe2O3"],
        "recipe": {"ZnO": 0.317242, "Fe2O3": 15.251573},
        "coefficients": {"ZnO": 0.04, "Fe2O3": 0.98},
        "powder_basis": 15.568815,
        "target_molar_mass": 160.0684,
        "precursor_formula_mass": 159.74842,
        "formula_units": 0.097458336561,
        "estimated_target_mass": 15.6,
    },
    {
        "recipe_id": "R002",
        "target": "CoFe1.99Ti0.01O4",
        "mass": 15.485,
        "selected_powders": ["Fe2O3", "TiO2", "Co3O4"],
        "recipe": {"Fe2O3": 10.490311, "TiO2": 0.052729, "Co3O4": 5.299342},
        "coefficients": {"Fe2O3": 0.995, "TiO2": 0.01, "Co3O4": 0.333333333333},
        "powder_basis": 15.842382,
        "target_molar_mass": 234.53922,
        "precursor_formula_mass": 239.952215,
        "formula_units": 0.066023072815,
        "estimated_target_mass": 15.485,
    },
]


def powder_db_for(entry):
    return {
        powder: {"elements": parse_formula(powder)}
        for powder in entry["selected_powders"]
    }


def mass_basis_for(entry):
    return entry.get("calculation", {}).get("mass_basis") or MASS_BASIS_TARGET_FORMULA


class GoldenHistoryRecipeTests(unittest.TestCase):
    def test_saved_history_recipes_reproduce_exact_masses(self):
        entries = GOLDEN_HISTORY_RECIPES
        self.assertGreater(len(entries), 0)

        for entry in entries:
            with self.subTest(target=entry.get("target"), recipe_id=entry.get("recipe_id")):
                result = compute_recipe(
                    entry["target"],
                    entry["mass"],
                    powder_db_for(entry),
                    entry["selected_powders"],
                    mass_basis=mass_basis_for(entry),
                )

                self.assertIsNone(result["warning"])
                self.assertEqual(set(result["recipe"]), set(entry["recipe"]))
                self.assertEqual(result["basis"], "cation balance")
                self.assertEqual(result["ignored_elements"], ["O"])
                self.assertLessEqual(result["residual"], 1e-12)
                self.assertEqual(result["coefficients"], entry["coefficients"])
                self.assertAlmostEqual(result["powder_basis"], entry["powder_basis"], places=6)
                self.assertAlmostEqual(result["target_molar_mass"], entry["target_molar_mass"], places=6)
                self.assertAlmostEqual(
                    result["precursor_formula_mass"],
                    entry["precursor_formula_mass"],
                    places=6,
                )
                self.assertAlmostEqual(result["formula_units"], entry["formula_units"], places=12)
                self.assertAlmostEqual(result["estimated_target_mass"], entry["estimated_target_mass"], places=6)
                for powder, expected_mass in entry["recipe"].items():
                    self.assertAlmostEqual(result["recipe"][powder], expected_mass, places=6)

    def test_saved_history_recipes_infer_original_target_mass_from_powder_masses(self):
        entries = GOLDEN_HISTORY_RECIPES
        self.assertGreater(len(entries), 0)

        for entry in entries:
            with self.subTest(target=entry.get("target"), recipe_id=entry.get("recipe_id")):
                inferred = infer_target_mass_from_recipe(
                    entry["target"],
                    entry["recipe"],
                    powder_db_for(entry),
                    entry["selected_powders"],
                )

                self.assertIsNone(inferred["warning"])
                self.assertAlmostEqual(inferred["target_mass"], entry["estimated_target_mass"], delta=1e-6)
                self.assertAlmostEqual(
                    inferred["reference"]["precursor_formula_mass"],
                    entry["precursor_formula_mass"],
                    places=6,
                )
                self.assertLessEqual(inferred["max_abs_deviation"], 1e-6)

    def test_saved_history_recipes_round_trip_through_pellet_height_mode(self):
        entries = GOLDEN_HISTORY_RECIPES
        self.assertGreater(len(entries), 0)

        for entry in entries:
            with self.subTest(target=entry.get("target"), recipe_id=entry.get("recipe_id")):
                reference = compute_recipe(
                    entry["target"],
                    entry["mass"],
                    powder_db_for(entry),
                    entry["selected_powders"],
                    mass_basis=mass_basis_for(entry),
                )
                height, _ = target_height_from_mass(
                    TEST_DENSITY_G_CM3,
                    reference["estimated_target_mass"],
                )
                mass_from_height, _ = target_mass_from_height(TEST_DENSITY_G_CM3, height)
                from_height = compute_recipe(
                    entry["target"],
                    mass_from_height,
                    powder_db_for(entry),
                    entry["selected_powders"],
                    mass_basis=MASS_BASIS_TARGET_FORMULA,
                )

                self.assertEqual(from_height["coefficients"], reference["coefficients"])
                for powder, expected_mass in entry["recipe"].items():
                    self.assertAlmostEqual(from_height["recipe"][powder], expected_mass, places=6)


if __name__ == "__main__":
    unittest.main()
