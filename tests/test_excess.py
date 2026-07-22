"""
tests.test_excess

Fast, network-free unit tests for pipeline.excess: the alignment check, the
excess-significance statistic, the disqualifying-flag rollups, and the
full join/assembly against small synthetic a0/a1/miri_photometry datasets
(no live archive data needed -- everything this module does is pure
arithmetic/bookkeeping over already-extracted fluxes).
"""

import numpy as np
import pytest
import xarray as xr

from pipeline import excess as ex

STOPGAP_TOKENS = {
    "young_cluster": ["Young star clusters", "Stellar Cluster"],
    "evolved_star": ["Planetary nebulae nuclei"],
}

CONFIG = {
    "excess": {
        "primary_bands": ["F770W", "F1000W"],
        "significance_threshold_sigma": None,
        "single_band_significance_threshold_sigma": None,
        "stopgap_contaminant_tokens": STOPGAP_TOKENS,
    },
    "photosphere": {"grids": {"hot_teff_min_k": 8000.0}},
}

CONFIG_WITH_THRESHOLD = {
    "excess": {
        "primary_bands": ["F770W", "F1000W"],
        "significance_threshold_sigma": 3.0,
        "single_band_significance_threshold_sigma": None,
        "stopgap_contaminant_tokens": STOPGAP_TOKENS,
    },
    "photosphere": {"grids": {"hot_teff_min_k": 8000.0}},
}

CONFIG_WITH_SINGLE_BAND_THRESHOLD = {
    "excess": {
        "primary_bands": ["F770W", "F1000W"],
        "significance_threshold_sigma": 3.0,
        "single_band_significance_threshold_sigma": 5.0,
        "stopgap_contaminant_tokens": STOPGAP_TOKENS,
    },
    "photosphere": {"grids": {"hot_teff_min_k": 8000.0}},
}


def _single_band_f770w_dataset(sigma_f770w_observed, sigma_f770w_err=0.1, predicted=1.0, predicted_err=0.1):
    """A single, realistic single-filter-detection star: F1000W genuinely
    absent (qc_no_mosaic_for_filter_F1000W=1, NaN flux -- matching how a
    real single-band-only field looks, not just qc_single_filter_detection
    set with both bands populated), F770W otherwise clean."""
    a0 = _dataset(
        1,
        star_id=[1],
        gaia_source_id=[1],
        target_classification=["Star"],
        qc_single_filter_detection=[1],
    )
    a1 = _dataset(
        1,
        star_id=[1],
        predicted_flux_F770W=[predicted],
        predicted_flux_F770W_err=[predicted_err],
        predicted_flux_F1000W=[np.nan],
        predicted_flux_F1000W_err=[np.nan],
        qc_ambiguous_gaia_match=[0],
        qc_no_photosphere_grid=[0],
        qc_poor_photosphere_fit=[0],
        qc_possible_binary=[0],
        qc_pms_veiling_risk=[0],
        qc_rj_extrapolated=[0],
    )
    miri = _dataset(
        1,
        star_id=[1],
        observed_flux_F770W=[sigma_f770w_observed],
        observed_flux_F770W_err=[sigma_f770w_err],
        observed_flux_F1000W=[np.nan],
        observed_flux_F1000W_err=[np.nan],
        qc_no_mosaic_for_filter_F770W=[0],
        qc_source_off_mosaic_F770W=[0],
        qc_saturated_F770W=[0],
        qc_crowded_source_F770W=[0],
        qc_psf_fit_failed_F770W=[0],
        qc_psf_disagreement_complex_F770W=[0],
        qc_no_mosaic_for_filter_F1000W=[1],
        qc_source_off_mosaic_F1000W=[0],
        qc_saturated_F1000W=[0],
        qc_crowded_source_F1000W=[0],
        qc_psf_fit_failed_F1000W=[0],
        qc_psf_disagreement_complex_F1000W=[0],
    )
    return a0, a1, miri


def _dataset(n, **data_vars):
    coords = {"star": np.arange(n)}
    return xr.Dataset(
        data_vars={k: ("star", np.asarray(v)) for k, v in data_vars.items()},
        coords=coords,
    )


# --- assert_star_aligned -----------------------------------------------------


def test_assert_star_aligned_passes_for_matching_ids():
    a0 = _dataset(3, star_id=[1, 2, 3], gaia_source_id=[1, 2, 3])
    a1 = _dataset(3, star_id=[1, 2, 3])
    miri = _dataset(3, star_id=[1, 2, 3])
    ex.assert_star_aligned(a0, a1, miri)  # should not raise


