"""Powder Mass Calculation page for Stoichio Buddy."""


def render(ctx):
    DEFAULT_DIE_DIAMETER_MM = ctx.DEFAULT_DIE_DIAMETER_MM
    LOW_STOCK_THRESHOLD_G = ctx.LOW_STOCK_THRESHOLD_G
    MASS_BASIS_TARGET_FORMULA = ctx.MASS_BASIS_TARGET_FORMULA
    check_stock = ctx.check_stock
    clear_data_cache = ctx.clear_data_cache
    compute_recipe = ctx.compute_recipe
    consume_stock = ctx.consume_stock
    csv_bytes = ctx.csv_bytes
    database_dataframe = ctx.database_dataframe
    db = ctx.db
    delete_powder_set = ctx.delete_powder_set
    density_source_control = ctx.density_source_control
    display_dataframe = ctx.display_dataframe
    format_target_id = ctx.format_target_id
    hashlib = ctx.hashlib
    history = ctx.history
    infer_target_mass_from_recipe = ctx.infer_target_mass_from_recipe
    inventory = ctx.inventory
    known_recipe_height_check_dataframe = ctx.known_recipe_height_check_dataframe
    load_history = ctx.load_history
    load_inventory = ctx.load_inventory
    log_synthesis = ctx.log_synthesis
    matching_powder_sets_for_target = ctx.matching_powder_sets_for_target
    material_densities = ctx.material_densities
    next_target_number = ctx.next_target_number
    normalize_formula = ctx.normalize_formula
    powder_sets = ctx.powder_sets
    recipe_balance_dataframe = ctx.recipe_balance_dataframe
    recipe_basis_audit_dataframe = ctx.recipe_basis_audit_dataframe
    recipe_calculation_metadata = ctx.recipe_calculation_metadata
    recipe_coefficients_dataframe = ctx.recipe_coefficients_dataframe
    recipe_dataframe = ctx.recipe_dataframe
    recipe_input_signature = ctx.recipe_input_signature
    recipe_lab_summary = ctx.recipe_lab_summary
    recipe_report_html = ctx.recipe_report_html
    recipe_validation_warnings = ctx.recipe_validation_warnings
    record_powder_set_use = ctx.record_powder_set_use
    relevant_powders_for_target = ctx.relevant_powders_for_target
    safe_filename = ctx.safe_filename
    save_powder_set = ctx.save_powder_set
    st = ctx.st
    stock_row_class = ctx.stock_row_class
    target_height_from_mass = ctx.target_height_from_mass
    target_mass_from_height = ctx.target_mass_from_height
    theme_mode = ctx.theme_mode
    widget_key = ctx.widget_key

    left, right = st.columns([0.95, 1.05], gap="large")

    with left:
        st.subheader("Powder mass setup")
        target = st.text_input(
            "Target formula",
            placeholder="Fe1.98Ti0.02O3",
            help="Supports decimals, parentheses, and hydrates with middle dot or asterisk.",
        )
        recipe_target_for = st.text_input(
            "Target for (optional)",
            placeholder="Person or project name",
            key="recipe_target_for",
        )
        recipe_target_owner = recipe_target_for.strip()
        if recipe_target_owner:
            preview_number = next_target_number(history, recipe_target_owner)
            st.caption(
                f"This recipe will be the before-sintering record for "
                f"{format_target_id(recipe_target_owner, preview_number)}."
            )
        amount_mode = st.radio(
            "Target amount mode",
            ["Target formula mass", "Pellet height"],
            horizontal=True,
            help="This uses the original lab math. Powder totals may be slightly higher or lower than the target formula mass.",
        )

        target_mass = None
        planning_volume = None
        theoretical_density_used = None
        theoretical_density_source = ""
        theoretical_density_verified = False
        planning_height = None
        planning_error = None

        if amount_mode == "Target formula mass":
            target_mass = st.number_input(
                "Target formula mass (g)",
                min_value=0.0,
                value=15.6,
                step=0.1,
                format="%.4f",
                help="Original basis: the target compound/formula is scaled to this mass.",
            )
        else:
            st.caption(f"Fixed die diameter: {DEFAULT_DIE_DIAMETER_MM:.2f} mm")
            planning_height = st.number_input(
                "Desired target height (mm)",
                min_value=0.0,
                value=1.0,
                step=0.1,
                format="%.4f",
            )
            theoretical_density_used, theoretical_density_source = density_source_control(
                target,
                material_densities,
                key_prefix="recipe_height",
            )
            theoretical_density_verified = st.session_state.get("recipe_height_density_verified", False)
            if theoretical_density_used is not None and planning_height > 0:
                try:
                    target_mass, planning_volume = target_mass_from_height(
                        theoretical_density_used,
                        planning_height,
                        DEFAULT_DIE_DIAMETER_MM,
                    )
                    st.info(
                        f"Calculated target formula mass: {target_mass:.4f} g "
                        f"from {planning_volume:.4f} cm3."
                    )
                    st.caption(f"Density source: {theoretical_density_source}")
                    if str(theoretical_density_source).startswith("Related"):
                        st.warning(
                            "This height plan uses a related density cell, not an exact saved density for the target formula."
                        )
                    if not theoretical_density_verified:
                        st.warning("This density record is not marked as lab-checked or preferred.")
                except ValueError as exc:
                    planning_error = str(exc)
                    st.error(planning_error)

        powder_options, hidden_powders, target_powder_elements, powder_filter_error = relevant_powders_for_target(target, db)
        show_all_powders = st.checkbox(
            "Show all powders",
            value=False,
            help="Turn this on if you intentionally want to choose from powders that do not match the target cations.",
        )
        if powder_filter_error:
            st.warning(f"Powder filter could not read the target formula. Showing all powders. Details: {powder_filter_error}")
            powder_options = list(db.keys())
        elif show_all_powders:
            powder_options = list(db.keys())
            if target_powder_elements:
                st.caption(
                    "Showing all powders. Normally this target would show only sources for: "
                    + ", ".join(sorted(target_powder_elements))
                    + "."
                )
        elif target_powder_elements:
            if powder_options:
                st.caption(
                    f"Showing {len(powder_options)} relevant powder(s) for "
                    + ", ".join(sorted(target_powder_elements))
                    + f". Hidden: {len(hidden_powders)}."
                )
            else:
                st.warning(
                    "No powder in the database matches this target's cations. "
                    "Turn on Show all powders if you want to choose manually."
                )

        if "selected_recipe_powders" in st.session_state and not show_all_powders:
            selected_powders_state = [
                powder
                for powder in st.session_state.selected_recipe_powders
                if powder in powder_options
            ]
            if selected_powders_state != st.session_state.selected_recipe_powders:
                st.session_state.selected_recipe_powders = selected_powders_state

        powder_set_message = st.session_state.pop("powder_set_message", None)
        if powder_set_message:
            st.success(powder_set_message)

        matching_sets = matching_powder_sets_for_target(target, powder_sets) if target.strip() else []
        if matching_sets:
            st.markdown("##### Saved powder sets")
            powder_set_choice = st.selectbox(
                "Powder set",
                [""] + [record_id for record_id, _ in matching_sets],
                format_func=lambda value: (
                    "Choose saved set"
                    if not value
                    else f"{powder_sets[value]['name']} ({', '.join(powder_sets[value]['powders'])})"
                ),
                key="recipe_powder_set_choice",
                help="Saved sets are grouped by target cations. Applying a set still leaves you in control of the final powder choices.",
            )
            set_cols = st.columns(2, gap="small")
            if set_cols[0].button("Apply Powder Set", width="stretch", disabled=not powder_set_choice):
                chosen_set = powder_sets[powder_set_choice]
                available_set_powders = [
                    powder
                    for powder in chosen_set.get("powders", [])
                    if powder in db and (show_all_powders or powder in powder_options)
                ]
                skipped_powders = [
                    powder
                    for powder in chosen_set.get("powders", [])
                    if powder not in available_set_powders
                ]
                if not available_set_powders:
                    st.error("This powder set has no powders available for the current target/filter.")
                else:
                    st.session_state.selected_recipe_powders = available_set_powders
                    record_powder_set_use(powder_set_choice)
                    clear_data_cache()
                    st.session_state.powder_set_message = (
                        f"Applied {chosen_set['name']}."
                        + (f" Skipped unavailable powders: {', '.join(skipped_powders)}." if skipped_powders else "")
                    )
                    st.rerun()

            if set_cols[1].button("Delete Powder Set", width="stretch", disabled=not powder_set_choice):
                if powder_set_choice:
                    delete_powder_set(powder_set_choice)
                    clear_data_cache()
                    st.session_state.powder_set_message = "Powder set deleted."
                    st.rerun()
        elif target_powder_elements:
            st.caption("No saved powder set for this target family yet.")

        selected = st.multiselect(
            "Selected powders",
            powder_options,
            key="selected_recipe_powders",
            help="Only these powders will be used in the calculation. The list is filtered to powders matching the target cations.",
        )
        visible_powder_db = {
            powder: db[powder]
            for powder in powder_options
            if powder in db
        }

        with st.expander("Save selected powders as a set", expanded=False):
            default_set_name = (
                f"{'-'.join(sorted(target_powder_elements))} powder set"
                if target_powder_elements
                else "Powder set"
            )
            powder_set_key = hashlib.sha1(default_set_name.encode("utf-8")).hexdigest()[:10]
            powder_set_name = st.text_input(
                "Set name",
                value=default_set_name,
                key=f"new_powder_set_name_{powder_set_key}",
            )
            powder_set_notes = st.text_area(
                "Set notes",
                placeholder="Example: standard Fe-Ti precursor set",
                height=70,
                key=f"new_powder_set_notes_{powder_set_key}",
            )
            if st.button(
                "Save Powder Set",
                width="stretch",
                disabled=not selected or not target_powder_elements,
            ):
                try:
                    save_powder_set(
                        target,
                        selected,
                        name=powder_set_name,
                        notes=powder_set_notes,
                    )
                    clear_data_cache()
                    st.session_state.powder_set_message = "Powder set saved."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

        with st.expander("Check height from known powder masses", expanded=False):
            st.caption(
                "Enter known precursor masses to infer the matching target formula mass, "
                "then convert that mass to a target height with the same density calculation."
            )
            if not target.strip():
                st.info("Enter a target formula first.")
            elif not selected:
                st.info("Select the powders used in the known recipe first.")
            else:
                known_masses = {}
                for powder in selected:
                    powder_key = hashlib.sha1(f"known-height-{powder}".encode("utf-8")).hexdigest()[:10]
                    known_masses[powder] = st.number_input(
                        f"{powder} known mass (g)",
                        min_value=0.0,
                        value=0.0,
                        step=0.001,
                        format="%.6f",
                        key=f"known_recipe_height_mass_{powder_key}",
                    )

                height_check_density, height_check_density_label = density_source_control(
                    target,
                    material_densities,
                    key_prefix="known_recipe_height",
                )
                if st.button("Calculate Height From Known Masses", key="known_recipe_height_calculate"):
                    if height_check_density is None:
                        st.error("Choose a valid theoretical density source first.")
                    else:
                        check_result = infer_target_mass_from_recipe(
                            target,
                            known_masses,
                            db,
                            selected,
                        )
                        if check_result.get("target_mass") is None:
                            st.error(check_result.get("warning", "Could not infer target formula mass"))
                        else:
                            try:
                                checked_height, checked_volume = target_height_from_mass(
                                    height_check_density,
                                    check_result["target_mass"],
                                    DEFAULT_DIE_DIAMETER_MM,
                                )
                                roundtrip_target_mass, _ = target_mass_from_height(
                                    height_check_density,
                                    checked_height,
                                    DEFAULT_DIE_DIAMETER_MM,
                                )
                                roundtrip = compute_recipe(
                                    target,
                                    roundtrip_target_mass,
                                    db,
                                    selected,
                                    mass_basis=MASS_BASIS_TARGET_FORMULA,
                                )
                            except ValueError as exc:
                                st.error(str(exc))
                            else:
                                height_cols = st.columns(3)
                                height_cols[0].metric(
                                    "Inferred target formula mass (g)",
                                    round(check_result["target_mass"], 6),
                                )
                                height_cols[1].metric("Equivalent height (mm)", round(checked_height, 6))
                                height_cols[2].metric("Volume (cm3)", round(checked_volume, 6))
                                st.caption(
                                    f"Density source: {height_check_density_label}; "
                                    f"fixed die diameter {DEFAULT_DIE_DIAMETER_MM:.2f} mm."
                                )

                                display_dataframe(
                                    known_recipe_height_check_dataframe(check_result),
                                    theme_mode,
                                    width="stretch",
                                    hide_index=True,
                                )

                                if roundtrip.get("recipe") is not None:
                                    st.caption(
                                        "Pellet-height round trip: "
                                        + ", ".join(
                                            f"{powder} {grams:.6f} g"
                                            for powder, grams in roundtrip["recipe"].items()
                                        )
                                    )
                                if check_result["max_abs_deviation"] <= 0.001:
                                    st.success("Known masses round-trip within 0.001 g.")
                                else:
                                    st.warning(check_result["warning"])

        deduct_inventory = st.checkbox("Deduct inventory when saving recipe")

        solve = st.button("Calculate Recipe", type="primary", width="stretch")
        current_signature = recipe_input_signature(target, target_mass, selected, amount_mode)

        if solve:
            if target_mass is None or target_mass <= 0:
                st.session_state.last_recipe_result = {
                    "error": "Enter a valid target formula mass, or a valid height and theoretical density.",
                    "signature": current_signature,
                }
            elif planning_error:
                st.session_state.last_recipe_result = {
                    "error": planning_error,
                    "signature": current_signature,
                }
            else:
                result = compute_recipe(
                    target,
                    target_mass,
                    db,
                    selected,
                    mass_basis=MASS_BASIS_TARGET_FORMULA,
                )
                st.session_state.last_recipe_result = {
                    "result": result,
                    "target": target,
                    "target_mass": target_mass,
                    "selected": selected,
                    "amount_mode": amount_mode,
                    "planning_height": planning_height,
                    "planning_volume": planning_volume,
                    "theoretical_density": theoretical_density_used,
                    "density_source": theoretical_density_source,
                    "density_verified": theoretical_density_verified,
                    "signature": current_signature,
                }
                st.session_state.last_recipe_saved = False

    with right:
        st.subheader("Result")
        save_message = st.session_state.pop("recipe_save_message", None)
        if save_message:
            st.success(save_message)

        last_recipe = st.session_state.get("last_recipe_result")
        if not last_recipe:
            st.info("Enter a target formula, target mass, and selected powders, then calculate.")
            if visible_powder_db:
                display_dataframe(database_dataframe(visible_powder_db), theme_mode, width="stretch", hide_index=True)
        else:
            if last_recipe.get("error"):
                st.error(last_recipe["error"])
            else:
                result = last_recipe["result"]

                if result is None or result.get("recipe") is None:
                    st.error(result.get("warning", "No valid solution found") if result else "No valid solution found")
                else:
                    recipe_masses = result["recipe"]
                    current_inventory = inventory
                    in_stock, stock_messages = check_stock(current_inventory, recipe_masses)
                    recipe_df = recipe_dataframe(recipe_masses, current_inventory)
                    total_powder = sum(recipe_masses.values())
                    displayed_target_mass = last_recipe["target_mass"]

                    metric_cols = st.columns(3)
                    metric_cols[0].metric("Target formula mass (g)", round(displayed_target_mass, 3))
                    metric_cols[1].metric("Precursor powder total (g)", round(total_powder, 3))
                    metric_cols[2].metric("Powders used", len(recipe_masses))

                    if last_recipe["amount_mode"] == "Pellet height":
                        detail_cols = st.columns(3)
                        detail_cols[0].metric("Die diameter (mm)", round(DEFAULT_DIE_DIAMETER_MM, 3))
                        detail_cols[1].metric("Desired height (mm)", round(last_recipe["planning_height"], 3))
                        detail_cols[2].metric("Theoretical density", round(last_recipe["theoretical_density"], 4))
                        st.caption(f"Calculated planning volume: {last_recipe['planning_volume']:.6f} cm3")
                        st.caption(f"Density source: {last_recipe.get('density_source', '')}")

                    display_dataframe(
                        recipe_df,
                        theme_mode,
                        row_class_func=stock_row_class,
                        width="stretch",
                        hide_index=True,
                    )
                    st.download_button(
                        "Download Recipe CSV",
                        data=csv_bytes(recipe_df),
                        file_name="stoichio_recipe.csv",
                        mime="text/csv",
                        width="stretch",
                    )

                    if result.get("warning"):
                        st.warning(result["warning"])
                        st.caption(f"Residual: {result['residual']:.6g}")
                    else:
                        st.success("Exact cation-balance solution computed.")

                    if result.get("ignored_elements"):
                        st.caption(
                            "Solve basis: "
                            + result.get("basis", "element balance")
                            + "; ignored in balance: "
                            + ", ".join(result["ignored_elements"])
                        )

                    st.markdown("#### Calculation audit")
                    display_dataframe(
                        recipe_basis_audit_dataframe(result, recipe_masses, last_recipe),
                        theme_mode,
                        width="stretch",
                        hide_index=True,
                    )

                    with st.expander("Detailed stoichiometry audit", expanded=False):
                        audit_cols = st.columns(4)
                        audit_cols[0].metric("Solve basis", result.get("basis", "element balance"))
                        audit_cols[1].metric("Precursor formula mass", result.get("precursor_formula_mass", ""))
                        audit_cols[2].metric("Target molar mass", result.get("target_molar_mass", ""))
                        audit_cols[3].metric("Residual", f"{result.get('residual', 0):.3g}")

                        coeff_df = recipe_coefficients_dataframe(result, recipe_masses)
                        balance_df = recipe_balance_dataframe(result, db)

                        st.markdown("##### Precursor coefficients")
                        display_dataframe(coeff_df, theme_mode, width="stretch", hide_index=True)
                        st.download_button(
                            "Download Coefficients CSV",
                            data=csv_bytes(coeff_df),
                            file_name="stoichio_recipe_coefficients.csv",
                            mime="text/csv",
                            width="stretch",
                        )

                        st.markdown("##### Element balance")
                        display_dataframe(balance_df, theme_mode, width="stretch", hide_index=True)
                        st.download_button(
                            "Download Element Balance CSV",
                            data=csv_bytes(balance_df),
                            file_name="stoichio_element_balance.csv",
                            mime="text/csv",
                            width="stretch",
                        )

                    low_after_recipe = [
                        row["Powder"]
                        for _, row in recipe_df.iterrows()
                        if "Low after recipe" in str(row.get("Stock status", ""))
                    ]

                    if stock_messages:
                        st.error("Inventory shortage: " + "; ".join(stock_messages))
                    else:
                        if low_after_recipe:
                            st.warning(
                                "Low inventory after this recipe: "
                                + ", ".join(low_after_recipe)
                                + f" will be below {LOW_STOCK_THRESHOLD_G:g} g."
                            )

                    validation_warnings = recipe_validation_warnings(
                        result,
                        recipe_masses,
                        stock_messages=stock_messages,
                        planning_context=last_recipe,
                    )
                    if validation_warnings:
                        with st.expander("Validation warnings", expanded=True):
                            for warning in validation_warnings:
                                st.warning(warning)

                    inputs_changed = last_recipe["signature"] != current_signature
                    if inputs_changed:
                        st.warning("Inputs changed after this calculation. Recalculate before saving.")

                    recipe_target_owner = recipe_target_for.strip()
                    recipe_target_id = None
                    if recipe_target_owner:
                        recipe_target_number = next_target_number(history, recipe_target_owner)
                        recipe_target_id = format_target_id(recipe_target_owner, recipe_target_number)
                        st.caption(
                            f"Will save before-sintering recipe as {recipe_target_id} "
                            f"for {recipe_target_owner}."
                        )
                    else:
                        st.caption("No target owner set. This can still be saved as a quick recipe record.")

                    recipe_notes = st.text_area(
                        "Recipe notes",
                        placeholder="Example: calcination plan, pressing force, operator notes",
                        key=widget_key("recipe_save_notes", last_recipe["signature"]),
                    )
                    st.markdown("#### Lab notebook summary")
                    recipe_summary_text = recipe_lab_summary(
                        normalize_formula(last_recipe["target"]),
                        displayed_target_mass,
                        recipe_masses,
                        target_for=recipe_target_owner,
                        target_id=recipe_target_id,
                        notes=recipe_notes,
                        result=result,
                    )
                    st.code(recipe_summary_text, language="text")
                    st.download_button(
                        "Download Recipe Summary TXT",
                        data=recipe_summary_text,
                        file_name="stoichio_recipe_summary.txt",
                        mime="text/plain",
                        width="stretch",
                    )
                    recipe_report = recipe_report_html(
                        normalize_formula(last_recipe["target"]),
                        displayed_target_mass,
                        recipe_masses,
                        target_for=recipe_target_owner,
                        target_id=recipe_target_id,
                        notes=recipe_notes,
                        result=result,
                        stock_messages=stock_messages,
                        low_after_recipe=low_after_recipe,
                        planning_context=last_recipe,
                    )
                    st.download_button(
                        "Download Printable Recipe Report HTML",
                        data=recipe_report,
                        file_name=f"{safe_filename(recipe_target_id or last_recipe['target'])}_recipe_report.html",
                        mime="text/html",
                        width="stretch",
                    )
                    save_disabled = (
                        inputs_changed
                        or st.session_state.get("last_recipe_saved", False)
                    )
                    if st.button("Save Recipe to History", type="primary", width="stretch", disabled=save_disabled):
                        latest_history = load_history()
                        assigned_target_number = (
                            next_target_number(latest_history, recipe_target_owner)
                            if recipe_target_owner
                            else None
                        )
                        latest_inventory = load_inventory()
                        latest_in_stock, latest_stock_messages = check_stock(latest_inventory, recipe_masses)

                        inventory_deducted = False
                        if deduct_inventory:
                            if latest_in_stock:
                                consume_stock(
                                    latest_inventory,
                                    recipe_masses,
                                    reason=f"Saved recipe for {normalize_formula(last_recipe['target'])}",
                                )
                                inventory_deducted = True
                            else:
                                st.error(
                                    "Recipe was not saved because inventory is insufficient: "
                                    + "; ".join(latest_stock_messages)
                                )
                                st.stop()

                        saved_history = log_synthesis(
                            normalize_formula(last_recipe["target"]),
                            displayed_target_mass,
                            recipe_masses,
                            selected_powders=last_recipe["selected"],
                            warning=result.get("warning"),
                            inventory_deducted=inventory_deducted,
                            notes=recipe_notes,
                            target_for=recipe_target_owner or None,
                            target_number=assigned_target_number,
                            calculation=recipe_calculation_metadata(result),
                        )
                        saved_recipe = saved_history[-1] if saved_history else {}
                        recipe_id = saved_recipe.get("target_id") or saved_recipe.get("recipe_id", "Recipe")
                        clear_data_cache()
                        st.session_state.last_recipe_saved = True
                        st.session_state.recipe_save_message = (
                            f"{recipe_id} saved to history"
                            + (" and inventory deducted." if inventory_deducted else ".")
                        )
                        st.rerun()

                    if st.session_state.get("last_recipe_saved", False):
                        st.caption("This recipe has already been saved. Recalculate to save a new entry.")
