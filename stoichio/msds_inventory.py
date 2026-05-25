"""Inventory and MSDS/SDS records for lab materials."""

from __future__ import annotations

import base64
import io
import re
import textwrap
import uuid
from datetime import datetime
from typing import Any

from stoichio import storage
from stoichio.chemistry.formula_parser import normalize_formula


CLOSETS = {
    1: "Powders",
    2: "Acids",
    3: "Flammables",
    4: "Fridge",
}

_DEFAULT_STORE = {"items": [], "deletedPowderImports": []}
_CAS_RE = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")
_MAX_TEXT_LINES_PER_PAGE = 43


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def closet_label(closet_number: int | str) -> str:
    number = normalize_closet_number(closet_number)
    return f"{number} \u2014 {CLOSETS[number]}"


def closet_options() -> dict[int, str]:
    return dict(CLOSETS)


def normalize_closet_number(value: int | str | None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Choose one of the four fixed storage closets.") from exc
    if number not in CLOSETS:
        raise ValueError("Choose one of the four fixed storage closets.")
    return number


def normalize_cas_number(value: str | None) -> str:
    cas_number = str(value or "").strip()
    if not cas_number:
        return ""
    cas_number = re.sub(r"\s+", "", cas_number)
    match = _CAS_RE.fullmatch(cas_number)
    if not match or not cas_checksum_valid(cas_number):
        raise ValueError("CAS number does not pass the standard CAS format/checksum.")
    return cas_number


def cas_checksum_valid(cas_number: str) -> bool:
    digits = cas_number.replace("-", "")
    check_digit = int(digits[-1])
    body = digits[:-1][::-1]
    checksum = sum((index + 1) * int(digit) for index, digit in enumerate(body)) % 10
    return checksum == check_digit


def material_key(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return normalize_formula(text).lower()
    except ValueError:
        return re.sub(r"\s+", " ", text).lower()


def material_id_for(cas_number: str, name_or_formula: str) -> str:
    if cas_number:
        return f"cas:{cas_number}"
    key = material_key(name_or_formula)
    if key:
        return f"material:{key}"
    return f"material:{uuid.uuid4().hex[:12]}"


def powder_import_id(powder: str) -> str:
    return f"powder:{normalize_formula(powder)}"


def msds_status(item: dict[str, Any]) -> str:
    if item.get("msdsFileDataBase64"):
        return "uploaded"
    if item.get("msdsExternalUrl"):
        return "link only"
    return "missing"


def _empty_store() -> dict[str, Any]:
    return {"items": [], "deletedPowderImports": []}


def _load_store() -> dict[str, Any]:
    raw = storage.load_json(storage.MSDS_INVENTORY_FILE, _empty_store())
    if isinstance(raw, list):
        return {"items": raw, "deletedPowderImports": []}
    if not isinstance(raw, dict):
        return _empty_store()
    return {
        "items": raw.get("items", []) if isinstance(raw.get("items", []), list) else [],
        "deletedPowderImports": raw.get("deletedPowderImports", [])
        if isinstance(raw.get("deletedPowderImports", []), list)
        else [],
    }


def _save_store(store: dict[str, Any]) -> None:
    storage.save_json(storage.MSDS_INVENTORY_FILE, store)


def normalize_item(record: dict[str, Any]) -> dict[str, Any]:
    created = record.get("createdAt") or now_iso()
    cas_number = normalize_cas_number(record.get("casNumber"))
    name_or_formula = str(record.get("nameOrFormula") or "").strip()
    item_id = str(record.get("id") or material_id_for(cas_number, name_or_formula)).strip()
    closet_number = normalize_closet_number(record.get("closetNumber", 1))

    return {
        "id": item_id,
        "casNumber": cas_number,
        "nameOrFormula": name_or_formula,
        "purity": str(record.get("purity") or "").strip(),
        "closetNumber": closet_number,
        "msdsFileUrl": str(record.get("msdsFileUrl") or "").strip(),
        "msdsExternalUrl": str(record.get("msdsExternalUrl") or "").strip(),
        "msdsFileName": str(record.get("msdsFileName") or "").strip(),
        "msdsFileContentType": str(record.get("msdsFileContentType") or "").strip(),
        "msdsFileDataBase64": str(record.get("msdsFileDataBase64") or "").strip(),
        "company": str(record.get("company") or "").strip(),
        "identityStatus": str(record.get("identityStatus") or "needs verification").strip(),
        "source": str(record.get("source") or "").strip(),
        "sourcePowderId": str(record.get("sourcePowderId") or "").strip(),
        "createdAt": created,
        "updatedAt": record.get("updatedAt") or created,
    }


def item_payload(item: dict[str, Any], include_file_data: bool = False) -> dict[str, Any]:
    payload = {
        "id": item["id"],
        "casNumber": item.get("casNumber", ""),
        "nameOrFormula": item.get("nameOrFormula", ""),
        "purity": item.get("purity", ""),
        "closetNumber": item.get("closetNumber", 1),
        "closetLabel": closet_label(item.get("closetNumber", 1)),
        "msdsFileUrl": item.get("msdsFileUrl", ""),
        "msdsExternalUrl": item.get("msdsExternalUrl", ""),
        "msdsFileName": item.get("msdsFileName", ""),
        "company": item.get("company", ""),
        "identityStatus": item.get("identityStatus", "needs verification"),
        "source": item.get("source", ""),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
        "msdsStatus": msds_status(item),
    }
    if include_file_data:
        payload["msdsFileContentType"] = item.get("msdsFileContentType", "")
        payload["msdsFileDataBase64"] = item.get("msdsFileDataBase64", "")
    return payload


def load_msds_inventory(include_file_data: bool = False) -> list[dict[str, Any]]:
    try:
        store = _load_store()
    except Exception as exc:
        storage.record_shared_storage_error(exc)
        store = _empty_store()
    changed = False
    normalized = []
    seen_ids = set()
    for raw_item in store["items"]:
        try:
            item = normalize_item(raw_item)
        except ValueError:
            continue
        if item["id"] in seen_ids:
            changed = True
            continue
        seen_ids.add(item["id"])
        normalized.append(item)
        if item != raw_item:
            changed = True

    store["items"] = normalized
    if import_powders_into_msds_store(store):
        changed = True

    if changed:
        try:
            _save_store(store)
        except Exception as exc:
            storage.record_shared_storage_error(exc)

    return [item_payload(item, include_file_data=include_file_data) for item in store["items"]]


def save_msds_inventory_items(items: list[dict[str, Any]]) -> None:
    store = _empty_store()
    seen = set()
    for raw_item in items:
        item = normalize_item(raw_item)
        if item["id"] in seen:
            raise ValueError(f"Duplicate material inventory item id: {item['id']}")
        seen.add(item["id"])
        store["items"].append(item)
    _save_store(store)


def import_powders_into_msds_store(store: dict[str, Any]) -> bool:
    from stoichio.powders import load_powders

    changed = False
    deleted = set(store.get("deletedPowderImports", []))
    items = store["items"]
    existing_powder_ids = {item.get("sourcePowderId") for item in items if item.get("sourcePowderId")}
    existing_names = {material_key(item.get("nameOrFormula")) for item in items if not item.get("casNumber")}

    for powder, record in load_powders().items():
        source_id = powder_import_id(powder)
        if source_id in deleted or source_id in existing_powder_ids:
            continue
        if material_key(powder) in existing_names:
            continue

        now = now_iso()
        item = {
            "id": source_id,
            "casNumber": normalize_cas_number(record.get("casNumber") or record.get("cas") or ""),
            "nameOrFormula": powder,
            "purity": str(record.get("purity") or "").strip(),
            "closetNumber": 1,
            "msdsFileUrl": "",
            "msdsExternalUrl": "",
            "msdsFileName": "",
            "msdsFileContentType": "",
            "msdsFileDataBase64": "",
            "company": str(record.get("company") or record.get("supplier") or "").strip(),
            "identityStatus": "needs verification",
            "source": "powder database",
            "sourcePowderId": source_id,
            "createdAt": now,
            "updatedAt": now,
        }
        items.append(item)
        existing_powder_ids.add(source_id)
        existing_names.add(material_key(powder))
        changed = True

    return changed


def find_known_identity(cas_number: str = "", name_or_formula: str = "") -> dict[str, Any] | None:
    cas = normalize_cas_number(cas_number) if cas_number else ""
    name_key = material_key(name_or_formula)

    for item in load_msds_inventory(include_file_data=False):
        if cas and item.get("casNumber") == cas:
            return item
    if name_key:
        for item in load_msds_inventory(include_file_data=False):
            if material_key(item.get("nameOrFormula")) == name_key:
                return item
    return None


def save_msds_inventory_item(payload: dict[str, Any], item_id: str | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    store = _load_store()
    load_msds_inventory()
    store = _load_store()

    incoming = normalize_item({
        **payload,
        "id": item_id or payload.get("id") or material_id_for(
            normalize_cas_number(payload.get("casNumber")),
            payload.get("nameOrFormula", ""),
        ),
    })

    existing_index = None
    for index, item in enumerate(store["items"]):
        item = normalize_item(item)
        if item_id and item["id"] == item_id:
            existing_index = index
            break
        if not item_id and incoming["casNumber"] and item.get("casNumber") == incoming["casNumber"]:
            existing_index = index
            incoming["id"] = item["id"]
            break
        if (
            not item_id
            and not incoming["casNumber"]
            and material_key(incoming["nameOrFormula"])
            and material_key(item.get("nameOrFormula")) == material_key(incoming["nameOrFormula"])
        ):
            existing_index = index
            incoming["id"] = item["id"]
            break

    if item_id and existing_index is None:
        raise ValueError("Material inventory item was not found.")

    if incoming["casNumber"]:
        for index, item in enumerate(store["items"]):
            item = normalize_item(item)
            if index != existing_index and item.get("casNumber") == incoming["casNumber"]:
                raise ValueError("Another material already uses this CAS number.")

    now = now_iso()
    if existing_index is None:
        incoming["createdAt"] = now
        incoming["updatedAt"] = now
        store["items"].append(incoming)
        saved = incoming
    else:
        existing = normalize_item(store["items"][existing_index])
        saved = {
            **existing,
            "casNumber": incoming["casNumber"],
            "nameOrFormula": incoming["nameOrFormula"],
            "purity": incoming["purity"],
            "closetNumber": incoming["closetNumber"],
            "msdsExternalUrl": incoming["msdsExternalUrl"],
            "company": incoming["company"],
            "identityStatus": incoming["identityStatus"] or existing.get("identityStatus", "needs verification"),
            "updatedAt": now,
        }
        store["items"][existing_index] = saved

    _save_store(store)
    return item_payload(saved), load_msds_inventory()


def delete_msds_inventory_item(item_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    store = _load_store()
    removed = None
    next_items = []
    for item in store["items"]:
        normalized = normalize_item(item)
        if normalized["id"] == item_id:
            removed = normalized
            continue
        next_items.append(normalized)
    if removed is None:
        raise ValueError("Material inventory item was not found.")

    if removed.get("sourcePowderId"):
        deleted = set(store.get("deletedPowderImports", []))
        deleted.add(removed["sourcePowderId"])
        store["deletedPowderImports"] = sorted(deleted)

    store["items"] = next_items
    _save_store(store)
    return item_payload(removed), load_msds_inventory()


def attach_msds_pdf(item_id: str, filename: str, content_type: str, pdf_bytes: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not pdf_bytes:
        raise ValueError("Upload a non-empty MSDS PDF.")
    if len(pdf_bytes) > 10 * 1024 * 1024:
        raise ValueError("MSDS PDF is too large. Keep uploads under 10 MB.")
    if not filename.lower().endswith(".pdf") and content_type != "application/pdf":
        raise ValueError("Upload an MSDS/SDS PDF file.")
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Uploaded file does not look like a PDF.")

    store = _load_store()
    for index, item in enumerate(store["items"]):
        normalized = normalize_item(item)
        if normalized["id"] != item_id:
            continue
        normalized["msdsFileName"] = filename
        normalized["msdsFileContentType"] = content_type or "application/pdf"
        normalized["msdsFileDataBase64"] = base64.b64encode(pdf_bytes).decode("ascii")
        normalized["msdsFileUrl"] = f"/api/msds-inventory/{item_id}/msds-file"
        normalized["updatedAt"] = now_iso()
        store["items"][index] = normalized
        _save_store(store)
        return item_payload(normalized), load_msds_inventory()
    raise ValueError("Material inventory item was not found.")


def get_msds_pdf(item_id: str) -> tuple[str, str, bytes]:
    for item in load_msds_inventory(include_file_data=True):
        if item.get("id") != item_id:
            continue
        data = item.get("msdsFileDataBase64") or ""
        if not data:
            raise ValueError("This material does not have an uploaded MSDS PDF.")
        return (
            item.get("msdsFileName") or "msds.pdf",
            item.get("msdsFileContentType") or "application/pdf",
            base64.b64decode(data),
        )
    raise ValueError("Material inventory item was not found.")


def sorted_inventory_items(include_file_data: bool = False) -> list[dict[str, Any]]:
    return sorted(
        load_msds_inventory(include_file_data=include_file_data),
        key=lambda item: (item.get("closetNumber", 99), material_key(item.get("nameOrFormula")), item.get("casNumber", "")),
    )


def build_msds_binder_pdf() -> bytes:
    items = sorted_inventory_items(include_file_data=True)
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return _simple_text_pdf(_binder_text_pages(items, append_warning=True))

    writer = PdfWriter()

    def append_text_pages(pages: list[list[str]]) -> None:
        reader = PdfReader(io.BytesIO(_simple_text_pdf(pages)))
        for page in reader.pages:
            writer.add_page(page)

    append_text_pages(_binder_text_pages(items))

    for item in items:
        heading = item.get("nameOrFormula") or "Unnamed material"
        metadata = _material_page_lines(item)
        if item.get("msdsFileDataBase64"):
            append_text_pages([["Uploaded MSDS/SDS", "", *metadata]])
            try:
                reader = PdfReader(io.BytesIO(base64.b64decode(item["msdsFileDataBase64"])))
                if reader.is_encrypted:
                    reader.decrypt("")
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as exc:
                append_text_pages([[f"Could not append uploaded PDF for {heading}.", str(exc), "", *metadata]])
        elif item.get("msdsExternalUrl"):
            append_text_pages([["MSDS/SDS link only", "", *metadata, "", item["msdsExternalUrl"]]])
        else:
            append_text_pages([["MSDS not uploaded yet", "", *metadata]])

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _binder_text_pages(items: list[dict[str, Any]], append_warning: bool = False) -> list[list[str]]:
    pages: list[list[str]] = [
        [
            "Lab Inventory MSDS Binder",
            "",
            f"Generated: {now_iso()}",
            f"Materials: {len(items)}",
        ]
    ]
    index_lines = ["Index", ""]
    if append_warning:
        index_lines.extend([
            "PDF merge support is not installed.",
            "Uploaded MSDS PDFs are listed but not appended in this binder.",
            "",
        ])
    for closet_number in CLOSETS:
        index_lines.append(closet_label(closet_number))
        closet_items = [item for item in items if item.get("closetNumber") == closet_number]
        if not closet_items:
            index_lines.append("  No materials recorded.")
        for item in closet_items:
            index_lines.append(
                "  "
                f"CAS: {item.get('casNumber') or 'needs verification'} | "
                f"{item.get('nameOrFormula') or 'needs verification'} | "
                f"Purity: {item.get('purity') or ''} | "
                f"MSDS: {msds_status(item)}"
            )
        index_lines.append("")
    pages.extend(_split_lines_into_pages(index_lines))
    return pages


def _material_page_lines(item: dict[str, Any]) -> list[str]:
    return [
        f"CAS number: {item.get('casNumber') or 'needs verification'}",
        f"Name / formula: {item.get('nameOrFormula') or 'needs verification'}",
        f"Purity: {item.get('purity') or ''}",
        f"Closet: {closet_label(item.get('closetNumber', 1))}",
        f"MSDS status: {msds_status(item)}",
    ]


def _split_lines_into_pages(lines: list[str]) -> list[list[str]]:
    pages = []
    current = []
    for line in lines:
        wrapped = textwrap.wrap(line, width=92) or [""]
        for wrapped_line in wrapped:
            current.append(wrapped_line)
            if len(current) >= _MAX_TEXT_LINES_PER_PAGE:
                pages.append(current)
                current = []
    if current:
        pages.append(current)
    return pages


def _simple_text_pdf(pages: list[list[str]]) -> bytes:
    objects: list[bytes] = []

    def add_object(payload: str | bytes) -> int:
        if isinstance(payload, str):
            payload = payload.encode("latin-1", "replace")
        objects.append(payload)
        return len(objects)

    font_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    content_ids = []

    for lines in pages:
        stream = _page_stream(lines)
        content_id = add_object(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        )
        content_ids.append(content_id)
        page_ids.append(None)

    pages_id = len(objects) + len(pages) + 1
    for index, _ in enumerate(pages):
        page_ids[index] = add_object(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_ids[index]} 0 R >>"
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_id = add_object(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(payload)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def _page_stream(lines: list[str]) -> bytes:
    stream_lines = ["BT", "/F1 13 Tf", "50 742 Td", "17 TL"]
    first = True
    for line in lines:
        if not first:
            stream_lines.append("T*")
        first = False
        stream_lines.append(f"({_escape_pdf_text(line)}) Tj")
    stream_lines.append("ET")
    return "\n".join(stream_lines).encode("latin-1", "replace")


def _escape_pdf_text(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
