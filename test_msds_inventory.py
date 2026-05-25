import os
import tempfile
import unittest

from stoichio.msds_inventory import (
    build_msds_binder_pdf,
    closet_label,
    find_known_identity,
    load_msds_inventory,
    save_msds_inventory_item,
)


class MsdsInventoryTest(unittest.TestCase):
    def setUp(self):
        self.previous_cwd = os.getcwd()
        self.tempdir = tempfile.TemporaryDirectory()
        os.chdir(self.tempdir.name)

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.tempdir.cleanup()

    def test_closet_label_is_derived_from_fixed_mapping(self):
        self.assertEqual(closet_label(1), "1 \u2014 Powders")
        self.assertEqual(closet_label("4"), "4 \u2014 Fridge")

    def test_powders_auto_import_once(self):
        first = load_msds_inventory()
        second = load_msds_inventory()
        self.assertEqual(len(first), len(second))
        self.assertIn("Fe2O3", {item["nameOrFormula"] for item in first})
        fe = next(item for item in first if item["nameOrFormula"] == "Fe2O3")
        self.assertEqual(fe["closetNumber"], 1)
        self.assertEqual(fe["closetLabel"], "1 \u2014 Powders")

    def test_cas_and_name_lookup_use_known_records_only(self):
        saved, _ = save_msds_inventory_item({
            "casNumber": "7732-18-5",
            "nameOrFormula": "Water",
            "purity": "HPLC",
            "closetNumber": 4,
            "msdsExternalUrl": "",
        })

        by_cas = find_known_identity(cas_number="7732-18-5")
        by_name = find_known_identity(name_or_formula="Water")
        unknown = find_known_identity(cas_number="")

        self.assertEqual(by_cas["id"], saved["id"])
        self.assertEqual(by_name["casNumber"], "7732-18-5")
        self.assertIsNone(unknown)

    def test_msds_binder_generates_pdf_even_without_uploaded_files(self):
        save_msds_inventory_item({
            "casNumber": "7732-18-5",
            "nameOrFormula": "Water",
            "purity": "HPLC",
            "closetNumber": 4,
            "msdsExternalUrl": "https://example.com/water-sds.pdf",
        })
        pdf = build_msds_binder_pdf()
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"Lab Inventory MSDS Binder", pdf)


if __name__ == "__main__":
    unittest.main()
