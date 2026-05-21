"""Powder Mass Calculation page for Stoichio Buddy."""


def render(ctx):
    globals().update(ctx.__dict__)

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

        selected = st.multiselect(
            "Selected powders",
            list(db.keys()),
            help="Only these powders will be used in the calculation.",
        )

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
            if db:
                display_dataframe(database_dataframe(db), theme_mode, width="stretch", hide_index=True)
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

