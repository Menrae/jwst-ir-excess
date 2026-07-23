"""
tests.test_retriever

STATUS: not yet implemented (Phase 1 scaffold only), except for
regression tests on real bugs found 2026-07-22/2026-07-23 (see
RESEARCH_CONTEXT.md): assemble_level_a0's generic per-column
np.asarray(star_table[name]) pass-through leaves _cat.ecsv-derived
bool-valued object columns (e.g. is_extended_{band}) as dtype=object,
which Dataset.to_netcdf cannot always write -- it fails specifically
when every star has a real True/False value (no missing entries to
dilute the column away from a pure-bool resolution); pivot_to_one_row_per_star's
former unintended sort order; coronagraphic-target handling; the
Gaia-crossmatch query-deduplication helper; and the download-timeout
adapter. Most tests will be written alongside the rest of the
corresponding pipeline module.
"""

import numpy as np
import pytest
import requests
from astropy.table import Table

from pipeline.retriever import (
    DOWNLOAD_TIMEOUT_S,
    _DefaultTimeoutAdapter,
    _group_observations_by_position,
    _is_coronagraphic,
    assemble_level_a0,
    load_miri_catalog_sources,
    pivot_to_one_row_per_star,
)

CONFIG = {
    "retriever": {
        "mast": {"filters": ["F770W", "F1000W"]},
        "gaia": {"crossmatch_radius_arcsec": 0.5},
        "twomass": {"crossmatch_radius_arcsec": 1.0},
    }
}


def _minimal_star_table(is_extended_f770w) -> Table:
    n = len(is_extended_f770w)
    return Table(
        {
            "star_row_id": np.arange(n),
            "star_id": np.arange(100, 100 + n),
            "gaia_ra": np.full(n, 10.0),
            "gaia_dec": np.full(n, 20.0),
            "gaia_pmra": np.zeros(n),
            "gaia_pmdec": np.zeros(n),
            "gaia_parallax": np.ones(n),
            "miri_ra_F770W": np.full(n, 10.0),
            "miri_dec_F770W": np.full(n, 20.0),
            "miri_ra_F1000W": np.full(n, 10.0),
            "miri_dec_F1000W": np.full(n, 20.0),
            "is_extended_F770W": np.array(is_extended_f770w, dtype=object),
        }
    )


def test_assemble_level_a0_handles_all_true_false_is_extended_without_netcdf_error(tmp_path):
    # Regression test for the real 2026-07-22 GD153 bug: every star has a
    # real bool value (no NaN to dilute the object array away from a pure
    # bool resolution) -- this used to write an unwritable dtype=object
    # (effectively bool) column.
    star_table = _minimal_star_table([True, False])
    ds = assemble_level_a0(star_table, CONFIG, ["F770W", "F1000W"])
    assert ds["is_extended_F770W"].dtype == np.float64
    np.testing.assert_array_equal(ds["is_extended_F770W"].values, [1.0, 0.0])
    ds.to_netcdf(tmp_path / "a0.nc")  # must not raise


def test_assemble_level_a0_handles_mixed_nan_and_bool_is_extended(tmp_path):
    star_table = _minimal_star_table([True, np.nan, False])
    ds = assemble_level_a0(star_table, CONFIG, ["F770W", "F1000W"])
    assert ds["is_extended_F770W"].dtype == np.float64
    np.testing.assert_array_equal(
        np.isnan(ds["is_extended_F770W"].values), [False, True, False]
    )
    ds.to_netcdf(tmp_path / "a0.nc")  # must not raise


def test_assemble_level_a0_handles_all_nan_is_extended(tmp_path):
    star_table = _minimal_star_table([np.nan, np.nan])
    ds = assemble_level_a0(star_table, CONFIG, ["F770W", "F1000W"])
    ds.to_netcdf(tmp_path / "a0.nc")  # must not raise


