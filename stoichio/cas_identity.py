"""CAS-based chemical identity lookup helpers."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from stoichio.msds_inventory import normalize_cas_number, preferred_lab_material_name


_PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_IDENTITY_WARNING = (
    "CAS identity metadata was applied from a saved CAS record or PubChem. "
    "Supplier SDS PDFs still need to match the material, manufacturer, and bottle."
)


def lookup_cas_identity(
    cas_number: str,
    known_items: list[dict[str, Any]] | None = None,
    timeout_sec: float = 6,
    prefer_name: bool = False,
) -> dict[str, Any]:
    cas = normalize_cas_number(cas_number)
    warnings = [_IDENTITY_WARNING]

    local_identity = _local_identity(cas, known_items or [], prefer_name=prefer_name)
    if local_identity:
        return {
            "source": "local",
            "warnings": warnings,
            "identity": local_identity,
        }

    pubchem_identity = _pubchem_identity(cas, timeout_sec=timeout_sec, prefer_name=prefer_name)
    if pubchem_identity:
        return {
            "source": "pubchem",
            "warnings": warnings,
            "identity": pubchem_identity,
        }

    return {
        "source": "none",
        "warnings": warnings + ["No PubChem identity match was found for this CAS number."],
        "identity": None,
    }


def _local_identity(cas_number: str, known_items: list[dict[str, Any]], prefer_name: bool = False) -> dict[str, Any] | None:
    for item in known_items:
        if item.get("casNumber") != cas_number:
            continue
        name_or_formula = _preferred_identity_text(cas_number, item, prefer_name=prefer_name)
        if not name_or_formula:
            continue
        return {
            "casNumber": cas_number,
            "nameOrFormula": name_or_formula,
            "identityStatus": "CAS identity applied",
            "source": "local saved CAS record",
            "casSource": item.get("casSource") or "Saved lab CAS record",
            "casSourceUrl": item.get("casSourceUrl") or "",
            "pubchemCid": item.get("pubchemCid") or "",
            "pubchemFormula": item.get("pubchemFormula") or "",
            "pubchemIupacName": item.get("pubchemIupacName") or "",
            "pubchemTitle": item.get("pubchemTitle") or "",
        }
    return None


def _pubchem_identity(cas_number: str, timeout_sec: float, prefer_name: bool = False) -> dict[str, Any] | None:
    path_cas = urllib.parse.quote(cas_number, safe="")
    urls = [
        f"{_PUBCHEM_BASE}/compound/name/{path_cas}/property/MolecularFormula,IUPACName,Title/JSON",
        f"{_PUBCHEM_BASE}/compound/xref/RN/{path_cas}/property/MolecularFormula,IUPACName,Title/JSON",
    ]
    last_error = None
    for url in urls:
        try:
            records = _pubchem_property_records(url, timeout_sec)
        except _PubChemNotFound:
            continue
        except RuntimeError as exc:
            last_error = exc
            continue
        if records:
            return _identity_from_pubchem_record(cas_number, records[0], prefer_name=prefer_name)
    if last_error:
        raise last_error
    return None


def _pubchem_property_records(url: str, timeout_sec: float) -> list[dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": "stoichio-buddy"})
    try:
        with _open_pubchem_url(request, timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise _PubChemNotFound() from exc
        raise RuntimeError("PubChem identity lookup failed.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("PubChem identity lookup failed.") from exc

    return payload.get("PropertyTable", {}).get("Properties", [])


def _open_pubchem_url(request: urllib.request.Request, timeout_sec: float):
    context = _pubchem_ssl_context()
    if context is None:
        return urllib.request.urlopen(request, timeout=timeout_sec)
    return urllib.request.urlopen(request, timeout=timeout_sec, context=context)


def _pubchem_ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _preferred_identity_text(cas_number: str, item: dict[str, Any], prefer_name: bool = False) -> str:
    if prefer_name:
        return (
            preferred_lab_material_name(cas_number)
            or str(item.get("pubchemTitle") or "").strip()
            or str(item.get("pubchemIupacName") or "").strip()
            or str(item.get("nameOrFormula") or "").strip()
            or str(item.get("pubchemFormula") or "").strip()
        )
    return (
        str(item.get("nameOrFormula") or "").strip()
        or str(item.get("pubchemFormula") or "").strip()
        or str(item.get("pubchemTitle") or "").strip()
        or str(item.get("pubchemIupacName") or "").strip()
    )


def _identity_from_pubchem_record(cas_number: str, record: dict[str, Any], prefer_name: bool = False) -> dict[str, Any]:
    cid = str(record.get("CID") or "").strip()
    formula = str(record.get("MolecularFormula") or "").strip()
    iupac = str(record.get("IUPACName") or "").strip()
    title = str(record.get("Title") or "").strip()
    lab_name = preferred_lab_material_name(cas_number)

    return {
        "casNumber": cas_number,
        "nameOrFormula": (lab_name or title or iupac or formula) if prefer_name else (formula or lab_name or title or iupac),
        "identityStatus": "CAS identity applied",
        "source": "PubChem identity metadata",
        "casSource": "PubChem PUG REST",
        "casSourceUrl": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}" if cid else "",
        "pubchemCid": cid,
        "pubchemFormula": formula,
        "pubchemIupacName": iupac,
        "pubchemTitle": title,
    }


class _PubChemNotFound(Exception):
    pass
