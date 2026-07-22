"""
pipeline.output

Stage 5 (terminal) of the jwst-ir-excess pipeline (see RESEARCH_CONTEXT.md
for the 5-stage architecture): joins a0 onto contaminants.py's b2 output
and produces the actual, user/paper-facing artifacts -- a FITS catalogue,
per-star diagnostic figures, and two LaTeX tables. Does not produce a new
intermediate xarray Dataset for further pipeline stages -- this is the
end of the chain.

STATUS: complete. FITS catalogue, all three planned figures (per-star SED
diagnostic plot, population excess_sigma scatter, HR diagram), and both
LaTeX tables (candidates, flagged-for-review) are implemented and
verified against real data for all three test fields.

- write_candidate_table/write_flagged_for_review_table are two separate
  tables, not one, per the researcher's explicit design call
  (2026-07-22): a true qc_candidate_preliminary_refined hit and a
  disqualified-but-notable-signal case (e.g. CONTROLFIELD star index 13)
  are not the same kind of claim, and collapsing them into one table
  with a status column would blur that distinction right where a reader
  is most likely to skim. Both share _write_star_table's rendering logic
  (same columns, same escaping, same empty-table placeholder-row
  behavior) so the two tables can't drift apart in format, only in which
  rows they select.
- Both tables degrade to an explicit multicolumn placeholder row (not a
  missing or empty file) when their selection picks nobody -- verified
  live against all three current test fields, all of which have zero
  qc_candidate_preliminary_refined hits, so write_candidate_table's
  placeholder path is exercised by real data today, not just a
  theoretical branch.
- LaTeX escaping is deliberately narrow: only underscore is escaped
  (_escape_latex), because qc_* flag names and disqualifying_flags are
  the only free-text-ish content in these tables and both are strictly
  snake_case -- no other LaTeX special characters can occur in this
  pipeline's own generated strings.

Key design decisions -- see RESEARCH_CONTEXT.md Decision Log (2026-07-22
entries) for the full discussion:

- Inputs are just a0 and b2 -- b2 already carries forward everything from
  a1/miri_photometry/b1 (79 columns in real test data), so output.py
  doesn't touch those intermediate files directly, same "join identity +
  latest stage" pattern excess.py and contaminants.py both already use.
  Three a0 columns NOT otherwise carried through anywhere
  (gaia_parallax, gaia_parallax_error, gaia_phot_g_mean_mag -- the direct
  inputs to qc_evolved_star's own math) are pulled in explicitly, so a
  downloaded catalogue is self-explanatory without reopening a0.
- qc_candidate_preliminary_refined is kept as the literal FITS/table
  column name, NOT shortened to something friendlier (researcher's
  explicit decision, 2026-07-22): the "preliminary"/"refined" qualifiers
  are the load-bearing part of the name, not verbosity, for a project
  whose stated Scientific Claim is deliberately modest. A shorter public
  alias would risk exactly the overclaiming this project has avoided
  everywhere else (qc_stopgap_* naming, the significance-threshold
  framing, qc_contaminant_flagged_partial's own name). The FITS header
  COMMENT (see save_catalogue) states plainly that this is NOT the final
  qc_anomalous_excess, so the caveat travels with the file even for a
  reader who only looks at the header, not just column names.
- should_have_sed_figure selects a star for an individual diagnostic plot
  if EITHER it's a preliminary candidate OR its raw excess_sigma_{band}
  (either band, NOT gated by qc_excess_clean) clears
  excess.significance_threshold_sigma in magnitude -- so a case like
  CONTROLFIELD star index 13 (real, ~100-sigma signal, disqualified for
  reasons unrelated to whether the signal itself is real) still gets a
  plot. The whole point of this figure is surfacing interesting cases
  regardless of automated disqualification, matching this project's
  Carrigan/Griffith-derived "cut wide, then vet every survivor by hand"
  philosophy.
- has_sed_figure is computed ONCE (by should_have_sed_figure) and reused
  for both the actual plotting loop and the catalogue column, so the
  catalogue's own has_sed_figure column is guaranteed consistent with what
  files actually exist in results/figures/ -- not two independently-
  computed values that could silently drift apart (researcher's request,
  2026-07-22: something in the catalogue itself, not just a log line, so
  someone browsing figures/ isn't left guessing why some stars have a plot
  and others don't).
- Join mechanics/alignment: reuses pipeline.contaminants.assert_star_aligned
  directly (a0 vs. a later stage's star_id arrays) rather than
  reimplementing the same check a third time -- this is the one place in
  this pipeline's output-stage code that imports a check function rather
  than duplicating a couple of lines, since the check itself is more than
  a couple of lines and is already exercised by contaminants.py's own
  tests.
- Both new figures are scoped per-field, same as the SED plots and every
  other stage in this pipeline -- one PNG per run() call, not an
  aggregation across multiple fields' b2 files (which would need a
  different orchestration signature that wasn't asked for).
- plot_excess_sigma_scatter marks each star by a star-level status
  (qc_candidate_preliminary_refined / qc_star_disqualified_refined), not
  a per-band breakdown -- the axes themselves already show both bands'
  sigma explicitly, so encoding per-band disqualification in color too
  would be redundant with what the point's own position already conveys.
  Reference lines at +-significance_threshold_sigma make "how far into
  candidate territory" visually explicit. Stars missing either band's
  sigma (single-filter-detection, or a fully NaN case) cannot be placed on
  a 2D scatter and are silently excluded from this figure specifically
  (not from the catalogue) -- the function logs how many were excluded so
  this isn't a silent gap.
- plot_hr_diagram reuses pipeline.contaminants.absolute_g_mag/
  expected_ms_abs_g directly rather than reimplementing the same math a
  third time -- the overlaid main-sequence reference curve is the exact
  same (approximate, Pecaut & Mamajek-like, not independently re-verified)
  relation qc_evolved_star's own disqualifying logic uses, so the figure
  visually explains the mechanism rather than approximating it separately.
  Standard HR-diagram axis convention (both axes inverted: hot/left,
  bright/top). Stars missing Teff or a usable absolute magnitude
  (no/untrustworthy parallax) are excluded from this figure the same way,
  with the same "log the exclusion count" discipline.
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from astropy.table import Table

from pipeline import __version__
from pipeline.contaminants import assert_star_aligned

logger = logging.getLogger(__name__)

# Nominal MIRI filter pivot wavelengths, for plotting only -- not intended
# as precision values for any scientific calculation elsewhere in this
# pipeline (predict_miri_flux/observed flux extraction use the real
# bandpass transmission curves, not these single numbers).
MIRI_BAND_WAVELENGTH_UM = {
    "F770W": 7.7,
    "F1000W": 10.0,
}

# a0 columns not otherwise carried through b1/b2, needed for the catalogue
# to be self-explanatory (these are the direct inputs to
# contaminants.py's is_evolved_star_overluminous) without reopening a0.
EXTRA_A0_COLUMNS = ("gaia_parallax", "gaia_parallax_error", "gaia_phot_g_mean_mag")


# --- SED diagnostic plot selection --------------------------------------------


def _notable_by_raw_sigma(b2_ds: xr.Dataset, config: dict) -> np.ndarray:
    """Boolean, per-star: True if raw excess_sigma_{band} (NOT gated by
    qc_excess_clean) clears excess.significance_threshold_sigma in
    magnitude in either configured band. Factored out of
    should_have_sed_figure so select_flagged_for_review_rows uses the
    exact same "is this star's signal notable" check rather than a second,
    independently-maintained copy that could silently drift from it."""
    bands = config["excess"]["primary_bands"]
    threshold = config["excess"].get("significance_threshold_sigma")
    n = b2_ds.sizes["star"]

    notable = np.zeros(n, dtype=bool)
    if threshold is not None:
        for band in bands:
            col = f"excess_sigma_{band}"
            if col in b2_ds:
                sigma = b2_ds[col].values
                notable |= np.isfinite(sigma) & (np.abs(sigma) >= threshold)
    return notable


def should_have_sed_figure(b2_ds: xr.Dataset, config: dict) -> np.ndarray:
    """Boolean, per-star: True if this star should get an individual SED
    diagnostic plot -- either it's a preliminary candidate
    (qc_candidate_preliminary_refined), or its raw excess_sigma_{band} (NOT
    gated by qc_excess_clean) clears
    excess.significance_threshold_sigma in magnitude in either configured
    band. See module docstring for why disqualification status is
    deliberately ignored here."""
    n = b2_ds.sizes["star"]
    notable = _notable_by_raw_sigma(b2_ds, config)
    candidate = (
        b2_ds["qc_candidate_preliminary_refined"].values.astype(bool)
        if "qc_candidate_preliminary_refined" in b2_ds
        else np.zeros(n, dtype=bool)
    )
    return notable | candidate


# --- SED diagnostic plot rendering --------------------------------------------


def plot_sed(row: dict, bands: list[str], output_path: Path) -> None:
    """Renders one star's observed-vs-predicted flux SED (both configured
    MIRI bands) to a PNG, with error bars, self-annotated (star_id, fitted
    Teff, per-band sigma, disqualifying_flags) so the image is
    interpretable without re-opening the catalogue -- the core diagnostic
    figure for this project's manual-vetting workflow. A band with no
    finite observed/predicted value is simply omitted from that series,
    not treated as an error (e.g. qc_single_filter_detection stars only
    ever have one band's worth of points)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    wavelengths = np.array([MIRI_BAND_WAVELENGTH_UM[b] for b in bands])
    observed = np.array([row.get(f"observed_flux_{b}", np.nan) for b in bands], dtype=float)
    observed_err = np.array([row.get(f"observed_flux_{b}_err", np.nan) for b in bands], dtype=float)
    predicted = np.array([row.get(f"predicted_flux_{b}", np.nan) for b in bands], dtype=float)
    predicted_err = np.array([row.get(f"predicted_flux_{b}_err", np.nan) for b in bands], dtype=float)

    obs_mask = np.isfinite(observed)
    pred_mask = np.isfinite(predicted)

    fig, ax = plt.subplots(figsize=(6, 5))
    if np.any(pred_mask):
        ax.errorbar(
            wavelengths[pred_mask],
            predicted[pred_mask],
            yerr=np.nan_to_num(predicted_err[pred_mask]),
            fmt="s--",
            color="tab:blue",
            label="Predicted (photosphere)",
            capsize=3,
        )
    if np.any(obs_mask):
        ax.errorbar(
            wavelengths[obs_mask],
            observed[obs_mask],
            yerr=np.nan_to_num(observed_err[obs_mask]),
            fmt="o-",
            color="tab:red",
            label="Observed (MIRI)",
            capsize=3,
        )
    ax.set_xlabel("Wavelength (micron)")
    ax.set_ylabel("Flux density (Jy)")
    ax.set_yscale("log")

    teff = row.get("photosphere_teff", np.nan)
    sigma_parts = [
        f"{b} sigma={row[f'excess_sigma_{b}']:.2f}"
        for b in bands
        if np.isfinite(row.get(f"excess_sigma_{b}", np.nan))
    ]
    title = f"star_id={row.get('star_id')}"
    if np.isfinite(teff):
        title += f"   Teff={teff:.0f} K"
    if sigma_parts:
        title += "\n" + ", ".join(sigma_parts)
    ax.set_title(title, fontsize=9)

    flags = row.get("disqualifying_flags", "") or "(none -- clean per current qc_* flags)"
    # matplotlib's own wrap=True was tried first and found (2026-07-22, real
    # data: CONTROLFIELD star index 13's genuinely long flag list) to run
    # text past the figure edge rather than actually wrapping it -- fixed
    # by wrapping explicitly with textwrap before handing matplotlib a
    # string it can't be trusted to break correctly on its own.
    # ", ".join (not plain ",") so textwrap has real whitespace to break on
    # -- without it, a long flags string is one unbroken "word" and
    # textwrap's break_long_words falls back to splitting mid-flag-name.
    caption_text = f"disqualifying_flags: {flags}".replace(",", ", ")
    caption_lines = textwrap.wrap(caption_text, width=70)
    fig.text(0.5, 0.01, "\n".join(caption_lines), ha="center", va="bottom", fontsize=7)

    ax.legend(fontsize=8)
    bottom_margin = 0.04 + 0.02 * len(caption_lines)
    fig.tight_layout(rect=(0, bottom_margin, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def generate_sed_figures(a0_ds: xr.Dataset, b2_ds: xr.Dataset, config: dict, figures_dir: Path) -> np.ndarray:
    """Generates one sed_{star_id}.png per star selected by
    should_have_sed_figure. Returns the has_sed_figure boolean array (same
    selection used for the catalogue column, see module docstring)."""
    assert_star_aligned(a0_ds, b2_ds)
    bands = config["excess"]["primary_bands"]
    selected = should_have_sed_figure(b2_ds, config)
    star_ids = b2_ds["star_id"].values
    indices = np.flatnonzero(selected)

    for count, i in enumerate(indices, start=1):
        row = {name: b2_ds[name].values[i] for name in b2_ds.data_vars}
        row["star_id"] = star_ids[i]
        out_path = figures_dir / f"sed_{star_ids[i]}.png"
        plot_sed(row, bands, out_path)
        logger.info("Wrote SED figure %d/%d: %s", count, len(indices), out_path)

    logger.info("Generated %d SED figures (of %d stars)", len(indices), b2_ds.sizes["star"])
    return selected


# --- Population excess_sigma scatter -------------------------------------------


def plot_excess_sigma_scatter(b2_ds: xr.Dataset, config: dict, output_path: Path) -> None:
    """Renders a population-level excess_sigma_{band0} vs. excess_sigma_{band1}
    scatter (both configured bands; this project currently always has
    exactly two -- F770W/F1000W), star-level status marked by colour/marker
    (see module docstring for why status is star-level, not per-band).
    Stars missing either band's sigma cannot be placed on a 2D scatter and
    are excluded from THIS figure specifically (not from the catalogue) --
    the exclusion count is logged, not silent."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bands = config["excess"]["primary_bands"]
    if len(bands) != 2:
        raise ValueError(
            f"plot_excess_sigma_scatter needs exactly 2 configured bands, got {bands!r}"
        )
    band_x, band_y = bands
    sigma_x = b2_ds[f"excess_sigma_{band_x}"].values
    sigma_y = b2_ds[f"excess_sigma_{band_y}"].values
    n = b2_ds.sizes["star"]

    plottable = np.isfinite(sigma_x) & np.isfinite(sigma_y)
    excluded = n - int(plottable.sum())
    if excluded:
        logger.info(
            "plot_excess_sigma_scatter: excluding %d/%d stars missing a finite sigma in "
            "both %s and %s (e.g. single-filter-detection stars)",
            excluded,
            n,
            band_x,
            band_y,
        )

    candidate = (
        b2_ds["qc_candidate_preliminary_refined"].values.astype(bool)
        if "qc_candidate_preliminary_refined" in b2_ds
        else np.zeros(n, dtype=bool)
    )
    disqualified = (
        b2_ds["qc_star_disqualified_refined"].values.astype(bool)
        if "qc_star_disqualified_refined" in b2_ds
        else np.zeros(n, dtype=bool)
    )
    clean_not_candidate = plottable & ~candidate & ~disqualified
    disqualified_mask = plottable & disqualified & ~candidate
    candidate_mask = plottable & candidate

    fig, ax = plt.subplots(figsize=(6, 6))
    threshold = config["excess"].get("significance_threshold_sigma")
    if threshold is not None:
        ax.axvline(threshold, color="gray", linestyle=":", linewidth=1)
        ax.axvline(-threshold, color="gray", linestyle=":", linewidth=1)
        ax.axhline(threshold, color="gray", linestyle=":", linewidth=1)
        ax.axhline(-threshold, color="gray", linestyle=":", linewidth=1)

    ax.scatter(
        sigma_x[disqualified_mask],
        sigma_y[disqualified_mask],
        marker="x",
        s=20,
        color="lightgray",
        label=f"disqualified (n={int(disqualified_mask.sum())})",
        zorder=1,
    )
    ax.scatter(
        sigma_x[clean_not_candidate],
        sigma_y[clean_not_candidate],
        marker="o",
        s=25,
        color="tab:blue",
        label=f"clean, not a candidate (n={int(clean_not_candidate.sum())})",
        zorder=2,
    )
    ax.scatter(
        sigma_x[candidate_mask],
        sigma_y[candidate_mask],
        marker="*",
        s=140,
        color="gold",
        edgecolor="black",
        linewidth=0.5,
        label=f"qc_candidate_preliminary_refined (n={int(candidate_mask.sum())})",
        zorder=3,
    )

    # symlog, not linear: real test data spans excess_sigma from roughly
    # -70 to ~977 (2026-07-22, CONTROLFIELD) -- on a linear scale the
    # handful of extreme outliers squash the entire rest of the population
    # into a single unreadable point at the origin, and the
    # +-significance_threshold_sigma reference lines become invisible.
    # symlog keeps a linear region near zero (where the threshold lines and
    # the bulk of modest-sigma stars live) while still showing the extreme
    # tail. linthresh matches the significance threshold itself where set,
    # so "inside vs. outside the triage cut" stays visually meaningful.
    linthresh = threshold if threshold is not None else 1.0
    ax.set_xscale("symlog", linthresh=linthresh)
    ax.set_yscale("symlog", linthresh=linthresh)

    ax.set_xlabel(f"excess_sigma_{band_x}")
    ax.set_ylabel(f"excess_sigma_{band_y}")
    ax.legend(fontsize=7, loc="best")
    ax.set_title(
        f"Excess significance ({excluded} of {n} stars excluded -- missing a band)", fontsize=9
    )
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


# --- HR diagram -----------------------------------------------------------------


def plot_hr_diagram(a0_ds: xr.Dataset, b2_ds: xr.Dataset, config: dict, output_path: Path) -> None:
    """Renders an HR diagram (photosphere_teff vs. Gaia-parallax-based
    absolute G magnitude, standard inverted axes), qc_evolved_star
    highlighted, with the same expected main-sequence relation that flag's
    own logic uses overlaid as a reference curve. See module docstring."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from pipeline.contaminants import absolute_g_mag, expected_ms_abs_g

    assert_star_aligned(a0_ds, b2_ds)
    teff = b2_ds["photosphere_teff"].values
    phot_g = a0_ds["gaia_phot_g_mean_mag"].values
    parallax = a0_ds["gaia_parallax"].values
    n = b2_ds.sizes["star"]

    abs_g = np.array([absolute_g_mag(g, p) for g, p in zip(phot_g, parallax)])
    plottable = np.isfinite(teff) & np.isfinite(abs_g)
    excluded = n - int(plottable.sum())
    if excluded:
        logger.info(
            "plot_hr_diagram: excluding %d/%d stars missing photosphere_teff or a usable "
            "(trustworthy-parallax-based) absolute G magnitude",
            excluded,
            n,
        )

    evolved = (
        b2_ds["qc_evolved_star"].values.astype(bool)
        if "qc_evolved_star" in b2_ds
        else np.zeros(n, dtype=bool)
    )
    evolved_mask = plottable & evolved
    other_mask = plottable & ~evolved

    fig, ax = plt.subplots(figsize=(6, 6))
    # Fixed, generously-wide range (not read from contaminants.py's own
    # anchor table directly -- expected_ms_abs_g already clips at its own
    # table boundaries, so extending past them just repeats the boundary
    # value harmlessly, without this module reaching into another
    # module's private constant).
    ms_teff = np.geomspace(2000, 45000, 200)
    ms_abs_g = [expected_ms_abs_g(t) for t in ms_teff]
    ax.plot(ms_teff, ms_abs_g, color="gray", linestyle="--", linewidth=1, label="Expected main sequence")

    ax.scatter(
        teff[other_mask],
        abs_g[other_mask],
        marker="o",
        s=25,
        color="tab:blue",
        label=f"other (n={int(other_mask.sum())})",
        zorder=2,
    )
    ax.scatter(
        teff[evolved_mask],
        abs_g[evolved_mask],
        marker="*",
        s=140,
        color="tab:red",
        edgecolor="black",
        linewidth=0.5,
        label=f"qc_evolved_star (n={int(evolved_mask.sum())})",
        zorder=3,
    )

    ax.set_xlabel("photosphere_teff (K)")
    ax.set_ylabel("Absolute G magnitude")
    ax.invert_xaxis()
    ax.invert_yaxis()
    ax.legend(fontsize=7, loc="best")
    ax.set_title(f"HR diagram ({excluded} of {n} stars excluded -- no Teff/usable parallax)", fontsize=9)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


# --- LaTeX tables -----------------------------------------------------------------


def select_candidate_rows(b2_ds: xr.Dataset) -> np.ndarray:
    """Boolean, per-star: qc_candidate_preliminary_refined. Selection logic
    for the primary candidate table."""
    n = b2_ds.sizes["star"]
    if "qc_candidate_preliminary_refined" not in b2_ds:
        return np.zeros(n, dtype=bool)
    return b2_ds["qc_candidate_preliminary_refined"].values.astype(bool)


def select_flagged_for_review_rows(b2_ds: xr.Dataset, config: dict) -> np.ndarray:
    """Boolean, per-star: selection for the secondary "flagged for
    individual review" table -- stars with a notable raw excess_sigma
    (the same _notable_by_raw_sigma check should_have_sed_figure uses)
    that were disqualified by qc_star_disqualified_refined, and are NOT
    already a preliminary candidate (those belong in the candidate table,
    not this one). This is the concrete, general-purpose version of what
    the CONTROLFIELD star index 13 walkthrough did by hand: a real-looking
    signal explained away (correctly or not) by an automated qc flag,
    surfaced here instead of silently disappearing once disqualified."""
    n = b2_ds.sizes["star"]
    notable = _notable_by_raw_sigma(b2_ds, config)
    candidate = select_candidate_rows(b2_ds)
    disqualified = (
        b2_ds["qc_star_disqualified_refined"].values.astype(bool)
        if "qc_star_disqualified_refined" in b2_ds
        else np.zeros(n, dtype=bool)
    )
    return notable & disqualified & ~candidate


def _format_sigma(value: float) -> str:
    return f"{value:.2f}" if np.isfinite(value) else "--"


def _format_teff(value: float) -> str:
    return f"{value:.0f}" if np.isfinite(value) else "--"


def _escape_latex(text: str) -> str:
    """Escapes the one special character this project's own identifiers
    actually contain -- qc_* flag names and disqualifying_flags are all
    snake_case, so underscore is the only LaTeX special character that
    can realistically appear in this pipeline's own strings."""
    return text.replace("_", r"\_")


def _write_star_table(
    b2_ds: xr.Dataset,
    config: dict,
    mask: np.ndarray,
    output_path: Path,
    caption: str,
    label: str,
    empty_message: str,
) -> None:
    """Shared LaTeX-writing logic for both the candidate table and the
    flagged-for-review table: one row per star selected by `mask`, columns
    star_id / photosphere_teff / excess_sigma_{band} per configured band /
    disqualifying_flags. Degrades explicitly to a single multicolumn
    placeholder row reading `empty_message` when `mask` selects nobody --
    a real, visible row in the compiled table, not a missing/empty file a
    reader could mistake for a bug."""
    bands = config["excess"]["primary_bands"]
    star_ids = b2_ds["star_id"].values
    teff = b2_ds["photosphere_teff"].values
    flags = b2_ds["disqualifying_flags"].values if "disqualifying_flags" in b2_ds else None
    sigma_by_band = {
        band: b2_ds[f"excess_sigma_{band}"].values for band in bands if f"excess_sigma_{band}" in b2_ds
    }

    header_cols = ["star\\_id", "Teff (K)"] + [f"{band} $\\sigma$" for band in bands] + ["disqualifying\\_flags"]
    n_cols = len(header_cols)
    # The last column (disqualifying_flags) is the one column with
    # unbounded-length free text -- a plain "l" column does not wrap and
    # was found (2026-07-22, real CONTROLFIELD data: star index 13's own
    # multi-flag row) to run straight off the compiled page edge. p{}
    # wraps within the tabular environment itself, no extra LaTeX package
    # needed.
    col_spec = "l" * (n_cols - 1) + "p{5.5cm}"

    lines = [
        "\\begin{table}",
        "\\centering",
        "\\begin{tabular}{" + col_spec + "}",
        "\\hline",
        " & ".join(header_cols) + " \\\\",
        "\\hline",
    ]

    indices = np.flatnonzero(mask)
    if len(indices) == 0:
        lines.append(f"\\multicolumn{{{n_cols}}}{{c}}{{{_escape_latex(empty_message)}}} \\\\")
    else:
        for i in indices:
            row_cells = [str(star_ids[i]), _format_teff(teff[i])]
            for band in bands:
                sigma = sigma_by_band[band][i] if band in sigma_by_band else np.nan
                row_cells.append(_format_sigma(sigma))
            flag_str = flags[i] if flags is not None and flags[i] else "(none)"
            # ", " (not plain ",") gives a p{}-column paragraph real
            # whitespace break points -- without it, a long flags string
            # is one unbroken "word" and LaTeX cannot wrap it at all,
            # same underlying fix as plot_sed's caption wrapping.
            lines_flag_str = str(flag_str).replace(",", ", ")
            row_cells.append(_escape_latex(lines_flag_str))
            lines.append(" & ".join(row_cells) + " \\\\")

    lines += [
        "\\hline",
        "\\end{tabular}",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        "\\end{table}",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")
    logger.info("Wrote LaTeX table (%d rows) to %s", len(indices), output_path)


def write_candidate_table(b2_ds: xr.Dataset, config: dict, output_path: Path) -> None:
    """Writes the primary LaTeX candidate table: one row per
    qc_candidate_preliminary_refined star. Real 2026-07-22 test data has
    zero candidates across all three fields, so this degrades to the
    "No candidates in this sample." placeholder row for every field
    currently run -- see _write_star_table."""
    mask = select_candidate_rows(b2_ds)
    _write_star_table(
        b2_ds,
        config,
        mask,
        output_path,
        caption="Preliminary infrared-excess candidates (qc\\_candidate\\_preliminary\\_refined). "
        "This is a triage-level flag, not a confirmed detection -- see the accompanying text.",
        label="tab:candidates",
        empty_message="No candidates in this sample.",
    )


def write_flagged_for_review_table(b2_ds: xr.Dataset, config: dict, output_path: Path) -> None:
    """Writes the secondary LaTeX table: stars disqualified by an
    automated qc flag whose raw excess_sigma is still notable in either
    configured band, e.g. CONTROLFIELD star index 13 (Gaia
    5258785479377301248, ~109/94 sigma, disqualified for
    qc_poor_photosphere_fit/qc_rj_extrapolated/qc_stopgap_young_cluster/
    qc_crowded_source_{band} -- see the dedicated walkthrough in
    RESEARCH_CONTEXT.md). These are not candidates and are not in the
    primary table, but are worth a human actually looking at rather than
    silently disappearing once disqualified."""
    mask = select_flagged_for_review_rows(b2_ds, config)
    _write_star_table(
        b2_ds,
        config,
        mask,
        output_path,
        caption="Stars with a notable raw excess significance that were disqualified by an "
        "automated quality-control flag, listed here for individual manual review rather than "
        "silently dropped.",
        label="tab:flagged-for-review",
        empty_message="No stars flagged for individual review in this sample.",
    )


# --- FITS catalogue -------------------------------------------------------------


def assemble_catalogue(
    a0_ds: xr.Dataset, b2_ds: xr.Dataset, config: dict, has_sed_figure: np.ndarray
) -> Table:
    """Builds the full output catalogue: every b2 column (full population,
    not just candidates -- same null-result-completeness principle as
    every stage since Tier 1), plus EXTRA_A0_COLUMNS, plus has_sed_figure.

    Empty strings in any string column (e.g. disqualifying_flags=="" for a
    clean star, photosphere_model_grid=="" for a skipped white-dwarf fit)
    are replaced with an explicit "(none)" placeholder before writing --
    verified (2026-07-22) that astropy's FITS writer round-trips an empty
    string as a MASKED value, not a real empty string, which would make
    "clean" and "genuinely absent/unknown" indistinguishable to anyone
    reading the FITS file directly. "(none)" is unambiguous either way."""
    assert_star_aligned(a0_ds, b2_ds)
    df = b2_ds.to_dataframe().reset_index()
    for col in EXTRA_A0_COLUMNS:
        if col in a0_ds:
            df[col] = a0_ds[col].values
    df["has_sed_figure"] = has_sed_figure.astype(np.int32)

    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].replace("", "(none)")

    return Table.from_pandas(df)


def save_catalogue(table: Table, path: Path) -> None:
    """Writes the catalogue to a FITS binary table, with a COMMENT header
    stating plainly that qc_candidate_preliminary_refined is not the final
    qc_anomalous_excess -- so the caveat travels with the file even for a
    reader who only opens the header, not the surrounding code/docs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    table.meta["COMMENT"] = (
        "qc_candidate_preliminary_refined is NOT the final qc_anomalous_excess. "
        "qc_photometric_artifact, the extragalactic (SMC/LMC) young-cluster "
        "membership catalogue, and the single-band significance threshold all "
        "remain unimplemented as of 2026-07-22. See RESEARCH_CONTEXT.md's "
        "'Deferred to Future Work' section for the complete, current list of "
        "what this pipeline does and does not yet handle."
    )
    table.write(path, format="fits", overwrite=True)
    logger.info("Saved catalogue to %s (%d stars, %d columns)", path, len(table), len(table.colnames))


# --- Orchestration -------------------------------------------------------------


def run(config: dict, a0_path: Path, b2_path: Path, output_dir: Path) -> Table:
    """Runs the full output stage: load a0/b2 -> generate SED figures + the
    population scatter + the HR diagram -> write both LaTeX tables ->
    assemble and save the FITS catalogue."""
    a0_ds = xr.open_dataset(a0_path)
    b2_ds = xr.open_dataset(b2_path)

    figures_dir = output_dir / config["output"]["figures_dir"]
    has_sed_figure = generate_sed_figures(a0_ds, b2_ds, config, figures_dir)
    plot_excess_sigma_scatter(b2_ds, config, figures_dir / "excess_sigma_scatter.png")
    plot_hr_diagram(a0_ds, b2_ds, config, figures_dir / "hr_diagram.png")

    tables_dir = output_dir / config["output"]["tables_dir"]
    write_candidate_table(b2_ds, config, tables_dir / "candidates.tex")
    write_flagged_for_review_table(b2_ds, config, tables_dir / "flagged_for_review.tex")

    table = assemble_catalogue(a0_ds, b2_ds, config, has_sed_figure)
    catalogue_path = tables_dir / "catalogue.fits"
    save_catalogue(table, catalogue_path)
    return table
