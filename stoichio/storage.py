"""Storage backends and JSON persistence helpers."""

import datetime
import json
import os
import re
import tempfile
from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None

POWDERS_FILE = "powders.json"
INVENTORY_FILE = "inventory.json"
INVENTORY_LOG_FILE = "inventory_log.json"
HISTORY_FILE = "history.json"
MATERIAL_DENSITIES_FILE = "material_densities.json"
POWDER_SETS_FILE = "powder_sets.json"
BACKUP_DIR_NAME = "backups"
BACKUP_LIMIT_PER_FILE = 30

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
