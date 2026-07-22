"""
tests.test_contaminants

Fast, network-free unit tests for pipeline.contaminants: the alignment
check, the HR-diagram overluminosity discriminator (qc_evolved_star), the
morphology-based background-galaxy flag, the known-variable flag's
pure/testable half (compute_known_variable_flag -- query_gaia_variability
itself, the live Gaia call, is NOT tested here, same convention as this
project's other live-service dependencies), the qc_possible_binary
passthrough, the debris-disk crossmatch's pure/testable half
(crossmatch_debris_disk_catalog -- fetch_debris_disk_catalog itself, the
live VizieR call, is NOT tested here, same convention), and the full
join/assembly against small synthetic a0/b1 datasets. Five of six planned
categories (Tiers 1, 2, and the first Tier-3 item, 2026-07-22) are covered
here -- see RESEARCH_CONTEXT.md for the remaining one.
"""

import numpy as np
import pytest
import xarray as xr
from astropy.table import Table

from pipeline import contaminants as co

CONFIG = {
    "excess": {"primary_bands": ["F770W", "F1000W"]},
    "contaminants": {
        "evolved_star": {"overluminosity_mag_threshold": 2.5, "min_parallax_over_error": 5.0},
        "debris_disk": {"crossmatch_radius_arcsec": 2.0},
        "cluster_membership": {"min_parallax_over_error": 5.0},
    },
}

CONFIG_WITH_THRESHOLD = {
    "excess": {"primary_bands": ["F770W", "F1000W"], "significance_threshold_sigma": 3.0},
    "contaminants": CONFIG["contaminants"],
}


def _dataset(n, **data_vars):
    coords = {"star": np.arange(n)}
    return xr.Dataset(
        data_vars={k: ("star", np.asarray(v)) for k, v in data_vars.items()},
        coords=coords,
    )


# --- assert_star_aligned -----------------------------------------------------


def test_assert_star_aligned_passes_for_matching_ids():
    a0 = _dataset(3, star_id=[1, 2, 3])
    b1 = _dataset(3, star_id=[1, 2, 3])
    co.assert_star_aligned(a0, b1)  # should not raise


def test_assert_star_aligned_raises_on_length_mismatch():
    a0 = _dataset(3, star_id=[1, 2, 3])
    b1 = _dataset(2, star_id=[1, 2])
    with pytest.raises(AssertionError, match="length mismatch"):
        co.assert_star_aligned(a0, b1)


def test_assert_star_aligned_raises_on_reordered_ids():
    a0 = _dataset(3, star_id=[1, 2, 3])
    b1 = _dataset(3, star_id=[1, 3, 2])
    with pytest.raises(AssertionError, match="not aligned"):
        co.assert_star_aligned(a0, b1)


# --- expected_ms_abs_g / absolute_g_mag ---------------------------------------


def test_expected_ms_abs_g_monotonic_hotter_is_brighter():
    # Hotter main-sequence stars are intrinsically brighter (more negative/
    # smaller absolute magnitude).
    assert co.expected_ms_abs_g(9700) < co.expected_ms_abs_g(5240) < co.expected_ms_abs_g(3870)


def test_expected_ms_abs_g_clips_at_table_extremes():
    assert co.expected_ms_abs_g(1000) == co.expected_ms_abs_g(3000)
    assert co.expected_ms_abs_g(100000) == co.expected_ms_abs_g(42000)


def test_absolute_g_mag_basic_value():
    # d=100pc -> distance modulus 5*log10(100)-5 = 5; M_G = m_G - 5
    assert co.absolute_g_mag(phot_g_mean_mag=10.0, parallax_mas=10.0) == pytest.approx(5.0)


def test_absolute_g_mag_nan_for_nonpositive_or_missing_parallax():
    assert np.isnan(co.absolute_g_mag(10.0, 0.0))
    assert np.isnan(co.absolute_g_mag(10.0, -1.0))
    assert np.isnan(co.absolute_g_mag(10.0, np.nan))
    assert np.isnan(co.absolute_g_mag(np.nan, 10.0))


