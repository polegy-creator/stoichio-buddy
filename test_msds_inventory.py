import os
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from stoichio.msds_inventory import (
    attach_msds_pdf,
    build_msds_binder_archive,
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

    def test_powder_cas_metadata_migrates_existing_blank_import(self):
        Path("powders.json").write_text(json.dumps({
            "Fe2O3": {
                "elements": {"Fe": 2, "O": 3},
                "casNumber": "1309-37-1",
                "casSourceUrl": "https://pubchem.ncbi.nlm.nih.gov/compound/518696",
                "pubchemCid": "518696",
            }
        }))
        Path("msds_inventory.json").write_text(json.dumps({
            "items": [{
                "id": "powder:Fe2O3",
                "casNumber": "",
                "nameOrFormula": "Fe2O3",
                "purity": "",
                "closetNumber": 1,
                "sourcePowderId": "powder:Fe2O3",
            }],
            "deletedPowderImports": [],
        }))

        items = load_msds_inventory()
        fe = next(item for item in items if item["nameOrFormula"] == "Fe2O3")

        self.assertEqual(fe["casNumber"], "1309-37-1")
        self.assertEqual(fe["casSourceUrl"], "https://pubchem.ncbi.nlm.nih.gov/compound/518696")
        self.assertEqual(fe["pubchemCid"], "518696")
        self.assertIn("needs lab verification", fe["identityStatus"])

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

    def test_same_cas_can_have_different_vendor_records(self):
        first, items = save_msds_inventory_item({
            "casNumber": "1309-37-1",
            "nameOrFormula": "Fe2O3",
            "purity": "99.9%",
            "company": "Vendor A",
            "closetNumber": 1,
        })
        second, items = save_msds_inventory_item({
            "casNumber": "1309-37-1",
            "nameOrFormula": "Fe2O3",
            "purity": "99.9%",
            "company": "Vendor B",
            "closetNumber": 1,
        })

        matching = [item for item in items if item["casNumber"] == "1309-37-1"]

        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual({item["company"] for item in matching}, {"Vendor A", "Vendor B"})

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

    def test_msds_binder_archive_groups_by_closet_and_preserves_source_and_pdf(self):
        saved, _ = save_msds_inventory_item({
            "casNumber": "1309-37-1",
            "nameOrFormula": "Fe2O3",
            "purity": "99.9%",
            "company": "Vendor A",
            "closetNumber": 1,
            "msdsExternalUrl": "https://example.com/fe2o3-sds.pdf",
        })
        attach_msds_pdf(
            saved["id"],
            "fe2o3_sds.pdf",
            "application/pdf",
            b"%PDF-1.4\n% test msds\n",
        )

        archive_bytes = build_msds_binder_archive()

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            self.assertIn("README.txt", names)
            self.assertIn("index.html", names)
            self.assertIn("inventory_index.json", names)
            self.assertIn("1 - Powders/index.html", names)
            self.assertIn("2 - Acids/index.html", names)

            material_sources = [
                name for name in names
                if name.startswith("1 - Powders/") and name.endswith("/source.html")
            ]
            material_pdfs = [
                name for name in names
                if name.startswith("1 - Powders/") and name.endswith("/fe2o3_sds.pdf")
            ]
            material_links = [
                name for name in names
                if name.startswith("1 - Powders/") and name.endswith("/source_link.url")
            ]

            self.assertEqual(len(material_pdfs), 1)
            material_folder = str(Path(material_pdfs[0]).parent)
            source_name = f"{material_folder}/source.html"
            shortcut_name = f"{material_folder}/source_link.url"

            self.assertIn(source_name, material_sources)
            self.assertIn(shortcut_name, material_links)
            source_html = archive.read(source_name).decode("utf-8")
            shortcut = archive.read(shortcut_name).decode("utf-8")

            self.assertIn("Vendor A", source_html)
            self.assertIn("https://example.com/fe2o3-sds.pdf", source_html)
            self.assertIn("URL=https://example.com/fe2o3-sds.pdf", shortcut)
            self.assertEqual(archive.read(material_pdfs[0]), b"%PDF-1.4\n% test msds\n")


if __name__ == "__main__":
    unittest.main()
