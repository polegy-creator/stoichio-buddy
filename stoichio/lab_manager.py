"""Compatibility facade for Stoichio Buddy lab data helpers.

The implementation now lives in focused modules (`storage`, `powders`,
`inventory`, `history`, `density_records`, `powder_sets`, and `backup_data`).
This facade keeps older imports working while new code can depend on the
smaller domain modules directly.
"""

import os
import sys
import types

import stoichio.density_records as _density_records_module
import stoichio.history as _history_module
import stoichio.inventory as _inventory_module
import stoichio.powder_sets as _powder_sets_module
import stoichio.powders as _powders_module
import stoichio.storage as _storage_module

from stoichio.backup_data import restore_backup_data, validate_backup_data
from stoichio.density_records import (
    BLOCKED_DENSITY_STATUS,
    CODEX_UNVERIFIED_DENSITY_STATUS,
    LAB_CHECKED_DENSITY_STATUS,
    LAB_UNVERIFIED_DENSITY_STATUS,
    PREFERRED_DENSITY_STATUS,
    delete_material_density,
    first_cod_id,
    first_doi,
    first_url,
    load_material_densities,
    material_density_record_key,
    material_density_status,
    material_density_trust_rank,
    normalize_density_record,
    related_material_density_records,
    save_material_densities,
    set_preferred_material_density,
    update_material_density_review_status,
    upsert_material_density,
)
from stoichio.history import (
    clear_history_for_target,
    clear_history_for_target_id,
    clear_target_density_history_for_person,
    delete_history_entry,
    format_recipe_id,
    format_target_id,
    history_entry_type,
    load_history,
    log_synthesis,
    log_target_density,
    next_recipe_number,
    next_target_number,
    save_history,
)
from stoichio.inventory import (
    add_to_inventory,
    check_stock,
    consume_stock,
    load_inventory,
    load_inventory_log,
    log_inventory_transaction,
    save_inventory,
    save_inventory_log,
    set_inventory_quantity,
)
from stoichio.powder_sets import (
    delete_powder_set,
    load_powder_sets,
    matching_powder_sets_for_target,
    normalize_powder_set_record,
    powder_family_key,
    powder_set_family_for_target,
    record_powder_set_use,
    save_powder_set,
    save_powder_sets,
)
from stoichio.powders import (
    POWDER_RELEVANCE_IGNORED_ELEMENTS,
    add_powder,
    default_powders,
    delete_powder,
    formula_cation_elements,
    load_powders,
    normalize_powder,
    normalize_powder_record,
    powder_relevance_elements,
    relevant_powders_for_target,
    save_powders,
)
from stoichio.storage import (
    BACKUP_DIR_NAME,
    BACKUP_LIMIT_PER_FILE,
    HISTORY_FILE,
    INVENTORY_FILE,
    INVENTORY_LOG_FILE,
    MATERIAL_DENSITIES_FILE,
    POWDER_SETS_FILE,
    POWDERS_FILE,
    SHEET_TABS,
    AppsScriptStore,
    GoogleSheetsStore,
    _storage_backend,
    _storage_error,
    _storage_label,
    backup_json_file,
    configure_apps_script,
    configure_google_sheets,
    disable_shared_storage,
    json_file_lock,
    load_json,
    load_json_file,
    prune_json_backups,
    save_json,
    save_json_file,
    storage_error,
    storage_label,
)


_COMPAT_ASSIGN_TARGETS = {
    "POWDERS_FILE": (_storage_module, _powders_module),
    "INVENTORY_FILE": (_storage_module, _inventory_module),
    "INVENTORY_LOG_FILE": (_storage_module, _inventory_module),
    "HISTORY_FILE": (_storage_module, _history_module),
    "MATERIAL_DENSITIES_FILE": (_storage_module, _density_records_module),
    "POWDER_SETS_FILE": (_storage_module, _powder_sets_module),
    "_storage_backend": (_storage_module,),
    "_storage_label": (_storage_module,),
    "_storage_error": (_storage_module,),
}


class _LabManagerCompatModule(types.ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for module in _COMPAT_ASSIGN_TARGETS.get(name, ()):
            setattr(module, name, value)


def _sync_storage_state():
    globals()["_storage_backend"] = _storage_module._storage_backend
    globals()["_storage_label"] = _storage_module._storage_label
    globals()["_storage_error"] = _storage_module._storage_error


def configure_google_sheets(credentials_info, spreadsheet_id=None, spreadsheet_name=None):
    _storage_module.configure_google_sheets(credentials_info, spreadsheet_id, spreadsheet_name)
    _sync_storage_state()


def configure_apps_script(web_app_url, token):
    _storage_module.configure_apps_script(web_app_url, token)
    _sync_storage_state()


def disable_shared_storage(exc):
    _storage_module.disable_shared_storage(exc)
    _sync_storage_state()


sys.modules[__name__].__class__ = _LabManagerCompatModule
