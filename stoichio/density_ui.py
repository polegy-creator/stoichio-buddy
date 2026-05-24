"""Density-related Streamlit controls."""

import streamlit as st

from stoichio.chemistry.density_engine import theoretical_density_from_cell
from stoichio.chemistry.formula_parser import normalize_formula
from stoichio.density_records import related_material_density_records
from stoichio.ui_models import (
    density_record_is_blocked,
    density_record_is_verified,
    density_record_label,
    density_record_sort_key,
    density_records_for_formula,
    target_cation_label,
)


def density_source_control(target, material_densities, key_prefix):
    source_mode = st.radio(
        "Theoretical density source",
        ["Known material density", "Use another density record", "Manual density"],
        horizontal=True,
        key=f"{key_prefix}_density_source",
    )

    if source_mode == "Known material density":
        normalized_target, density_records, error = density_records_for_formula(target, material_densities)
        if density_records:
            if len(density_records) > 1:
                selected_record_key = st.selectbox(
                    "Known density phase",
                    [record_key for record_key, _ in density_records],
                    format_func=lambda value: density_record_label(value, material_densities[value]),
                    key=f"{key_prefix}_known_density_phase",
                )
            else:
                selected_record_key = density_records[0][0]

            record = material_densities[selected_record_key]
            density = record.get("theoretical_density_g_cm3")
            if density is None or density <= 0:
                st.warning(f"Saved density for {density_record_label(selected_record_key, record, False)} is missing")
                return None, source_mode

            density = float(density)
            st.success(f"Using {density_record_label(selected_record_key, record)}")
            if not density_record_is_verified(record):
                st.warning(
                    "This density record is not lab-verified yet. "
                    "Check the source before using it for final planning."
                )
            if density_record_is_blocked(record):
                st.error("This density record is marked Do not use.")
                return None, source_mode
            if record.get("source") or record.get("density_source"):
                st.caption(
                    "Source: "
                    + (record.get("source") or record.get("density_source") or "saved material density")
                )
            st.session_state[f"{key_prefix}_density_verified"] = density_record_is_verified(record)
            st.session_state[f"{key_prefix}_density_record_key"] = selected_record_key
            return density, f"Known material density: {density_record_label(selected_record_key, record, False)}"
        else:
            related_records = related_material_density_records(target, material_densities)
            if related_records and normalized_target:
                cation_text = target_cation_label(target)
                st.warning(f"No exact density for {normalized_target}. Choose a related cation-containing record.")
                if cation_text:
                    st.caption(
                        f"Showing {len(related_records)} records that contain target cation(s): {cation_text}."
                    )
                selected_record_key = st.selectbox(
                    "Related density record",
                    [record_key for record_key, _ in related_records],
                    format_func=lambda value: density_record_label(value, material_densities[value]),
                    key=f"{key_prefix}_related_known_density",
                )
                source_record = material_densities[selected_record_key]
                if density_record_is_blocked(source_record):
                    st.error("This density record is marked Do not use.")
                    return None, source_mode
                volume = source_record.get("unit_cell_volume_A3")
                z_value = source_record.get("z")
                if volume and z_value:
                    try:
                        density = theoretical_density_from_cell(normalized_target, volume, z_value)
                        st.success(
                            f"Using {density_record_label(selected_record_key, source_record, False)} unit cell "
                            f"for {normalized_target}: {density:.4f} g/cm3"
                        )
                        st.caption(
                            f"Recalculated from V={volume:g} A3 and Z={z_value:g}; "
                            "molar mass comes from the current target formula."
                        )
                        st.session_state[f"{key_prefix}_density_verified"] = density_record_is_verified(source_record)
                        st.session_state[f"{key_prefix}_density_record_key"] = selected_record_key
                        return (
                            density,
                            f"Related material density: {density_record_label(selected_record_key, source_record, False)}",
                        )
                    except ValueError as exc:
                        st.warning(str(exc))
                else:
                    st.warning(f"{density_record_label(selected_record_key, source_record, False)} has no unit cell data.")
            else:
                st.warning(error)
        return None, source_mode

    if source_mode == "Use another density record":
        related_records = related_material_density_records(target, material_densities)
        all_records = sorted(
            material_densities.items(),
            key=lambda item: density_record_sort_key(item[0], item[1]),
        )
        show_all_density_records = False
        if related_records:
            cation_text = target_cation_label(target)
            if cation_text:
                st.caption(
                    f"Showing {len(related_records)} records that contain target cation(s): {cation_text}."
                )
            show_all_density_records = st.checkbox(
                "Show all density records",
                value=False,
                key=f"{key_prefix}_show_all_density_records",
            )
            record_choices = all_records if show_all_density_records else related_records
        else:
            record_choices = all_records
            if target:
                st.warning("No density records share cations with this target. Showing all records.")

        source_target = st.selectbox(
            "Density record to use",
            [""] + [record_key for record_key, _ in record_choices],
            format_func=lambda value: density_record_label(value, material_densities[value]) if value else "Choose saved material",
            key=f"{key_prefix}_density_record",
        )
        if not source_target:
            st.warning("Choose a saved material density record")
            return None, source_mode

        try:
            normalized_target = normalize_formula(target)
        except ValueError as exc:
            st.warning(str(exc))
            return None, source_mode

        source_record = material_densities[source_target]
        if not density_record_is_verified(source_record):
            st.warning(
                "This density record is not lab-verified yet. "
                "Check the source before using it for final planning."
            )
        if density_record_is_blocked(source_record):
            st.error("This density record is marked Do not use.")
            return None, source_mode
        volume = source_record.get("unit_cell_volume_A3")
        z_value = source_record.get("z")
        if volume and z_value:
            try:
                density = theoretical_density_from_cell(normalized_target, volume, z_value)
                st.success(
                    f"Using {density_record_label(source_target, source_record, False)} unit cell "
                    f"for {normalized_target}: "
                    f"{density:.4f} g/cm3"
                )
                st.caption(
                    f"Recalculated from V={volume:g} A3 and Z={z_value:g}; "
                    "molar mass comes from the current target formula."
                )
                st.session_state[f"{key_prefix}_density_verified"] = density_record_is_verified(source_record)
                st.session_state[f"{key_prefix}_density_record_key"] = source_target
                return density, f"Related/manual density record: {density_record_label(source_target, source_record, False)}"
            except ValueError as exc:
                st.warning(str(exc))
                return None, source_mode

        density = source_record.get("theoretical_density_g_cm3")
        if density:
            st.warning(
                f"{source_target} has no saved unit cell volume and Z. "
                "Using its stored density directly."
            )
            st.session_state[f"{key_prefix}_density_verified"] = density_record_is_verified(source_record)
            st.session_state[f"{key_prefix}_density_record_key"] = source_target
            return float(density), f"Stored density record: {density_record_label(source_target, source_record, False)}"

        st.warning(f"{source_target} has no usable density data")
        return None, source_mode

    density = st.number_input(
        "Manual theoretical density (g/cm3)",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.5f",
        key=f"{key_prefix}_manual_density",
    )
    st.session_state[f"{key_prefix}_density_verified"] = False
    st.session_state[f"{key_prefix}_density_record_key"] = ""
    return density if density > 0 else None, source_mode


