import json
import os
import datetime
import tempfile
import re
import uuid
from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None

from formula_parser import molar_mass, normalize_formula, parse_formula

# =========================
# FILE PATHS
# =========================

POWDERS_FILE = "powders.json"
INVENTORY_FILE = "inventory.json"
HISTORY_FILE = "history.json"
MATERIAL_DENSITIES_FILE = "material_densities.json"

SHEET_TABS = {
    POWDERS_FILE: "powders",
    INVENTORY_FILE: "inventory",
    HISTORY_FILE: "history",
    MATERIAL_DENSITIES_FILE: "material_densities",
}

_storage_backend = None
_storage_label = "Local JSON files"
_storage_error = None

# =========================
# NORMALIZATION
# =========================

def normalize_powder(name):
    return normalize_formula(name)


class GoogleSheetsStore:
    """Tiny JSON document store backed by Google Sheets tabs."""

    def __init__(self, credentials_info, spreadsheet_id=None, spreadsheet_name=None):
        try:
            import gspread
            from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
        except ImportError as exc:
            raise RuntimeError(
                "Google Sheets storage needs gspread and google-auth. "
                "Run pip install -r requirements.txt."
            ) from exc

        self.gspread = gspread
        self.SpreadsheetNotFound = SpreadsheetNotFound
        self.WorksheetNotFound = WorksheetNotFound
        self.credentials_info = self._clean_credentials(credentials_info)
        self.client = gspread.service_account_from_dict(self.credentials_info)

        if spreadsheet_id:
            self.spreadsheet = self.client.open_by_key(spreadsheet_id)
        else:
            name = spreadsheet_name or "Stoichio Buddy Data"
            try:
                self.spreadsheet = self.client.open(name)
            except SpreadsheetNotFound:
                self.spreadsheet = self.client.create(name)

    @staticmethod
    def _clean_credentials(credentials_info):
        credentials = dict(credentials_info)
        private_key = credentials.get("private_key")
        if isinstance(private_key, str):
            credentials["private_key"] = private_key.replace("\\n", "\n")
        return credentials

    def _worksheet(self, path):
        title = SHEET_TABS.get(os.path.basename(path), os.path.splitext(path)[0])
        try:
            return self.spreadsheet.worksheet(title)
        except self.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=title, rows=200, cols=2)

    def load(self, path, default):
        worksheet = self._worksheet(path)
        chunks = worksheet.col_values(1)
        payload = "".join(chunks).strip()
        if not payload:
            return default
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return default

    def save(self, path, data):
        worksheet = self._worksheet(path)
        payload = json.dumps(data, indent=4)
        chunk_size = 40000
        chunks = [payload[i:i + chunk_size] for i in range(0, len(payload), chunk_size)] or [""]

        worksheet.clear()
        for index, chunk in enumerate(chunks, start=1):
            worksheet.update_acell(f"A{index}", chunk)