def test_assert_star_aligned_raises_on_length_mismatch():
    a0 = _dataset(3, star_id=[1, 2, 3], gaia_source_id=[1, 2, 3])
    a1 = _dataset(2, star_id=[1, 2])
    miri = _dataset(3, star_id=[1, 2, 3])
    with pytest.raises(AssertionError, match="length mismatch"):
        ex.assert_star_aligned(a0, a1, miri)


def test_assert_star_aligned_raises_on_reordered_ids():
    # Same set of ids, different order -- exactly the silent-misalignment
    # shape of bug this check exists to catch (retriever.py, 2026-07-15).
    a0 = _dataset(3, star_id=[1, 2, 3], gaia_source_id=[1, 2, 3])
    a1 = _dataset(3, star_id=[1, 3, 2])
    miri = _dataset(3, star_id=[1, 2, 3])
    with pytest.raises(AssertionError, match="a0 and a1"):
        ex.assert_star_aligned(a0, a1, miri)


def test_assert_star_aligned_raises_on_miri_mismatch():
    a0 = _dataset(3, star_id=[1, 2, 3], gaia_source_id=[1, 2, 3])
    a1 = _dataset(3, star_id=[1, 2, 3])
    miri = _dataset(3, star_id=[1, 2, 99])
    with pytest.raises(AssertionError, match="a0 and miri_photometry"):
        ex.assert_star_aligned(a0, a1, miri)


# --- Stopgap contaminant classification ---------------------------------------


def test_is_stopgap_young_cluster_matches_any_component():
    assert ex.is_stopgap_young_cluster("Stellar Cluster; Young star clusters", CONFIG)
    assert ex.is_stopgap_young_cluster("Young star clusters", CONFIG)
    assert not ex.is_stopgap_young_cluster("Star; Planetary nebulae nuclei", CONFIG)
    assert not ex.is_stopgap_young_cluster("Star", CONFIG)


# is_stopgap_evolved_star retired 2026-07-22 -- superseded by
# pipeline.contaminants.is_evolved_star_overluminous (see tests/test_contaminants.py).
# Its tests were removed here along with the function itself.


# --- compute_excess_sigma -----------------------------------------------------


def test_compute_excess_sigma_basic_value():
    sigma = ex.compute_excess_sigma(
        observed=np.array([10.0]),
        observed_err=np.array([1.0]),
        predicted=np.array([5.0]),
        predicted_err=np.array([0.0]),
    )
    assert sigma[0] == pytest.approx(5.0)


def test_compute_excess_sigma_is_signed():
    sigma = ex.compute_excess_sigma(
        observed=np.array([1.0]),
        observed_err=np.array([1.0]),
        predicted=np.array([5.0]),
        predicted_err=np.array([0.0]),
    )
    assert sigma[0] < 0


def test_compute_excess_sigma_nan_when_any_input_nan():
    sigma = ex.compute_excess_sigma(
        observed=np.array([np.nan, 10.0]),
        observed_err=np.array([1.0, 1.0]),
        predicted=np.array([5.0, np.nan]),
        predicted_err=np.array([1.0, 1.0]),
    )
    assert np.isnan(sigma).all()


def test_compute_excess_sigma_nan_when_combined_error_zero():
    sigma = ex.compute_excess_sigma(
        observed=np.array([10.0]),
        observed_err=np.array([0.0]),
        predicted=np.array([5.0]),
        predicted_err=np.array([0.0]),
    )
    assert np.isnan(sigma[0])


# --- disqualifying-flag rollups ------------------------------------------------


def test_compute_star_disqualified_true_if_any_flag_set():
    a1 = _dataset(
        3,
        qc_ambiguous_gaia_match=[0, 0, 0],
        qc_no_photosphere_grid=[0, 1, 0],
        qc_poor_photosphere_fit=[0, 0, 0],
        qc_possible_binary=[0, 0, 0],
        qc_pms_veiling_risk=[0, 0, 0],
        qc_rj_extrapolated=[0, 0, 0],
    )
    result = ex.compute_star_disqualified(a1)
    np.testing.assert_array_equal(result, [False, True, False])