def lattice_parameter_inputs(crystal_system):
    system = crystal_system.lower()
    a = b = c = alpha = beta = gamma = None

    if system == "cubic":
        a = st.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = c = a
        alpha = beta = gamma = 90.0
    elif system == "tetragonal":
        col_a, col_c = st.columns(2)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = a
        alpha = beta = gamma = 90.0
    elif system == "orthorhombic":
        col_a, col_b, col_c = st.columns(3)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = col_b.number_input("b (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        alpha = beta = gamma = 90.0
    elif system == "hexagonal":
        col_a, col_c = st.columns(2)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = a
        alpha = beta = 90.0
        gamma = 120.0
    elif system == "rhombohedral":
        col_a, col_alpha = st.columns(2)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        alpha = col_alpha.number_input(
            "alpha = beta = gamma (deg)",
            min_value=0.0,
            value=90.0,
            step=0.1,
            format="%.6f",
        )
        b = c = a
        beta = gamma = alpha
    elif system == "monoclinic":
        col_a, col_b, col_c = st.columns(3)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = col_b.number_input("b (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        beta = st.number_input("beta (deg)", min_value=0.0, value=90.0, step=0.1, format="%.6f")
        alpha = gamma = 90.0
    else:
        col_a, col_b, col_c = st.columns(3)
        a = col_a.number_input("a (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        b = col_b.number_input("b (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        c = col_c.number_input("c (A)", min_value=0.0, value=0.0, step=0.01, format="%.6f")
        col_alpha, col_beta, col_gamma = st.columns(3)
        alpha = col_alpha.number_input("alpha (deg)", min_value=0.0, value=90.0, step=0.1, format="%.6f")
        beta = col_beta.number_input("beta (deg)", min_value=0.0, value=90.0, step=0.1, format="%.6f")
        gamma = col_gamma.number_input("gamma (deg)", min_value=0.0, value=90.0, step=0.1, format="%.6f")

    return {
        "a": a,
        "b": b,
        "c": c,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
    }
