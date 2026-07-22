"""
tests.test_retriever

STATUS: not yet implemented (Phase 1 scaffold only), except for a
regression test on a real bug found 2026-07-22 (see
RESEARCH_CONTEXT.md): assemble_level_a0's generic per-column
np.asarray(star_table[name]) pass-through leaves _cat.ecsv-derived
bool-valued object columns (e.g. is_extended_{band}) as dtype=object,
which Dataset.to_netcdf cannot always write -- it fails specifically
when every star has a real True/False value (no missing entries to
dilute the column away from a pure-bool resolution). Most tests will be
written alongside the rest of the corresponding pipeline module.
"""

import numpy as np
from astropy.table import Table

from pipeline.retriever import assemble_level_a0

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
