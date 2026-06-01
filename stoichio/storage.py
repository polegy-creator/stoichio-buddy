"""Storage backends and JSON persistence helpers."""

import datetime
import base64
import copy
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
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
MSDS_INVENTORY_FILE = "msds_inventory.json"
BACKUP_DIR_NAME = "backups"
BACKUP_LIMIT_PER_FILE = 30

SHEET_TABS = {
    POWDERS_FILE: "powders",
    INVENTORY_FILE: "inventory",
    INVENTORY_LOG_FILE: "inventory_log",
    HISTORY_FILE: "history",
    MATERIAL_DENSITIES_FILE: "material_densities",
    POWDER_SETS_FILE: "powder_sets",
    MSDS_INVENTORY_FILE: "msds_inventory",
}

_storage_backend = None
_storage_label = "Local JSON files"
_storage_error = None
_MISSING = object()


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


class GitHubJsonStore:
    """Tiny JSON document store backed by GitHub repository files.

    This is meant for the Vercel lab website: the deployed app cannot persist
    local file writes, so JSON documents are committed to a data branch instead.
    """

    def __init__(self, repo, token, branch="lab-data", path_prefix=""):
        if not repo or "/" not in repo:
            raise RuntimeError("GITHUB_DATA_REPO must look like owner/repository")
        if not token:
            raise RuntimeError("GITHUB_DATA_TOKEN is required for GitHub JSON storage")

        self.repo = repo.strip()
        self.token = token.strip()
        self.branch = str(branch or "lab-data").strip()
        self.path_prefix = str(path_prefix or "").strip().strip("/")
        self.api_root = f"https://api.github.com/repos/{self.repo}/contents"
        self._loaded_documents = {}

    def _repo_path(self, path, preserve_dirs=False):
        repo_path = str(path or "").strip().strip("/") if preserve_dirs else os.path.basename(path)
        if self.path_prefix:
            return f"{self.path_prefix}/{repo_path}"
        return repo_path

    def _request(self, method, url, payload=None, allow_404=False):
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "stoichio-buddy",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read().decode("utf-8")
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as exc:
            if allow_404 and exc.code == 404:
                return None
            try:
                error_payload = json.loads(exc.read().decode("utf-8"))
                message = error_payload.get("message", str(exc))
            except Exception:
                message = str(exc)
            raise RuntimeError(f"GitHub storage HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitHub storage request failed: {exc}") from exc

    def _content_url(self, path, preserve_dirs=False):
        repo_path = urllib.parse.quote(self._repo_path(path, preserve_dirs=preserve_dirs), safe="/")
        return f"{self.api_root}/{repo_path}?ref={urllib.parse.quote(self.branch)}"

    def _put_url(self, path, preserve_dirs=False):
        repo_path = urllib.parse.quote(self._repo_path(path, preserve_dirs=preserve_dirs), safe="/")
        return f"{self.api_root}/{repo_path}"

    def _load_content_record(self, path, allow_404=False, preserve_dirs=False):
        record = self._request("GET", self._content_url(path, preserve_dirs=preserve_dirs), allow_404=allow_404)
        if record is None:
            return None
        if not record.get("content") and record.get("git_url"):
            blob = self._request("GET", record["git_url"], allow_404=allow_404)
            if blob:
                record = {
                    **record,
                    "content": blob.get("content", ""),
                    "encoding": blob.get("encoding", record.get("encoding")),
                }
        return record

    def load(self, path, default):
        record = self._load_content_record(path, allow_404=True)
        if record is None:
            self._remember_loaded_document(path, default, None)
            return default
        content = record.get("content", "")
        if not content:
            self._remember_loaded_document(path, default, record.get("sha"))
            return default
        try:
            decoded = base64.b64decode(content).decode("utf-8").strip()
            data = json.loads(decoded) if decoded else default
            self._remember_loaded_document(path, data, record.get("sha"))
            return data
        except (ValueError, json.JSONDecodeError):
            self._remember_loaded_document(path, default, record.get("sha"))
            return default

    @staticmethod
    def _decode_content_record(record, default):
        if record is None:
            return copy.deepcopy(default), None
        content = record.get("content", "")
        if not content:
            return copy.deepcopy(default), record.get("sha")
        decoded = base64.b64decode(content).decode("utf-8").strip()
        return (json.loads(decoded) if decoded else copy.deepcopy(default)), record.get("sha")

    def _remember_loaded_document(self, path, data, sha):
        self._loaded_documents[self._repo_path(path)] = {
            "sha": sha,
            "data": copy.deepcopy(data),
        }

    def save(self, path, data):
        repo_path = self._repo_path(path)
        existing = self._load_content_record(path, allow_404=True)
        existing_data, existing_sha = self._decode_content_record(existing, None)
        loaded = self._loaded_documents.get(repo_path)
        data_to_save = data

        if loaded and loaded.get("sha") != existing_sha:
            data_to_save = merge_json_documents(
                loaded.get("data"),
                data,
                existing_data,
                path=os.path.basename(path),
            )

        payload = {
            "message": f"Update Stoichio Buddy data: {os.path.basename(path)}",
            "content": self._encoded_content(data_to_save),
            "branch": self.branch,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        try:
            response = self._request("PUT", self._put_url(path), payload=payload)
        except RuntimeError as exc:
            # Retry once with a fresh SHA in case two lab users saved near the same time.
            if "409" not in str(exc):
                raise
            existing = self._load_content_record(path, allow_404=False)
            retry_data, retry_sha = self._decode_content_record(existing, None)
            data_to_save = merge_json_documents(
                loaded.get("data") if loaded else existing_data,
                data_to_save,
                retry_data,
                path=os.path.basename(path),
            )
            payload["content"] = self._encoded_content(data_to_save)
            payload["sha"] = retry_sha
            response = self._request("PUT", self._put_url(path), payload=payload)

        saved_sha = (response.get("content") or {}).get("sha") if isinstance(response, dict) else None
        self._remember_loaded_document(path, data_to_save, saved_sha)

    @staticmethod
    def _encoded_content(data):
        payload_text = json.dumps(data, indent=4)
        return base64.b64encode((payload_text + "\n").encode("utf-8")).decode("ascii")

    def load_binary(self, path, default=b""):
        record = self._load_content_record(path, allow_404=True, preserve_dirs=True)
        if record is None:
            return default
        content = record.get("content", "")
        if not content:
            return default
        try:
            return base64.b64decode(content)
        except ValueError:
            return default

    def save_binary(self, path, data, message=None):
        record = self._load_content_record(path, allow_404=True, preserve_dirs=True)
        existing_sha = record.get("sha") if record else None
        payload = {
            "message": message or f"Update Stoichio Buddy file: {path}",
            "content": base64.b64encode(data).decode("ascii"),
            "branch": self.branch,
        }
        if existing_sha:
            payload["sha"] = existing_sha
        return self._request("PUT", self._put_url(path, preserve_dirs=True), payload=payload)

    def delete_binary(self, path, message=None):
        record = self._load_content_record(path, allow_404=True, preserve_dirs=True)
        if record is None:
            return
        payload = {
            "message": message or f"Delete Stoichio Buddy file: {path}",
            "sha": record["sha"],
            "branch": self.branch,
        }
        self._request("DELETE", self._put_url(path, preserve_dirs=True), payload=payload)


def merge_json_documents(base, local, remote, path="JSON document"):
    try:
        return _merge_json_value(base, local, remote)
    except RuntimeError as exc:
        raise RuntimeError(f"Could not merge concurrent edits in {path}: {exc}") from exc


def _merge_json_value(base, local, remote):
    if local == remote:
        return _copy_json_value(local)
    if remote == base:
        return _copy_json_value(local)
    if local == base:
        return _copy_json_value(remote)

    if isinstance(base, dict) and isinstance(local, dict) and isinstance(remote, dict):
        return _merge_json_dict(base, local, remote)

    if isinstance(base, list) and isinstance(local, list) and isinstance(remote, list):
        return _merge_json_list(base, local, remote)

    raise RuntimeError("same value changed differently by two saves")


def _merge_json_dict(base, local, remote):
    merged = {}
    ordered_keys = []
    for source in (remote, local, base):
        for key in source:
            if key not in ordered_keys:
                ordered_keys.append(key)

    for key in ordered_keys:
        base_value = base.get(key, _MISSING)
        local_value = local.get(key, _MISSING)
        remote_value = remote.get(key, _MISSING)
        merged_value = _merge_json_slot(base_value, local_value, remote_value)
        if merged_value is not _MISSING:
            merged[key] = merged_value
    return merged


def _merge_json_slot(base_value, local_value, remote_value):
    if local_value == remote_value:
        return _copy_json_value(local_value)
    if remote_value == base_value:
        return _copy_json_value(local_value)
    if local_value == base_value:
        return _copy_json_value(remote_value)
    if base_value is _MISSING or local_value is _MISSING or remote_value is _MISSING:
        raise RuntimeError("same key was edited and deleted or created differently")
    return _merge_json_value(base_value, local_value, remote_value)


def _copy_json_value(value):
    if value is _MISSING:
        return _MISSING
    return copy.deepcopy(value)


def _merge_json_list(base, local, remote):
    identity_key = _list_identity_key(base, local, remote)
    if not identity_key:
        raise RuntimeError("same list changed differently and cannot be merged safely")

    base_map = {item[identity_key]: item for item in base}
    local_map = {item[identity_key]: item for item in local}
    remote_map = {item[identity_key]: item for item in remote}

    merged_map = {}
    ordered_ids = []
    for source in (remote, local, base):
        for item in source:
            item_id = item[identity_key]
            if item_id not in ordered_ids:
                ordered_ids.append(item_id)

    for item_id in ordered_ids:
        merged_value = _merge_json_slot(
            base_map.get(item_id, _MISSING),
            local_map.get(item_id, _MISSING),
            remote_map.get(item_id, _MISSING),
        )
        if merged_value is not _MISSING:
            merged_map[item_id] = merged_value

    return [merged_map[item_id] for item_id in ordered_ids if item_id in merged_map]


def _list_identity_key(*lists):
    items = [item for values in lists for item in values]
    if not items:
        return None
    if not all(isinstance(item, dict) for item in items):
        return None

    for key in ("entry_id", "record_id", "id"):
        if all(key in item and item.get(key) for item in items) and all(
            len([item[key] for item in values]) == len({item[key] for item in values})
            for values in lists
        ):
            return key
    return None


def running_on_vercel():
    return os.environ.get("VERCEL") == "1"


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


def configure_github_json(repo, token, branch="lab-data", path_prefix=""):
    global _storage_backend, _storage_label, _storage_error
    _storage_backend = GitHubJsonStore(
        repo=repo,
        token=token,
        branch=branch,
        path_prefix=path_prefix,
    )
    _storage_label = f"GitHub JSON: {_storage_backend.repo}@{_storage_backend.branch}"
    _storage_error = None


def disable_shared_storage(exc):
    global _storage_backend, _storage_label, _storage_error
    _storage_backend = None
    _storage_label = "Local JSON files (shared storage unavailable)"
    _storage_error = str(exc)


def record_shared_storage_error(exc):
    global _storage_error
    _storage_error = str(exc)


def storage_label():
    return _storage_label


def storage_error():
    return _storage_error


def has_shared_storage():
    return _storage_backend is not None


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
            if running_on_vercel():
                record_shared_storage_error(exc)
                raise RuntimeError(
                    f"Shared storage write failed; data was not saved: {exc}"
                ) from exc
            disable_shared_storage(exc)
    if running_on_vercel():
        raise RuntimeError("Shared storage is unavailable; data was not saved.")
    save_json_file(path, data)


def has_binary_storage():
    return _storage_backend is None or all(
        hasattr(_storage_backend, method)
        for method in ("load_binary", "save_binary")
    )


def load_binary_file(path, default=b""):
    try:
        with open(path, "rb") as source:
            return source.read()
    except OSError:
        return default


def save_binary_file(path, data):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=directory, delete=False) as f:
        f.write(data)
        temp_path = f.name
    os.replace(temp_path, path)


