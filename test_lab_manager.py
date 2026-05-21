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

    def test_related_material_density_records_match_target_cations(self):
        records = {
            "Fe2O3__hematite-alpha": {
                "formula": "Fe2O3",
                "phase": "hematite alpha",
                "display_name": "Fe2O3 (hematite alpha)",
            },
            "Ti2O3__tistarite-alpha": {
                "formula": "Ti2O3",
                "phase": "tistarite alpha",
                "display_name": "Ti2O3 (tistarite alpha)",
            },
            "BaTiO3__tetragonal-perovskite": {
                "formula": "BaTiO3",
                "phase": "tetragonal perovskite",
                "display_name": "BaTiO3 (tetragonal perovskite)",
            },
            "ZnO__zincite-wurtzite": {
                "formula": "ZnO",
                "phase": "zincite wurtzite",
                "display_name": "ZnO (zincite wurtzite)",
            },
        }

        related = lab_manager.related_material_density_records("Fe1.98Ti0.02O3", records)
        related_keys = [record_key for record_key, _ in related]

        self.assertIn("Fe2O3__hematite-alpha", related_keys)
        self.assertIn("Ti2O3__tistarite-alpha", related_keys)
        self.assertIn("BaTiO3__tetragonal-perovskite", related_keys)
        self.assertNotIn("ZnO__zincite-wurtzite", related_keys)

    def test_material_density_records_keep_trust_status(self):
        record_key, records = lab_manager.upsert_material_density(
            "Fe2O3",
            phase="hematite",
            theoretical_density=5.25,
            unit_cell_volume=302.722,
            z=6,
            verification_status="Preferred for formula",
            verified_by="Daniel",
            verified_date="2026-05-21",
        )

        record = records[record_key]

        self.assertEqual(record["verification_status"], "Preferred for formula")
        self.assertEqual(record["verified_by"], "Daniel")
        self.assertEqual(record["verified_date"], "2026-05-21")

    def test_only_one_density_record_is_preferred_per_formula(self):
        hematite_key, _ = lab_manager.upsert_material_density(
            "Fe2O3",
            phase="hematite",
            theoretical_density=5.25,
            verification_status="Preferred for formula",
            verified_by="Daniel",
            verified_date="2026-05-21",
        )
        corundum_key, records = lab_manager.upsert_material_density(
            "Fe2O3",
            phase="corundum check",
            theoretical_density=5.24,
            verification_status="Preferred for formula",
            verified_by="Maya",
            verified_date="2026-05-22",
        )

        self.assertEqual(records[corundum_key]["verification_status"], "Preferred for formula")
        self.assertEqual(records[hematite_key]["verification_status"], "Lab checked")

    def test_review_status_helpers_update_and_prefer_records(self):
        rutile_key, _ = lab_manager.upsert_material_density(
            "TiO2",
            phase="rutile",
            theoretical_density=4.25,
            verification_status="Codex seeded - verify before use",
        )
        anatase_key, _ = lab_manager.upsert_material_density(
            "TiO2",
            phase="anatase",
            theoretical_density=3.89,
            verification_status="Lab entry - unverified",
        )

        _, records = lab_manager.update_material_density_review_status(
            rutile_key,
            "Lab checked",
            verified_by="Daniel",
            verified_date="2026-05-21",
        )
        self.assertEqual(records[rutile_key]["verification_status"], "Lab checked")
        self.assertEqual(records[rutile_key]["verified_by"], "Daniel")

        _, records = lab_manager.set_preferred_material_density(
            anatase_key,
            verified_by="Maya",
            verified_date="2026-05-22",
        )
        self.assertEqual(records[anatase_key]["verification_status"], "Preferred for formula")
        self.assertEqual(records[rutile_key]["verification_status"], "Lab checked")

    def test_related_density_records_prefer_reviewed_sources(self):
        records = {
            "Fe2O3__codex": {
                "formula": "Fe2O3",
                "phase": "codex",
                "verification_status": "Codex seeded - verify before use",
            },
            "Fe2O3__preferred": {
                "formula": "Fe2O3",
                "phase": "preferred",
                "verification_status": "Preferred for formula",
            },
        }

        related = lab_manager.related_material_density_records("Fe1.98Ti0.02O3", records)

        self.assertEqual(related[0][0], "Fe2O3__preferred")


class LabManagerInventoryLogTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_inventory_file = lab_manager.INVENTORY_FILE
        self.old_inventory_log_file = lab_manager.INVENTORY_LOG_FILE
        self.old_storage_backend = lab_manager._storage_backend
        lab_manager.INVENTORY_FILE = f"{self.tempdir.name}/inventory.json"
        lab_manager.INVENTORY_LOG_FILE = f"{self.tempdir.name}/inventory_log.json"
        lab_manager._storage_backend = None

    def tearDown(self):
        lab_manager.INVENTORY_FILE = self.old_inventory_file
        lab_manager.INVENTORY_LOG_FILE = self.old_inventory_log_file
        lab_manager._storage_backend = self.old_storage_backend
        self.tempdir.cleanup()

    def test_inventory_quantity_changes_are_logged(self):
        lab_manager.set_inventory_quantity("TiO2", 150, reason="Initial stock")
        lab_manager.set_inventory_quantity("TiO2", 125, reason="Manual correction")

        log_entries = lab_manager.load_inventory_log()

        self.assertEqual(len(log_entries), 2)
        self.assertEqual(log_entries[0]["powder"], "TiO2")
        self.assertEqual(log_entries[0]["change_g"], 150)
        self.assertEqual(log_entries[1]["change_g"], -25)
        self.assertEqual(log_entries[1]["after_g"], 125)

    def test_recipe_deduction_is_logged(self):
        inventory = lab_manager.set_inventory_quantity("Fe2O3", 20, reason="Initial stock")
        lab_manager.consume_stock(
            inventory,
            {"Fe2O3": 2.5},
            reason="Saved recipe",
            recipe_id="R001",
        )

        log_entries = lab_manager.load_inventory_log()

        self.assertEqual(len(log_entries), 2)
        self.assertEqual(log_entries[-1]["action"], "recipe deduction")
        self.assertEqual(log_entries[-1]["recipe_id"], "R001")
        self.assertEqual(log_entries[-1]["before_g"], 20)
        self.assertEqual(log_entries[-1]["after_g"], 17.5)


if __name__ == "__main__":
    unittest.main()
