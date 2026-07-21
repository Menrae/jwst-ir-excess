"""
tests.test_miri_photometry

Fast, network-free unit tests for the pure/deterministic parts of
pipeline.miri_photometry (APCORR table lookup, stamp geometry, QC-flag
logic, aperture photometry against synthetic arrays). Anything touching
stpsf/photutils.psf.PSFPhotometry against real mosaic data is exercised via
live smoke-testing instead (see RESEARCH_CONTEXT.md Decision Log,
2026-07-21), the same convention test_photosphere.py follows for
stsynphot/expecto/dustmaps.
"""

import numpy as np
import pytest
from astropy.table import Table

from pipeline import miri_photometry as mp


def _synthetic_apcorr_table() -> Table:
    return Table(
        {
            "filter": ["F770W", "F770W", "F1000W"],
            "subarray": ["FULL", "FULL", "FULL"],
            "eefraction": np.array([0.6, 0.7, 0.7], dtype=np.float32),
            "radius": np.array([2.75, 4.22, 4.60], dtype=np.float32),
            "apcorr": np.array([1.675, 1.442, 1.453], dtype=np.float32),
            "skyin": np.array([8.92, 8.92, 6.70], dtype=np.float32),
            "skyout": np.array([14.64, 14.64, 11.58], dtype=np.float32),
        }
    )


def test_suffix_column_puts_filter_before_err_suffix():
    # Must match photosphere.py's predicted_flux_{band}_err convention
    # (filter BEFORE _err) -- a naive f"{key}_{filt}" would instead produce
    # observed_flux_err_F770W, which is inconsistent with the rest of the
    # pipeline's column naming.
    assert mp._suffix_column("observed_flux_err", "F770W") == "observed_flux_F770W_err"
    assert mp._suffix_column("observed_flux", "F770W") == "observed_flux_F770W"
    assert mp._suffix_column("qc_saturated", "F1000W") == "qc_saturated_F1000W"


def test_select_apcorr_row_returns_matching_row():
    table = _synthetic_apcorr_table()
    row = mp.select_apcorr_row(table, "F770W", "FULL", 0.7)
    assert row["radius_px"] == pytest.approx(4.22, abs=1e-2)
    assert row["apcorr"] == pytest.approx(1.442, abs=1e-3)
    assert row["skyin_px"] == pytest.approx(8.92, abs=1e-2)
    assert row["skyout_px"] == pytest.approx(14.64, abs=1e-2)


def test_select_apcorr_row_distinguishes_filters():
    table = _synthetic_apcorr_table()
    f770 = mp.select_apcorr_row(table, "F770W", "FULL", 0.7)
    f1000 = mp.select_apcorr_row(table, "F1000W", "FULL", 0.7)
    assert f770["radius_px"] != f1000["radius_px"]


def test_select_apcorr_row_missing_combination_raises():
    table = _synthetic_apcorr_table()
    with pytest.raises(ValueError):
        mp.select_apcorr_row(table, "F2100W", "FULL", 0.7)


def test_stamp_half_width_px_rounds_up_and_adds_margin():
    assert mp.stamp_half_width_px(4.22, margin_px=2) == 5 + 2
    assert mp.stamp_half_width_px(4.0, margin_px=2) == 4 + 2


def test_is_within_mosaic_true_for_centered_source():
    assert mp.is_within_mosaic(300.0, 300.0, (600, 600), half_width=10)


def test_is_within_mosaic_false_near_edge():
    assert not mp.is_within_mosaic(5.0, 300.0, (600, 600), half_width=10)
    assert not mp.is_within_mosaic(300.0, 595.0, (600, 600), half_width=10)


def test_has_nonfinite_pixel_detects_nan_in_region():
    sci = np.ones((50, 50))
    sci[24, 24] = np.nan
    assert mp.has_nonfinite_pixel(sci, 25.0, 25.0, half_width=3)
    assert not mp.has_nonfinite_pixel(sci, 5.0, 5.0, half_width=2)


def test_has_close_neighbor_true_within_radius():
    others = [(310.0, 300.0)]  # 10 px away
    assert mp.has_close_neighbor(300.0, 300.0, others, min_separation_px=20.0)


