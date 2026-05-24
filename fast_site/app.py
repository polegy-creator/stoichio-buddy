"""FastAPI version of Stoichio Buddy.

Run from the project root:

    uvicorn fast_site.app:app --reload --host 0.0.0.0 --port 8701

This app intentionally reuses the same chemistry engine as the Streamlit app.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from stoichio.chemistry.density_engine import (
    DEFAULT_DIE_DIAMETER_MM,
    measured_density,
    relative_density_percent,
    target_mass_from_height,
)
from stoichio.chemistry.formula_parser import normalize_formula
from stoichio.chemistry.stoich_engine import MASS_BASIS_TARGET_FORMULA, compute_recipe
from stoichio.density_records import related_material_density_records
from stoichio.inventory import check_stock, load_inventory, set_inventory_quantity
from stoichio.powders import load_powders, relevant_powders_for_target


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
STATIC_DIR = PUBLIC_DIR / "static"
ASSET_DIR = PUBLIC_DIR / "assets"
IS_VERCEL = os.environ.get("VERCEL") == "1"

# Keep JSON storage relative to the project even when uvicorn is launched elsewhere.
os.chdir(ROOT)

app = FastAPI(
    title="Stoichio Buddy Fast",
    description="Fast API/static-site version using the same locked stoichiometry engine.",
    version="0.1.0",
)

if not IS_VERCEL:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")


class RecipeRequest(BaseModel):
    target: str = Field(..., min_length=1)
    mass_g: float = Field(..., gt=0)
    selected_powders: list[str] = Field(default_factory=list)
    mass_basis: str = MASS_BASIS_TARGET_FORMULA


class HeightRequest(BaseModel):
    theoretical_density_g_cm3: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    diameter_mm: float = Field(DEFAULT_DIE_DIAMETER_MM, gt=0)


class RelativeDensityRequest(BaseModel):
    final_mass_g: float = Field(..., gt=0)
    final_diameter_mm: float = Field(..., gt=0)
    final_height_mm: float = Field(..., gt=0)
    theoretical_density_g_cm3: float = Field(..., gt=0)


class InventoryQuantityRequest(BaseModel):
    grams: float = Field(..., ge=0)
    reason: str = "fast-site inventory update"


def powder_payload(powder: str, record: dict, inventory: dict | None = None) -> dict:
    inventory = inventory or {}
    available = inventory.get(powder)
    return {
        "formula": powder,
        "molar_mass_g_mol": record.get("molar_mass"),
        "elements": record.get("elements", {}),
        "available_g": available,
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
        "verification_status": record.get("verification_status", ""),
        "source_url": record.get("source_url", ""),
        "doi": record.get("doi", ""),
        "cod_id": record.get("cod_id", ""),
        "paper_title": record.get("paper_title", ""),
        "notes": record.get("notes", ""),
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


@app.get("/")
def index():
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "Stoichio Buddy Fast",
        "math_engine": "stoichio.chemistry.stoich_engine",
        "storage_mode": "Read-only Vercel seed data" if IS_VERCEL else "Local JSON seed data",
    }


@app.get("/api/powders")
def powders(target: str = Query(default="")):
    db = load_powders()
    inventory = load_inventory()
    relevant, hidden, target_elements, error = relevant_powders_for_target(target, db)
    powders_by_name = {
        powder: powder_payload(powder, record, inventory)
        for powder, record in db.items()
    }
    return {
        "powders": powders_by_name,
        "relevant": relevant,
        "hidden": hidden,
        "target_elements": sorted(target_elements),
        "filter_error": error,
    }


@app.get("/api/inventory")
def inventory():
    return {"inventory": load_inventory()}


@app.patch("/api/inventory/{powder}")
def update_inventory(powder: str, payload: InventoryQuantityRequest):
    if IS_VERCEL:
        raise HTTPException(
            status_code=409,
            detail="Vercel deployment is read-only. Add a database backend before shared inventory editing.",
        )
    try:
        updated = set_inventory_quantity(powder, payload.grams, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"inventory": updated}


@app.get("/api/densities")
def densities(target: str = Query(default="")):
    from stoichio.density_records import load_material_densities

    records = load_material_densities()
    exact = exact_density_records(target, records) if target else []
    related = related_material_density_records(target, records) if target else []
    related = [(key, record) for key, record in related if key not in {item[0] for item in exact}]
    return {
        "exact": [density_payload(key, record) for key, record in exact],
        "related": [density_payload(key, record) for key, record in related[:40]],
        "total_records": len(records),
    }


@app.post("/api/recipe")
def recipe(payload: RecipeRequest):
    db = load_powders()
    selected = []
    for powder in payload.selected_powders:
        try:
            selected.append(normalize_formula(powder))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{powder}: {exc}") from exc

    result = compute_recipe(
        payload.target,
        payload.mass_g,
        db,
        selected,
        mass_basis=payload.mass_basis,
    )
    recipe_masses = result.get("recipe") or {}
    stock_ok = True
    stock_messages: list[str] = []
    inventory = load_inventory()
    if recipe_masses:
        stock_ok, stock_messages = check_stock(inventory, recipe_masses)

    return {
        "result": result,
        "stock_ok": stock_ok,
        "stock_messages": stock_messages,
        "inventory": inventory,
    }


@app.post("/api/target-mass-from-height")
def mass_from_height(payload: HeightRequest):
    try:
        mass_g, volume_cm3 = target_mass_from_height(
            payload.theoretical_density_g_cm3,
            payload.height_mm,
            payload.diameter_mm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "target_mass_g": mass_g,
        "volume_cm3": volume_cm3,
        "diameter_mm": payload.diameter_mm,
        "height_mm": payload.height_mm,
    }


@app.post("/api/relative-density")
def relative_density(payload: RelativeDensityRequest):
    try:
        density, volume = measured_density(
            payload.final_mass_g,
            payload.final_diameter_mm,
            payload.final_height_mm,
        )
        relative = relative_density_percent(density, payload.theoretical_density_g_cm3)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "measured_density_g_cm3": density,
        "relative_density_percent": relative,
        "final_volume_cm3": volume,
    }
