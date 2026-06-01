"""Powder database page for Stoichio Buddy."""


def render(ctx):
    add_powder = ctx.add_powder
    clear_data_cache = ctx.clear_data_cache
    csv_bytes = ctx.csv_bytes
    database_dataframe = ctx.database_dataframe
    db = ctx.db
    delete_powder = ctx.delete_powder
    display_dataframe = ctx.display_dataframe
    powder_display_name = ctx.powder_display_name
    st = ctx.st
    theme_mode = ctx.theme_mode

    st.subheader("Powder database")

    add_col, delete_col = st.columns([1, 0.9], gap="large")

    with add_col:
        st.markdown("#### Add powder")
        new_formula = st.text_input("Powder formula", placeholder="Fe2O3")
        new_purity = st.text_input("Purity", placeholder="99.9%")
        new_company = st.text_input("Vendor / supplier", placeholder="Sigma-Aldrich")

        if st.button("Add Powder", type="primary", width="stretch"):
            try:
                powder_name, powders = add_powder(new_formula, purity=new_purity, company=new_company)
                clear_data_cache()
                st.success(f"Added {powder_display_name(powder_name, powders[powder_name])}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Molar masses are recalculated from atomic_masses.json every time the database is loaded.")

    with delete_col:
        st.markdown("#### Delete powder")
        powder_to_delete = st.selectbox(
            "Powder to delete",
            [""] + list(db.keys()),
            format_func=lambda value: powder_display_name(value, db.get(value, {})) if value else "Choose powder",
        )

        if st.button("Delete Powder", width="stretch"):
            try:
                if not powder_to_delete:
                    raise ValueError("Choose a powder")
                delete_powder(powder_to_delete, remove_inventory=True)
                clear_data_cache()
                st.success(f"Deleted {powder_display_name(powder_to_delete, db.get(powder_to_delete, {}))}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Deleting a powder removes it from future calculations. History entries are kept unchanged.")

    st.divider()
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
