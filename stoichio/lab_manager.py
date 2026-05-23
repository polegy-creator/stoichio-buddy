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

from stoichio.chemistry.formula_parser import molar_mass, normalize_formula, parse_formula

# =========================
# FILE PATHS
# =========================

POWDERS_FILE = "powders.json"
INVENTORY_FILE = "inventory.json"
INVENTORY_LOG_FILE = "inventory_log.json"
HISTORY_FILE = "history.json"
MATERIAL_DENSITIES_FILE = "material_densities.json"
POWDER_SETS_FILE = "powder_sets.json"
BACKUP_DIR_NAME = "backups"
BACKUP_LIMIT_PER_FILE = 30

PREFERRED_DENSITY_STATUS = "Preferred for formula"
LAB_CHECKED_DENSITY_STATUS = "Lab checked"
LAB_UNVERIFIED_DENSITY_STATUS = "Lab entry - unverified"
CODEX_UNVERIFIED_DENSITY_STATUS = "Codex seeded - verify before use"
BLOCKED_DENSITY_STATUS = "Do not use"
POWDER_RELEVANCE_IGNORED_ELEMENTS = {"O", "H", "C", "N"}

SHEET_TABS = {
    POWDERS_FILE: "powders",
    INVENTORY_FILE: "inventory",
    INVENTORY_LOG_FILE: "inventory_log",
    HISTORY_FILE: "history",
    MATERIAL_DENSITIES_FILE: "material_densities",
    POWDER_SETS_FILE: "powder_sets",
}

_storage_backend = None
_storage_label = "Local JSON files"
_storage_error = None

# =========================
# NORMALIZATION
# =========================

def normalize_powder(name):
    return normalize_formula(name)


def material_density_record_key(formula, phase=""):
    formula_key = normalize_formula(formula)
    phase_key = re.sub(r"[^A-Za-z0-9]+", "-", str(phase or "").strip()).strip("-").lower()
    if not phase_key:
        return formula_key
    return f"{formula_key}__{phase_key}"


def first_url(value):
    match = re.search(r"https?://[^\s<>\"]+", str(value or ""))
    return match.group(0) if match else ""


def first_doi(value):
    text = str(value or "").strip()
    doi_match = re.search(r"(10\.\d{4,9}/[^\s<>\"]+)", text, flags=re.IGNORECASE)
    if doi_match:
        return doi_match.group(1).rstrip(".,;)")

    doi_url_match = re.search(r"doi\.org/(10\.\d{4,9}/[^\s<>\"]+)", text, flags=re.IGNORECASE)
    if doi_url_match:
        return doi_url_match.group(1).rstrip(".,;)")
    return ""