def test_compute_star_disqualified_missing_columns_default_clean():
    # Only a subset of DISQUALIFYING_STAR_FLAGS present -- shouldn't crash,
    # and absent flags shouldn't count against a star.
    a1 = _dataset(2, qc_possible_binary=[1, 0])
    result = ex.compute_star_disqualified(a1)
    np.testing.assert_array_equal(result, [True, False])


def test_compute_band_disqualified_checks_only_that_bands_suffix():
    miri = _dataset(
        2,
        qc_saturated_F770W=[1, 0],
        qc_saturated_F1000W=[0, 1],
        qc_crowded_source_F770W=[0, 0],
    )
    assert list(ex.compute_band_disqualified(miri, "F770W")) == [True, False]
    assert list(ex.compute_band_disqualified(miri, "F1000W")) == [False, True]


def test_build_disqualifying_flags_summary_lists_fired_flags_only():
    flag_arrays = {
        "qc_possible_binary": np.array([1, 0]),
        "qc_saturated_F770W": np.array([0, 1]),
    }
    summary = ex.build_disqualifying_flags_summary(
        flag_arrays, ["qc_possible_binary", "qc_saturated_F770W"], n=2
    )
    assert summary[0] == "qc_possible_binary"
    assert summary[1] == "qc_saturated_F770W"


def test_build_disqualifying_flags_summary_empty_string_when_clean():
    flag_arrays = {"qc_possible_binary": np.array([0])}
    summary = ex.build_disqualifying_flags_summary(flag_arrays, ["qc_possible_binary"], n=1)
    assert summary[0] == ""


def test_build_disqualifying_flags_summary_does_not_truncate_when_every_flag_fires():
    # Regression test for a real, if latent, bug found 2026-07-22: a fixed
    # "U256" dtype silently truncated (no error -- numpy just cuts fixed-
    # width unicode arrays on assignment) once enough flags fired
    # simultaneously. This project's real flag set needs 475 chars in the
    # worst case. Use a deliberately long, made-up flag-name list here so
    # this test doesn't silently stop catching the bug if the real flag
    # set ever shrinks back under 256 chars.
    flag_names = [f"qc_some_very_long_flag_name_number_{i:03d}" for i in range(20)]
    flag_arrays = {name: np.array([1]) for name in flag_names}
    summary = ex.build_disqualifying_flags_summary(flag_arrays, flag_names, n=1)
    expected = ",".join(flag_names)
    assert len(expected) > 256, "test setup must exceed the old fixed U256 width to be meaningful"
    assert summary[0] == expected


# --- assemble_level_b1 (small synthetic end-to-end) ----------------------------


def _synthetic_a0(n=3):
    return _dataset(
        n,
        star_id=[1, 2, 3],
        gaia_source_id=[1, 2, 3],
        target_classification=["Star", "Star", "Star"],
        gaia_ra=[10.0, 20.0, 30.0],
        gaia_dec=[-5.0, -6.0, -7.0],
        qc_single_filter_detection=[0, 1, 0],
    )


def _synthetic_a1(n=3):
    return _dataset(
        n,
        star_id=[1, 2, 3],
        predicted_flux_F770W=[1.0, 2.0, np.nan],
        predicted_flux_F770W_err=[0.1, 0.2, np.nan],
        predicted_flux_F1000W=[0.8, 1.5, np.nan],
        predicted_flux_F1000W_err=[0.1, 0.2, np.nan],
        qc_ambiguous_gaia_match=[0, 0, 0],
        qc_no_photosphere_grid=[0, 0, 1],
        qc_poor_photosphere_fit=[0, 0, 0],
        qc_possible_binary=[0, 0, 0],
        qc_pms_veiling_risk=[0, 0, 0],
        qc_rj_extrapolated=[0, 1, 0],
        qc_extinction_uncertain=[0, 0, 0],
        qc_grid_disagreement=[0, 0, 0],
    )


