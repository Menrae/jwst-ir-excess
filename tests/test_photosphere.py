"""
tests.test_photosphere

Fast, network-free unit tests for the pure/deterministic parts of
pipeline.photosphere (grid/bucket selection, target-classification gates,
discrete-grid fitting machinery). Anything touching stsynphot/expecto/
dustmaps/astroquery.svo_fps is exercised via live smoke-testing instead (see
RESEARCH_CONTEXT.md Decision Log, 2026-07-20) rather than mocked here.
"""

import numpy as np
import pytest

from pipeline import photosphere as ps

CONFIG = {
    "photosphere": {
        "grids": {
            "hot_teff_min_k": 8000.0,
            "cool_teff_max_k": 3500.0,
            "cross_check_buffer_k": 500.0,
        },
        "target_classification_tokens": {
            "white_dwarf": ["White dwarfs"],
            "pms_veiling_risk": ["T Tauri stars", "Protostars"],
        },
    }
}


def test_rough_teff_from_bp_rp_monotonic_and_clipped():
    # Bluer (smaller BP-RP) -> hotter; redder -> cooler.
    assert ps.rough_teff_from_bp_rp(-0.3) > ps.rough_teff_from_bp_rp(0.6) > ps.rough_teff_from_bp_rp(2.0)
    # Clipped, not extrapolated, past the anchor table's extremes.
    assert ps.rough_teff_from_bp_rp(-10.0) == ps.rough_teff_from_bp_rp(-0.35)
    assert ps.rough_teff_from_bp_rp(10.0) == ps.rough_teff_from_bp_rp(3.15)


def test_select_grids_hot_bucket_no_cross_check_far_from_boundary():
    primary, fit_grids = ps.select_grids(20000.0, CONFIG)
    assert primary == "kurucz"
    assert fit_grids == ["kurucz"]


def test_select_grids_cool_bucket_no_cross_check_far_from_boundary():
    primary, fit_grids = ps.select_grids(2500.0, CONFIG)
    assert primary == "phoenix"
    assert fit_grids == ["phoenix"]


def test_select_grids_fgk_bucket_cross_checks():
    primary, fit_grids = ps.select_grids(5500.0, CONFIG)
    assert primary == "kurucz"
    assert set(fit_grids) == {"kurucz", "phoenix"}


def test_select_grids_buffer_widens_cross_check_near_hot_boundary():
    # 8300 K is above hot_teff_min_k (8000) so primary is kurucz, but within
    # the 500 K buffer -- should still cross-check, not skip it just because
    # the rough BP-RP estimate landed a little on the hot side of the line.
    primary, fit_grids = ps.select_grids(8300.0, CONFIG)
    assert primary == "kurucz"
    assert set(fit_grids) == {"kurucz", "phoenix"}
    # Far beyond the buffer: no cross-check.
    primary, fit_grids = ps.select_grids(9000.0, CONFIG)
    assert fit_grids == ["kurucz"]


def test_is_white_dwarf_matches_any_component():
    assert ps.is_white_dwarf("Star; White dwarfs", CONFIG)
    assert not ps.is_white_dwarf("Star; T Tauri stars", CONFIG)
    assert not ps.is_white_dwarf("", CONFIG)


def test_is_pms_veiling_risk_matches_any_component():
    assert ps.is_pms_veiling_risk("ISM; Molecular gas; Pre-main sequence stars; T Tauri stars", CONFIG)
    assert ps.is_pms_veiling_risk("Protostars", CONFIG)
    assert not ps.is_pms_veiling_risk("Star; White dwarfs", CONFIG)


def test_has_mid_ir_coverage():
    assert ps.has_mid_ir_coverage("kurucz")
    assert not ps.has_mid_ir_coverage("phoenix")


def test_discrete_local_search_finds_quadratic_minimum():
    nodes = np.arange(2300.0, 7000.0, 100.0)
    true_min = 4500.0

    def chi2_at(teff):
        return ((teff - true_min) / 200.0) ** 2

    best_teff, chi2_min, cache = ps._discrete_local_search(nodes, chi2_at, start_teff=5000.0)
    assert best_teff == pytest.approx(true_min, abs=50.0)
    # Hill-climb should visit far fewer nodes than a full scan.
    assert len(cache) < len(nodes) / 2


def test_discrete_local_search_converges_regardless_of_start():
    nodes = np.arange(2300.0, 7000.0, 100.0)
    true_min = 3000.0

    def chi2_at(teff):
        return ((teff - true_min) / 150.0) ** 2

    best_teff, _, _ = ps._discrete_local_search(nodes, chi2_at, start_teff=6900.0)
    assert best_teff == pytest.approx(true_min, abs=50.0)


def test_profile_teff_err_discrete_unexplored_neighbor_returns_one_node_step():
    nodes = np.arange(2300.0, 7000.0, 100.0)
    best_teff = 4500.0
    # A cache with only the best node visited (neighbors never evaluated by
    # the local search) -- with no information beyond the best node, the
    # function should not understate the uncertainty by guessing a smaller
    # value; it reports the nearest unexplored node's distance instead.
    best_i = int(np.argmin(np.abs(nodes - best_teff)))
    cache = {best_i: 0.0}
    err = ps._profile_teff_err_discrete(nodes, cache, best_teff, chi2_min=0.0)
    assert err == pytest.approx(100.0)


def test_profile_teff_err_discrete_floors_at_half_node_spacing():
    nodes = np.arange(2300.0, 7000.0, 100.0)
    best_teff = 4500.0
    best_i = int(np.argmin(np.abs(nodes - best_teff)))
    # A very sharp minimum: chi2 already exceeds min+1 at the immediate
    # neighbors, so the delta-chi2=1 crossing (interpolated) falls very
    # close to best_teff on both sides -- the result should still floor at
    # half the node spacing (the grid's own resolution limit) rather than
    # report an implausibly tight error.
    cache = {best_i: 0.0, best_i - 1: 50.0, best_i + 1: 50.0}
    err = ps._profile_teff_err_discrete(nodes, cache, best_teff, chi2_min=0.0)
    assert err == pytest.approx(50.0)
