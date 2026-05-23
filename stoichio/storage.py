"""Storage facade for Stoichio Buddy persistence backends."""

from stoichio.lab_manager import (
    AppsScriptStore,
    GoogleSheetsStore,
    backup_json_file,
    configure_apps_script,
    configure_google_sheets,
    disable_shared_storage,
    load_json,
    load_json_file,
    save_json,
    save_json_file,
    storage_error,
    storage_label,
)