class AppsScriptStore:
    """Tiny JSON document store backed by a Google Apps Script web app."""

    def __init__(self, web_app_url, token):
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "Apps Script storage needs requests. Run pip install -r requirements.txt."
            ) from exc

        self.requests = requests
        self.web_app_url = web_app_url
        self.token = token

    def _request(self, action, path, data=None):
        response = self.requests.post(
            self.web_app_url,
            json={
                "token": self.token,
                "action": action,
                "path": os.path.basename(path),
                "data": data,
            },
            timeout=30,
        )

        if response.status_code >= 400:
            response_text = response.text.replace("\n", " ").strip()
            if len(response_text) > 280:
                response_text = response_text[:280] + "..."
            raise RuntimeError(
                f"Apps Script returned HTTP {response.status_code}. "
                "Check that the web app URL ends in /exec, the deployment access is "
                "'Anyone with the link', and the script is deployed as 'Execute as me'. "
                f"Response: {response_text}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            response_text = self._summarize_non_json_response(response.text)
            raise RuntimeError(
                "Apps Script did not return JSON. Make sure you copied the Web App URL "
                "ending in /exec, not the script editor URL. "
                f"HTTP {response.status_code} response started with: {response_text}"
            ) from exc

        if not payload.get("ok"):
            raise RuntimeError(payload.get("error", "Apps Script storage request failed"))
        return payload.get("data")

    @staticmethod
    def _summarize_non_json_response(text):
        message_match = re.search(
            r'<div[^>]*class="errorMessage"[^>]*>(.*?)</div>',
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if message_match:
            text = message_match.group(1)

        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 900:
            text = text[:900] + "..."
        return text

    def load(self, path, default):
        data = self._request("load", path)
        return default if data is None else data

    def save(self, path, data):
        self._request("save", path, data=data)


def configure_google_sheets(credentials_info, spreadsheet_id=None, spreadsheet_name=None):
    global _storage_backend, _storage_label, _storage_error
    _storage_backend = GoogleSheetsStore(
        credentials_info=credentials_info,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_name=spreadsheet_name,
    )
    _storage_error = None
    if spreadsheet_id:
        _storage_label = "Google Sheets"
    else:
        _storage_label = f"Google Sheets: {spreadsheet_name or 'Stoichio Buddy Data'}"


def configure_apps_script(web_app_url, token):
    global _storage_backend, _storage_label, _storage_error
    _storage_backend = AppsScriptStore(web_app_url=web_app_url, token=token)
    _storage_label = "Google Sheets via Apps Script"
    _storage_error = None


def disable_shared_storage(exc):
    global _storage_backend, _storage_label, _storage_error
    _storage_backend = None
    _storage_label = "Local JSON files (shared storage unavailable)"
    _storage_error = str(exc)


def storage_label():
    return _storage_label


def storage_error():
    return _storage_error


def load_json_file(path, default):
    with json_file_lock(path):
        if not os.path.exists(path):
            return default

        try:
            with open(path, "r") as f:
                content = f.read().strip()
                if not content:
                    return default
                return json.loads(content)
        except (OSError, json.JSONDecodeError):
            return default


def save_json_file(path, data):
    with json_file_lock(path):
        directory = os.path.dirname(os.path.abspath(path)) or "."
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as f:
            json.dump(data, f, indent=4)
            f.write("\n")
            temp_path = f.name
        os.replace(temp_path, path)


@contextmanager
def json_file_lock(path):
    if fcntl is None:
        yield
        return

    lock_path = f"{path}.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def load_json(path, default):
    if _storage_backend is None:
        return load_json_file(path, default)

    try:
        data = _storage_backend.load(path, None)
    except Exception as exc:
        disable_shared_storage(exc)
        return load_json_file(path, default)

    if data is not None:
        return data

    seed_data = load_json_file(path, default)
    if seed_data is not None:
        try:
            _storage_backend.save(path, seed_data)
        except Exception as exc:
            disable_shared_storage(exc)
    return seed_data


def save_json(path, data):
    if _storage_backend is not None:
        try:
            _storage_backend.save(path, data)
            return
        except Exception as exc:
            disable_shared_storage(exc)
    save_json_file(path, data)


# =========================
# POWDER DATABASE
# =========================

def default_powders():
    powders = {}
    for formula in ("Fe2O3", "TiO2"):
        composition = parse_formula(formula)
        powders[normalize_formula(formula)] = {
            "molar_mass": molar_mass(composition),
            "elements": composition,
        }
    return powders


def normalize_powder_record(record):
    elements = {element: float(amount) for element, amount in record.get("elements", {}).items()}
    return {
        "molar_mass": molar_mass(elements),
        "elements": elements,
    }


def load_powders():
    powders = load_json(POWDERS_FILE, None)
    if powders is None:
        powders = default_powders()
        save_powders(powders)
        return powders

    normalized = {}
    for name, record in powders.items():
        key = normalize_powder(name)
        normalized[key] = normalize_powder_record(record)
    if normalized != powders:
        save_powders(normalized)
    return normalized


def save_powders(powders):
    save_json(POWDERS_FILE, powders)


def add_powder(formula):
    powders = load_powders()
    key = normalize_formula(formula)
    composition = parse_formula(key)
    powders[key] = {
        "molar_mass": molar_mass(composition),
        "elements": composition,
    }
    save_powders(powders)
    return key, powders


def delete_powder(powder, remove_inventory=True):
    powders = load_powders()
    key = normalize_powder(powder)

    if key not in powders:
        raise ValueError(f"Powder not found: {key}")

    powders.pop(key)
    save_powders(powders)

    if remove_inventory:
        inventory = load_inventory()
        inventory.pop(key, None)
        save_inventory(inventory)

    return powders


# =========================
# MATERIAL DENSITY DATABASE
# =========================

def normalize_density_record(formula, record):
    key = normalize_formula(formula)
    normalized = {
        "formula": key,
        "unit_cell_volume_A3": None,
        "z": None,
        "theoretical_density_g_cm3": None,
        "density_source": record.get("density_source", "manual"),
        "crystal_system": str(record.get("crystal_system", "")).strip(),
        "a_A": None,
        "b_A": None,
        "c_A": None,
        "alpha_deg": None,
        "beta_deg": None,
        "gamma_deg": None,
        "source": str(record.get("source", "")).strip(),
        "notes": str(record.get("notes", "")).strip(),
    }

    volume = record.get("unit_cell_volume_A3")
    if volume not in (None, ""):
        normalized["unit_cell_volume_A3"] = float(volume)

    z = record.get("z")
    if z not in (None, ""):
        normalized["z"] = float(z)

    density = record.get("theoretical_density_g_cm3")
    if density not in (None, ""):
        normalized["theoretical_density_g_cm3"] = float(density)

    for source_key, dest_key in (
        ("a_A", "a_A"),
        ("b_A", "b_A"),
        ("c_A", "c_A"),
        ("alpha_deg", "alpha_deg"),
        ("beta_deg", "beta_deg"),
        ("gamma_deg", "gamma_deg"),
    ):
        value = record.get(source_key)
        if value not in (None, ""):
            normalized[dest_key] = float(value)

    return normalized


def load_material_densities():
    raw_records = load_json(MATERIAL_DENSITIES_FILE, {})
    records = {}

    for formula, record in raw_records.items():
        key = normalize_formula(formula)
        records[key] = normalize_density_record(key, record)

    if records != raw_records:
        save_material_densities(records)
    return records


def save_material_densities(records):
    save_json(MATERIAL_DENSITIES_FILE, records)


def upsert_material_density(
    formula,
    theoretical_density=None,
    unit_cell_volume=None,
    z=None,
    density_source="manual",
    crystal_system="",
    a=None,
    b=None,
    c=None,
    alpha=None,
    beta=None,
    gamma=None,
    source="",
    notes="",
):
    records = load_material_densities()
    key = normalize_formula(formula)
    record = {
        "formula": key,
        "unit_cell_volume_A3": unit_cell_volume,
        "z": z,
        "theoretical_density_g_cm3": theoretical_density,
        "density_source": density_source,
        "crystal_system": crystal_system,
        "a_A": a,
        "b_A": b,
        "c_A": c,
        "alpha_deg": alpha,
        "beta_deg": beta,
        "gamma_deg": gamma,
        "source": source,
        "notes": notes,
    }
    records[key] = normalize_density_record(key, record)
    save_material_densities(records)
    return key, records


def delete_material_density(formula):
    records = load_material_densities()
    key = normalize_formula(formula)
    if key not in records:
        raise ValueError(f"Material density not found: {key}")
    records.pop(key)
    save_material_densities(records)
    return records


# =========================
# INVENTORY SYSTEM
# =========================

def load_inventory():
    raw_inventory = load_json(INVENTORY_FILE, {})
    inventory = {}

    for powder, grams in raw_inventory.items():
        try:
            key = normalize_powder(powder)
        except ValueError:
            key = powder.strip()
        inventory[key] = inventory.get(key, 0.0) + float(grams)

    return inventory


def save_inventory(inventory):
    save_json(INVENTORY_FILE, inventory)


def add_to_inventory(powder, grams):
    inventory = load_inventory()
    key = normalize_powder(powder)

    inventory[key] = inventory.get(key, 0.0) + float(grams)

    save_inventory(inventory)
    return inventory


def set_inventory_quantity(powder, grams):
    inventory = load_inventory()
    key = normalize_powder(powder)

    if grams <= 0:
        inventory.pop(key, None)
    else:
        inventory[key] = float(grams)

    save_inventory(inventory)
    return inventory

# =========================
# STOCK CONTROL
# =========================

def check_stock(inventory, recipe):
    missing = []

    for powder, required in recipe.items():
        key = normalize_powder(powder)
        available = inventory.get(key)

        if available is None:
            missing.append(f"{powder} (not in inventory)")
        elif required > available:
            missing.append(f"{powder} (need {required:.3f} g, have {available:.3f} g)")

    return len(missing) == 0, missing


def consume_stock(inventory, recipe):
    for powder, amount in recipe.items():
        key = normalize_powder(powder)

        if key in inventory:
            inventory[key] -= amount
            if inventory[key] < 0:
                inventory[key] = 0

    save_inventory(inventory)
    return inventory

# =========================
# HISTORY SYSTEM
# =========================

def _positive_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _history_name_code(value, fallback):
    cleaned = "".join(character for character in str(value or "").strip() if character.isalnum())
    return cleaned[:24] or fallback


def _next_unused_number(used_numbers):
    number = max(used_numbers, default=0) + 1
    while number in used_numbers:
        number += 1
    return number


def format_recipe_id(recipe_number):
    number = _positive_int(recipe_number) or 1
    return f"R{number:03d}"


def format_target_id(target_for, target_number):
    number = _positive_int(target_number) or 1
    return f"{_history_name_code(target_for, 'Target')}-T{number:03d}"


def _recipe_number_from_entry(entry):
    number = _positive_int(entry.get("recipe_number"))
    if number is not None:
        return number

    recipe_id = str(entry.get("recipe_id", ""))
    match = re.fullmatch(r"R0*(\d+)", recipe_id, flags=re.IGNORECASE)
    if match:
        return _positive_int(match.group(1))
    return None


def _target_number_from_entry(entry):
    number = _positive_int(entry.get("target_number"))
    if number is not None:
        return number

    target_id = str(entry.get("target_id", ""))
    match = re.search(r"-T0*(\d+)$", target_id, flags=re.IGNORECASE)
    if match:
        return _positive_int(match.group(1))
    return None


def next_recipe_number(history):
    used_numbers = {
        number
        for entry in history
        if isinstance(entry, dict) and history_entry_type(entry) == "synthesis"
        for number in [_recipe_number_from_entry(entry)]
        if number is not None
    }
    return _next_unused_number(used_numbers)


def next_target_number(history, target_for):
    person = str(target_for).strip()
    if not person:
        return 1

    used_numbers = {
        number
        for entry in history
        if isinstance(entry, dict) and str(entry.get("target_for", "")).strip() == person
        for number in [_target_number_from_entry(entry)]
        if number is not None
    }
    return _next_unused_number(used_numbers)


def load_history():
    history = load_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        return []

    changed = False
    used_recipe_numbers = {
        number
        for entry in history
        if isinstance(entry, dict) and history_entry_type(entry) == "synthesis"
        for number in [_recipe_number_from_entry(entry)]
        if number is not None
    }
    used_target_numbers = {}

    for entry in history:
        if not isinstance(entry, dict):
            continue
        person = str(entry.get("target_for", "")).strip()
        if not person:
            continue
        number = _target_number_from_entry(entry)
        if number is not None:
            used_target_numbers.setdefault(person, set()).add(number)

    for entry in history:
        if not isinstance(entry, dict):
            continue

        if not entry.get("entry_id"):
            entry["entry_id"] = uuid.uuid4().hex
            changed = True

        entry_type = history_entry_type(entry)
        if entry_type == "synthesis":
            recipe_number = _recipe_number_from_entry(entry)
            if recipe_number is None:
                recipe_number = _next_unused_number(used_recipe_numbers)
                used_recipe_numbers.add(recipe_number)
                entry["recipe_number"] = recipe_number
                entry["recipe_id"] = format_recipe_id(recipe_number)
                changed = True
            else:
                used_recipe_numbers.add(recipe_number)
                if entry.get("recipe_number") != recipe_number:
                    entry["recipe_number"] = recipe_number
                    changed = True
                if not entry.get("recipe_id"):
                    entry["recipe_id"] = format_recipe_id(recipe_number)
                    changed = True

            person = str(entry.get("target_for", "")).strip()
            if person:
                used_for_person = used_target_numbers.setdefault(person, set())
                target_number = _target_number_from_entry(entry)

                if target_number is None:
                    target_number = _next_unused_number(used_for_person)
                    used_for_person.add(target_number)
                    entry["target_number"] = target_number
                    entry["target_id"] = format_target_id(person, target_number)
                    changed = True
                else:
                    used_for_person.add(target_number)
                    if entry.get("target_number") != target_number:
                        entry["target_number"] = target_number
                        changed = True
                    if not entry.get("target_id"):
                        entry["target_id"] = format_target_id(person, target_number)
                        changed = True

        if entry_type == "target_density":
            person = str(entry.get("target_for", "")).strip()
            used_for_person = used_target_numbers.setdefault(person, set())
            target_number = _target_number_from_entry(entry)

            if target_number is None:
                target_number = _next_unused_number(used_for_person)
                used_for_person.add(target_number)
                entry["target_number"] = target_number
                entry["target_id"] = format_target_id(person, target_number)
                changed = True
            else:
                used_for_person.add(target_number)
                if entry.get("target_number") != target_number:
                    entry["target_number"] = target_number
                    changed = True
                if not entry.get("target_id"):
                    entry["target_id"] = format_target_id(person, target_number)
                    changed = True

    if changed:
        save_history(history)

    return history


def save_history(history):
    save_json(HISTORY_FILE, history)


def history_entry_type(entry):
    return entry.get("entry_type", "synthesis")


def clear_history_for_target(target):
    history = load_history()
    remaining = [
        entry
        for entry in history
        if not (history_entry_type(entry) == "synthesis" and entry.get("target") == target)
    ]
    removed_count = len(history) - len(remaining)
    save_history(remaining)
    return removed_count, remaining


def delete_history_entry(entry_id):
    history = load_history()
    entry_key = str(entry_id)
    remaining = [
        entry
        for entry in history
        if str(entry.get("entry_id", "")) != entry_key
    ]
    removed_count = len(history) - len(remaining)
    if removed_count:
        save_history(remaining)
    return removed_count, remaining


def clear_target_density_history_for_person(target_for):
    history = load_history()
    person = str(target_for).strip()
    remaining = [
        entry
        for entry in history
        if not (
            history_entry_type(entry) == "target_density"
            and str(entry.get("target_for", "")).strip() == person
        )
    ]
    removed_count = len(history) - len(remaining)
    save_history(remaining)
    return removed_count, remaining


def clear_history_for_target_id(target_id):
    history = load_history()
    target_key = str(target_id).strip()
    remaining = [
        entry
        for entry in history
        if str(entry.get("target_id", "")).strip() != target_key
    ]
    removed_count = len(history) - len(remaining)
    if removed_count:
        save_history(remaining)
    return removed_count, remaining


def log_synthesis(
    target,
    mass,
    recipe,
    selected_powders=None,
    warning=None,
    inventory_deducted=False,
    notes=None,
    target_for=None,
    target_number=None,
    target_id=None,
):
    history = load_history()
    recipe_number = next_recipe_number(history)
    target_for = str(target_for or "").strip()
    if target_for:
        target_number = int(target_number or next_target_number(history, target_for))
        target_id = target_id or format_target_id(target_for, target_number)

    entry = {
        "entry_id": uuid.uuid4().hex,
        "entry_type": "synthesis",
        "recipe_id": format_recipe_id(recipe_number),
        "recipe_number": recipe_number,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "target": target,
        "mass": mass,
        "selected_powders": selected_powders or [],
        "recipe": recipe,
        "warning": warning,
        "inventory_deducted": inventory_deducted,
        "notes": str(notes or "").strip(),
    }
    if target_for:
        entry.update(
            {
                "target_id": target_id,
                "target_number": target_number,
                "target_for": target_for,
            }
        )

    history.append(entry)
    save_history(history)
    return history


def log_target_density(
    target,
    target_number,
    target_for,
    measured_density,
    theoretical_density,
    relative_density,
    final_volume,
    final_mass,
    final_diameter,
    final_height,
    density_source=None,
    notes=None,
    target_id=None,
):
    history = load_history()
    target_for = str(target_for).strip()
    target_number = int(target_number)
    target_id = target_id or format_target_id(target_for, target_number)

    entry = {
        "entry_id": uuid.uuid4().hex,
        "entry_type": "target_density",
        "target_id": target_id,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "target": target,
        "target_number": target_number,
        "target_for": target_for,
        "measured_density_g_cm3": float(measured_density),
        "theoretical_density_g_cm3": float(theoretical_density),
        "relative_density_percent": float(relative_density),
        "final_volume_cm3": float(final_volume),
        "final_mass_g": float(final_mass),
        "final_diameter_mm": float(final_diameter),
        "final_height_mm": float(final_height),
        "density_source": density_source or "",
        "notes": str(notes or "").strip(),
    }

    history.append(entry)
    save_history(history)
    return history
