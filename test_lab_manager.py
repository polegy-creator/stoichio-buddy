import tempfile
import unittest

from stoichio import lab_manager


class LabManagerPowderRelevanceTests(unittest.TestCase):
    def test_relevant_powders_hide_non_target_cations(self):
        powders = {
            "Fe2O3": {"elements": {"Fe": 2, "O": 3}},
            "TiO2": {"elements": {"Ti": 1, "O": 2}},
            "Y2O3": {"elements": {"Y": 2, "O": 3}},
            "BaTiO3": {"elements": {"Ba": 1, "Ti": 1, "O": 3}},
        }

        relevant, hidden, target_elements, error = lab_manager.relevant_powders_for_target("FeTiO3", powders)

        self.assertIsNone(error)
        self.assertEqual(target_elements, {"Fe", "Ti"})
        self.assertEqual(relevant, ["Fe2O3", "TiO2"])
        self.assertIn("Y2O3", hidden)
        self.assertIn("BaTiO3", hidden)

    def test_relevant_powders_allow_common_decomposition_anions(self):
        powders = {
            "BaCO3": {"elements": {"Ba": 1, "C": 1, "O": 3}},
            "TiO2": {"elements": {"Ti": 1, "O": 2}},
            "Fe2O3": {"elements": {"Fe": 2, "O": 3}},
        }

        relevant, hidden, _, error = lab_manager.relevant_powders_for_target("BaTiO3", powders)

        self.assertIsNone(error)
        self.assertEqual(relevant, ["BaCO3", "TiO2"])
        self.assertEqual(hidden, ["Fe2O3"])

    def test_relevant_powders_show_all_until_target_is_parseable(self):
        powders = {
            "Fe2O3": {"elements": {"Fe": 2, "O": 3}},
            "TiO2": {"elements": {"Ti": 1, "O": 2}},
        }

        relevant, hidden, target_elements, error = lab_manager.relevant_powders_for_target("Fe(", powders)

        self.assertEqual(relevant, ["Fe2O3", "TiO2"])
        self.assertEqual(hidden, [])
        self.assertEqual(target_elements, set())
        self.assertIsNotNone(error)


class LabManagerPowderSetTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_powder_sets_file = lab_manager.POWDER_SETS_FILE
        self.old_storage_backend = lab_manager._storage_backend
        lab_manager.POWDER_SETS_FILE = f"{self.tempdir.name}/powder_sets.json"
        lab_manager._storage_backend = None

    def tearDown(self):
        lab_manager.POWDER_SETS_FILE = self.old_powder_sets_file
        lab_manager._storage_backend = self.old_storage_backend
        self.tempdir.cleanup()

    def test_save_and_match_powder_set_by_target_family(self):
        record_id, records = lab_manager.save_powder_set(
            "FeTiO3",
            ["Fe2O3", "TiO2"],
            name="Fe-Ti standard",
        )

        matches = lab_manager.matching_powder_sets_for_target("Fe1.98Ti0.02O3", records)

        self.assertEqual(matches[0][0], record_id)
        self.assertEqual(records[record_id]["family"], "Fe-Ti")
        self.assertEqual(records[record_id]["powders"], ["Fe2O3", "TiO2"])

    def test_record_powder_set_use_updates_usage(self):
        record_id, _ = lab_manager.save_powder_set(
            "BaTiO3",
            ["BaCO3", "TiO2"],
            name="Ba-Ti carbonate set",
        )

        _, records = lab_manager.record_powder_set_use(record_id)

        self.assertEqual(records[record_id]["use_count"], 1)
        self.assertTrue(records[record_id]["last_used_at"])


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

    def test_target_owner_names_are_case_insensitive_and_display_capitalized(self):
        history = lab_manager.log_synthesis(
            "Fe1.98Ti0.02O3",
            15.615,
            {"Fe2O3": 15.458808, "TiO2": 0.156192},
            selected_powders=["Fe2O3", "TiO2"],
            target_for="  vinoth  ",
        )

        self.assertEqual(history[-1]["target_for"], "Vinoth")
        self.assertEqual(history[-1]["target_id"], "Vinoth-T001")
        self.assertEqual(lab_manager.next_target_number(history, "VINOTH"), 2)

    def test_load_history_migrates_old_owner_name_case(self):
        lab_manager.save_history(
            [
                {
                    "entry_id": "old-entry",
                    "entry_type": "synthesis",
                    "recipe_id": "R001",
                    "recipe_number": 1,
                    "target": "Fe1.98Ti0.02O3",
                    "mass": 15.615,
                    "recipe": {"Fe2O3": 15.458808, "TiO2": 0.156192},
                    "target_for": "vinoth",
                    "target_number": 1,
                    "target_id": "vinoth-T001",
                }
            ]
        )

        history = lab_manager.load_history()

        self.assertEqual(history[0]["target_for"], "Vinoth")
        self.assertEqual(history[0]["target_id"], "Vinoth-T001")
        self.assertEqual(lab_manager.next_target_number(history, "vInOtH"), 2)

    def test_update_recipe_planning_backfills_target_height_details(self):
        history = lab_manager.log_synthesis(
            "Ti0.82Yb0.15Er0.03",
            9.724402961875791,
            {"Er2O3": 0.55362, "Yb2O3": 2.8519, "TiO2": 6.318883},
            selected_powders=["Er2O3", "Yb2O3", "TiO2"],
            target_for="Vinoth",
            calculation={"mass_basis": "total_precursor_powder"},
        )

        entry, updated_history = lab_manager.update_recipe_planning(
            history[-1]["entry_id"],
            target_height_mm=3.9,
            die_diameter_mm=25.05,
            theoretical_density_g_cm3=5.24,
            target_porosity_percent=5,
            density_source="Manual lab note",
        )
        planning = entry["calculation"]["planning"]

        self.assertEqual(updated_history[-1]["entry_id"], entry["entry_id"])
        self.assertEqual(planning["amount_mode"], "Target height")
        self.assertEqual(planning["target_height_mm"], 3.9)
        self.assertEqual(planning["die_diameter_mm"], 25.05)
        self.assertEqual(planning["target_porosity_percent"], 5)
        self.assertEqual(planning["theoretical_density_g_cm3"], 5.24)
        self.assertEqual(planning["density_source"], "Manual lab note")
        self.assertIn("solid_volume_cm3", planning)
        self.assertIn("calculated_target_mass_g", planning)


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

    def test_related_material_density_records_rank_by_cation_fraction(self):
        records = {
            "TiO2__rutile": {
                "formula": "TiO2",
                "phase": "rutile",
                "verification_status": "Preferred for formula",
            },
            "FeTiO3__ilmenite": {
                "formula": "FeTiO3",
                "phase": "ilmenite",
                "verification_status": "Lab checked",
            },
            "Fe2O3__hematite-alpha": {
                "formula": "Fe2O3",
                "phase": "hematite alpha",
                "verification_status": "Codex seeded - verify before use",
            },
            "Fe3O4__magnetite": {
                "formula": "Fe3O4",
                "phase": "magnetite",
                "verification_status": "Lab checked",
            },
            "BaFe12O19__hexaferrite": {
                "formula": "BaFe12O19",
                "phase": "hexaferrite",
                "verification_status": "Lab checked",
            },
        }

        related = lab_manager.related_material_density_records("Fe1.98Ti0.02O3", records)
        related_keys = [record_key for record_key, _ in related]

        self.assertEqual(related_keys[:4], [
            "Fe2O3__hematite-alpha",
            "Fe3O4__magnetite",
            "FeTiO3__ilmenite",
            "TiO2__rutile",
        ])
        self.assertGreater(
            related_keys.index("BaFe12O19__hexaferrite"),
            related_keys.index("TiO2__rutile"),
        )

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

    def test_material_density_records_keep_structured_source_fields(self):
        record_key, records = lab_manager.upsert_material_density(
            "Fe2O3",
            phase="hematite",
            theoretical_density=5.25,
            source="Hematite refinement. COD 1011241. https://doi.org/10.1000/example",
            source_url="https://www.crystallography.net/cod/1011241.html",
            doi="10.1000/example",
            cod_id="1011241",
            paper_title="Hematite structural refinement",
        )

        record = records[record_key]

        self.assertEqual(record["source_url"], "https://www.crystallography.net/cod/1011241.html")
        self.assertEqual(record["doi"], "10.1000/example")
        self.assertEqual(record["cod_id"], "1011241")
        self.assertEqual(record["paper_title"], "Hematite structural refinement")

    def test_material_density_records_extract_source_url_doi_and_cod_id(self):
        record = lab_manager.normalize_density_record(
            "Fe2O3",
            {
                "formula": "Fe2O3",
                "theoretical_density_g_cm3": 5.25,
                "source": "Paper COD 1011241 https://doi.org/10.1000/example",
            },
        )

        self.assertEqual(record["source_url"], "https://doi.org/10.1000/example")
        self.assertEqual(record["doi"], "10.1000/example")
        self.assertEqual(record["cod_id"], "1011241")

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

    def test_inventory_keeps_powder_variants_separate(self):
        lab_manager.set_inventory_quantity("Fe2O3 | purity 99.9% | vendor A", 10, reason="Vendor A stock")
        lab_manager.set_inventory_quantity("Fe2O3 | purity 95% | vendor B", 4, reason="Vendor B stock")

        inventory = lab_manager.load_inventory()

        self.assertEqual(inventory["Fe2O3 | purity 99.9% | vendor A"], 10)
        self.assertEqual(inventory["Fe2O3 | purity 95% | vendor B"], 4)

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


class LabManagerBackupTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = f"{self.tempdir.name}/history.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_save_json_file_rotates_previous_file_into_backup(self):
        lab_manager.save_json_file(self.path, [{"entry_id": "first"}])
        lab_manager.save_json_file(self.path, [{"entry_id": "second"}])

        backup_dir = f"{self.tempdir.name}/backups"
        backups = lab_manager.os.listdir(backup_dir)

        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0].startswith("history_"))
        backup_data = lab_manager.load_json_file(f"{backup_dir}/{backups[0]}", [])
        self.assertEqual(backup_data, [{"entry_id": "first"}])


if __name__ == "__main__":
    unittest.main()
