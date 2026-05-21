"""History page for Stoichio Buddy."""


def render(ctx):
    globals().update(ctx.__dict__)

    st.subheader("History")

    target_tab, recipe_tab, density_tab, raw_tab = st.tabs(["Targets", "Recipes", "Target Density", "Raw Log"])

    with target_tab:
        st.markdown("#### Target lifecycle")
        lifecycle_groups = target_lifecycle_groups(history)
        if not lifecycle_groups:
            st.info("No saved target records yet.")
        else:
            search_col, owner_col, status_col = st.columns([1.45, 0.9, 0.85], gap="small")
            lifecycle_search = search_col.text_input(
                "Search targets",
                placeholder="Target ID, person, formula, powder, notes",
            )
            owner_options = ["All"] + sorted({group_key[0] for group_key, _ in lifecycle_groups})
            owner_filter = owner_col.selectbox("Target for", owner_options)
            status_filter = status_col.selectbox(
                "Status",
                ["All", "Complete", "Needs density", "Needs recipe"],
            )
            filtered_lifecycle_groups = filter_target_lifecycle_groups(
                lifecycle_groups,
                search_text=lifecycle_search,
                owner_filter=owner_filter,
                status_filter=status_filter,
            )
            lifecycle_df = target_lifecycle_dataframe(lifecycle_groups=filtered_lifecycle_groups)
            st.caption(f"Showing {len(filtered_lifecycle_groups)} of {len(lifecycle_groups)} target groups.")

            if not filtered_lifecycle_groups:
                st.info("No target records match these filters.")

            for group_key, entries in filtered_lifecycle_groups:
                summary = target_lifecycle_summary(group_key, entries)
                target_id = summary["target_id"]
                can_clear_group = any(entry.get("target_id") for entry in entries)
                group_col, group_delete_col = st.columns([0.94, 0.06], gap="small")
                with group_col:
                    with st.expander(summary["title"], expanded=True):
                        st.markdown(
                            '<div class="history-item-meta">'
                            f'{html.escape(summary["meta"])}'
                            "</div>",
                            unsafe_allow_html=True,
                        )
                        st.download_button(
                            "Download Target Report HTML",
                            data=target_traceability_report_html(group_key, summary),
                            file_name=f"{safe_filename(target_id)}_target_report.html",
                            mime="text/html",
                            key=widget_key("target_report_html", target_id),
                            width="stretch",
                        )

                        if summary["recipes"]:
                            st.markdown("##### Before sintering")
                            for entry in summary["recipes"]:
                                entry_id = entry.get("entry_id")
                                item_summary = recipe_history_summary(entry)
                                item_col, item_delete_col = st.columns([0.94, 0.06], gap="small")
                                with item_col:
                                    st.markdown(
                                        '<div class="history-item">'
                                        f'<div class="history-item-title">{html.escape(item_summary["title"])}</div>'
                                        f'<div class="history-item-meta">{html.escape(item_summary["meta"])}</div>'
                                        "</div>",
                                        unsafe_allow_html=True,
                                    )
                                with item_delete_col:
                                    st.write("")
                                    if entry_id and trash_button(
                                        widget_key("delete_lifecycle_recipe", entry_id),
                                        "Delete this before-sintering recipe",
                                    ):
                                        removed_count, _ = delete_history_entry(entry_id)
                                        cached_load_history.clear()
                                        st.success(f"Deleted {removed_count} recipe item.")
                                        st.rerun()
                        else:
                            st.caption("No before-sintering recipe saved for this target.")

                        if summary["densities"]:
                            st.markdown("##### After sintering")
                            for entry in summary["densities"]:
                                entry_id = entry.get("entry_id")
                                item_summary = target_density_history_summary(entry)
                                item_col, item_delete_col = st.columns([0.94, 0.06], gap="small")
                                with item_col:
                                    st.markdown(
                                        '<div class="history-item">'
                                        f'<div class="history-item-title">{html.escape(item_summary["title"])}</div>'
                                        f'<div class="history-item-meta">{html.escape(item_summary["meta"])}</div>'
                                        "</div>",
                                        unsafe_allow_html=True,
                                    )
                                with item_delete_col:
                                    st.write("")
                                    if entry_id and trash_button(
                                        widget_key("delete_lifecycle_density", entry_id),
                                        "Delete this after-sintering density record",
                                    ):
                                        removed_count, _ = delete_history_entry(entry_id)
                                        cached_load_history.clear()
                                        st.success(f"Deleted {removed_count} target-density item.")
                                        st.rerun()
                        else:
                            st.caption("No after-sintering density saved for this target yet.")
                with group_delete_col:
                    st.write("")
                    if can_clear_group and trash_button(
                        widget_key("clear_lifecycle_group", target_id),
                        f"Clear all history for {target_id}",
                    ):
                        removed_count, _ = clear_history_for_target_id(target_id)
                        cached_load_history.clear()
                        st.success(f"Removed {removed_count} item(s) for {target_id}.")
                        st.rerun()

            if not lifecycle_df.empty:
                st.download_button(
                    "Download Filtered Target Lifecycle CSV",
                    data=csv_bytes(lifecycle_df),
                    file_name="stoichio_target_lifecycle.csv",
                    mime="text/csv",
                    width="stretch",
                )

    with recipe_tab:
        st.markdown("#### Recipe history")
        history_df = history_dataframe(recipe_history)
        if history_df.empty:
            st.info("No saved recipes yet.")
        else:
            for target_name, entries in grouped_history(recipe_history).items():
                group_col, group_delete_col = st.columns([0.94, 0.06], gap="small")
                with group_col:
                    with st.expander(f"{target_name} ({len(entries)})", expanded=False):
                        for entry in reversed(entries):
                            entry_id = entry.get("entry_id")
                            summary = recipe_history_summary(entry)
                            item_col, item_delete_col = st.columns([0.94, 0.06], gap="small")
                            with item_col:
                                st.markdown(
                                    '<div class="history-item">'
                                    f'<div class="history-item-title">{html.escape(summary["title"])}</div>'
                                    f'<div class="history-item-meta">{html.escape(summary["meta"])}</div>'
                                    "</div>",
                                    unsafe_allow_html=True,
                                )
                            with item_delete_col:
                                st.write("")
                                if entry_id and trash_button(
                                    widget_key("delete_recipe", entry_id),
                                    "Delete this saved recipe",
                                ):
                                    removed_count, _ = delete_history_entry(entry_id)
                                    cached_load_history.clear()
                                    st.success(f"Deleted {removed_count} recipe item.")
                                    st.rerun()
                with group_delete_col:
                    st.write("")
                    if trash_button(
                        widget_key("clear_recipe_group", target_name),
                        f"Clear all recipe history for {target_name}",
                    ):
                        removed_count, _ = clear_history_for_target(target_name)
                        cached_load_history.clear()
                        st.success(f"Removed {removed_count} recipe(s) for {target_name}.")
                        st.rerun()

            st.download_button(
                "Download Recipe History CSV",
                data=csv_bytes(history_df),
                file_name="stoichio_recipe_history.csv",
                mime="text/csv",
                width="stretch",
            )

    with density_tab:
        st.markdown("#### Target density log")
        density_history_df = target_density_dataframe(target_density_records)
        if density_history_df.empty:
            st.info("No saved target-density records yet.")
        else:
            for person, entries in grouped_target_density_history(target_density_records).items():
                group_col, group_delete_col = st.columns([0.94, 0.06], gap="small")
                with group_col:
                    with st.expander(f"{person} ({len(entries)} target{'s' if len(entries) != 1 else ''})", expanded=True):
                        for entry in sorted(entries, key=lambda item: item.get("target_number", 0), reverse=True):
                            entry_id = entry.get("entry_id")
                            summary = target_density_history_summary(entry)
                            item_col, item_delete_col = st.columns([0.94, 0.06], gap="small")
                            with item_col:
                                st.markdown(
                                    '<div class="history-item">'
                                    f'<div class="history-item-title">{html.escape(summary["title"])}</div>'
                                    f'<div class="history-item-meta">{html.escape(summary["meta"])}</div>'
                                    "</div>",
                                    unsafe_allow_html=True,
                                )
                            with item_delete_col:
                                st.write("")
                                if entry_id and trash_button(
                                    widget_key("delete_target_density", entry_id),
                                    "Delete this saved target-density record",
                                ):
                                    removed_count, _ = delete_history_entry(entry_id)
                                    cached_load_history.clear()
                                    st.success(f"Deleted {removed_count} target-density item.")
                                    st.rerun()
                with group_delete_col:
                    st.write("")
                    if trash_button(
                        widget_key("clear_target_density_group", person),
                        f"Clear all target-density records for {person}",
                    ):
                        removed_count, _ = clear_target_density_history_for_person(person)
                        cached_load_history.clear()
                        st.success(f"Removed {removed_count} target-density record(s) for {person}.")
                        st.rerun()

            st.download_button(
                "Download Target Density CSV",
                data=csv_bytes(density_history_df),
                file_name="stoichio_target_density_history.csv",
                mime="text/csv",
                width="stretch",
            )

    with raw_tab:
        if not history:
            st.info("No saved history yet.")
        else:
            for entry in reversed(history):
                st.json(entry)