def test_assemble_level_a0_handles_field_with_only_one_band_present():
    # Regression test for the real 2026-07-22 trial-batch bug: a field
    # with detections in only ONE of the configured filters (confirmed
    # real: -BET-PIC and NGC-1266-BACKGROUND, both F770W-only with zero
    # F1000W observations) never gets miri_ra_F1000W/miri_dec_F1000W
    # columns at all -- pivot_to_one_row_per_star's unstack("filter")
    # only creates columns for filters actually present in the input.
    # This used to crash with KeyError: 'miri_ra_F1000W' inside
    # assemble_level_a0's per-filter units-attrs loop.
    n = 2
    star_table = Table(
        {
            "star_row_id": np.arange(n),
            "star_id": np.arange(100, 100 + n),
            "gaia_ra": np.full(n, 10.0),
            "gaia_dec": np.full(n, 20.0),
            "gaia_pmra": np.zeros(n),
            "gaia_pmdec": np.zeros(n),
            "gaia_parallax": np.ones(n),
            "miri_ra_F770W": np.full(n, 10.0),
            "miri_dec_F770W": np.full(n, 20.0),
            "is_extended_F770W": np.array([True, False], dtype=object),
        }
    )
    ds = assemble_level_a0(star_table, CONFIG, ["F770W", "F1000W"])  # must not raise
    assert "miri_ra_F1000W" not in ds.data_vars
    assert ds["miri_ra_F770W"].attrs["units"] == "deg"


# --- pivot_to_one_row_per_star row order (2026-07-23 bug) ---------------------


def test_pivot_to_one_row_per_star_does_not_bias_a_downstream_cap_against_gaia_matched_stars():
    # Regression test for the real 2026-07-23 bug (found via the 75-field
    # smoke batch: 100% single-band, 0/1425 dual-band stars, across a
    # sample where the true archive rate is not zero): unstack("filter")
    # implicitly sorts its result ascending by star_id. Unmatched-source
    # sentinel star_ids are small negative integers; Gaia-matched star_ids
    # are ~19-digit positive gaia_source_ids -- so every unmatched star used
    # to sort before every Gaia-matched star, silently. A naive downstream
    # "first N rows" cap (used by this project's trial/smoke batch scripts)
    # would then always miss Gaia-matched -- and therefore all dual-band-
    # capable -- stars whenever a field had more than N unmatched
    # detections (confirmed the common case on real archive data).
    #
    # Mimics that real shape: 8 unmatched singleton detections, with one
    # genuine dual-band Gaia-matched star's two detections (source_row_id
    # 0 and 9) at the very front and back of raw arrival order.
    n = 10
    gaia_source_id = [5258785479377301248] + [0] * 8 + [5258785479377301248]
    qc_no_gaia_match = [0] + [1] * 8 + [0]
    filt = ["F770W"] + ["F770W"] * 8 + ["F1000W"]
    sources = Table(
        {
            "star_row_id": np.arange(n),
            "source_row_id": np.arange(n),
            "gaia_source_id": gaia_source_id,
            "qc_no_gaia_match": qc_no_gaia_match,
            "filter": filt,
            "miri_ra": np.linspace(10.0, 11.0, n),
            "miri_dec": np.linspace(20.0, 21.0, n),
            "target_classification": ["Star"] * n,
        }
    )
    result = pivot_to_one_row_per_star(sources, ["F770W", "F1000W"])

    dual_band_mask = np.array(result["qc_single_filter_detection"]) == 0
    assert dual_band_mask.sum() == 1
    # First-appearance order must be preserved: the dual-band star's first
    # detection (source_row_id 0) was the very first row in raw input, so
    # it must be the first pivoted row too -- not sorted to the tail behind
    # 8 unmatched singletons the way the pre-fix ascending star_id sort did.
    assert np.flatnonzero(dual_band_mask)[0] == 0


def test_pivot_to_one_row_per_star_preserves_first_appearance_order_generally():
    # Broader than the dual-band-specific case above: row order should
    # match first-appearance order of star_id in the input, full stop --
    # not just "happens to work for one dual-band star."
    n = 5
    sources = Table(
        {
            "star_row_id": np.arange(n),
            "source_row_id": np.arange(n),
            "gaia_source_id": [0, 9111111111111111111 % (2**63), 0, 0, 0],
            "qc_no_gaia_match": [1, 0, 1, 1, 1],
            "filter": ["F770W"] * n,
            "miri_ra": np.linspace(10.0, 11.0, n),
            "miri_dec": np.linspace(20.0, 21.0, n),
            "target_classification": ["Star"] * n,
        }
    )
    result = pivot_to_one_row_per_star(sources, ["F770W", "F1000W"])
    # star_id order should be [-1, <gaia id>, -3, -4, -5] (first-appearance),
    # NOT ascending-numeric ([-5, -4, -3, -1, <gaia id>]).
    star_ids = list(result["star_id"])
    assert star_ids == [-1, 9111111111111111111 % (2**63), -3, -4, -5]


# --- coronagraphic target handling (2026-07-23 bug) ---------------------------


