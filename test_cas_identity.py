import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from stoichio.cas_identity import lookup_cas_identity


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class CasIdentityTests(unittest.TestCase):
    def test_local_identity_is_used_before_pubchem(self):
        known = [{
            "casNumber": "1309-37-1",
            "nameOrFormula": "Fe2O3",
            "company": "Do not autofill",
            "purity": "Do not autofill",
            "closetNumber": 1,
            "pubchemCid": "518696",
        }]

        with patch("stoichio.cas_identity.urllib.request.urlopen") as urlopen:
            result = lookup_cas_identity("1309-37-1", known)

        urlopen.assert_not_called()
        self.assertEqual(result["source"], "local")
        self.assertEqual(result["identity"]["nameOrFormula"], "Fe2O3")
        self.assertNotIn("company", result["identity"])
        self.assertNotIn("purity", result["identity"])
        self.assertNotIn("closetNumber", result["identity"])

    def test_pubchem_identity_fills_formula_and_metadata(self):
        payload = {
            "PropertyTable": {
                "Properties": [{
                    "CID": 518696,
                    "MolecularFormula": "Fe2O3",
                    "IUPACName": "oxo(oxoferriooxy)iron",
                    "Title": "Ferric Oxide",
                }]
            }
        }

        with patch("stoichio.cas_identity.urllib.request.urlopen", return_value=_FakeResponse(payload)):
            result = lookup_cas_identity("1309-37-1", [])

        identity = result["identity"]
        self.assertEqual(result["source"], "pubchem")
        self.assertEqual(identity["nameOrFormula"], "Fe2O3")
        self.assertEqual(identity["pubchemCid"], "518696")
        self.assertEqual(identity["pubchemFormula"], "Fe2O3")
        self.assertEqual(identity["pubchemTitle"], "Ferric Oxide")
        self.assertEqual(identity["identityStatus"], "CAS identity applied")
        self.assertIn("pubchem.ncbi.nlm.nih.gov/compound/518696", identity["casSourceUrl"])

    def test_pubchem_identity_can_prefer_common_name_for_non_powder_closets(self):
        payload = {
            "PropertyTable": {
                "Properties": [{
                    "CID": 176,
                    "MolecularFormula": "C2H4O2",
                    "IUPACName": "acetic acid",
                    "Title": "Acetic Acid",
                }]
            }
        }

        with patch("stoichio.cas_identity.urllib.request.urlopen", return_value=_FakeResponse(payload)):
            result = lookup_cas_identity("64-19-7", [], prefer_name=True)

        identity = result["identity"]
        self.assertEqual(result["source"], "pubchem")
        self.assertEqual(identity["nameOrFormula"], "Acetic Acid")
        self.assertEqual(identity["pubchemFormula"], "C2H4O2")

    def test_pubchem_identity_uses_lab_preferred_name_when_available(self):
        payload = {
            "PropertyTable": {
                "Properties": [{
                    "CID": 14796,
                    "MolecularFormula": "GeO2",
                    "IUPACName": "dioxogermane",
                    "Title": "Dioxogermane",
                }]
            }
        }

        with patch("stoichio.cas_identity.urllib.request.urlopen", return_value=_FakeResponse(payload)):
            result = lookup_cas_identity("1310-53-8", [], prefer_name=True)

        identity = result["identity"]
        self.assertEqual(result["source"], "pubchem")
        self.assertEqual(identity["nameOrFormula"], "Germanium Dioxide")
        self.assertEqual(identity["pubchemFormula"], "GeO2")

    def test_pubchem_xref_fallback_is_used_when_name_route_fails(self):
        payload = {
            "PropertyTable": {
                "Properties": [{
                    "CID": 176,
                    "MolecularFormula": "C2H4O2",
                    "IUPACName": "acetic acid",
                }]
            }
        }
        http_error = urllib.error.HTTPError(
            url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/64-19-7",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

        with patch(
            "stoichio.cas_identity.urllib.request.urlopen",
            side_effect=[http_error, _FakeResponse(payload)],
        ):
            result = lookup_cas_identity("64-19-7", [])
        http_error.close()

        self.assertEqual(result["source"], "pubchem")
        self.assertEqual(result["identity"]["nameOrFormula"], "C2H4O2")
        self.assertEqual(result["identity"]["pubchemCid"], "176")

    def test_invalid_cas_raises_value_error(self):
        with self.assertRaises(ValueError):
            lookup_cas_identity("123-45-6", [])


if __name__ == "__main__":
    unittest.main()
