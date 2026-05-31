"""Review-only SDS/MSDS search candidate helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from stoichio.msds_inventory import normalize_cas_number


_UNVERIFIED_WARNING = (
    "SDS lookup candidates are not verified. Review the supplier, CAS number, "
    "product, region, and revision date before lab use."
)


def build_sds_lookup_candidates(cas_number: str, company: str, name_or_formula: str = "") -> dict[str, Any]:
    cas = normalize_cas_number(cas_number) if str(cas_number or "").strip() else ""
    supplier = _clean_text(company)
    material = _clean_text(name_or_formula)

    warnings = [_UNVERIFIED_WARNING]

    terms = ["SDS", "for"]
    if supplier:
        terms.append(supplier)
    if material:
        terms.append(material)
    if cas:
        terms.append(cas)

    candidates = []
    if cas or supplier or material:
        candidates.append(_candidate("SDS search", _search_url(" ".join(terms))))

    return {
        "warnings": warnings,
        "candidates": candidates,
    }


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
