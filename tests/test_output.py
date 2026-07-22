"""
tests.test_output

Fast, network-free unit tests for pipeline.output: SED-figure selection
logic, the actual plot rendering (matplotlib with the Agg backend is a
deterministic, offline operation -- not a live service, so this is tested
directly rather than smoke-tested only) for all three figures (per-star
SED, population excess_sigma scatter, HR diagram), catalogue assembly,
and both LaTeX tables (candidates, flagged-for-review), against small
synthetic a0/b2 datasets.
"""

import numpy as np
import pytest
import xarray as xr
from astropy.io import fits
from astropy.table import Table

from pipeline import output as out

CONFIG = {
    "excess": {"primary_bands": ["F770W", "F1000W"], "significance_threshold_sigma": 3.0},
    "output": {"figures_dir": "figures", "tables_dir": "tables"},
}

CONFIG_NO_THRESHOLD = {
    "excess": {"primary_bands": ["F770W", "F1000W"], "significance_threshold_sigma": None},
    "output": {"figures_dir": "figures", "tables_dir": "tables"},
}


def _dataset(n, **data_vars):
    coords = {"star": np.arange(n)}
    return xr.Dataset(
        data_vars={k: ("star", np.asarray(v)) for k, v in data_vars.items()},
        coords=coords,
    )


def _synthetic_b2(n=4):
    return _dataset(
        n,
        star_id=[1, 2, 3, 4],
        photosphere_teff=[5000.0, 5000.0, np.nan, 5000.0],
        excess_sigma_F770W=[5.0, 1.0, -6.0, np.nan],
        excess_sigma_F1000W=[np.nan, 1.0, np.nan, np.nan],
        observed_flux_F770W=[1.2e-4, 5.0e-5, 3.0e-5, np.nan],
        observed_flux_F770W_err=[2.0e-6, 3.0e-6, 2.0e-6, np.nan],
        observed_flux_F1000W=[np.nan, 4.0e-5, np.nan, np.nan],
        observed_flux_F1000W_err=[np.nan, 2.0e-6, np.nan, np.nan],
        predicted_flux_F770W=[9.0e-5, 4.8e-5, 4.5e-5, np.nan],
        predicted_flux_F770W_err=[1.0e-6, 1.0e-6, 1.0e-6, np.nan],
        predicted_flux_F1000W=[np.nan, 3.9e-5, np.nan, np.nan],
        predicted_flux_F1000W_err=[np.nan, 1.0e-6, np.nan, np.nan],
        qc_candidate_preliminary_refined=[0, 1, 0, 0],
        disqualifying_flags=["", "", "qc_poor_photosphere_fit", "qc_no_photosphere_grid"],
    )


def _synthetic_a0(n=4):
    return _dataset(
        n,
        star_id=[1, 2, 3, 4],
        gaia_parallax=[1.0, 2.0, 3.0, np.nan],
        gaia_parallax_error=[0.1, 0.1, 0.1, np.nan],
        gaia_phot_g_mean_mag=[10.0, 11.0, 12.0, np.nan],
    )


def _synthetic_b2_population(n=5):
    """A richer fixture for the two population-level figures and the two
    LaTeX tables: star 0 is a candidate, star 1 is clean-not-candidate,
    star 2 is disqualified with a notable (|sigma|>=3) signal -- the
    flagged-for-review case, modeled on CONTROLFIELD star index 13 -- star
    3 is missing F1000W's sigma (excluded from the scatter only), star 4
    has no photosphere_teff (excluded from the HR diagram only)."""
    return _dataset(
        n,
        star_id=[1, 2, 3, 4, 5],
        photosphere_teff=[5000.0, 5500.0, 6000.0, 4500.0, np.nan],
        excess_sigma_F770W=[5.0, 1.0, -6.0, 4.0, 2.0],
        excess_sigma_F1000W=[4.0, 0.5, -5.0, np.nan, 1.5],
        qc_candidate_preliminary_refined=[1, 0, 0, 0, 0],
        qc_star_disqualified_refined=[0, 0, 1, 0, 0],
        qc_evolved_star=[0, 1, 0, 0, 0],
        disqualifying_flags=["", "", "qc_poor_photosphere_fit,qc_crowded_source_F770W", "", ""],
    )


def _synthetic_a0_population(n=5):
    return _dataset(
        n,
        star_id=[1, 2, 3, 4, 5],
        gaia_parallax=[1.0, 2.0, 3.0, 4.0, 5.0],
        gaia_parallax_error=[0.05, 0.05, 0.05, 0.05, 0.05],
        gaia_phot_g_mean_mag=[10.0, 6.0, 12.0, 11.0, 13.0],
    )


