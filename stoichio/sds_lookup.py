"""Review-only SDS/MSDS search candidate helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from stoichio.msds_inventory import canonical_company_name, company_identity_key, company_sds_search_terms, normalize_cas_number


_UNVERIFIED_WARNING = (
    "SDS lookup candidates are not verified. Review the supplier, CAS number, "
    "product, region, and revision date before lab use."
)


def build_sds_lookup_candidates(cas_number: str, company: str, name_or_formula: str = "") -> dict[str, Any]:
    cas = normalize_cas_number(cas_number) if str(cas_number or "").strip() else ""
    canonical_supplier = canonical_company_name(company)
    supplier_terms = company_sds_search_terms(company)
    material = _clean_text(name_or_formula)

    warnings = [_UNVERIFIED_WARNING]

    candidates = []
    for candidate in _supplier_specific_candidates(canonical_supplier, material, cas):
        candidates.append(candidate)
    search_suppliers = supplier_terms or [""]
    for index, supplier in enumerate(search_suppliers):
        terms = ["SDS", "for"]
        if supplier:
            terms.append(supplier)
        if material:
            terms.append(material)
        if cas:
            terms.append(cas)
        query = " ".join(terms)
        if cas or supplier or material:
            label = "SDS search" if index == 0 else f"SDS search: {supplier}"
            candidates.append(_candidate(label, _search_url(query)))

    return {
        "warnings": warnings,
        "candidates": candidates,
    }


def _supplier_specific_candidates(supplier: str, material: str, cas: str) -> list[dict[str, Any]]:
    supplier_key = company_identity_key(supplier)
    if supplier_key != "biolabltd":
        return []

    identity_terms = _query_terms("Bio-Lab Ltd.", material, cas)
    return [
        _candidate(
            "Bio-Lab official website search",
            _search_url(" ".join(["site:biolab-chemicals.com", "SDS", *identity_terms])),
        ),
        _candidate(
            "Bio-Lab legacy domain search",
            _search_url(" ".join(["site:bio-lab.co.il", "SDS", *identity_terms])),
        ),
        _candidate(
            "Bio-Lab search without BGU results",
            _search_url(" ".join(["SDS", "for", *identity_terms, "-bgu", "-ben-gurion", "-nano-fab"])),
        ),
    ]


def _query_terms(supplier: str, material: str, cas: str) -> list[str]:
    terms = []
    if supplier:
        terms.append(supplier)
    if material:
        terms.append(material)
    if cas:
        terms.append(cas)
    return terms


def _search_url(query: str) -> str:
    return f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"


def _candidate(label: str, url: str, kind: str = "search") -> dict[str, Any]:
    return {
        "label": label,
        "url": url,
        "kind": kind,
        "requiresReview": True,
    }


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())
