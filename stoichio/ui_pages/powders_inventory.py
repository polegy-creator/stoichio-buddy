"""Powders & Inventory page for Stoichio Buddy."""


def render(ctx):
    LOW_STOCK_THRESHOLD_G = ctx.LOW_STOCK_THRESHOLD_G
    active_recipe_masses = ctx.active_recipe_masses
    add_powder = ctx.add_powder
    check_stock = ctx.check_stock
    clear_data_cache = ctx.clear_data_cache
    csv_bytes = ctx.csv_bytes
    database_dataframe = ctx.database_dataframe
    db = ctx.db
    delete_powder = ctx.delete_powder
    display_dataframe = ctx.display_dataframe
    inventory = ctx.inventory
    inventory_dataframe = ctx.inventory_dataframe
    inventory_log = ctx.inventory_log
    inventory_log_dataframe = ctx.inventory_log_dataframe
    powder_display_name = ctx.powder_display_name
    set_inventory_quantity = ctx.set_inventory_quantity
    st = ctx.st
    stock_row_class = ctx.stock_row_class
    theme_mode = ctx.theme_mode
    unknown_inventory_items = ctx.unknown_inventory_items

    st.subheader("Powders & inventory")

    unknown_stock = unknown_inventory_items(inventory, db)
    if unknown_stock:
        st.warning(
            "These inventory entries are not in the powder database: "
            + ", ".join(unknown_stock)
            + ". Select one below and set it to 0 g to remove it."
        )

    add_col, edit_col, delete_col = st.columns([1, 1, 0.9], gap="large")

    with add_col:
        st.markdown("#### Add powder")
        new_formula = st.text_input("Powder formula", placeholder="Fe2O3")
        new_purity = st.text_input("Purity", placeholder="99.9%")
        new_company = st.text_input("Vendor / supplier", placeholder="Sigma-Aldrich")
        new_grams = st.number_input(
            "Initial inventory grams",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.4f",
        )

        if st.button("Add Powder & Stock", type="primary", width="stretch"):
            try:
                powder_name, powders = add_powder(new_formula, purity=new_purity, company=new_company)
                if new_grams > 0:
                    set_inventory_quantity(powder_name, new_grams, reason="Initial stock when powder was added")
                clear_data_cache()
                if new_grams > 0:
                    st.success(f"Added {powder_display_name(powder_name, powders[powder_name])} with {new_grams:g} g in inventory.")
                else:
                    st.success(f"Added {powder_display_name(powder_name, powders[powder_name])}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Molar masses are recalculated from atomic_masses.json every time the database is loaded.")

    with edit_col:
        st.markdown("#### Set quantity")
        powder_options = [""] + list(db.keys()) + [powder for powder in unknown_stock if powder not in db]
        powder = st.selectbox(
            "Powder",
            powder_options,
            format_func=lambda value: powder_display_name(value, db.get(value, {})) if value else "Choose powder",
        )
        grams = st.number_input("Available grams", min_value=0.0, value=0.0, step=1.0, format="%.4f")

        if st.button("Save Quantity", type="primary", width="stretch"):
            try:
                if not powder:
                    raise ValueError("Choose a powder")
                set_inventory_quantity(powder, grams, reason="Manual inventory edit from UI")
                clear_data_cache()
                st.success(f"Updated {powder_display_name(powder, db.get(powder, {}))} to {grams:g} g.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Set quantity to 0 to remove a powder from inventory.")

    with delete_col:
        st.markdown("#### Delete powder")
        powder_to_delete = st.selectbox(
            "Powder to delete",
            [""] + list(db.keys()),
            format_func=lambda value: powder_display_name(value, db.get(value, {})) if value else "Choose powder",
        )
        remove_deleted_stock = st.checkbox("Also remove its inventory entry", value=True)

        if st.button("Delete Powder", width="stretch"):
            try:
                if not powder_to_delete:
                    raise ValueError("Choose a powder")
                delete_powder(powder_to_delete, remove_inventory=remove_deleted_stock)
                clear_data_cache()
                st.success(f"Deleted {powder_display_name(powder_to_delete, db.get(powder_to_delete, {}))}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Deleting a powder removes it from future calculations. History entries are kept unchanged.")

    st.divider()

    powder_table_col, stock_table_col = st.columns(2, gap="large")
    with powder_table_col:
        st.markdown("#### Powder database")
        powder_df = database_dataframe(db)
        display_dataframe(powder_df, theme_mode, width="stretch", hide_index=True)
        st.download_button(
            "Download Powder Database CSV",
            data=csv_bytes(powder_df),
            file_name="powders.csv",
            mime="text/csv",
            width="stretch",
        )

    with stock_table_col:
        st.markdown("#### Current inventory")
        if inventory:
            comparison_recipe = active_recipe_masses()
            if comparison_recipe:
                in_stock, stock_messages = check_stock(inventory, comparison_recipe)
                st.caption("Compared with the last calculated recipe.")
                if stock_messages:
                    st.error("Last recipe needs more powder than inventory: " + "; ".join(stock_messages))

            low_stock_powders = [
                powder
                for powder, grams in inventory.items()
                if grams < LOW_STOCK_THRESHOLD_G
            ]
            if low_stock_powders:
                st.warning(
                    f"Low inventory below {LOW_STOCK_THRESHOLD_G:g} g: "
                    + ", ".join(low_stock_powders)
                )
                low_stock_df = inventory_dataframe(
                    {
                        powder: inventory[powder]
                        for powder in low_stock_powders
                    },
                    comparison_recipe,
                )
                st.markdown("##### Low-stock dashboard")
                display_dataframe(
                    low_stock_df,
                    theme_mode,
                    row_class_func=stock_row_class,
                    width="stretch",
                    hide_index=True,
                )

            stock_df = inventory_dataframe(inventory, comparison_recipe)
            st.markdown("##### Full inventory")
            display_dataframe(
                stock_df,
                theme_mode,
                row_class_func=stock_row_class,
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "Download Inventory CSV",
                data=csv_bytes(stock_df),
                file_name="inventory.csv",
                mime="text/csv",
                width="stretch",
            )
        else:
            st.info("Inventory is empty.")

    st.divider()
    st.markdown("#### Inventory ledger")
    if inventory_log:
        ledger_df = inventory_log_dataframe(inventory_log)
        display_dataframe(ledger_df, theme_mode, width="stretch", hide_index=True)
        st.download_button(
            "Download Inventory Ledger CSV",
            data=csv_bytes(ledger_df),
            file_name="inventory_ledger.csv",
            mime="text/csv",
            width="stretch",
        )
    else:
        st.info("No inventory transactions logged yet.")