# --- should_have_sed_figure ----------------------------------------------------


def test_should_have_sed_figure_true_for_candidate():
    b2 = _synthetic_b2()
    selected = out.should_have_sed_figure(b2, CONFIG)
    assert selected[1]  # qc_candidate_preliminary_refined==1


def test_should_have_sed_figure_true_for_high_sigma_regardless_of_disqualification():
    b2 = _synthetic_b2()
    selected = out.should_have_sed_figure(b2, CONFIG)
    # Star 0 (sigma=5.0, not a candidate) and star 2 (sigma=-6.0, disqualified) both selected.
    assert selected[0]
    assert selected[2]


def test_should_have_sed_figure_false_below_threshold_and_not_candidate():
    b2 = _synthetic_b2()
    selected = out.should_have_sed_figure(b2, CONFIG)
    assert not selected[3]


def test_should_have_sed_figure_none_when_threshold_not_set():
    b2 = _synthetic_b2()
    selected = out.should_have_sed_figure(b2, CONFIG_NO_THRESHOLD)
    # Only the explicit preliminary candidate (star 1) should be selected --
    # the sigma-based criterion is inactive without a threshold.
    np.testing.assert_array_equal(selected, [False, True, False, False])


# --- plot_sed (real rendering, Agg backend -- deterministic and offline) ------


