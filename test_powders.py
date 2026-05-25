import unittest

from stoichio.powders import normalize_powder_record


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


if __name__ == "__main__":
    unittest.main()