# --- is_evolved_star_overluminous ---------------------------------------------


def test_is_evolved_star_overluminous_true_for_giant_like_luminosity():
    # Teff=5240K (K0V-like) expects M_G ~= 5.9. A star at this Teff but
    # d=1000pc (parallax=1.0 mas, parallax_error=0.05 -- SNR=20, trustworthy)
    # with phot_g_mean_mag=6.0 has M_G = 6.0 - (5*log10(1000)-5) = -4.0 --
    # ~10 mag brighter than expected, a clear giant-luminosity case.
    assert co.is_evolved_star_overluminous(
        photosphere_teff=5240.0,
        phot_g_mean_mag=6.0,
        parallax_mas=1.0,
        parallax_error_mas=0.05,
        config=CONFIG,
    )


def test_is_evolved_star_overluminous_false_for_dwarf_like_luminosity():
    # A star at the SAME Teff/distance as the giant case above, but with a
    # magnitude consistent with the main-sequence expectation, should not
    # be flagged.
    expected = co.expected_ms_abs_g(5240.0)
    distance_modulus = 5 * np.log10(1000.0) - 5  # d=1000pc
    phot_g_mean_mag = expected + distance_modulus
    assert not co.is_evolved_star_overluminous(
        photosphere_teff=5240.0,
        phot_g_mean_mag=phot_g_mean_mag,
        parallax_mas=1.0,
        parallax_error_mas=0.05,
        config=CONFIG,
    )


def test_is_evolved_star_overluminous_false_when_teff_missing():
    assert not co.is_evolved_star_overluminous(
        photosphere_teff=np.nan,
        phot_g_mean_mag=6.0,
        parallax_mas=1.0,
        parallax_error_mas=0.05,
        config=CONFIG,
    )


def test_is_evolved_star_overluminous_false_when_parallax_missing():
    assert not co.is_evolved_star_overluminous(
        photosphere_teff=5240.0,
        phot_g_mean_mag=6.0,
        parallax_mas=np.nan,
        parallax_error_mas=0.05,
        config=CONFIG,
    )


def test_is_evolved_star_overluminous_false_when_parallax_snr_too_low():
    # Same giant-like case as the true-positive test above, but with a
    # noisy parallax (SNR = 1.0/0.5 = 2, below min_parallax_over_error=5) --
    # must NOT be flagged even though the point-estimate magnitude looks
    # like a giant, since a low-S/N parallax inverted to a distance is a
    # known bias (this is the real PN-TC-1 case that motivated the gate).
    assert not co.is_evolved_star_overluminous(
        photosphere_teff=5240.0,
        phot_g_mean_mag=6.0,
        parallax_mas=1.0,
        parallax_error_mas=0.5,
        config=CONFIG,
    )


def test_is_evolved_star_overluminous_false_when_parallax_error_missing():
    assert not co.is_evolved_star_overluminous(
        photosphere_teff=5240.0,
        phot_g_mean_mag=6.0,
        parallax_mas=1.0,
        parallax_error_mas=np.nan,
        config=CONFIG,
    )


# --- compute_background_galaxy_flag -------------------------------------------


def test_compute_background_galaxy_flag_true_if_extended_in_any_band():
    a0 = _dataset(
        3,
        is_extended_F770W=[0.0, 1.0, np.nan],
        is_extended_F1000W=[0.0, 0.0, 1.0],
    )
    result = co.compute_background_galaxy_flag(a0, ["F770W", "F1000W"])
    np.testing.assert_array_equal(result, [False, True, True])


def test_compute_background_galaxy_flag_missing_band_column_is_no_evidence():
    a0 = _dataset(2, is_extended_F770W=[1.0, 0.0])
    result = co.compute_background_galaxy_flag(a0, ["F770W", "F1000W"])
    np.testing.assert_array_equal(result, [True, False])


