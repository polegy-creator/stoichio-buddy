import unittest

from stoichio.powders import (
    normalize_powder,
    normalize_powder_record,
    powder_display_name,
    powder_key_for,
)


class PowderMetadataTests(unittest.TestCase):
    def test_normalize_powder_record_keeps_safety_metadata(self):
        record = normalize_powder_record({
            "elements": {"Fe": 2, "O": 3},
            "cas": "1309-37-1",
            "purity": "99.9%",
            "supplier": "Lab supplier",
            "casSourceUrl": "https://pubchem.ncbi.nlm.nih.gov/compound/518696",
        })

        self.assertEqual(record["casNumber"], "1309-37-1")
        self.assertEqual(record["purity"], "99.9%")
        self.assertEqual(record["supplier"], "Lab supplier")
        self.assertEqual(record["casSourceUrl"], "https://pubchem.ncbi.nlm.nih.gov/compound/518696")
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


if __name__ == "__main__":
    unittest.main()