def first_cod_id(value):
    match = re.search(r"\bCOD\s*[:#]?\s*(\d{5,})\b", str(value or ""), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def formula_cation_elements(formula):
    composition = parse_formula(normalize_formula(formula))
    return {element for element in composition if element != "O"}


def powder_relevance_elements(composition):
    return {
        element
        for element, amount in composition.items()
        if float(amount) != 0.0 and element not in POWDER_RELEVANCE_IGNORED_ELEMENTS
    }


def relevant_powders_for_target(target, powders):
    powder_names = list(powders.keys())
    if not str(target or "").strip():
        return powder_names, [], set(), None

    try:
        target_elements = powder_relevance_elements(parse_formula(normalize_formula(target)))
    except ValueError as exc:
        return powder_names, [], set(), str(exc)

    if not target_elements:
        return powder_names, [], target_elements, None

    relevant = []
    hidden = []
    for powder, record in powders.items():
        powder_elements = powder_relevance_elements(record.get("elements", {}))
        if powder_elements and powder_elements <= target_elements and powder_elements & target_elements:
            relevant.append(powder)
        else:
            hidden.append(powder)

    return relevant, hidden, target_elements, None


def powder_family_key(elements):
    return "-".join(sorted(elements))


def powder_set_family_for_target(target):
    if not str(target or "").strip():
        return "", set(), None

    try:
        normalized_target = normalize_formula(target)
        target_elements = powder_relevance_elements(parse_formula(normalized_target))
    except ValueError as exc:
        return "", set(), str(exc)

    if not target_elements:
        return "", target_elements, None
    return powder_family_key(target_elements), target_elements, None


def material_density_status(record):
    status = str(record.get("verification_status", "")).strip()
    if status:
        return status
    if str(record.get("origin", "")).lower().startswith("codex"):
        return CODEX_UNVERIFIED_DENSITY_STATUS
    return LAB_UNVERIFIED_DENSITY_STATUS


def material_density_trust_rank(record):
    status = material_density_status(record).lower()
    if "do not use" in status:
        return 99
    if "preferred" in status:
        return 0
    if "checked" in status:
        return 1
    if "lab entry" in status:
        return 2
    if "codex" in status:
        return 3
    return 4


def related_material_density_records(target, material_densities):
    try:
        target_elements = formula_cation_elements(target)
    except ValueError:
        return []

    if not target_elements:
        return []

    matches = []
    for record_key, record in material_densities.items():
        try:
            record_elements = formula_cation_elements(record.get("formula", record_key))
        except ValueError:
            continue

        overlap = target_elements & record_elements
        if not overlap:
            continue

        matches.append(
            (
                -len(overlap),
                len(record_elements - target_elements),
                material_density_trust_rank(record),
                record.get("formula", record_key),
                record.get("phase", ""),
                record.get("display_name", record_key),
                record_key,
                record,
            )
        )

    matches.sort()
    return [(record_key, record) for *_, record_key, record in matches]


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
        backup_json_file(path)
        directory = os.path.dirname(os.path.abspath(path)) or "."
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as f:
            json.dump(data, f, indent=4)
            f.write("\n")
            temp_path = f.name
        os.replace(temp_path, path)


def backup_json_file(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None

    directory = os.path.dirname(os.path.abspath(path)) or "."
    backup_dir = os.path.join(directory, BACKUP_DIR_NAME)
    os.makedirs(backup_dir, exist_ok=True)

    base_name = os.path.basename(path)
    stem, extension = os.path.splitext(base_name)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = os.path.join(backup_dir, f"{stem}_{timestamp}{extension or '.json'}")

    with open(path, "rb") as source, open(backup_path, "wb") as destination:
        destination.write(source.read())

    prune_json_backups(backup_dir, stem, extension or ".json")
    return backup_path


def prune_json_backups(backup_dir, stem, extension):
    prefix = f"{stem}_"
    backups = sorted(
        os.path.join(backup_dir, name)
        for name in os.listdir(backup_dir)
        if name.startswith(prefix) and name.endswith(extension)
    )
    excess = len(backups) - BACKUP_LIMIT_PER_FILE
    for backup_path in backups[:max(0, excess)]:
        try:
            os.remove(backup_path)
        except OSError:
            pass


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
        before = inventory.pop(key, None)
        save_inventory(inventory)
        if before is not None:
            log_inventory_transaction(
                key,
                -float(before),
                before_g=float(before),
                after_g=0.0,
                action="delete powder",
                reason="Powder deleted from database",
            )

    return powders


# =========================
# SAVED POWDER SETS
# =========================

def _unique_normalized_powders(powders):
    normalized = []
    seen = set()
    for powder in powders or []:
        key = normalize_powder(powder)
        if key not in seen:
            normalized.append(key)
            seen.add(key)
    return normalized


def normalize_powder_set_record(record_id, record):
    raw_elements = record.get("target_elements", [])
    target_elements = {
        str(element).strip()
        for element in raw_elements
        if str(element).strip()
    }

    target_formula = str(record.get("target_formula", "")).strip()
    if target_formula:
        try:
            target_formula = normalize_formula(target_formula)
            if not target_elements:
                target_elements = powder_relevance_elements(parse_formula(target_formula))
        except ValueError:
            target_formula = str(record.get("target_formula", "")).strip()

    family = str(record.get("family", "")).strip()
    if not family and target_elements:
        family = powder_family_key(target_elements)

    powders = _unique_normalized_powders(record.get("powders", []))
    name = str(record.get("name", "")).strip()
    if not name:
        name = f"{family or 'General'} powder set"

    created_at = str(record.get("created_at", "")).strip()
    updated_at = str(record.get("updated_at", "")).strip()

    return {
        "record_id": str(record.get("record_id") or record_id or uuid.uuid4().hex),
        "name": name,
        "family": family,
        "target_formula": target_formula,
        "target_elements": sorted(target_elements),
        "powders": powders,
        "notes": str(record.get("notes", "")).strip(),
        "created_at": created_at,
        "updated_at": updated_at,
        "last_used_at": str(record.get("last_used_at", "")).strip(),
        "use_count": int(record.get("use_count", 0) or 0),
    }


def load_powder_sets():
    raw_sets = load_json(POWDER_SETS_FILE, {})
    if not isinstance(raw_sets, dict):
        raw_sets = {}

    powder_sets = {}
    for record_id, record in raw_sets.items():
        if not isinstance(record, dict):
            continue
        normalized = normalize_powder_set_record(record_id, record)
        powder_sets[normalized["record_id"]] = normalized

    if powder_sets != raw_sets:
        save_powder_sets(powder_sets)
    return powder_sets


def save_powder_sets(powder_sets):
    save_json(POWDER_SETS_FILE, powder_sets)


def save_powder_set(target, powders, name="", notes="", record_id=None):
    family, target_elements, error = powder_set_family_for_target(target)
    if error:
        raise ValueError(error)
    if not target_elements:
        raise ValueError("Enter a target formula before saving a powder set")

    selected_powders = _unique_normalized_powders(powders)
    if not selected_powders:
        raise ValueError("Select at least one powder before saving a powder set")

    powder_sets = load_powder_sets()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    record_key = str(record_id or uuid.uuid4().hex)
    existing = powder_sets.get(record_key, {})
    record = {
        "record_id": record_key,
        "name": str(name or "").strip() or f"{family} powder set",
        "family": family,
        "target_formula": normalize_formula(target),
        "target_elements": sorted(target_elements),
        "powders": selected_powders,
        "notes": str(notes or "").strip(),
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "last_used_at": existing.get("last_used_at", ""),
        "use_count": existing.get("use_count", 0),
    }
    normalized = normalize_powder_set_record(record_key, record)
    powder_sets[record_key] = normalized
    save_powder_sets(powder_sets)
    return record_key, powder_sets


def matching_powder_sets_for_target(target, powder_sets):
    family, _, error = powder_set_family_for_target(target)
    if error or not family:
        return []
    matches = [
        (record_id, record)
        for record_id, record in powder_sets.items()
        if record.get("family") == family
    ]
    matches.sort(
        key=lambda item: (
            -int(item[1].get("use_count", 0) or 0),
            item[1].get("name", ""),
            item[0],
        )
    )
    return matches


def record_powder_set_use(record_id):
    powder_sets = load_powder_sets()
    key = str(record_id).strip()
    if key not in powder_sets:
        raise ValueError(f"Powder set not found: {record_id}")

    record = dict(powder_sets[key])
    record["use_count"] = int(record.get("use_count", 0) or 0) + 1
    record["last_used_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    powder_sets[key] = normalize_powder_set_record(key, record)
    save_powder_sets(powder_sets)
    return key, powder_sets


def delete_powder_set(record_id):
    powder_sets = load_powder_sets()
    key = str(record_id).strip()
    if key not in powder_sets:
        raise ValueError(f"Powder set not found: {record_id}")
    powder_sets.pop(key)
    save_powder_sets(powder_sets)
    return powder_sets


# =========================
# MATERIAL DENSITY DATABASE
# =========================

def normalize_density_record(formula, record):
    raw_formula = record.get("formula") or str(formula).split("__", 1)[0]
    key = normalize_formula(raw_formula)
    phase = str(record.get("phase", "")).strip()
    display_name = str(record.get("display_name", "")).strip()
    if not display_name:
        display_name = f"{key} ({phase})" if phase else key
    record_id = material_density_record_key(key, phase)
    normalized = {
        "record_id": record_id,
        "formula": key,
        "phase": phase,
        "display_name": display_name,
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
        "reported_density_g_cm3": None,
        "density_delta_g_cm3": None,
        "density_validation": str(record.get("density_validation", "")).strip(),
        "source": str(record.get("source", "")).strip(),
        "source_url": str(record.get("source_url", "")).strip(),
        "doi": str(record.get("doi", "")).strip(),
        "cod_id": str(record.get("cod_id", "")).strip(),
        "paper_title": str(record.get("paper_title", "")).strip(),
        "notes": str(record.get("notes", "")).strip(),
        "origin": str(record.get("origin", record.get("added_by", "Lab entry"))).strip() or "Lab entry",
        "verification_status": str(record.get("verification_status", "")).strip(),
        "verified_by": str(record.get("verified_by", "")).strip(),
        "verified_date": str(record.get("verified_date", "")).strip(),
    }
    if not normalized["source_url"]:
        normalized["source_url"] = first_url(normalized["source"])
    if not normalized["doi"]:
        normalized["doi"] = first_doi(normalized["source"])
    if not normalized["cod_id"]:
        normalized["cod_id"] = first_cod_id(normalized["source"])
    if not normalized["verification_status"]:
        if normalized["origin"].lower().startswith("codex"):
            normalized["verification_status"] = "Codex seeded - verify before use"
        else:
            normalized["verification_status"] = "Lab entry - unverified"

    volume = record.get("unit_cell_volume_A3")
    if volume not in (None, ""):
        normalized["unit_cell_volume_A3"] = float(volume)

    z = record.get("z")
    if z not in (None, ""):
        normalized["z"] = float(z)

    density = record.get("theoretical_density_g_cm3")
    if density not in (None, ""):
        normalized["theoretical_density_g_cm3"] = float(density)

    reported_density = record.get("reported_density_g_cm3")
    if reported_density not in (None, ""):
        normalized["reported_density_g_cm3"] = float(reported_density)

    density_delta = record.get("density_delta_g_cm3")
    if density_delta not in (None, ""):
        normalized["density_delta_g_cm3"] = float(density_delta)

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

    for record_key, record in raw_records.items():
        normalized = normalize_density_record(record_key, record)
        records[normalized["record_id"]] = normalized

    if records != raw_records:
        save_material_densities(records)
    return records


def save_material_densities(records):
    save_json(MATERIAL_DENSITIES_FILE, records)


def resolve_material_density_key(identifier, records):
    key = str(identifier).strip()
    if key not in records:
        key = material_density_record_key(identifier)
    if key not in records:
        raise ValueError(f"Material density not found: {identifier}")
    return key


def demote_other_preferred_material_densities(records, preferred_key):
    preferred_formula = records[preferred_key].get("formula")
    if not preferred_formula:
        return records

    for record_key, record in records.items():
        if record_key == preferred_key:
            continue
        if record.get("formula") != preferred_formula:
            continue
        if "preferred" in material_density_status(record).lower():
            record["verification_status"] = LAB_CHECKED_DENSITY_STATUS
    return records


def set_preferred_material_density(identifier, verified_by="", verified_date=""):
    records = load_material_densities()
    key = resolve_material_density_key(identifier, records)
    record = dict(records[key])
    record["verification_status"] = PREFERRED_DENSITY_STATUS
    record["verified_by"] = str(verified_by or record.get("verified_by", "")).strip()
    record["verified_date"] = str(verified_date or record.get("verified_date", "")).strip()
    records[key] = normalize_density_record(key, record)
    demote_other_preferred_material_densities(records, key)
    save_material_densities(records)
    return key, records


def update_material_density_review_status(identifier, verification_status, verified_by="", verified_date=""):
    status = str(verification_status or "").strip()
    if not status:
        raise ValueError("Choose a density review status")
    if "preferred" in status.lower():
        return set_preferred_material_density(identifier, verified_by, verified_date)

    records = load_material_densities()
    key = resolve_material_density_key(identifier, records)
    record = dict(records[key])
    record["verification_status"] = status
    record["verified_by"] = str(verified_by or record.get("verified_by", "")).strip()
    record["verified_date"] = str(verified_date or record.get("verified_date", "")).strip()
    records[key] = normalize_density_record(key, record)
    save_material_densities(records)
    return key, records


def upsert_material_density(
    formula,
    phase="",
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
    source_url="",
    doi="",
    cod_id="",
    paper_title="",
    notes="",
    origin="Lab entry",
    reported_density=None,
    density_delta=None,
    density_validation="",
    verification_status="Lab entry - unverified",
    verified_by="",
    verified_date="",
):
    records = load_material_densities()
    key = normalize_formula(formula)
    record = {
        "formula": key,
        "phase": phase,
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
        "reported_density_g_cm3": reported_density,
        "density_delta_g_cm3": density_delta,
        "density_validation": density_validation,
        "source": source,
        "source_url": source_url,
        "doi": doi,
        "cod_id": cod_id,
        "paper_title": paper_title,
        "notes": notes,
        "origin": origin,
        "verification_status": verification_status,
        "verified_by": verified_by,
        "verified_date": verified_date,
    }
    normalized = normalize_density_record(key, record)
    records[normalized["record_id"]] = normalized
    if "preferred" in material_density_status(normalized).lower():
        demote_other_preferred_material_densities(records, normalized["record_id"])
    save_material_densities(records)
    return normalized["record_id"], records


def delete_material_density(identifier):
    records = load_material_densities()
    key = resolve_material_density_key(identifier, records)
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


def load_inventory_log():
    raw_log = load_json(INVENTORY_LOG_FILE, [])
    if not isinstance(raw_log, list):
        return []
    return [dict(entry) for entry in raw_log if isinstance(entry, dict)]


def save_inventory_log(log_entries):
    save_json(INVENTORY_LOG_FILE, log_entries)


def log_inventory_transaction(
    powder,
    change_g,
    before_g=None,
    after_g=None,
    action="manual update",
    reason="",
    recipe_id="",
    notes="",
):
    key = normalize_powder(powder)
    entry = {
        "entry_id": uuid.uuid4().hex,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "powder": key,
        "change_g": round(float(change_g), 6),
        "before_g": None if before_g is None else round(float(before_g), 6),
        "after_g": None if after_g is None else round(float(after_g), 6),
        "action": str(action or "").strip(),
        "reason": str(reason or "").strip(),
        "recipe_id": str(recipe_id or "").strip(),
        "notes": str(notes or "").strip(),
    }
    log_entries = load_inventory_log()
    log_entries.append(entry)
    save_inventory_log(log_entries)
    return entry


def add_to_inventory(powder, grams):
    inventory = load_inventory()
    key = normalize_powder(powder)
    before = inventory.get(key, 0.0)
    inventory[key] = before + float(grams)

    save_inventory(inventory)
    log_inventory_transaction(
        key,
        float(grams),
        before_g=before,
        after_g=inventory[key],
        action="add inventory",
    )
    return inventory


def set_inventory_quantity(powder, grams, reason="manual quantity set"):
    inventory = load_inventory()
    key = normalize_powder(powder)
    before = inventory.get(key, 0.0)

    if grams <= 0:
        inventory.pop(key, None)
        after = 0.0
    else:
        inventory[key] = float(grams)
        after = float(grams)

    save_inventory(inventory)
    if round(after - before, 6) != 0:
        log_inventory_transaction(
            key,
            after - before,
            before_g=before,
            after_g=after,
            action="set quantity",
            reason=reason,
        )
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


def consume_stock(inventory, recipe, reason="recipe deduction", recipe_id=""):
    transactions = []
    for powder, amount in recipe.items():
        key = normalize_powder(powder)

        if key in inventory:
            before = float(inventory[key])
            inventory[key] -= amount
            if inventory[key] < 0:
                inventory[key] = 0
            transactions.append((key, -float(amount), before, float(inventory[key])))

    save_inventory(inventory)
    for key, change, before, after in transactions:
        log_inventory_transaction(
            key,
            change,
            before_g=before,
            after_g=after,
            action="recipe deduction",
            reason=reason,
            recipe_id=recipe_id,
        )
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
            target_number = _target_number_from_entry(entry)
            if not person:
                if target_number is not None and entry.get("target_number") != target_number:
                    entry["target_number"] = target_number
                    changed = True
                continue

            used_for_person = used_target_numbers.setdefault(person, set())

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


def validate_backup_data(backup):
    errors = []
    if not isinstance(backup, dict):
        return ["Backup must be a JSON object"]

    required_sections = ("powders", "inventory", "material_densities", "history")
    for section in required_sections:
        if section not in backup:
            errors.append(f"Missing section: {section}")

    powders = backup.get("powders", {})
    if not isinstance(powders, dict):
        errors.append("powders must be an object")
    else:
        for name, record in powders.items():
            if not isinstance(record, dict):
                errors.append(f"Powder {name} must be an object")
                continue
            try:
                normalize_powder(name)
                normalize_powder_record(record)
            except Exception as exc:
                errors.append(f"Powder {name}: {exc}")

    inventory = backup.get("inventory", {})
    if not isinstance(inventory, dict):
        errors.append("inventory must be an object")
    else:
        for powder, grams in inventory.items():
            try:
                normalize_powder(powder)
                float(grams)
            except Exception as exc:
                errors.append(f"Inventory {powder}: {exc}")

    material_densities = backup.get("material_densities", {})
    if not isinstance(material_densities, dict):
        errors.append("material_densities must be an object")
    else:
        for formula, record in material_densities.items():
            if not isinstance(record, dict):
                errors.append(f"Material density {formula} must be an object")
                continue
            try:
                normalize_density_record(formula, record)
            except Exception as exc:
                errors.append(f"Material density {formula}: {exc}")

    powder_sets = backup.get("powder_sets", {})
    if not isinstance(powder_sets, dict):
        errors.append("powder_sets must be an object")
    else:
        for record_id, record in powder_sets.items():
            if not isinstance(record, dict):
                errors.append(f"Powder set {record_id} must be an object")
                continue
            try:
                normalize_powder_set_record(record_id, record)
            except Exception as exc:
                errors.append(f"Powder set {record_id}: {exc}")

    history = backup.get("history", [])
    if not isinstance(history, list):
        errors.append("history must be a list")
    else:
        for index, entry in enumerate(history, start=1):
            if not isinstance(entry, dict):
                errors.append(f"History entry {index} must be an object")

    inventory_log = backup.get("inventory_log", [])
    if not isinstance(inventory_log, list):
        errors.append("inventory_log must be a list")
    else:
        for index, entry in enumerate(inventory_log, start=1):
            if not isinstance(entry, dict):
                errors.append(f"Inventory log entry {index} must be an object")

    return errors


def restore_backup_data(backup):
    errors = validate_backup_data(backup)
    if errors:
        raise ValueError("; ".join(errors))

    powders = {
        normalize_powder(name): normalize_powder_record(record)
        for name, record in backup.get("powders", {}).items()
    }
    inventory = {
        normalize_powder(powder): float(grams)
        for powder, grams in backup.get("inventory", {}).items()
    }
    material_densities = {}
    for record_key, record in backup.get("material_densities", {}).items():
        normalized_record = normalize_density_record(record_key, record)
        material_densities[normalized_record["record_id"]] = normalized_record
    powder_sets = {}
    for record_id, record in backup.get("powder_sets", {}).items():
        normalized_set = normalize_powder_set_record(record_id, record)
        powder_sets[normalized_set["record_id"]] = normalized_set
    history = [dict(entry) for entry in backup.get("history", [])]
    inventory_log = [dict(entry) for entry in backup.get("inventory_log", [])]

    save_powders(powders)
    save_inventory(inventory)
    save_inventory_log(inventory_log)
    save_material_densities(material_densities)
    save_powder_sets(powder_sets)
    save_history(history)

    return {
        "powders": len(powders),
        "inventory": len(inventory),
        "inventory_log": len(inventory_log),
        "material_densities": len(material_densities),
        "powder_sets": len(powder_sets),
        "history": len(history),
    }


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
    calculation=None,
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
    if calculation:
        entry["calculation"] = calculation
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
    linked_recipe=None,
):
    history = load_history()
    target_for = str(target_for or "").strip()
    target_number = _positive_int(target_number)
    target_id = str(target_id or "").strip()

    if target_for and target_number is None:
        target_number = next_target_number(history, target_for)
    if target_for and not target_id:
        target_id = format_target_id(target_for, target_number)

    entry = {
        "entry_id": uuid.uuid4().hex,
        "entry_type": "target_density",
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "target": target,
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
    if linked_recipe:
        entry["linked_recipe"] = linked_recipe
    if target_id:
        entry["target_id"] = target_id
    if target_number is not None:
        entry["target_number"] = target_number
    if target_for:
        entry["target_for"] = target_for

    history.append(entry)
    save_history(history)
    return history
