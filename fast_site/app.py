"""FastAPI/Vercel version of Stoichio Buddy.

This app intentionally reuses the same locked chemistry engine as the Streamlit
lab app, but serves a normal web frontend that can run well on Vercel.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from stoichio import storage
from stoichio.backup_export import data_backup_json
from stoichio.chemistry.density_engine import (
    DEFAULT_DIE_DIAMETER_MM,
    cylinder_volume_cm3,
    measured_density,
    relative_density_percent,
    target_mass_from_height,
    theoretical_density_from_cell,
    unit_cell_volume_from_lattice,
)
from stoichio.chemistry.formula_parser import normalize_formula
from stoichio.chemistry.stoich_engine import MASS_BASIS_TOTAL_PRECURSOR, compute_recipe
from stoichio.density_records import (
    delete_material_density,
    load_material_densities,
    related_material_density_records,
    set_preferred_material_density,
    update_material_density_review_status,
    upsert_material_density,
)
from stoichio.history import (
    clear_history_for_target,
    clear_history_for_target_id,
    clear_target_density_history_for_person,
    delete_history_entry,
    format_target_id,
    load_history,
    log_synthesis,
    log_target_density,
    next_target_number,
    normalize_person_name,
    update_recipe_planning,
)
from stoichio.inventory import (
    consume_stock,
    load_inventory,
    load_inventory_log,
    set_inventory_quantity,
)
from stoichio.msds_inventory import (
    attach_msds_pdf,
    build_msds_binder_archive,
    build_msds_binder_pdf,
    closet_options,
    delete_msds_inventory_item,
    download_msds_pdf_from_url,
    find_known_identity,
    get_msds_pdf,
    load_msds_inventory,
    save_msds_inventory_item,
)
from stoichio.cas_identity import lookup_cas_identity
from stoichio.sds_lookup import build_sds_lookup_candidates
from stoichio.powder_sets import (
    delete_powder_set,
    load_powder_sets,
    matching_powder_sets_for_target,
    save_powder_set,
)
from stoichio.powders import (
    add_powder,
    delete_powder,
    load_powders,
    load_reference_powders,
    normalize_powder,
    powder_display_name,
    relevant_powders_for_target,
    sync_powders_from_msds_inventory,
    update_powder_notes,
)


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
STATIC_DIR = PUBLIC_DIR / "static"
ASSET_DIR = PUBLIC_DIR / "assets"
IS_VERCEL = os.environ.get("VERCEL") == "1"
WRITE_PIN = os.environ.get("STOICHIO_ADMIN_PIN", "").strip()

# Keep JSON seed storage relative to the project even when uvicorn is launched elsewhere.
os.chdir(ROOT)

if os.environ.get("GITHUB_DATA_REPO") and os.environ.get("GITHUB_DATA_TOKEN"):
    try:
        storage.configure_github_json(
            repo=os.environ["GITHUB_DATA_REPO"],
            token=os.environ["GITHUB_DATA_TOKEN"],
            branch=os.environ.get("GITHUB_DATA_BRANCH", "lab-data"),
            path_prefix=os.environ.get("GITHUB_DATA_PATH_PREFIX", ""),
        )
    except Exception as exc:
        storage.disable_shared_storage(exc)

app = FastAPI(
    title="Stoichio Buddy",
    description="Lab synthesis calculator and inventory manager.",
    version="1.0.0",
)

if not IS_VERCEL:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def runtime_error_handler(_: Request, exc: RuntimeError):
    message = str(exc)
    if "Shared storage" in message or "data was not saved" in message:
        return JSONResponse(status_code=409, content={"detail": message})
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error."})


def storage_mode() -> str:
    if storage.has_shared_storage():
        return storage.storage_label()
    if IS_VERCEL:
        return "Read-only seed JSON. Configure GitHub data storage to save edits."
    return "Local JSON files"


def require_write_pin(x_stoichio_pin: str | None = Header(default=None)):
    if WRITE_PIN and x_stoichio_pin != WRITE_PIN:
        raise HTTPException(status_code=401, detail="Admin PIN is required to edit lab data.")
    if IS_VERCEL and not storage.has_shared_storage():
        raise HTTPException(
            status_code=409,
            detail=(
                "This Vercel deployment has no writable data backend. Add "
                "GITHUB_DATA_REPO, GITHUB_DATA_BRANCH, and GITHUB_DATA_TOKEN."
            ),
        )


class RecipeRequest(BaseModel):
    target: str = Field(..., min_length=1)
    mass_g: float = Field(..., gt=0)
    selected_powders: list[str] = Field(default_factory=list)
    mass_basis: str = MASS_BASIS_TOTAL_PRECURSOR


class RecipeSaveRequest(RecipeRequest):
    result: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    target_for: str = ""
    target_number: int | None = None
    target_id: str = ""
    inventory_deducted: bool = False


class HeightRequest(BaseModel):
    theoretical_density_g_cm3: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    diameter_mm: float = Field(DEFAULT_DIE_DIAMETER_MM, gt=0)
    target_porosity_percent: float = Field(5.0, ge=0, lt=100)


class HistoryPlanningRequest(BaseModel):
    target_height_mm: float = Field(..., gt=0)
    die_diameter_mm: float = Field(DEFAULT_DIE_DIAMETER_MM, gt=0)
    theoretical_density_g_cm3: float = Field(..., gt=0)
    target_porosity_percent: float = Field(5.0, ge=0, lt=100)
    density_source: str = "Manual backfill"
    density_choice: str = "__manual__"


class RelativeDensityRequest(BaseModel):
    final_mass_g: float = Field(..., gt=0)
    final_diameter_mm: float = Field(..., gt=0)
    final_height_mm: float = Field(..., gt=0)
    theoretical_density_g_cm3: float = Field(..., gt=0)


class TargetDensitySaveRequest(RelativeDensityRequest):
    target: str = Field(..., min_length=1)
    target_for: str = ""
    target_number: int | None = None
    target_id: str = ""
    density_source: str = ""
    notes: str = ""
    linked_recipe_entry_id: str = ""


class InventoryQuantityRequest(BaseModel):
    grams: float = Field(..., ge=0)
    reason: str = "inventory update"


class InventoryDeductRequest(BaseModel):
    recipe: dict[str, float]
    reason: str = "recipe deduction"
    recipe_id: str = ""


class PowderCreateRequest(BaseModel):
    formula: str = Field(..., min_length=1)
    initial_grams: float = Field(0, ge=0)
    purity: str = ""
    company: str = ""
    notes: str = ""


class PowderNoteRequest(BaseModel):
    powder: str = Field(..., min_length=1)
    notes: str = ""


class PowderSetRequest(BaseModel):
    target: str
    powders: list[str]
    name: str = ""
    notes: str = ""


class DensityCellRequest(BaseModel):
    formula: str
    crystal_system: str = "Cubic"
    a_A: float | None = None
    b_A: float | None = None
    c_A: float | None = None
    alpha_deg: float | None = None
    beta_deg: float | None = None
    gamma_deg: float | None = None
    unit_cell_volume_A3: float | None = None
    z: float = Field(..., gt=0)


class DensityRecordRequest(DensityCellRequest):
    phase: str = ""
    theoretical_density_g_cm3: float | None = None
    density_source: str = "manual"
    source: str = ""
    source_url: str = ""
    doi: str = ""
    cod_id: str = ""
    paper_title: str = ""
    notes: str = ""
    origin: str = "Lab entry"
    verification_status: str = "Lab entry - unverified"
    verified_by: str = ""
    verified_date: str = ""
    reported_density_g_cm3: float | None = None


class DensityStatusRequest(BaseModel):
    verification_status: str
    verified_by: str = ""
    verified_date: str = ""


class MsdsInventoryRequest(BaseModel):
    casNumber: str = ""
    nameOrFormula: str = ""
    purity: str = ""
    closetNumber: int = Field(1, ge=1, le=4)
    msdsExternalUrl: str = ""
    company: str = ""
    identityStatus: str = "needs verification"
    source: str = ""
    casSource: str = ""
    casSourceUrl: str = ""
    pubchemCid: str = ""
    pubchemFormula: str = ""
    pubchemIupacName: str = ""
    pubchemTitle: str = ""


class MsdsUrlDownloadRequest(BaseModel):
    url: str = ""


def powder_payload(powder: str, record: dict) -> dict:
    return {
        "id": powder,
        "display_name": powder_display_name(powder, record),
        "formula": record.get("formula", powder),
        "molar_mass_g_mol": record.get("molar_mass"),
        "elements": record.get("elements", {}),
        "purity": record.get("purity", ""),
        "company": record.get("company") or record.get("supplier", ""),
        "casNumber": record.get("casNumber", ""),
        "notes": record.get("notes", ""),
    }


def density_payload(record_key: str, record: dict) -> dict:
    return {
        "record_key": record_key,
        "display_name": record.get("display_name", record_key),
        "formula": record.get("formula", record_key),
        "phase": record.get("phase", ""),
        "theoretical_density_g_cm3": record.get("theoretical_density_g_cm3"),
        "unit_cell_volume_A3": record.get("unit_cell_volume_A3"),
        "z": record.get("z"),
        "crystal_system": record.get("crystal_system", ""),
        "a_A": record.get("a_A"),
        "b_A": record.get("b_A"),
        "c_A": record.get("c_A"),
        "alpha_deg": record.get("alpha_deg"),
        "beta_deg": record.get("beta_deg"),
        "gamma_deg": record.get("gamma_deg"),
        "reported_density_g_cm3": record.get("reported_density_g_cm3"),
        "density_delta_g_cm3": record.get("density_delta_g_cm3"),
        "verification_status": record.get("verification_status", ""),
        "origin": record.get("origin", ""),
        "source": record.get("source", ""),
        "source_url": record.get("source_url", ""),
        "doi": record.get("doi", ""),
        "cod_id": record.get("cod_id", ""),
        "paper_title": record.get("paper_title", ""),
        "notes": record.get("notes", ""),
        "verified_by": record.get("verified_by", ""),
        "verified_date": record.get("verified_date", ""),
    }


def all_powders_payload() -> dict:
    db = load_powders()
    return {
        powder: powder_payload(powder, record)
        for powder, record in db.items()
    }


def exact_density_records(target: str, records: dict) -> list[tuple[str, dict]]:
    try:
        key = normalize_formula(target)
    except ValueError:
        return []
    return [
        (record_key, record)
        for record_key, record in records.items()
        if record_key == key or record.get("formula") == key
    ]


def linked_recipe_snapshot(entry_id: str) -> dict[str, Any] | None:
    if not entry_id:
        return None
    for entry in load_history():
        if entry.get("entry_id") != entry_id:
            continue
        if entry.get("entry_type", "synthesis") != "synthesis":
            continue
        return {
            "entry_id": entry.get("entry_id"),
            "recipe_id": entry.get("recipe_id"),
            "target": entry.get("target"),
            "target_for": entry.get("target_for", ""),
            "target_id": entry.get("target_id", ""),
            "target_number": entry.get("target_number"),
            "input_basis_g": entry.get("mass"),
            "selected_powders": entry.get("selected_powders", []),
            "recipe": entry.get("recipe", {}),
            "notes": entry.get("notes", ""),
            "calculation": entry.get("calculation", {}),
        }
    return None


def linked_recipe_options(history: list[dict]) -> list[dict]:
    options = []
    for entry in history:
        if entry.get("entry_type", "synthesis") != "synthesis":
            continue
        options.append(
            {
                "entry_id": entry.get("entry_id"),
                "recipe_id": entry.get("recipe_id", ""),
                "target": entry.get("target", ""),
                "target_for": entry.get("target_for", ""),
                "target_id": entry.get("target_id", ""),
                "target_number": entry.get("target_number"),
                "time": entry.get("time", ""),
            }
        )
    return list(reversed(options))


@app.get("/")
def index():
    if IS_VERCEL:
        return RedirectResponse("/index.html", status_code=307)
    if not (PUBLIC_DIR / "index.html").exists():
        return HTMLResponse(
            "<h1>Stoichio Buddy</h1><p>public/index.html was not found.</p>",
            status_code=500,
        )
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "Stoichio Buddy",
        "math_engine": "stoichio.chemistry.stoich_engine",
        "storage_mode": storage_mode(),
        "storage_error": storage.storage_error(),
        "writes_enabled": not (IS_VERCEL and not storage.has_shared_storage()),
        "pin_required": bool(WRITE_PIN),
    }


@app.get("/api/bootstrap")
def bootstrap():
    records = load_material_densities()
    history = load_history()
    powders = load_powders()
    return {
        "health": health(),
        "powders": {
            powder: powder_payload(powder, record)
            for powder, record in powders.items()
        },
        "msds_inventory": load_msds_inventory(),
        "closets": closet_options(),
        "densities": {
            key: density_payload(key, record)
            for key, record in records.items()
        },
        "history": history,
        "linked_recipes": linked_recipe_options(history),
        "powder_sets": load_powder_sets(),
        "defaults": {
            "die_diameter_mm": DEFAULT_DIE_DIAMETER_MM,
        },
    }


@app.get("/api/powders")
def powders(target: str = Query(default=""), show_all: bool = Query(default=False)):
    db = load_powders()
    relevant, hidden, target_elements, error = relevant_powders_for_target(target, db)
    options = list(db.keys()) if show_all or error or not target else relevant
    return {
        "powders": {
            powder: powder_payload(powder, record)
            for powder, record in db.items()
        },
        "options": options,
        "relevant": relevant,
        "hidden": hidden,
        "target_elements": sorted(target_elements),
        "filter_error": error,
        "matching_powder_sets": [
            {"record_id": record_id, **record}
            for record_id, record in matching_powder_sets_for_target(target, load_powder_sets())
        ] if target else [],
    }


@app.post("/api/powders")
def create_powder(payload: PowderCreateRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    powder, _ = add_powder(
        payload.formula,
        purity=payload.purity,
        company=payload.company,
        notes=payload.notes,
    )
    return {
        "powder": powder,
        "powders": all_powders_payload(),
        "msds_inventory": load_msds_inventory(),
    }


@app.post("/api/powders/note")
def save_powder_note(payload: PowderNoteRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    powder, _ = update_powder_notes(payload.powder, payload.notes)
    return {
        "powder": powder,
        "powders": all_powders_payload(),
    }


@app.post("/api/powders/sync-msds")
def sync_powder_database_from_msds(x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    summary = sync_powders_from_msds_inventory(
        load_msds_inventory(),
        reference_powders=load_reference_powders(),
    )
    return {
        "created": summary["created"],
        "updated": summary["updated"],
        "removed": summary["removed"],
        "skipped": summary["skipped"],
        "ignored": summary["ignored"],
        "powders": {
            powder: powder_payload(powder, record)
            for powder, record in summary["powders"].items()
        },
    }


@app.delete("/api/powders/{powder}")
def remove_powder(powder: str, remove_inventory: bool = Query(default=True), x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    delete_powder(powder, remove_inventory=remove_inventory)
    return {"powders": all_powders_payload(), "inventory": load_inventory()}


@app.get("/api/inventory")
def inventory():
    return {"inventory": load_inventory(), "inventory_log": load_inventory_log()}


@app.patch("/api/inventory/{powder}")
def update_inventory(powder: str, payload: InventoryQuantityRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    updated = set_inventory_quantity(powder, payload.grams, reason=payload.reason)
    return {"inventory": updated, "inventory_log": load_inventory_log()}


@app.post("/api/inventory/deduct")
def deduct_inventory(payload: InventoryDeductRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    inventory = consume_stock(
        load_inventory(),
        payload.recipe,
        reason=payload.reason,
        recipe_id=payload.recipe_id,
    )
    return {"inventory": inventory, "inventory_log": load_inventory_log()}


@app.get("/api/msds-inventory")
def msds_inventory():
    return {"items": load_msds_inventory(), "closets": closet_options()}


@app.get("/api/msds-inventory/lookup")
def lookup_msds_identity(cas_number: str = Query(default=""), name_or_formula: str = Query(default="")):
    match = find_known_identity(cas_number=cas_number, name_or_formula=name_or_formula)
    return {"match": match}


@app.get("/api/msds-inventory/cas-identity")
def lookup_msds_cas_identity(cas_number: str = Query(default=""), closet_number: int = Query(default=1)):
    try:
        return lookup_cas_identity(cas_number, load_msds_inventory(), prefer_name=closet_number != 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/msds-inventory/sds-lookup")
def lookup_sds_candidates(
    cas_number: str = Query(default=""),
    company: str = Query(default=""),
    name_or_formula: str = Query(default=""),
):
    try:
        return build_sds_lookup_candidates(cas_number, company, name_or_formula)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/msds-inventory")
def create_msds_inventory_item(payload: MsdsInventoryRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    item, items = save_msds_inventory_item(payload.model_dump())
    return {"item": item, "items": items, "closets": closet_options()}


@app.patch("/api/msds-inventory/{item_id}")
def update_msds_inventory_item(item_id: str, payload: MsdsInventoryRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    item, items = save_msds_inventory_item(payload.model_dump(), item_id=item_id)
    return {"item": item, "items": items, "closets": closet_options()}


@app.delete("/api/msds-inventory/{item_id}")
def remove_msds_inventory_item(item_id: str, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    removed, items = delete_msds_inventory_item(item_id)
    return {"removed": removed, "items": items, "closets": closet_options()}


@app.post("/api/msds-inventory/{item_id}/msds-file")
async def upload_msds_file(item_id: str, request: Request, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="Choose an MSDS/SDS PDF to upload.")
    pdf_bytes = await upload.read()
    item, items = attach_msds_pdf(
        item_id,
        getattr(upload, "filename", "") or "msds.pdf",
        getattr(upload, "content_type", "") or "application/pdf",
        pdf_bytes,
    )
    return {"item": item, "items": items, "closets": closet_options()}


@app.post("/api/msds-inventory/{item_id}/msds-file-from-url")
def upload_msds_file_from_url(
    item_id: str,
    payload: MsdsUrlDownloadRequest,
    x_stoichio_pin: str | None = Header(default=None),
):
    require_write_pin(x_stoichio_pin)
    try:
        item, items = download_msds_pdf_from_url(item_id, payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"item": item, "items": items, "closets": closet_options()}


@app.get("/api/msds-inventory/{item_id}/msds-file")
def download_msds_file(item_id: str):
    filename, content_type, pdf_bytes = get_msds_pdf(item_id)
    safe_name = filename.replace('"', "")
    return Response(
        content=pdf_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@app.get("/api/msds-binder")
def download_msds_binder():
    return Response(
        content=build_msds_binder_archive(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="stoichio_msds_binder.zip"'},
    )


@app.get("/api/msds-binder.zip")
def download_msds_binder_archive():
    return Response(
        content=build_msds_binder_archive(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="stoichio_msds_binder.zip"'},
    )


@app.get("/api/msds-binder.pdf")
def download_msds_binder_pdf():
    return Response(
        content=build_msds_binder_pdf(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="stoichio_msds_binder.pdf"'},
    )


@app.get("/api/densities")
def densities(target: str = Query(default="")):
    records = load_material_densities()
    exact = exact_density_records(target, records) if target else []
    related = related_material_density_records(target, records) if target else []
    exact_keys = {item[0] for item in exact}
    related = [(key, record) for key, record in related if key not in exact_keys]
    return {
        "records": {
            key: density_payload(key, record)
            for key, record in records.items()
        },
        "exact": [density_payload(key, record) for key, record in exact],
        "related": [density_payload(key, record) for key, record in related[:80]],
        "total_records": len(records),
    }


@app.post("/api/density-from-cell")
def density_from_cell(payload: DensityCellRequest):
    volume = payload.unit_cell_volume_A3
    if not volume:
        volume = unit_cell_volume_from_lattice(
            payload.crystal_system,
            payload.a_A,
            payload.b_A,
            payload.c_A,
            payload.alpha_deg,
            payload.beta_deg,
            payload.gamma_deg,
        )
    density = theoretical_density_from_cell(payload.formula, volume, payload.z)
    return {"unit_cell_volume_A3": volume, "theoretical_density_g_cm3": density}


@app.post("/api/densities")
def save_density_record(payload: DensityRecordRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    volume = payload.unit_cell_volume_A3
    density = payload.theoretical_density_g_cm3
    source = payload.density_source
    if density is None:
        if not volume:
            volume = unit_cell_volume_from_lattice(
                payload.crystal_system,
                payload.a_A,
                payload.b_A,
                payload.c_A,
                payload.alpha_deg,
                payload.beta_deg,
                payload.gamma_deg,
            )
            source = "lattice parameters"
        density = theoretical_density_from_cell(payload.formula, volume, payload.z)
        if source == "manual":
            source = "unit cell"

    reported = payload.reported_density_g_cm3
    delta = None if reported is None else density - reported
    record_id, records = upsert_material_density(
        payload.formula,
        phase=payload.phase,
        theoretical_density=density,
        unit_cell_volume=volume,
        z=payload.z,
        density_source=source,
        crystal_system=payload.crystal_system,
        a=payload.a_A,
        b=payload.b_A,
        c=payload.c_A,
        alpha=payload.alpha_deg,
        beta=payload.beta_deg,
        gamma=payload.gamma_deg,
        source=payload.source,
        source_url=payload.source_url,
        doi=payload.doi,
        cod_id=payload.cod_id,
        paper_title=payload.paper_title,
        notes=payload.notes,
        origin=payload.origin,
        reported_density=reported,
        density_delta=delta,
        density_validation=("matches reported density" if delta is not None and abs(delta) < 0.03 else ""),
        verification_status=payload.verification_status,
        verified_by=payload.verified_by,
        verified_date=payload.verified_date,
    )
    return {
        "record_id": record_id,
        "records": {
            key: density_payload(key, record)
            for key, record in records.items()
        },
    }


@app.patch("/api/densities/{identifier}/status")
def update_density_status(identifier: str, payload: DensityStatusRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    if "preferred" in payload.verification_status.lower():
        _, records = set_preferred_material_density(
            identifier,
            verified_by=payload.verified_by,
            verified_date=payload.verified_date,
        )
    else:
        _, records = update_material_density_review_status(
            identifier,
            payload.verification_status,
            verified_by=payload.verified_by,
            verified_date=payload.verified_date,
        )
    return {
        "records": {
            key: density_payload(key, record)
            for key, record in records.items()
        },
    }


@app.delete("/api/densities/{identifier}")
def remove_density_record(identifier: str, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    records = delete_material_density(identifier)
    return {
        "records": {
            key: density_payload(key, record)
            for key, record in records.items()
        },
    }


@app.post("/api/recipe")
def recipe(payload: RecipeRequest):
    db = load_powders()
    selected = []
    for powder in payload.selected_powders:
        selected.append(normalize_powder(powder))

    result = compute_recipe(
        payload.target,
        payload.mass_g,
        db,
        selected,
        mass_basis=payload.mass_basis,
    )
    return {"result": result}


@app.post("/api/history/recipe")
def save_recipe(payload: RecipeSaveRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    result = payload.result or {}
    recipe_masses = result.get("recipe")
    if not recipe_masses:
        raise HTTPException(status_code=400, detail="Calculate a valid recipe before saving.")

    history = log_synthesis(
        result.get("normalized_target") or normalize_formula(payload.target),
        payload.mass_g,
        recipe_masses,
        selected_powders=payload.selected_powders,
        warning=result.get("warning"),
        inventory_deducted=payload.inventory_deducted,
        notes=payload.notes,
        target_for=payload.target_for,
        target_number=payload.target_number,
        target_id=payload.target_id,
        calculation=result,
    )
    return {
        "history": history,
        "linked_recipes": linked_recipe_options(history),
        "saved_entry": history[-1] if history else None,
    }


@app.post("/api/history/recipe-and-deduct")
def save_recipe_and_deduct(payload: RecipeSaveRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    result = payload.result or {}
    recipe_masses = result.get("recipe")
    if not recipe_masses:
        raise HTTPException(status_code=400, detail="Calculate a valid recipe before saving.")

    history = log_synthesis(
        result.get("normalized_target") or normalize_formula(payload.target),
        payload.mass_g,
        recipe_masses,
        selected_powders=payload.selected_powders,
        warning=result.get("warning"),
        inventory_deducted=True,
        notes=payload.notes,
        target_for=payload.target_for,
        target_number=payload.target_number,
        target_id=payload.target_id,
        calculation=result,
    )
    saved_entry = history[-1] if history else None
    inventory = consume_stock(
        load_inventory(),
        recipe_masses,
        reason="Saved recipe and deducted inventory from Vercel lab website",
        recipe_id=(saved_entry or {}).get("recipe_id") or result.get("normalized_target") or "",
    )
    return {
        "history": history,
        "linked_recipes": linked_recipe_options(history),
        "saved_entry": saved_entry,
        "inventory": inventory,
        "inventory_log": load_inventory_log(),
    }


@app.get("/api/history")
def history():
    records = load_history()
    return {"history": records, "linked_recipes": linked_recipe_options(records)}


@app.patch("/api/history/{entry_id}/planning")
def update_history_planning(
    entry_id: str,
    payload: HistoryPlanningRequest,
    x_stoichio_pin: str | None = Header(default=None),
):
    require_write_pin(x_stoichio_pin)
    entry, records = update_recipe_planning(
        entry_id,
        target_height_mm=payload.target_height_mm,
        die_diameter_mm=payload.die_diameter_mm,
        theoretical_density_g_cm3=payload.theoretical_density_g_cm3,
        target_porosity_percent=payload.target_porosity_percent,
        density_source=payload.density_source,
        density_choice=payload.density_choice,
    )
    return {
        "history": records,
        "linked_recipes": linked_recipe_options(records),
        "saved_entry": entry,
    }


@app.delete("/api/history/{entry_id}")
def remove_history_item(entry_id: str, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    removed, records = delete_history_entry(entry_id)
    return {"removed": removed, "history": records, "linked_recipes": linked_recipe_options(records)}


@app.delete("/api/history/groups/recipe-target/{target}")
def clear_recipe_group(target: str, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    removed, records = clear_history_for_target(target)
    return {"removed": removed, "history": records, "linked_recipes": linked_recipe_options(records)}


@app.delete("/api/history/groups/target-id/{target_id}")
def clear_target_id_group(target_id: str, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    removed, records = clear_history_for_target_id(target_id)
    return {"removed": removed, "history": records, "linked_recipes": linked_recipe_options(records)}


@app.delete("/api/history/groups/density-person/{person}")
def clear_density_person_group(person: str, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    removed, records = clear_target_density_history_for_person(person)
    return {"removed": removed, "history": records, "linked_recipes": linked_recipe_options(records)}


@app.post("/api/target-mass-from-height")
def mass_from_height(payload: HeightRequest):
    mass_g, volume_cm3 = target_mass_from_height(
        payload.theoretical_density_g_cm3,
        payload.height_mm,
        payload.diameter_mm,
        payload.target_porosity_percent,
    )
    cylinder_volume = cylinder_volume_cm3(payload.diameter_mm, payload.height_mm)
    return {
        "target_mass_g": mass_g,
        "volume_cm3": cylinder_volume,
        "solid_volume_cm3": volume_cm3,
        "diameter_mm": payload.diameter_mm,
        "height_mm": payload.height_mm,
        "target_porosity_percent": payload.target_porosity_percent,
    }


@app.post("/api/relative-density")
def relative_density(payload: RelativeDensityRequest):
    density, volume = measured_density(
        payload.final_mass_g,
        payload.final_diameter_mm,
        payload.final_height_mm,
    )
    relative = relative_density_percent(density, payload.theoretical_density_g_cm3)
    return {
        "measured_density_g_cm3": density,
        "relative_density_percent": relative,
        "final_volume_cm3": volume,
    }


@app.post("/api/history/target-density")
def save_target_density(payload: TargetDensitySaveRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    density, volume = measured_density(
        payload.final_mass_g,
        payload.final_diameter_mm,
        payload.final_height_mm,
    )
    relative = relative_density_percent(density, payload.theoretical_density_g_cm3)
    target_for = normalize_person_name(payload.target_for)
    target_number = payload.target_number
    target_id = payload.target_id.strip()

    linked_recipe = linked_recipe_snapshot(payload.linked_recipe_entry_id)
    if linked_recipe:
        target_for = target_for or normalize_person_name(linked_recipe.get("target_for", ""))
        target_number = target_number or linked_recipe.get("target_number")
        target_id = target_id or str(linked_recipe.get("target_id", "")).strip()

    if target_for and not target_number:
        target_number = next_target_number(load_history(), target_for)
    if target_for and not target_id:
        target_id = format_target_id(target_for, target_number)

    history = log_target_density(
        normalize_formula(payload.target),
        target_number,
        target_for,
        density,
        payload.theoretical_density_g_cm3,
        relative,
        volume,
        payload.final_mass_g,
        payload.final_diameter_mm,
        payload.final_height_mm,
        density_source=payload.density_source,
        notes=payload.notes,
        target_id=target_id,
        linked_recipe=linked_recipe,
    )
    return {
        "history": history,
        "linked_recipes": linked_recipe_options(history),
        "saved_entry": history[-1] if history else None,
    }


@app.post("/api/powder-sets")
def save_set(payload: PowderSetRequest, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    record_id, powder_sets = save_powder_set(
        payload.target,
        payload.powders,
        name=payload.name,
        notes=payload.notes,
    )
    return {"record_id": record_id, "powder_sets": powder_sets}


@app.delete("/api/powder-sets/{record_id}")
def remove_set(record_id: str, x_stoichio_pin: str | None = Header(default=None)):
    require_write_pin(x_stoichio_pin)
    return {"powder_sets": delete_powder_set(record_id)}


@app.get("/api/backup")
def backup():
    return Response(
        content=data_backup_json(
            load_powders(),
            load_inventory(),
            load_material_densities(),
            load_history(),
            inventory_log=load_inventory_log(),
            powder_sets=load_powder_sets(),
            msds_inventory=load_msds_inventory(include_file_data=True),
        ),
        media_type="application/json",
    )


@app.get("/api/target-id-preview")
def target_id_preview(target_for: str = Query(default="")):
    person = normalize_person_name(target_for)
    number = next_target_number(load_history(), person) if person else 1
    return {
        "target_number": number,
        "target_id": format_target_id(person, number) if person else "",
    }