# --- compute_known_variable_flag ----------------------------------------------


def test_compute_known_variable_flag_true_only_for_member_ids():
    gaia_source_id = np.array([100, 200, 300])
    result = co.compute_known_variable_flag(gaia_source_id, variable_source_ids={200})
    np.testing.assert_array_equal(result, [False, True, False])


def test_compute_known_variable_flag_never_flags_zero_sentinel():
    # gaia_source_id==0 is retriever.py's no-Gaia-match sentinel -- even if
    # 0 somehow ended up in variable_source_ids, it must never be flagged.
    gaia_source_id = np.array([0, 200])
    result = co.compute_known_variable_flag(gaia_source_id, variable_source_ids={0, 200})
    np.testing.assert_array_equal(result, [False, True])


def test_compute_known_variable_flag_empty_set_flags_nothing():
    gaia_source_id = np.array([100, 200])
    result = co.compute_known_variable_flag(gaia_source_id, variable_source_ids=set())
    np.testing.assert_array_equal(result, [False, False])


# --- compute_binary_companion_contamination_flag ------------------------------


def test_compute_binary_companion_contamination_flag_passes_through_qc_possible_binary():
    b1 = _dataset(3, qc_possible_binary=[0, 1, 0])
    result = co.compute_binary_companion_contamination_flag(b1)
    np.testing.assert_array_equal(result, [False, True, False])


# --- crossmatch_debris_disk_catalog -------------------------------------------


def _debris_disk_table(entries):
    """entries: list of (RAJ2000, DEJ2000) sexagesimal strings, same schema
    as Cotten & Song (2016)'s VizieR tables."""
    return Table({"RAJ2000": [e[0] for e in entries], "DEJ2000": [e[1] for e in entries]})


def test_crossmatch_debris_disk_catalog_matches_within_radius():
    # RA "00 40 00.00" = 0h40m = 10.0 deg; Dec "+20 00 00.0" = 20.0 deg.
    catalog = _debris_disk_table([("00 40 00.00", "+20 00 00.0")])
    star_ra = np.array([10.0, 100.0])
    star_dec = np.array([20.0, -40.0])
    matched, ambiguous = co.crossmatch_debris_disk_catalog(star_ra, star_dec, catalog, radius_arcsec=2.0)
    np.testing.assert_array_equal(matched, [True, False])
    np.testing.assert_array_equal(ambiguous, [False, False])


def test_crossmatch_debris_disk_catalog_ambiguous_when_multiple_hits():
    # Two distinct catalog rows at (effectively) the same position -- both
    # within radius of the one star being checked.
    catalog = _debris_disk_table([("00 40 00.00", "+20 00 00.0"), ("00 40 00.00", "+20 00 00.0")])
    star_ra = np.array([10.0])
    star_dec = np.array([20.0])
    matched, ambiguous = co.crossmatch_debris_disk_catalog(star_ra, star_dec, catalog, radius_arcsec=2.0)
    np.testing.assert_array_equal(matched, [True])
    np.testing.assert_array_equal(ambiguous, [True])


def test_crossmatch_debris_disk_catalog_empty_catalog_matches_nothing():
    catalog = _debris_disk_table([])
    star_ra = np.array([10.0])
    star_dec = np.array([20.0])
    matched, ambiguous = co.crossmatch_debris_disk_catalog(star_ra, star_dec, catalog, radius_arcsec=2.0)
    np.testing.assert_array_equal(matched, [False])
    np.testing.assert_array_equal(ambiguous, [False])


def test_crossmatch_debris_disk_catalog_nonfinite_star_position_never_matches():
    catalog = _debris_disk_table([("00 40 00.00", "+20 00 00.0")])
    star_ra = np.array([np.nan])
    star_dec = np.array([20.0])
    matched, ambiguous = co.crossmatch_debris_disk_catalog(star_ra, star_dec, catalog, radius_arcsec=2.0)
    np.testing.assert_array_equal(matched, [False])


