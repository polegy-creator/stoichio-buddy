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


class LabManagerMaterialDensityTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_material_densities_file = lab_manager.MATERIAL_DENSITIES_FILE
        self.old_storage_backend = lab_manager._storage_backend
        lab_manager.MATERIAL_DENSITIES_FILE = f"{self.tempdir.name}/material_densities.json"
        lab_manager._storage_backend = None

    def tearDown(self):
        lab_manager.MATERIAL_DENSITIES_FILE = self.old_material_densities_file
        lab_manager._storage_backend = self.old_storage_backend
        self.tempdir.cleanup()

    def test_material_density_records_are_phase_specific(self):
        rutile_key, _ = lab_manager.upsert_material_density(
            "TiO2",
            phase="rutile",
            theoretical_density=4.25,
            unit_cell_volume=62.435,
            z=2,
        )
        anatase_key, records = lab_manager.upsert_material_density(
            "TiO2",
            phase="anatase",
            theoretical_density=3.89,
            unit_cell_volume=136.251,
            z=4,
        )

        self.assertEqual(rutile_key, "TiO2__rutile")
        self.assertEqual(anatase_key, "TiO2__anatase")
        self.assertEqual(records[rutile_key]["formula"], "TiO2")
        self.assertEqual(records[anatase_key]["phase"], "anatase")
        self.assertEqual(records[anatase_key]["origin"], "Lab entry")
        self.assertEqual(len(records), 2)


if __name__ == "__main__":
    unittest.main()