def test_plot_sed_writes_a_nonempty_file(tmp_path):
    row = {
        "star_id": 42,
        "photosphere_teff": 5000.0,
        "excess_sigma_F770W": 5.0,
        "excess_sigma_F1000W": np.nan,
        "observed_flux_F770W": 1.2e-4,
        "observed_flux_F770W_err": 2.0e-6,
        "observed_flux_F1000W": np.nan,
        "observed_flux_F1000W_err": np.nan,
        "predicted_flux_F770W": 9.0e-5,
        "predicted_flux_F770W_err": 1.0e-6,
        "predicted_flux_F1000W": np.nan,
        "predicted_flux_F1000W_err": np.nan,
        "disqualifying_flags": "",
    }
    out_path = tmp_path / "sed_42.png"
    out.plot_sed(row, ["F770W", "F1000W"], out_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_sed_handles_single_band_star(tmp_path):
    # qc_single_filter_detection-style star: F1000W entirely absent. Must
    # not raise -- the band is simply omitted from the plot.
    row = {
        "star_id": 7,
        "photosphere_teff": np.nan,
        "excess_sigma_F770W": 3.5,
        "excess_sigma_F1000W": np.nan,
        "observed_flux_F770W": 5.0e-5,
        "observed_flux_F770W_err": 1.0e-6,
        "observed_flux_F1000W": np.nan,
        "observed_flux_F1000W_err": np.nan,
        "predicted_flux_F770W": 4.0e-5,
        "predicted_flux_F770W_err": 1.0e-6,
        "predicted_flux_F1000W": np.nan,
        "predicted_flux_F1000W_err": np.nan,
        "disqualifying_flags": "",
    }
    out_path = tmp_path / "sed_7.png"
    out.plot_sed(row, ["F770W", "F1000W"], out_path)
    assert out_path.exists()


# --- generate_sed_figures -------------------------------------------------------


def test_generate_sed_figures_writes_one_file_per_selected_star(tmp_path):
    a0 = _synthetic_a0()
    b2 = _synthetic_b2()
    figures_dir = tmp_path / "figures"
    has_figure = out.generate_sed_figures(a0, b2, CONFIG, figures_dir)
    # Stars 0, 1, 2 selected (see should_have_sed_figure tests); star 3 not.
    np.testing.assert_array_equal(has_figure, [True, True, True, False])
    for star_id in [1, 2, 3]:
        assert (figures_dir / f"sed_{star_id}.png").exists()
    assert not (figures_dir / "sed_4.png").exists()


def test_generate_sed_figures_raises_on_misaligned_input(tmp_path):
    a0 = _synthetic_a0()
    b2 = _synthetic_b2()
    b2["star_id"].values[:] = [1, 2, 99, 4]
    with pytest.raises(AssertionError):
        out.generate_sed_figures(a0, b2, CONFIG, tmp_path / "figures")


# --- assemble_catalogue / save_catalogue ---------------------------------------


def test_assemble_catalogue_includes_extra_a0_columns_and_has_sed_figure():
    a0 = _synthetic_a0()
    b2 = _synthetic_b2()
    has_figure = np.array([True, True, True, False])
    table = out.assemble_catalogue(a0, b2, CONFIG, has_figure)
    for col in out.EXTRA_A0_COLUMNS:
        assert col in table.colnames
    assert "has_sed_figure" in table.colnames
    np.testing.assert_array_equal(table["has_sed_figure"], [1, 1, 1, 0])
    np.testing.assert_array_equal(table["gaia_parallax"], a0["gaia_parallax"].values)


def test_assemble_catalogue_keeps_full_population_not_just_candidates():
    a0 = _synthetic_a0()
    b2 = _synthetic_b2()
    table = out.assemble_catalogue(a0, b2, CONFIG, np.zeros(4, dtype=bool))
    assert len(table) == 4


def test_assemble_catalogue_raises_on_misaligned_input():
    a0 = _synthetic_a0()
    b2 = _synthetic_b2()
    b2["star_id"].values[:] = [1, 2, 99, 4]
    with pytest.raises(AssertionError):
        out.assemble_catalogue(a0, b2, CONFIG, np.zeros(4, dtype=bool))


def test_save_catalogue_round_trips_through_fits(tmp_path):
    a0 = _synthetic_a0()
    b2 = _synthetic_b2()
    table = out.assemble_catalogue(a0, b2, CONFIG, np.array([True, True, True, False]))
    path = tmp_path / "catalogue.fits"
    out.save_catalogue(table, path)

    reloaded = Table.read(path, format="fits")
    assert len(reloaded) == 4
    assert set(table.colnames) == set(reloaded.colnames)
    # disqualifying_flags (a string column) must not be corrupted/truncated.
    np.testing.assert_array_equal(
        [str(v) for v in reloaded["disqualifying_flags"]],
        ["(none)", "(none)", "qc_poor_photosphere_fit", "qc_no_photosphere_grid"],
    )


def test_assemble_catalogue_replaces_empty_strings_to_avoid_fits_masking():
    # Regression test for a real bug found 2026-07-22: astropy's FITS
    # writer round-trips an empty string as a MASKED value, not a real
    # empty string -- making "clean" and "genuinely unknown" indistinguishable.
    a0 = _synthetic_a0()
    b2 = _synthetic_b2()
    table = out.assemble_catalogue(a0, b2, CONFIG, np.zeros(4, dtype=bool))
    assert "" not in list(table["disqualifying_flags"])
    assert table["disqualifying_flags"][0] == "(none)"


def test_save_catalogue_writes_preliminary_caveat_comment(tmp_path):
    a0 = _synthetic_a0()
    b2 = _synthetic_b2()
    table = out.assemble_catalogue(a0, b2, CONFIG, np.zeros(4, dtype=bool))
    path = tmp_path / "catalogue.fits"
    out.save_catalogue(table, path)

    with fits.open(path) as hdul:
        comment = str(hdul[1].header["COMMENT"])
    assert "qc_candidate_preliminary_refined" in comment
    assert "NOT the final qc_anomalous_excess" in comment


# --- plot_excess_sigma_scatter --------------------------------------------------


def test_plot_excess_sigma_scatter_writes_a_nonempty_file(tmp_path):
    b2 = _synthetic_b2_population()
    out_path = tmp_path / "scatter.png"
    out.plot_excess_sigma_scatter(b2, CONFIG, out_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_excess_sigma_scatter_raises_for_wrong_band_count(tmp_path):
    b2 = _synthetic_b2_population()
    bad_config = {**CONFIG, "excess": {**CONFIG["excess"], "primary_bands": ["F770W"]}}
    with pytest.raises(ValueError):
        out.plot_excess_sigma_scatter(b2, bad_config, tmp_path / "scatter.png")


def test_plot_excess_sigma_scatter_handles_all_stars_missing_a_band(tmp_path):
    # Degenerate case: every star missing one band's sigma -- must not
    # crash, just produce an (empty-of-points) figure.
    b2 = _dataset(
        2,
        star_id=[1, 2],
        excess_sigma_F770W=[5.0, 1.0],
        excess_sigma_F1000W=[np.nan, np.nan],
        qc_candidate_preliminary_refined=[0, 0],
        qc_star_disqualified_refined=[0, 0],
    )
    out_path = tmp_path / "scatter.png"
    out.plot_excess_sigma_scatter(b2, CONFIG, out_path)
    assert out_path.exists()


# --- plot_hr_diagram -------------------------------------------------------------


def test_plot_hr_diagram_writes_a_nonempty_file(tmp_path):
    a0 = _synthetic_a0_population()
    b2 = _synthetic_b2_population()
    out_path = tmp_path / "hr_diagram.png"
    out.plot_hr_diagram(a0, b2, CONFIG, out_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_plot_hr_diagram_raises_on_misaligned_input(tmp_path):
    a0 = _synthetic_a0_population()
    b2 = _synthetic_b2_population()
    b2["star_id"].values[:] = [1, 2, 3, 4, 99]
    with pytest.raises(AssertionError):
        out.plot_hr_diagram(a0, b2, CONFIG, tmp_path / "hr_diagram.png")


def test_plot_hr_diagram_handles_all_stars_missing_teff(tmp_path):
    a0 = _synthetic_a0_population()
    b2 = _synthetic_b2_population()
    b2["photosphere_teff"].values[:] = np.nan
    out_path = tmp_path / "hr_diagram.png"
    out.plot_hr_diagram(a0, b2, CONFIG, out_path)
    assert out_path.exists()


# --- select_candidate_rows / select_flagged_for_review_rows ---------------------


def test_select_candidate_rows_only_true_candidate():
    b2 = _synthetic_b2_population()
    np.testing.assert_array_equal(
        out.select_candidate_rows(b2), [True, False, False, False, False]
    )


def test_select_flagged_for_review_rows_matches_star13_style_case():
    # Star 2: disqualified, notable |sigma|>=3 in both bands, not a
    # candidate -- the general form of the CONTROLFIELD star index 13 case.
    b2 = _synthetic_b2_population()
    np.testing.assert_array_equal(
        out.select_flagged_for_review_rows(b2, CONFIG), [False, False, True, False, False]
    )


def test_select_flagged_for_review_rows_excludes_candidates():
    # A star that is both disqualified-looking-notable AND a preliminary
    # candidate must appear only in the candidate table, not this one.
    b2 = _synthetic_b2_population()
    b2["qc_candidate_preliminary_refined"].values[2] = 1
    assert not out.select_flagged_for_review_rows(b2, CONFIG)[2]


# --- LaTeX tables -----------------------------------------------------------------


def test_write_candidate_table_degrades_to_placeholder_when_empty(tmp_path):
    # Real 2026-07-22 test data: zero qc_candidate_preliminary_refined
    # hits across all three fields -- this is the exercised, not just
    # theoretical, code path.
    b2 = _synthetic_b2_population()
    b2["qc_candidate_preliminary_refined"].values[:] = 0
    out_path = tmp_path / "candidates.tex"
    out.write_candidate_table(b2, CONFIG, out_path)
    text = out_path.read_text()
    assert "No candidates in this sample." in text
    assert "\\multicolumn" in text


def test_write_candidate_table_includes_real_candidate_row(tmp_path):
    b2 = _synthetic_b2_population()
    out_path = tmp_path / "candidates.tex"
    out.write_candidate_table(b2, CONFIG, out_path)
    text = out_path.read_text()
    assert "No candidates" not in text
    assert " 1 &" in text or "1 &" in text  # star_id=1 is the candidate


def test_write_flagged_for_review_table_includes_star13_style_row_with_flags_visible(tmp_path):
    b2 = _synthetic_b2_population()
    out_path = tmp_path / "flagged_for_review.tex"
    out.write_flagged_for_review_table(b2, CONFIG, out_path)
    text = out_path.read_text()
    assert "No stars flagged" not in text
    assert "3 &" in text  # star_id=3 is the flagged-for-review case
    # Underscore must be escaped, not left as a raw LaTeX special character.
    assert "qc\\_poor\\_photosphere\\_fit" in text
    assert "qc_poor_photosphere_fit" not in text


def test_write_flagged_for_review_table_degrades_to_placeholder_when_empty(tmp_path):
    b2 = _synthetic_b2_population()
    b2["qc_star_disqualified_refined"].values[:] = 0
    out_path = tmp_path / "flagged_for_review.tex"
    out.write_flagged_for_review_table(b2, CONFIG, out_path)
    text = out_path.read_text()
    assert "No stars flagged for individual review in this sample." in text


def test_write_star_table_output_is_valid_latex_table_environment(tmp_path):
    b2 = _synthetic_b2_population()
    out_path = tmp_path / "candidates.tex"
    out.write_candidate_table(b2, CONFIG, out_path)
    text = out_path.read_text()
    assert text.count("\\begin{table}") == 1
    assert text.count("\\end{table}") == 1
    assert text.count("\\begin{tabular}") == 1
    assert text.count("\\end{tabular}") == 1
    assert "\\caption{" in text
    assert "\\label{tab:candidates}" in text
