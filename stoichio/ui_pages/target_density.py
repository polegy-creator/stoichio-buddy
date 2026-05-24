"""Target Density % page for Stoichio Buddy."""


def render(ctx):
    clear_data_cache = ctx.clear_data_cache
    density_source_control = ctx.density_source_control
    display_dataframe = ctx.display_dataframe
    format_target_id = ctx.format_target_id
    history = ctx.history
    linked_recipe_target_label = ctx.linked_recipe_target_label
    linked_recipe_targets = ctx.linked_recipe_targets
    load_history = ctx.load_history
    log_target_density = ctx.log_target_density
    mass_basis_label = ctx.mass_basis_label
    material_densities = ctx.material_densities
    measured_density = ctx.measured_density
    next_target_number = ctx.next_target_number
    normalize_formula = ctx.normalize_formula
    recipe_dataframe = ctx.recipe_dataframe
    recipe_link_snapshot = ctx.recipe_link_snapshot
    relative_density_percent = ctx.relative_density_percent
    st = ctx.st
    target_density_lab_summary = ctx.target_density_lab_summary
    target_density_signature = ctx.target_density_signature
    theme_mode = ctx.theme_mode
    widget_key = ctx.widget_key

    st.subheader("Target density after sintering")
    st.caption("Use the final measured dimensions after sintering, not the 25.05 mm die diameter.")

    density_left, density_right = st.columns([0.95, 1.05], gap="large")

    with density_left:
        linked_targets = linked_recipe_targets(history)
        linked_target_lookup = {entry["entry_id"]: entry for entry in linked_targets}
        linked_target_key = st.selectbox(
            "Saved recipe target",
            [""] + list(linked_target_lookup.keys()),
            format_func=lambda key: (
                "New target not linked to a recipe"
                if not key
                else linked_recipe_target_label(linked_target_lookup[key])
            ),
            help="Choose the before-sintering recipe target when this density measurement belongs to it.",
        )
        linked_target = linked_target_lookup.get(linked_target_key)

        if linked_target:
            density_target = linked_target.get("target", "")
            target_for = str(linked_target.get("target_for", "")).strip()
            linked_target_number = int(linked_target.get("target_number", 0) or 0)
            linked_target_id = linked_target.get("target_id") or format_target_id(
                target_for,
                linked_target_number,
            )
            st.info(
                f"After-sintering density will be linked to {linked_target_id}"
                + (f" for {target_for}." if target_for else ".")
            )
            st.caption(
                "Linked before-sintering recipe: "
                + (linked_target.get("recipe_id") or linked_target.get("entry_id", "saved recipe"))
            )
            st.text_input(
                "Target formula",
                value=density_target,
                disabled=True,
                key=widget_key("linked_density_target", linked_target_key),
            )
        else:
            density_target = st.text_input("Target formula", placeholder="Fe1.98Ti0.02O3")
            target_for = st.text_input(
                "Target for (optional)",
                placeholder="Person or project name",
                key="target_density_for",
            )
            linked_target_number = None
            linked_target_id = None

        normalized_person = target_for.strip()
        if normalized_person:
            if linked_target_id:
                st.caption(f"This is the after-sintering record for {linked_target_id}.")
            else:
                preview_number = next_target_number(history, normalized_person)
                st.caption(
                    f"Next saved target for {normalized_person} will be "
                    f"{format_target_id(normalized_person, preview_number)}."
                )

        sintered_diameter = st.number_input(
            "Measured final diameter (mm)",
            min_value=0.0,
            value=0.0,
            step=0.1,
            format="%.4f",
        )
        sintered_height = st.number_input(
            "Measured final height (mm)",
            min_value=0.0,
            value=0.0,
            step=0.1,
            format="%.4f",
        )
        sintered_mass = st.number_input(
            "Measured final mass (g)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.6f",
        )
        relative_theoretical_density, density_source_mode = density_source_control(
            density_target,
            material_densities,
            key_prefix="relative_density",
        )
        relative_density_verified = st.session_state.get("relative_density_density_verified", False)
        current_density_signature = target_density_signature(
            density_target,
            target_for,
            sintered_diameter,
            sintered_height,
            sintered_mass,
            relative_theoretical_density,
            density_source_mode,
            target_id=linked_target_id,
            linked_recipe_entry_id=linked_target.get("entry_id") if linked_target else None,
        )
        calculate_density = st.button("Calculate Target Density %", type="primary", width="stretch")

        if calculate_density:
            try:
                if relative_theoretical_density is None:
                    raise ValueError("Choose a saved density or enter a manual theoretical density")

                normalized_density_target = normalize_formula(density_target)
                pellet_measured_density, final_volume = measured_density(
                    sintered_mass,
                    sintered_diameter,
                    sintered_height,
                )
                relative_percent = relative_density_percent(
                    pellet_measured_density,
                    relative_theoretical_density,
                )
                st.session_state.last_target_density_result = {
                    "target": normalized_density_target,
                    "target_for": normalized_person,
                    "measured_density": pellet_measured_density,
                    "theoretical_density": relative_theoretical_density,
                    "relative_percent": relative_percent,
                    "final_volume": final_volume,
                    "final_mass": sintered_mass,
                    "final_diameter": sintered_diameter,
                    "final_height": sintered_height,
                    "density_source": density_source_mode,
                    "density_verified": relative_density_verified,
                    "target_number": linked_target_number,
                    "target_id": linked_target_id,
                    "linked_recipe": recipe_link_snapshot(linked_target),
                    "signature": current_density_signature,
                }
                st.session_state.last_target_density_saved = False
            except ValueError as exc:
                st.session_state.last_target_density_result = {
                    "error": str(exc),
                    "signature": current_density_signature,
                }

    with density_right:
        st.markdown("#### Result")
        save_message = st.session_state.pop("target_density_save_message", None)
        if save_message:
            st.success(save_message)

        last_density = st.session_state.get("last_target_density_result")
        if not last_density:
            st.info("Enter final sintered dimensions, final mass, and a theoretical density.")
        elif last_density.get("error"):
            st.error(last_density["error"])
        else:
            deficit_percent = 100.0 - last_density["relative_percent"]
            current_target_owner = str(last_density.get("target_for", "")).strip()
            current_target_number = last_density.get("target_number")
            if not current_target_number and current_target_owner:
                current_target_number = next_target_number(history, current_target_owner)
            current_target_id = last_density.get("target_id")
            if not current_target_id and current_target_owner:
                current_target_id = format_target_id(current_target_owner, current_target_number)

            if current_target_id:
                st.caption(
                    f"Will save after-sintering density as {current_target_id} for "
                    f"{current_target_owner}: {last_density['target']}"
                )
            else:
                st.caption("This can be saved as a quick unassigned density record.")
            metric_cols = st.columns(3)
            metric_cols[0].metric("Measured density", round(last_density["measured_density"], 4))
            metric_cols[1].metric("Theoretical density", round(last_density["theoretical_density"], 4))
            metric_cols[2].metric("Relative density", f"{last_density['relative_percent']:.2f}%")

            detail_cols = st.columns(3)
            detail_cols[0].metric("Final volume (cm3)", round(last_density["final_volume"], 5))
            detail_cols[1].metric("Density deficit", f"{deficit_percent:.2f}%")
            detail_cols[2].metric("Final mass (g)", round(last_density["final_mass"], 5))

            linked_recipe = last_density.get("linked_recipe")
            if linked_recipe:
                linked_recipe_label = linked_recipe.get("recipe_id") or linked_recipe.get("entry_id", "saved recipe")
                st.info(f"Linked to before-sintering recipe {linked_recipe_label}.")
                with st.expander("Linked recipe details", expanded=False):
                    st.markdown(
                        f"**Input basis:** {linked_recipe.get('input_basis_g', '')} g "
                        f"({mass_basis_label(linked_recipe.get('input_basis_type'))})"
                    )
                    st.markdown(f"**Powder basis:** {linked_recipe.get('powder_basis_g', '')} g")
                    st.markdown(
                        "**Powders:** "
                        + ", ".join(linked_recipe.get("selected_powders") or [])
                    )
                    linked_recipe_masses = linked_recipe.get("recipe") or {}
                    if linked_recipe_masses:
                        display_dataframe(
                            recipe_dataframe(linked_recipe_masses),
                            theme_mode,
                            width="stretch",
                            hide_index=True,
                        )
                    if linked_recipe.get("notes"):
                        st.markdown(f"**Recipe notes:** {linked_recipe['notes']}")

            if last_density["relative_percent"] > 100:
                st.warning("Relative density is above 100%. Check dimensions, mass, or theoretical density.")
            else:
                st.success("Target density calculated.")
            if str(last_density.get("density_source", "")).startswith("Related"):
                st.warning("This calculation used a related density record, not an exact density for this formula.")
            if not last_density.get("density_verified", False):
                st.warning("The theoretical density source is not marked as lab-checked or preferred.")
            if last_density["relative_percent"] < 50:
                st.warning("Relative density is very low. Check final dimensions, mass, and selected theoretical density.")

            inputs_changed = last_density["signature"] != current_density_signature
            if inputs_changed:
                st.warning("Inputs changed after this calculation. Recalculate before saving.")

            target_density_notes = st.text_area(
                "Target density notes",
                placeholder="Example: sintering temperature, cracks, polish state, measurement notes",
                key=widget_key("target_density_save_notes", last_density["signature"]),
            )
            st.markdown("#### Lab notebook summary")
            density_summary_text = target_density_lab_summary(last_density, target_id=current_target_id)
            st.code(density_summary_text, language="text")
            st.download_button(
                "Download Density Summary TXT",
                data=density_summary_text,
                file_name="stoichio_density_summary.txt",
                mime="text/plain",
                width="stretch",
            )
            save_disabled = (
                inputs_changed
                or st.session_state.get("last_target_density_saved", False)
            )
            if st.button("Save Target Density % to History", type="primary", width="stretch", disabled=save_disabled):
                assigned_target_number = last_density.get("target_number")
                if not assigned_target_number and current_target_owner:
                    latest_history = load_history()
                    assigned_target_number = next_target_number(latest_history, current_target_owner)
                assigned_target_id = last_density.get("target_id")
                if not assigned_target_id and current_target_owner:
                    assigned_target_id = format_target_id(current_target_owner, assigned_target_number)

                saved_history = log_target_density(
                    last_density["target"],
                    assigned_target_number,
                    current_target_owner or None,
                    last_density["measured_density"],
                    last_density["theoretical_density"],
                    last_density["relative_percent"],
                    last_density["final_volume"],
                    last_density["final_mass"],
                    last_density["final_diameter"],
                    last_density["final_height"],
                    density_source=last_density["density_source"],
                    notes=target_density_notes,
                    target_id=assigned_target_id,
                    linked_recipe=last_density.get("linked_recipe"),
                )
                saved_target = saved_history[-1] if saved_history else {}
                target_id = saved_target.get("target_id") or "quick density record"
                clear_data_cache()
                st.session_state.pop("last_target_density_result", None)
                st.session_state.last_target_density_saved = False
                if current_target_owner:
                    st.session_state.target_density_save_message = (
                        f"Target density saved as {target_id} for {current_target_owner}."
                    )
                else:
                    st.session_state.target_density_save_message = "Target density saved as a quick record."
                st.rerun()

            if st.session_state.get("last_target_density_saved", False):
                st.caption("This target density has already been saved. Recalculate to save a new entry.")