def _synthetic_miri(n=3):
    return _dataset(
        n,
        star_id=[1, 2, 3],
        observed_flux_F770W=[5.0, 2.5, np.nan],
        observed_flux_F770W_err=[0.2, 0.2, np.nan],
        observed_flux_F1000W=[0.9, 1.6, np.nan],
        observed_flux_F1000W_err=[0.1, 0.2, np.nan],
        qc_no_mosaic_for_filter_F770W=[0, 0, 1],
        qc_source_off_mosaic_F770W=[0, 0, 0],
        qc_saturated_F770W=[0, 0, 0],
        qc_crowded_source_F770W=[0, 0, 0],
        qc_psf_fit_failed_F770W=[0, 0, 0],
        qc_psf_disagreement_complex_F770W=[0, 0, 0],
        qc_no_mosaic_for_filter_F1000W=[0, 0, 1],
        qc_source_off_mosaic_F1000W=[0, 0, 0],
        qc_saturated_F1000W=[0, 0, 0],
        qc_crowded_source_F1000W=[0, 0, 0],
        qc_psf_fit_failed_F1000W=[0, 0, 0],
        qc_psf_disagreement_complex_F1000W=[0, 0, 0],
    )


def test_assemble_level_b1_keeps_every_star_no_dropping():
    ds = ex.assemble_level_b1(_synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG)
    assert ds.sizes["star"] == 3


def test_assemble_level_b1_computes_expected_sigma_for_clean_star():
    ds = ex.assemble_level_b1(_synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG)
    # Star 0: observed=5.0+-0.2, predicted=1.0+-0.1 -> clear excess, positive sigma.
    assert ds["excess_sigma_F770W"].values[0] > 3.0


def test_assemble_level_b1_nan_star_stays_nan_not_dropped():
    ds = ex.assemble_level_b1(_synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG)
    # Star 2 has no photosphere fit (qc_no_photosphere_grid) and no mosaic --
    # both sides NaN, sigma must be NaN, but the row itself must still exist.
    assert np.isnan(ds["excess_sigma_F770W"].values[2])
    assert ds["qc_star_disqualified"].values[2] == 1


def test_assemble_level_b1_rj_extrapolated_star_disqualified_but_sigma_reported():
    ds = ex.assemble_level_b1(_synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG)
    # Star 1 is qc_rj_extrapolated -- must be disqualified from "clean"
    # candidacy, but its raw sigma must still be a real, reported number
    # (nothing silently dropped), per the researcher's decision (option A).
    assert ds["qc_star_disqualified"].values[1] == 1
    assert ds["qc_excess_clean_F770W"].values[1] == 0
    assert np.isfinite(ds["excess_sigma_F770W"].values[1])


def test_assemble_level_b1_clean_star_is_clean_in_both_bands():
    ds = ex.assemble_level_b1(_synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG)
    assert ds["qc_excess_clean_F770W"].values[0] == 1
    assert ds["qc_excess_clean_F1000W"].values[0] == 1


def test_assemble_level_b1_disqualifying_flags_summary_matches_fired_flags():
    ds = ex.assemble_level_b1(_synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG)
    assert ds["disqualifying_flags"].values[0] == ""
    assert "qc_rj_extrapolated" in str(ds["disqualifying_flags"].values[1])
    assert "qc_no_photosphere_grid" in str(ds["disqualifying_flags"].values[2])


def test_assemble_level_b1_does_not_compute_significance_boolean_or_final_flag():
    ds = ex.assemble_level_b1(_synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG)
    assert "qc_excess_significant_F770W" not in ds
    assert "qc_candidate_preliminary" not in ds
    assert "qc_single_band_candidate" not in ds
    assert "qc_anomalous_excess" not in ds


def test_assemble_level_b1_carries_through_qc_single_filter_detection():
    ds = ex.assemble_level_b1(_synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG)
    np.testing.assert_array_equal(ds["qc_single_filter_detection"].values, [0, 1, 0])


def test_assemble_level_b1_stopgap_flag_disqualifies_young_cluster():
    # assign (not mutating .values in place) to avoid numpy's fixed-width
    # string dtype silently truncating these longer classification strings
    # to the original array's narrower itemsize.
    a0 = _synthetic_a0().assign(
        target_classification=(
            "star",
            np.array(
                [
                    "Star",
                    "Stellar Cluster; Young star clusters",
                    "Star; Planetary nebulae nuclei",
                ]
            ),
        )
    )
    ds = ex.assemble_level_b1(a0, _synthetic_a1(), _synthetic_miri(), CONFIG)
    assert ds["qc_stopgap_young_cluster"].values.tolist() == [0, 1, 0]
    # Star 1 (young cluster) is otherwise clean per the other fixtures --
    # confirm the stopgap flag alone is enough to disqualify it.
    assert ds["qc_star_disqualified"].values[1] == 1
    assert "qc_stopgap_young_cluster" in str(ds["disqualifying_flags"].values[1])


