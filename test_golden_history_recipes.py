import unittest

from stoichio.chemistry.density_engine import target_height_from_mass, target_mass_from_height
from stoichio.chemistry.formula_parser import parse_formula
from stoichio.chemistry.stoich_engine import MASS_BASIS_TARGET_FORMULA, compute_recipe


TEST_DENSITY_G_CM3 = 5.0

GOLDEN_HISTORY_RECIPES = [
    {
        "recipe_id": "R001",
        "target": "Fe1.96Zn0.04O3",
        "mass": 15.6,
        "selected_powders": ["ZnO", "Fe2O3"],
        "recipe": {"ZnO": 0.317242, "Fe2O3": 15.251573},
    },
    {
        "recipe_id": "R002",
        "target": "CoFe1.99Ti0.01O4",
        "mass": 15.485,
        "selected_powders": ["Fe2O3", "TiO2", "Co3O4"],
        "recipe": {"Fe2O3": 10.490311, "TiO2": 0.052729, "Co3O4": 5.299342},
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
                for powder, expected_mass in entry["recipe"].items():
                    self.assertAlmostEqual(result["recipe"][powder], expected_mass, places=6)

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