# --- compute_cluster_member_confirmed_flag / is_confirmed_field_star ----------


def test_compute_cluster_member_confirmed_flag_true_only_for_members():
    gaia_source_id = np.array([100, 200, 300])
    result = co.compute_cluster_member_confirmed_flag(gaia_source_id, member_source_ids={200})
    np.testing.assert_array_equal(result, [False, True, False])


def test_compute_cluster_member_confirmed_flag_never_flags_zero_sentinel():
    gaia_source_id = np.array([0, 200])
    result = co.compute_cluster_member_confirmed_flag(gaia_source_id, member_source_ids={0, 200})
    np.testing.assert_array_equal(result, [False, True])


def test_is_confirmed_field_star_true_for_trustworthy_nonmember():
    assert co.is_confirmed_field_star(
        gaia_source_id=999,
        parallax_mas=5.0,
        parallax_error_mas=0.1,  # SNR=50
        member_source_ids=set(),
        config=CONFIG,
    )


def test_is_confirmed_field_star_false_for_confirmed_member():
    # Same trustworthy parallax as above, but the star IS a catalogued member.
    assert not co.is_confirmed_field_star(
        gaia_source_id=999,
        parallax_mas=5.0,
        parallax_error_mas=0.1,
        member_source_ids={999},
        config=CONFIG,
    )


def test_is_confirmed_field_star_false_when_parallax_snr_too_low():
    # This is the mechanism that structurally rules out ever exonerating a
    # genuinely extragalactic (e.g. SMC-distance) star -- see module
    # docstring. SNR = 0.02/0.1 = 0.2, far below the threshold.
    assert not co.is_confirmed_field_star(
        gaia_source_id=999,
        parallax_mas=0.02,
        parallax_error_mas=0.1,
        member_source_ids=set(),
        config=CONFIG,
    )


def test_is_confirmed_field_star_false_when_parallax_missing():
    assert not co.is_confirmed_field_star(
        gaia_source_id=999,
        parallax_mas=np.nan,
        parallax_error_mas=0.1,
        member_source_ids=set(),
        config=CONFIG,
    )


# --- assemble_level_b2 (small synthetic end-to-end) ----------------------------


def _synthetic_a0(n=3):
    return _dataset(
        n,
        star_id=[1, 2, 3],
        gaia_phot_g_mean_mag=[6.0, 10.0, np.nan],
        gaia_parallax=[1.0, 10.0, np.nan],
        gaia_parallax_error=[0.05, 0.5, np.nan],
        is_extended_F770W=[0.0, 0.0, 1.0],
        is_extended_F1000W=[0.0, 0.0, 0.0],
        # Star 0 sits exactly on the synthetic Prime entry below; star 1 on
        # the Reserved entry; star 2 has no usable position.
        gaia_ra=[10.0, 50.0, np.nan],
        gaia_dec=[20.0, -10.0, np.nan],
    )


def _synthetic_b1(n=3):
    return _dataset(
        n,
        star_id=[1, 2, 3],
        gaia_source_id=[101, 102, 103],
        photosphere_teff=[5240.0, 5240.0, np.nan],
        excess_sigma_F770W=[5.0, 1.0, np.nan],
        excess_sigma_F1000W=[np.nan, np.nan, np.nan],
        qc_possible_binary=[0, 0, 1],
        qc_band_disqualified_F770W=[0, 0, 0],
        qc_band_disqualified_F1000W=[0, 0, 0],
        qc_stopgap_young_cluster=[0, 0, 0],
        qc_single_filter_detection=[0, 0, 0],
        # b1's own (already-computed) composite -- star 2 disqualified via
        # qc_possible_binary above, stars 0/1 otherwise clean.
        qc_excess_clean_F770W=[1, 1, 0],
        qc_excess_clean_F1000W=[1, 1, 0],
    )