def test_assemble_level_b1_no_longer_computes_retired_evolved_star_stopgap():
    # qc_stopgap_evolved_star was retired 2026-07-22, superseded by
    # pipeline.contaminants.qc_evolved_star -- must not appear in b1 output,
    # even for a star whose classification would have matched it.
    a0 = _synthetic_a0().assign(
        target_classification=("star", np.array(["Star", "Star", "Star; Planetary nebulae nuclei"]))
    )
    ds = ex.assemble_level_b1(a0, _synthetic_a1(), _synthetic_miri(), CONFIG)
    assert "qc_stopgap_evolved_star" not in ds
    # Star 2 is still disqualified overall -- via qc_no_photosphere_grid
    # (from the a1 fixture), not via any stopgap.
    assert ds["qc_star_disqualified"].values[2] == 1
    assert "qc_no_photosphere_grid" in str(ds["disqualifying_flags"].values[2])


# --- qc_excess_significant_{band} / qc_candidate_preliminary (threshold set) ---


def test_assemble_level_b1_computes_significant_and_preliminary_when_threshold_set():
    ds = ex.assemble_level_b1(
        _synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG_WITH_THRESHOLD
    )
    assert "qc_excess_significant_F770W" in ds
    assert "qc_candidate_preliminary" in ds
    # qc_single_band_candidate is gated on its OWN threshold
    # (single_band_significance_threshold_sigma), still None in this
    # config -- so it's absent here even though significance_threshold_sigma
    # is set. qc_anomalous_excess is unimplemented regardless (needs
    # contaminants.py).
    assert "qc_single_band_candidate" not in ds
    assert "qc_anomalous_excess" not in ds


def test_qc_excess_significant_requires_clean_and_above_threshold():
    ds = ex.assemble_level_b1(
        _synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG_WITH_THRESHOLD
    )
    # Star 0: clean, sigma_F770W > 3 -> significant. Star 1: sigma > 3 but
    # disqualified (qc_rj_extrapolated) -> not significant despite the raw number.
    assert ds["qc_excess_significant_F770W"].values[0] == 1
    assert ds["qc_excess_significant_F770W"].values[1] == 0


def test_qc_candidate_preliminary_requires_both_bands_not_just_one():
    # Star 0 (dual-band): F770W is strongly significant
    # ((5.0-1.0)/sqrt(0.2**2+0.1**2) ~= 17.9), but F1000W is not
    # ((0.9-0.8)/sqrt(0.1**2+0.1**2) ~= 0.71, well under the 3.0 threshold)
    # -- qc_candidate_preliminary must require BOTH, not fire on F770W alone.
    ds = ex.assemble_level_b1(
        _synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG_WITH_THRESHOLD
    )
    assert ds["qc_excess_significant_F770W"].values[0] == 1
    assert ds["qc_excess_significant_F1000W"].values[0] == 0
    assert ds["qc_candidate_preliminary"].values[0] == 0


def test_qc_candidate_preliminary_excludes_single_filter_detection_stars():
    # A single star, both-bands strongly significant and otherwise clean --
    # would satisfy the both-bands criterion, but is marked
    # qc_single_filter_detection=1. Must NOT count as a preliminary candidate:
    # single-band-only stars get their own, separate (not-yet-set) tier
    # instead, per the researcher's design.
    a0 = _dataset(
        1,
        star_id=[1],
        gaia_source_id=[1],
        target_classification=["Star"],
        qc_single_filter_detection=[1],
    )
    a1 = _dataset(
        1,
        star_id=[1],
        predicted_flux_F770W=[1.0],
        predicted_flux_F770W_err=[0.1],
        predicted_flux_F1000W=[1.0],
        predicted_flux_F1000W_err=[0.1],
        qc_ambiguous_gaia_match=[0],
        qc_no_photosphere_grid=[0],
        qc_poor_photosphere_fit=[0],
        qc_possible_binary=[0],
        qc_pms_veiling_risk=[0],
        qc_rj_extrapolated=[0],
    )
    miri = _dataset(
        1,
        star_id=[1],
        observed_flux_F770W=[5.0],
        observed_flux_F770W_err=[0.2],
        observed_flux_F1000W=[5.0],
        observed_flux_F1000W_err=[0.2],
        qc_no_mosaic_for_filter_F770W=[0],
        qc_source_off_mosaic_F770W=[0],
        qc_saturated_F770W=[0],
        qc_crowded_source_F770W=[0],
        qc_psf_fit_failed_F770W=[0],
        qc_psf_disagreement_complex_F770W=[0],
        qc_no_mosaic_for_filter_F1000W=[0],
        qc_source_off_mosaic_F1000W=[0],
        qc_saturated_F1000W=[0],
        qc_crowded_source_F1000W=[0],
        qc_psf_fit_failed_F1000W=[0],
        qc_psf_disagreement_complex_F1000W=[0],
    )
    ds = ex.assemble_level_b1(a0, a1, miri, CONFIG_WITH_THRESHOLD)
    # Sanity: both bands really are individually significant here.
    assert ds["qc_excess_significant_F770W"].values[0] == 1
    assert ds["qc_excess_significant_F1000W"].values[0] == 1
    assert ds["qc_candidate_preliminary"].values[0] == 0


