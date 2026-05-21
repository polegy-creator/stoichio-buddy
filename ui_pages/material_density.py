"""Material Density page for Stoichio Buddy."""


def render(ctx):
    globals().update(ctx.__dict__)

    st.subheader("Material density database")
    st.caption("Known target densities are used for pellet-height planning and post-sintering relative density.")

    entry_col, table_col = st.columns([0.95, 1.05], gap="large")

    with entry_col:
        st.markdown("#### Add or update target")
        density_formula = st.text_input("Target formula", placeholder="Fe1.98Ti0.02O3")
        density_phase = st.text_input("Phase / polymorph (optional)", placeholder="rutile, anatase, hematite")
        density_entry_mode = st.radio(
            "Density entry mode",
            ["From lattice parameters", "From unit cell volume", "Manual theoretical density"],
        )

        unit_cell_volume = None
        z_value = None
        theoretical_density = None
        density_source = "manual"
        crystal_system = ""
        lattice_params = {
            "a": None,
            "b": None,
            "c": None,
            "alpha": None,
            "beta": None,
            "gamma": None,
        }

        if density_entry_mode == "From lattice parameters":
            crystal_system = st.selectbox(
                "Crystal system",
                ["Cubic", "Tetragonal", "Orthorhombic", "Hexagonal", "Rhombohedral", "Monoclinic", "Triclinic"],
            )
            lattice_params = lattice_parameter_inputs(crystal_system)
            z_value = st.number_input(
                "Z, formula units per unit cell",
                min_value=0.0,
                value=1.0,
                step=1.0,
                format="%.6f",
                help="Z is not atoms per unit cell. It is how many target formula units are in one unit cell.",
            )
            if density_formula and z_value > 0:
                try:
                    unit_cell_volume = unit_cell_volume_from_lattice(
                        crystal_system,
                        lattice_params["a"],
                        lattice_params["b"],
                        lattice_params["c"],
                        lattice_params["alpha"],
                        lattice_params["beta"],
                        lattice_params["gamma"],
                    )
                    theoretical_density = theoretical_density_from_cell(
                        density_formula,
                        unit_cell_volume,
                        z_value,
                    )
                    st.info(
                        f"Unit cell volume: {unit_cell_volume:.5f} A3; "
                        f"theoretical density: {theoretical_density:.5f} g/cm3"
                    )
                    density_source = "lattice parameters"
                except ValueError as exc:
                    st.warning(str(exc))
        elif density_entry_mode == "From unit cell volume":
            unit_cell_volume = st.number_input(
                "Unit cell volume (A3)",
                min_value=0.0,
                value=0.0,
                step=1.0,
                format="%.6f",
                help="Use Angstrom cubed. The app converts A3 to cm3.",
            )
            z_value = st.number_input(
                "Z, formula units per unit cell",
                min_value=0.0,
                value=1.0,
                step=1.0,
                format="%.6f",
                help="Z is not atoms per unit cell. It is how many target formula units are in one unit cell.",
            )
            if density_formula and unit_cell_volume > 0 and z_value > 0:
                try:
                    theoretical_density = theoretical_density_from_cell(
                        density_formula,
                        unit_cell_volume,
                        z_value,
                    )
                    st.info(f"Calculated theoretical density: {theoretical_density:.5f} g/cm3")
                    density_source = "unit cell"
                except ValueError as exc:
                    st.warning(str(exc))
        else:
            theoretical_density = st.number_input(
                "Manual theoretical density (g/cm3)",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.6f",
            )
            density_source = "manual"

        verification_status = st.selectbox(
            "Trust status",
            [
                "Lab checked",
                "Preferred for formula",
                "Lab entry - unverified",
                "Codex seeded - verify before use",
                "Do not use",
            ],
            index=2,
            help="Use this to control which density records should be trusted first in calculations.",
        )
        verified_by = st.text_input("Verified by (optional)", placeholder="Name")
        verified_date = st.text_input(
            "Verified date (optional)",
            value=datetime.now().date().isoformat() if verification_status in {"Lab checked", "Preferred for formula"} else "",
            placeholder="YYYY-MM-DD",
        )
        reference = st.text_input("Source / reference", placeholder="XRD refinement, paper, manual")
        notes = st.text_area("Notes", height=90)

        save_density = st.button("Save Material Density", type="primary", width="stretch")
        if save_density:
            try:
                if not density_formula:
                    raise ValueError("Enter a target formula")
                if theoretical_density is None or theoretical_density <= 0:
                    raise ValueError("Enter enough density information")
                upsert_material_density(
                    density_formula,
                    phase=density_phase,
                    theoretical_density=theoretical_density,
                    unit_cell_volume=unit_cell_volume if unit_cell_volume and unit_cell_volume > 0 else None,
                    z=z_value if z_value and z_value > 0 else None,
                    density_source=density_source,
                    crystal_system=crystal_system,
                    a=lattice_params["a"],
                    b=lattice_params["b"],
                    c=lattice_params["c"],
                    alpha=lattice_params["alpha"],
                    beta=lattice_params["beta"],
                    gamma=lattice_params["gamma"],
                    source=reference,
                    notes=notes,
                    verification_status=verification_status,
                    verified_by=verified_by,
                    verified_date=verified_date,
                )
                clear_data_cache()
                saved_label = normalize_formula(density_formula)
                if density_phase.strip():
                    saved_label = f"{saved_label} ({density_phase.strip()})"
                st.success(f"Saved density for {saved_label}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        st.divider()
        st.markdown("#### Delete target density")
        density_delete_target = st.selectbox(
            "Density record to delete",
            [""] + list(material_densities.keys()),
            format_func=lambda value: density_record_label(value, material_densities[value]) if value else "Choose target",
        )
        if st.button("Delete Density Record", width="stretch"):
            try:
                if not density_delete_target:
                    raise ValueError("Choose a target")
                delete_material_density(density_delete_target)
                clear_data_cache()
                st.success(f"Deleted density for {density_delete_target}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    with table_col:
        st.markdown("#### Known densities")
        density_df = material_density_dataframe(material_densities)
        if density_df.empty:
            st.info("No material densities saved yet.")
        else:
            filter_cols = st.columns([1, 1], gap="small")
            trust_filter = filter_cols[0].selectbox(
                "Trust filter",
                ["All", "Preferred for formula", "Lab checked", "Needs verification", "Do not use"],
            )
            formula_filter = filter_cols[1].text_input(
                "Search formula or phase",
                placeholder="Fe, Ti, hematite",
            ).strip().lower()

            if trust_filter == "Preferred for formula":
                density_df = density_df[density_df["Trust status"].str.contains("Preferred", case=False, na=False)]
            elif trust_filter == "Lab checked":
                density_df = density_df[density_df["Trust status"].str.contains("checked", case=False, na=False)]
            elif trust_filter == "Needs verification":
                density_df = density_df[
                    density_df["Trust status"].str.contains("unverified|Codex", case=False, na=False)
                ]
            elif trust_filter == "Do not use":
                density_df = density_df[density_df["Trust status"].str.contains("Do not use", case=False, na=False)]

            if formula_filter:
                density_df = density_df[
                    density_df.apply(
                        lambda row: formula_filter
                        in " ".join(str(value).lower() for value in row.values),
                        axis=1,
                    )
                ]

            st.caption(
                "Blue rows were seeded by Codex from COD/paper literature. "
                "Mark records as Lab checked or Preferred for formula after source review."
            )
            display_dataframe(
                density_df,
                theme_mode,
                row_class_func=lambda row: (
                    "stock-short"
                    if "do not use" in str(row.get("Trust status", "")).lower()
                    else (
                        "codex-seeded"
                        if str(row.get("Origin", "")).lower().startswith("codex")
                        else ""
                    )
                ),
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "Download Material Density CSV",
                data=csv_bytes(density_df),
                file_name="material_densities.csv",
                mime="text/csv",
                width="stretch",
            )

