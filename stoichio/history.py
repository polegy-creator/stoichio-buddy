"""History facade for synthesis and target-density records."""

from stoichio.lab_manager import (
    clear_history_for_target,
    clear_history_for_target_id,
    clear_target_density_history_for_person,
    delete_history_entry,
    format_recipe_id,
    format_target_id,
    load_history,
    log_synthesis,
    log_target_density,
    next_recipe_number,
    next_target_number,
    save_history,
)
