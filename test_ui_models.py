import unittest

from stoichio.ui_models import (
    recipe_calculation_metadata,
    target_lifecycle_dataframe,
    target_lifecycle_status,
)


class UiModelTests(unittest.TestCase):
    def test_target_lifecycle_status_uses_lab_filter_labels(self):
        self.assertEqual(
            target_lifecycle_status({"recipes": [{}], "densities": [{}]}),
            "Completed",
        )
        self.assertEqual(
            target_lifecycle_status({"recipes": [{}], "densities": []}),
            "Powder masses",
        )
        self.assertEqual(
            target_lifecycle_status({"recipes": [], "densities": [{}]}),
            "Density",
        )

    def test_recipe_calculation_metadata_keeps_height_planning_parameters(self):
        metadata = recipe_calculation_metadata(
            {
                "input_mass": 2.25,
                "mass_basis": "target_formula_mass",
                "basis": "cation",
            },
            planning_context={
                "amount_mode": "Pellet height",
                "target_mass": 2.25,
                "planning_height": 1.4,
                "planning_volume": 0.69,
                "theoretical_density": 5.24,
                "density_source": "Manual",
                "density_verified": True,
            },
        )

        self.assertEqual(metadata["planning"]["amount_mode"], "Target height")
        self.assertEqual(metadata["planning"]["target_mass_g"], 2.25)
        self.assertEqual(metadata["planning"]["target_height_mm"], 1.4)
        self.assertEqual(metadata["planning"]["die_diameter_mm"], 25.05)
        self.assertEqual(metadata["planning"]["solid_volume_cm3"], 0.69)

    def test_target_lifecycle_dataframe_exposes_recipe_height_planning(self):
        dataframe = target_lifecycle_dataframe(
            history=[
                {
                    "entry_type": "synthesis",
                    "target_for": "Daniel",
                    "target_id": "Daniel-T001",
                    "target": "Fe2O3",
                    "time": "2026-06-21T10:00:00",
                    "mass": 2.25,
                    "recipe": {"Fe2O3": 2.25},
                    "calculation": {
                        "mass_basis": "target_formula_mass",
                        "planning": {
                            "amount_mode": "Target height",
                            "target_height_mm": 1.4,
                            "die_diameter_mm": 25.05,
                            "target_porosity_percent": 0,
                            "theoretical_density_g_cm3": 5.24,
                            "density_source": "Manual",
                            "solid_volume_cm3": 0.69,
                        },
                    },
                }
            ]
        )

        self.assertEqual(dataframe.iloc[0]["Recipe target height (mm)"], 1.4)
        self.assertEqual(dataframe.iloc[0]["Recipe die diameter (mm)"], 25.05)
        self.assertEqual(dataframe.iloc[0]["Recipe planning density (g/cm3)"], 5.24)


if __name__ == "__main__":
    unittest.main()