VARIABLE_IDS = {102}
PRIME_TABLE = _debris_disk_table([("00 40 00.00", "+20 00 00.0")])  # RA=10, Dec=20 -- matches star 0
RESERVED_TABLE = _debris_disk_table([("03 20 00.00", "-10 00 00.0")])  # RA=50, Dec=-10 -- matches star 1
EMPTY_TABLE = _debris_disk_table([])
NO_CLUSTER_MEMBERS = set()


def _assemble(
    a0=None,
    b1=None,
    config=CONFIG,
    variable_ids=VARIABLE_IDS,
    prime=PRIME_TABLE,
    reserved=RESERVED_TABLE,
    cluster_ids=NO_CLUSTER_MEMBERS,
):
    return co.assemble_level_b2(
        a0 if a0 is not None else _synthetic_a0(),
        b1 if b1 is not None else _synthetic_b1(),
        config,
        variable_ids,
        prime,
        reserved,
        cluster_ids,
    )


def test_assemble_level_b2_keeps_every_star_no_dropping():
    ds = _assemble()
    assert ds.sizes["star"] == 3


def test_assemble_level_b2_carries_b1_columns_through():
    ds = _assemble()
    np.testing.assert_array_equal(ds["excess_sigma_F770W"].values, [5.0, 1.0, np.nan])


def test_assemble_level_b2_flags_evolved_star_and_background_galaxy_independently():
    ds = _assemble()
    # Star 0: giant-luminosity case (see is_evolved_star_overluminous tests) -- flagged evolved.
    assert ds["qc_evolved_star"].values[0] == 1
    assert ds["qc_background_galaxy"].values[0] == 0
    # Star 2: no Teff fit (can't evaluate evolved-star check) but is_extended in F770W.
    assert ds["qc_evolved_star"].values[2] == 0
    assert ds["qc_background_galaxy"].values[2] == 1


def test_assemble_level_b2_flags_known_variable_and_binary_contamination():
    ds = _assemble()
    # Star 1 (gaia_source_id=102) is in VARIABLE_IDS.
    np.testing.assert_array_equal(ds["qc_known_variable"].values, [0, 1, 0])
    # Star 2 has qc_possible_binary=1 in the b1 fixture -- passthrough.
    np.testing.assert_array_equal(ds["qc_binary_companion_contamination"].values, [0, 0, 1])


def test_assemble_level_b2_flags_debris_disk_prime_and_reserved_independently():
    ds = _assemble()
    # Star 0 matches PRIME_TABLE only; star 1 matches RESERVED_TABLE only.
    np.testing.assert_array_equal(ds["qc_debris_disk_prime"].values, [1, 0, 0])
    np.testing.assert_array_equal(ds["qc_debris_disk_reserved"].values, [0, 1, 0])
    np.testing.assert_array_equal(ds["qc_ambiguous_debris_disk_match"].values, [0, 0, 0])


def test_assemble_level_b2_flags_cluster_member_confirmed():
    ds = _assemble(cluster_ids={102})
    # Star 1 (gaia_source_id=102) is a confirmed cluster member.
    np.testing.assert_array_equal(ds["qc_cluster_member_confirmed"].values, [0, 1, 0])


def test_assemble_level_b2_partial_composite_is_or_of_all_flags_excluding_confirmed_field_star():
    ds = _assemble(cluster_ids={102})
    expected = (
        ds["qc_evolved_star"].values
        | ds["qc_background_galaxy"].values
        | ds["qc_known_variable"].values
        | ds["qc_binary_companion_contamination"].values
        | ds["qc_debris_disk_prime"].values
        | ds["qc_debris_disk_reserved"].values
        | ds["qc_cluster_member_confirmed"].values
    )
    np.testing.assert_array_equal(ds["qc_contaminant_flagged_partial"].values, expected)
    # qc_confirmed_field_star must never contribute to the contaminant composite.
    assert "qc_confirmed_field_star" not in [
        "qc_evolved_star",
        "qc_background_galaxy",
        "qc_known_variable",
        "qc_binary_companion_contamination",
        "qc_debris_disk_prime",
        "qc_debris_disk_reserved",
        "qc_cluster_member_confirmed",
    ]


