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

    def test_company_appears_url_encoded_in_primary_query(self):
        result = build_sds_lookup_candidates("1309-37-1", "Acme Chemicals", "Fe2O3")
        url = result["candidates"][0]["url"]

        self.assertIn("Acme+Chemicals", url)
        self.assertIn("1309-37-1", urllib.parse.unquote_plus(url))

    def test_missing_company_returns_warning(self):
        result = build_sds_lookup_candidates("1309-37-1", "", "Fe2O3")

        self.assertTrue(any("company/manufacturer" in warning for warning in result["warnings"]))

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