# --- qc_single_band_candidate (single_band_significance_threshold_sigma=5.0) --


def test_qc_single_band_candidate_absent_when_threshold_null():
    ds = ex.assemble_level_b1(
        _synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG_WITH_THRESHOLD
    )
    assert "qc_single_band_candidate" not in ds


def test_qc_single_band_candidate_fires_above_the_stricter_5sigma_bar():
    # observed=1.8485, predicted=1.0, err=0.1 each -> sigma = 0.8485/sqrt(0.02) = 6.0
    a0, a1, miri = _single_band_f770w_dataset(sigma_f770w_observed=1.8485)
    ds = ex.assemble_level_b1(a0, a1, miri, CONFIG_WITH_SINGLE_BAND_THRESHOLD)
    assert ds["excess_sigma_F770W"].values[0] == pytest.approx(6.0, abs=0.01)
    assert ds["qc_single_band_candidate"].values[0] == 1


def test_qc_single_band_candidate_is_genuinely_stricter_not_the_dual_band_bar_scaled_down():
    # observed=1.5657, predicted=1.0, err=0.1 each -> sigma = 0.5657/sqrt(0.02) ~= 4.0:
    # clears the 3.0 dual-band bar but NOT the 5.0 single-band bar. This is the
    # core requirement from the researcher's design: single-band significance
    # must be judged against its own, stricter threshold, not the primary one.
    a0, a1, miri = _single_band_f770w_dataset(sigma_f770w_observed=1.5657)
    ds = ex.assemble_level_b1(a0, a1, miri, CONFIG_WITH_SINGLE_BAND_THRESHOLD)
    assert ds["excess_sigma_F770W"].values[0] == pytest.approx(4.0, abs=0.01)
    assert ds["qc_excess_significant_F770W"].values[0] == 1  # clears 3.0
    assert ds["qc_single_band_candidate"].values[0] == 0  # does not clear 5.0


def test_qc_single_band_candidate_requires_star_to_be_clean():
    a0, a1, miri = _single_band_f770w_dataset(sigma_f770w_observed=10.0)
    a1["qc_poor_photosphere_fit"] = ("star", np.array([1]))
    ds = ex.assemble_level_b1(a0, a1, miri, CONFIG_WITH_SINGLE_BAND_THRESHOLD)
    assert ds["qc_star_disqualified"].values[0] == 1
    assert ds["qc_single_band_candidate"].values[0] == 0


def test_qc_single_band_candidate_excludes_dual_band_stars_even_if_one_band_is_huge():
    # A dual-band star (qc_single_filter_detection=0) with a huge F770W
    # sigma but a non-significant F1000W -- this correctly fails
    # qc_candidate_preliminary (needs both bands), and must NOT leak into
    # qc_single_band_candidate either: that tier is only for stars that were
    # genuinely never measured in the second band.
    ds = ex.assemble_level_b1(
        _synthetic_a0(), _synthetic_a1(), _synthetic_miri(), CONFIG_WITH_SINGLE_BAND_THRESHOLD
    )
    assert ds["qc_single_filter_detection"].values[0] == 0
    assert ds["qc_single_band_candidate"].values[0] == 0


def test_assemble_level_b1_raises_on_misaligned_input():
    a0 = _synthetic_a0()
    a1 = _synthetic_a1()
    miri = _synthetic_miri()
    miri["star_id"].values[:] = [1, 99, 3]
    with pytest.raises(AssertionError):
        ex.assemble_level_b1(a0, a1, miri, CONFIG)