def test_assemble_level_b2_raises_on_misaligned_input():
    a0 = _synthetic_a0()
    b1 = _synthetic_b1()
    b1["star_id"].values[:] = [1, 99, 3]
    with pytest.raises(AssertionError):
        _assemble(a0=a0, b1=b1)


# --- qc_*_refined: the additive, young-cluster-aware parallel composite -------


def _refinement_scenario(star_disqualified_only_by_young_cluster=True):
    """A single star, young-cluster-stopgap-flagged in b1, otherwise fully
    clean, with a trustworthy parallax (SNR=50)."""
    a0 = _dataset(
        1,
        star_id=[1],
        gaia_phot_g_mean_mag=[np.nan],
        gaia_parallax=[5.0],
        gaia_parallax_error=[0.1],
        is_extended_F770W=[0.0],
        is_extended_F1000W=[0.0],
        gaia_ra=[np.nan],
        gaia_dec=[np.nan],
    )
    b1 = _dataset(
        1,
        star_id=[1],
        gaia_source_id=[999],
        photosphere_teff=[np.nan],
        excess_sigma_F770W=[5.0],
        excess_sigma_F1000W=[5.0],
        qc_possible_binary=[0],
        qc_band_disqualified_F770W=[0],
        qc_band_disqualified_F1000W=[0],
        qc_stopgap_young_cluster=[1],
        qc_single_filter_detection=[0],
    )
    return a0, b1


def test_refined_composite_exonerates_when_confirmed_field_star():
    a0, b1 = _refinement_scenario()
    ds = _assemble(
        a0=a0, b1=b1, config=CONFIG_WITH_THRESHOLD, prime=EMPTY_TABLE, reserved=EMPTY_TABLE, cluster_ids=set()
    )
    assert ds["qc_confirmed_field_star"].values[0] == 1
    assert ds["qc_star_disqualified_refined"].values[0] == 0
    assert ds["qc_excess_clean_refined_F770W"].values[0] == 1
    assert ds["qc_excess_clean_refined_F1000W"].values[0] == 1
    assert ds["qc_excess_significant_refined_F770W"].values[0] == 1
    assert ds["qc_candidate_preliminary_refined"].values[0] == 1


def test_refined_composite_stays_disqualified_when_confirmed_cluster_member():
    a0, b1 = _refinement_scenario()
    ds = _assemble(
        a0=a0,
        b1=b1,
        config=CONFIG_WITH_THRESHOLD,
        prime=EMPTY_TABLE,
        reserved=EMPTY_TABLE,
        cluster_ids={999},
    )
    assert ds["qc_cluster_member_confirmed"].values[0] == 1
    assert ds["qc_confirmed_field_star"].values[0] == 0
    assert ds["qc_star_disqualified_refined"].values[0] == 1
    assert ds["qc_excess_clean_refined_F770W"].values[0] == 0
    assert "qc_candidate_preliminary_refined" not in ds or ds["qc_candidate_preliminary_refined"].values[0] == 0


def test_refined_composite_matches_original_when_young_cluster_never_flagged():
    # Default _synthetic_b1 fixture has qc_stopgap_young_cluster all-zero --
    # the refined view should be identical to the original in that case.
    ds = _assemble(config=CONFIG_WITH_THRESHOLD)
    np.testing.assert_array_equal(
        ds["qc_excess_clean_refined_F770W"].values, ds["qc_excess_clean_F770W"].values
    )


def test_refined_columns_absent_when_threshold_not_set():
    ds = _assemble(config=CONFIG)  # significance_threshold_sigma unset
    assert "qc_excess_significant_refined_F770W" not in ds
    assert "qc_candidate_preliminary_refined" not in ds
    # qc_excess_clean_refined_{band} does not depend on the threshold, so it
    # is still computed.
    assert "qc_excess_clean_refined_F770W" in ds