def test_has_close_neighbor_false_beyond_radius():
    others = [(400.0, 300.0)]  # 100 px away
    assert not mp.has_close_neighbor(300.0, 300.0, others, min_separation_px=20.0)


def test_has_close_neighbor_false_with_no_neighbors():
    assert not mp.has_close_neighbor(300.0, 300.0, [], min_separation_px=20.0)


def test_flags_indicate_fit_failure_nonzero_flags():
    # Real value observed live 2026-07-21 for a genuinely extended source
    # in the PN-TC-1 field (F1000W) -- see RESEARCH_CONTEXT.md. Kept as a
    # named regression case, not just an arbitrary nonzero flags value.
    assert mp.flags_indicate_fit_failure(12)


def test_flags_indicate_fit_failure_zero_flags_is_success():
    assert not mp.flags_indicate_fit_failure(0)


def test_psf_aperture_disagreement_flags_large_relative_difference():
    assert mp.psf_aperture_disagreement(
        psf_flux_jy=1.0e-3, aperture_flux_jy=2.0e-3, abs_floor_jy=1e-6, rel_frac=0.2
    )


def test_psf_aperture_disagreement_not_flagged_for_close_values():
    assert not mp.psf_aperture_disagreement(
        psf_flux_jy=1.0e-3, aperture_flux_jy=1.05e-3, abs_floor_jy=1e-6, rel_frac=0.2
    )


def test_psf_aperture_disagreement_false_for_nonfinite_inputs():
    assert not mp.psf_aperture_disagreement(
        psf_flux_jy=np.nan, aperture_flux_jy=1.0e-3, abs_floor_jy=1e-6, rel_frac=0.2
    )


def test_classify_disagreement_not_disagreeing_is_neither():
    assert mp.classify_disagreement(False, snr=5.0, snr_threshold=50.0) == (False, False)
    assert mp.classify_disagreement(False, snr=5000.0, snr_threshold=50.0) == (False, False)


def test_classify_disagreement_low_snr_is_faint():
    is_faint, is_complex = mp.classify_disagreement(True, snr=29.2, snr_threshold=50.0)
    assert is_faint and not is_complex


def test_classify_disagreement_high_snr_is_complex():
    # The real NGC-602 example that motivated the split.
    is_faint, is_complex = mp.classify_disagreement(True, snr=1425.5, snr_threshold=50.0)
    assert is_complex and not is_faint


def test_classify_disagreement_at_threshold_is_complex_not_faint():
    is_faint, is_complex = mp.classify_disagreement(True, snr=50.0, snr_threshold=50.0)
    assert is_complex and not is_faint


def test_classify_disagreement_nonfinite_snr_defaults_to_complex():
    # Uncomputable SNR (e.g. zero/NaN observed_flux_err) errs toward
    # "needs a closer look" rather than silently assuming it's noise-limited.
    is_faint, is_complex = mp.classify_disagreement(True, snr=np.nan, snr_threshold=50.0)
    assert is_complex and not is_faint


def test_aperture_flux_with_local_bkg_recovers_known_flux():
    # Synthetic frame: flat background + a compact Gaussian blob of known
    # total flux, well inside a generous aperture -- checks the background
    # annulus subtraction and aperture sum logic against ground truth,
    # without touching stpsf/PSFPhotometry (which need real reference data
    # and are smoke-tested live instead).
    size = 61
    y, x = np.mgrid[0:size, 0:size]
    x0, y0 = 30.0, 30.0
    true_bkg = 50.0
    true_flux = 1000.0
    sigma = 2.0
    blob = true_flux / (2 * np.pi * sigma**2) * np.exp(-((x - x0) ** 2 + (y - y0) ** 2) / (2 * sigma**2))
    sci = blob + true_bkg

    recovered = mp.aperture_flux_with_local_bkg(
        sci, x0, y0, radius_px=12.0, skyin_px=15.0, skyout_px=25.0
    )
    # A 12px-radius aperture around a sigma=2px Gaussian captures
    # effectively all the flux -- allow a small tolerance for the
    # background-annulus estimator's own noise-free-but-discrete pixel sum.
    assert recovered == pytest.approx(true_flux, rel=0.02)
