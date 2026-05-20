import tempfile
import unittest

import lab_manager


class LabManagerHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_history_file = lab_manager.HISTORY_FILE
        self.old_storage_backend = lab_manager._storage_backend
        lab_manager.HISTORY_FILE = f"{self.tempdir.name}/history.json"
        lab_manager._storage_backend = None

    def tearDown(self):
        lab_manager.HISTORY_FILE = self.old_history_file
        lab_manager._storage_backend = self.old_storage_backend
        self.tempdir.cleanup()

    def test_target_density_keeps_exact_linked_recipe_snapshot(self):
        linked_recipe = {
            "entry_id": "recipe-entry-1",
            "recipe_id": "R001",
            "recipe": {"Fe2O3": 15.459, "TiO2": 0.156},
        }

        history = lab_manager.log_target_density(
            "Fe1.98Ti0.02O3",
            1,
            "Daniel",
            measured_density=5.1,
            theoretical_density=5.2,
            relative_density=98.08,
            final_volume=0.12,
            final_mass=0.61,
            final_diameter=24.8,
            final_height=0.25,
            linked_recipe=linked_recipe,
        )

        self.assertEqual(history[-1]["target_id"], "Daniel-T001")
        self.assertEqual(history[-1]["linked_recipe"], linked_recipe)

    def test_unassigned_target_density_stays_quick_record(self):
        lab_manager.log_target_density(
            "Fe1.98Ti0.02O3",
            None,
            None,
            measured_density=5.1,
            theoretical_density=5.2,
            relative_density=98.08,
            final_volume=0.12,
            final_mass=0.61,
            final_diameter=24.8,
            final_height=0.25,
        )

        history = lab_manager.load_history()

        self.assertNotIn("target_id", history[-1])
        self.assertNotIn("target_number", history[-1])
        self.assertNotIn("target_for", history[-1])


if __name__ == "__main__":
    unittest.main()
