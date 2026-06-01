import unittest
import os
import tempfile

from stoichio.powders import (
    load_powders,
    normalize_powder,
    normalize_powder_record,
    powder_display_name,
    powder_key_for,
    sync_powders_from_msds_inventory,
    update_powder_notes,
)


class PowderMetadataTests(unittest.TestCase):
    def test_normalize_powder_record_keeps_safety_metadata(self):
        record = normalize_powder_record({
            "elements": {"Fe": 2, "O": 3},
            "cas": "1309-37-1",
            "purity": "99.9%",
            "supplier": "Lab supplier",
            "casSourceUrl": "https://pubchem.ncbi.nlm.nih.gov/compound/518696",
            "notes": "kept for lab label",
        })

        self.assertEqual(record["casNumber"], "1309-37-1")
        self.assertEqual(record["purity"], "99.9%")
        self.assertEqual(record["supplier"], "Lab supplier")
        self.assertEqual(record["casSourceUrl"], "https://pubchem.ncbi.nlm.nih.gov/compound/518696")
        self.assertEqual(record["notes"], "kept for lab label")
        self.assertEqual(record["elements"], {"Fe": 2.0, "O": 3.0})

    def test_powder_variants_keep_formula_but_distinguish_vendor_and_purity(self):
        key = powder_key_for("fe2o3", purity="99.9", company="Sigma/Aldrich")
        record = normalize_powder_record(
            {
                "formula": "Fe2O3",
                "elements": {"Fe": 2, "O": 3},
                "purity": "99.9%",
                "company": "Sigma/Aldrich",
            },
            fallback_formula="Fe2O3",
        )

        self.assertEqual(key, "Fe2O3 | purity 99.9% | vendor Sigma-Aldrich")
        self.assertEqual(normalize_powder(key), key)
        self.assertEqual(record["formula"], "Fe2O3")
        self.assertEqual(powder_display_name(key, record), "Fe2O3 | 99.9% | Sigma/Aldrich")


class PowderDatabaseSyncTests(unittest.TestCase):
    def setUp(self):
        self.previous_cwd = os.getcwd()
        self.tempdir = tempfile.TemporaryDirectory()
        os.chdir(self.tempdir.name)

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.tempdir.cleanup()

    def test_msds_powder_records_create_vendor_and_purity_variants(self):
        summary = sync_powders_from_msds_inventory([
            {
                "id": "msds-a",
                "casNumber": "1309-37-1",
                "nameOrFormula": "Fe2O3",
                "purity": "99.9",
                "company": "Vendor A",
                "closetNumber": 1,
            },
            {
                "id": "msds-b",
                "casNumber": "1309-37-1",
                "nameOrFormula": "Fe2O3",
                "purity": "99.5%",
                "company": "Vendor B",
                "closetNumber": 1,
            },
            {
                "id": "acid",
                "casNumber": "7647-01-0",
                "nameOrFormula": "HCl",
                "purity": "37%",
                "company": "Vendor C",
                "closetNumber": 2,
            },
        ])
        powders = load_powders()

        self.assertEqual(summary["created"], 2)
        self.assertIn("Fe2O3", powders)
        self.assertIn("Fe2O3 | purity 99.9% | vendor Vendor A", powders)
        self.assertIn("Fe2O3 | purity 99.5% | vendor Vendor B", powders)
        self.assertNotIn("HCl | purity 37% | vendor Vendor C", powders)
        self.assertEqual(powders["Fe2O3 | purity 99.9% | vendor Vendor A"]["company"], "Vendor A")
        self.assertEqual(powders["Fe2O3 | purity 99.9% | vendor Vendor A"]["purity"], "99.9%")

    def test_powder_notes_can_be_saved_and_cleared(self):
        powder, powders = update_powder_notes("Fe2O3", "Use bottle from upper shelf")
        self.assertEqual(powders[powder]["notes"], "Use bottle from upper shelf")

        powder, powders = update_powder_notes("Fe2O3", "")
        self.assertNotIn("notes", powders[powder])


if __name__ == "__main__":
    unittest.main()