def delete_binary_file(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def load_binary(path, default=b""):
    if _storage_backend is not None and hasattr(_storage_backend, "load_binary"):
        try:
            return _storage_backend.load_binary(path, default=default)
        except Exception as exc:
            if running_on_vercel():
                record_shared_storage_error(exc)
                raise RuntimeError(
                    f"Shared storage read failed; file was not loaded: {exc}"
                ) from exc
            disable_shared_storage(exc)
    if running_on_vercel():
        raise RuntimeError("Shared storage is unavailable; file was not loaded.")
    return load_binary_file(path, default)


def save_binary(path, data, message=None):
    if _storage_backend is not None and hasattr(_storage_backend, "save_binary"):
        try:
            _storage_backend.save_binary(path, data, message=message)
            return
        except Exception as exc:
            if running_on_vercel():
                record_shared_storage_error(exc)
                raise RuntimeError(
                    f"Shared storage write failed; file was not saved: {exc}"
                ) from exc
            disable_shared_storage(exc)
    if running_on_vercel():
        raise RuntimeError("Shared storage is unavailable; file was not saved.")
    save_binary_file(path, data)


def delete_binary(path, message=None):
    if _storage_backend is not None and hasattr(_storage_backend, "delete_binary"):
        try:
            _storage_backend.delete_binary(path, message=message)
            return
        except Exception as exc:
            if running_on_vercel():
                record_shared_storage_error(exc)
                raise RuntimeError(
                    f"Shared storage delete failed; file was not deleted: {exc}"
                ) from exc
            disable_shared_storage(exc)
    if running_on_vercel():
        raise RuntimeError("Shared storage is unavailable; file was not deleted.")
    delete_binary_file(path)
