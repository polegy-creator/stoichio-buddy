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
    sync_powders_from_msds_inventory = ctx.sync_powders_from_msds_inventory
    theme_mode = ctx.theme_mode
    update_powder_notes = ctx.update_powder_notes

    st.subheader("Powder database")

    add_col, note_col, delete_col = st.columns([1, 1, 0.9], gap="large")

    with add_col:
        st.markdown("#### Add powder")
        new_formula = st.text_input("Powder formula", placeholder="Fe2O3")
        new_purity = st.text_input("Purity", placeholder="99.9%")
        new_company = st.text_input("Vendor / supplier", placeholder="Sigma-Aldrich")
        new_notes = st.text_area("Notes", placeholder="Bottle label, batch, location, or handling notes", height=95)

        if st.button("Add Powder", type="primary", width="stretch"):
            try:
                powder_name, powders = add_powder(new_formula, purity=new_purity, company=new_company, notes=new_notes)
                clear_data_cache()
                st.success(f"Added {powder_display_name(powder_name, powders[powder_name])}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.caption("Molar masses are recalculated from atomic_masses.json every time the database is loaded.")

    with note_col:
        st.markdown("#### Powder notes")
        powder_for_note = st.selectbox(
            "Powder",
            [""] + list(db.keys()),
            format_func=lambda value: powder_display_name(value, db.get(value, {})) if value else "Choose powder",
            key="powder_note_select",
        )
        note_value = st.text_area(
            "Notes",
            value=db.get(powder_for_note, {}).get("notes", "") if powder_for_note else "",
            placeholder="Write or clear the note for this powder",
            height=130,
            key=f"powder_note_text_{powder_for_note or 'empty'}",
        )
        if st.button("Save Note", width="stretch"):
            try:
                if not powder_for_note:
                    raise ValueError("Choose a powder")
                update_powder_notes(powder_for_note, note_value)
                clear_data_cache()
                st.success("Powder note saved.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

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
    title_col, sync_col = st.columns([1, 0.42])
    with title_col:
        st.markdown("#### Powder database")
    with sync_col:
        if st.button("Sync Powders from MSDS", width="stretch"):
            try:
                summary = sync_powders_from_msds_inventory()
                clear_data_cache()
                st.success(
                    f"Synced MSDS powders: {summary['created']} added, {summary['updated']} updated, "
                    f"{summary['removed']} duplicate old rows removed, {summary['ignored']} old blank MSDS imports ignored."
                )
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    powder_df = database_dataframe(db)
    display_dataframe(powder_df, theme_mode, width="stretch", hide_index=True)
    st.download_button(
        "Download Powder Database CSV",
        data=csv_bytes(powder_df),
        file_name="powders.csv",
        mime="text/csv",
        width="stretch",
    )