def test_is_coronagraphic_matches_known_subarray_tokens():
    assert _is_coronagraphic("jw01037-o017_t010_miri_f1000w-masklyot")
    assert _is_coronagraphic("jw01037-o017_t010_miri_f1550c-mask1550")
    assert _is_coronagraphic("jw01037-o017_t010_miri_f1065c-mask1065")
    assert _is_coronagraphic("jw01037-o017_t010_miri_f1140c-mask1140")
    assert not _is_coronagraphic("jw01235-o001_t002_miri_f770w")
    assert not _is_coronagraphic("jw01235-o001_t002_miri_f1000w")


def test_is_coronagraphic_case_insensitive():
    assert _is_coronagraphic("JW01037-O017_T010_MIRI_F1000W-MASKLYOT")


def test_load_miri_catalog_sources_raises_clear_error_when_no_catalogs_downloaded():
    # Regression test for the real 2026-07-23 bug (TYC-2571-885-1, a
    # coronagraphic-only target): used to crash with astropy's generic
    # "ValueError: no values provided to stack." when every observation
    # for a target was missing a downloaded _cat.ecsv -- now query-time
    # filtered for the known cause (coronagraphy), but this guards any
    # other, not-yet-seen cause with an attributable error instead.
    manifest = Table(
        {
            "obs_id": ["jw01037-o017_t010_miri_f1000w-masklyot"],
            "productFilename": ["jw01037-o017_t010_miri_f1000w-masklyot_i2d.fits"],
            "Local Path": ["/tmp/fake_i2d.fits"],
        }
    )
    obs_table = Table(
        {
            "obs_id": ["jw01037-o017_t010_miri_f1000w-masklyot"],
            "filters": ["F1000W"],
            "proposal_id": ["1037"],
            "target_classification": ["Star; K stars"],
            "t_min": [59000.0],
            "target_name": ["TYC-2571-885-1"],
        }
    )
    with pytest.raises(ValueError, match="zero MIRI catalog sources"):
        load_miri_catalog_sources(manifest, obs_table)


# --- Gaia cone-search query deduplication (2026-07-23 bug) --------------------


def test_group_observations_by_position_clusters_repeat_visits_not_distinct_tiles():
    # Mimics BD+60-1753 (a calibration standard: 79 observations at
    # virtually the same sky position, ~0.2 arcsec spread, which used to
    # trigger 79 near-identical Gaia queries instead of 1) alongside a
    # genuinely different mosaic-tile pointing that must NOT be merged in.
    obs_centers = {
        "obs_a": (100.0, 20.0),
        "obs_b": (100.0 + 0.05 / 3600, 20.0),  # ~0.18 arcsec -- repeat visit
        "obs_c": (100.0 + 0.1 / 3600, 20.0 + 0.05 / 3600),  # ~0.4 arcsec -- repeat visit
        "obs_d": (100.05, 20.0),  # ~180 arcsec -- a genuinely different tile
    }
    groups = _group_observations_by_position(obs_centers, dedup_radius_arcsec=5.0)
    assert groups["obs_a"] == groups["obs_b"] == groups["obs_c"] == "obs_a"
    assert groups["obs_d"] == "obs_d"
    assert len(set(groups.values())) == 2


def test_group_observations_by_position_no_grouping_needed_is_identity():
    obs_centers = {"obs_a": (100.0, 20.0), "obs_b": (200.0, -30.0)}
    groups = _group_observations_by_position(obs_centers, dedup_radius_arcsec=5.0)
    assert groups == {"obs_a": "obs_a", "obs_b": "obs_b"}


# --- download timeout adapter (2026-07-23 bug: NGC6720 hung ~77 min) ---------


def test_default_timeout_adapter_injects_default_when_none_specified(monkeypatch):
    # Regression test for the real 2026-07-23 bug: requests.Session has no
    # built-in default timeout, and astroquery's own download code never
    # passes one explicitly -- confirmed directly in its source -- so a
    # stalled connection could hang indefinitely (NGC6720: ~77 minutes)
    # instead of failing fast and being caught by the batch's existing
    # per-field exception handling.
    captured = {}

    def fake_send(self, *args, **kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)
    adapter = _DefaultTimeoutAdapter(DOWNLOAD_TIMEOUT_S)
    adapter.send("fake_request")
    assert captured["timeout"] == DOWNLOAD_TIMEOUT_S


def test_default_timeout_adapter_does_not_override_an_explicit_timeout(monkeypatch):
    captured = {}

    def fake_send(self, *args, **kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)
    adapter = _DefaultTimeoutAdapter(DOWNLOAD_TIMEOUT_S)
    adapter.send("fake_request", timeout=5)
    assert captured["timeout"] == 5
