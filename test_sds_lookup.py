import unittest
import urllib.parse

from stoichio.sds_lookup import build_sds_lookup_candidates


class SdsLookupTests(unittest.TestCase):
    def test_valid_cas_builds_candidate(self):
        result = build_sds_lookup_candidates("1309-37-1", "Sigma-Aldrich", "Fe2O3")

        self.assertGreaterEqual(len(result["candidates"]), 1)
        self.assertIn("not verified", result["warnings"][0])

    def test_invalid_cas_raises_value_error(self):
        with self.assertRaises(ValueError):
            build_sds_lookup_candidates("123-45-6", "Sigma-Aldrich")

    def test_query_is_normal_sentence_with_company_material_and_cas(self):
        result = build_sds_lookup_candidates("1309-37-1", "ThermoScientific", "Fe2O3")
        url = result["candidates"][0]["url"]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]

        self.assertEqual(query, "SDS for Thermo Scientific Fe2O3 1309-37-1")

    def test_missing_company_does_not_block_lookup(self):
        result = build_sds_lookup_candidates("1309-37-1", "", "Fe2O3")

        self.assertEqual(len(result["warnings"]), 1)
        self.assertTrue(result["candidates"])

    def test_query_does_not_force_pdf_or_quote_terms(self):
        result = build_sds_lookup_candidates("1309-37-1", "Sigma-Aldrich", "Fe2O3")
        url = result["candidates"][0]["url"]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]

        self.assertNotIn('"', query)
        self.assertNotIn("filetype", query.lower())
        self.assertNotIn("pdf", query.lower())

    def test_pubchem_is_not_used_as_sds_source(self):
        result = build_sds_lookup_candidates("1309-37-1", "Sigma-Aldrich", "Fe2O3")
        text = " ".join(
            [candidate["label"] + " " + candidate["url"] for candidate in result["candidates"]]
        ).lower()

        self.assertNotIn("pubchem", text)

    def test_bgu_nano_fab_is_not_primary_source(self):
        result = build_sds_lookup_candidates("1309-37-1", "Sigma-Aldrich", "Fe2O3")
        primary = result["candidates"][0]
        text = f"{primary['label']} {primary['url']}".lower()

        self.assertNotIn("bgu", text)
        self.assertNotIn("nano-fab", text)

    def test_all_candidates_require_review(self):
        result = build_sds_lookup_candidates("1309-37-1", "Sigma-Aldrich", "Fe2O3")

        self.assertTrue(result["candidates"])
        self.assertTrue(all(candidate["requiresReview"] is True for candidate in result["candidates"]))


if __name__ == "__main__":
    unittest.main()
