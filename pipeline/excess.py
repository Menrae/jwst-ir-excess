"""
pipeline.excess

Stage 4 of the jwst-ir-excess pipeline (see RESEARCH_CONTEXT.md for the
5-stage architecture): joins photosphere.py's predicted mid-IR flux (a1)
against miri_photometry.py's observed mid-IR flux, on the star identity a0
established, and computes the excess significance -- the core scientific
measurement this whole project is built around. -> data level b1.

STATUS: implements continuous excess-significance scoring, the QC-based
"clean" rollup, the join/alignment scaffolding, qc_excess_significant_{band}/
qc_candidate_preliminary (2026-07-22), and (as of 2026-07-22)
qc_single_band_candidate now that single_band_significance_threshold_sigma
is set (see below). Deliberately does NOT yet compute:

- qc_anomalous_excess -- per quality_config.yaml, this additionally
  requires six contaminant flags (qc_photometric_artifact,
  qc_debris_disk_candidate, qc_background_galaxy, qc_evolved_star,
  qc_known_variable, qc_binary_companion_contamination) that
  pipeline/contaminants.py has not been written yet to produce.
  excess.py runs BEFORE contaminants.py, not the reverse: contaminants.py's
  cross-matching against external catalogues is expensive and only worth
  doing for stars this stage has already identified as excess-clean and
  excess-showing, so the final qc_anomalous_excess is assembled once
  contaminants.py exists (reading this module's output), not here.

**significance_threshold_sigma = 3.0 (set 2026-07-22) is a triage cut for a
manually-vetted shortlist, explicitly NOT a look-elsewhere/Bonferroni-
corrected statistical significance claim.** A real survivor-count check
against three already-characterized archive fields (PN-TC-1, CONTROLFIELD,
NGC-602 -- see RESEARCH_CONTEXT.md Decision Log) found the pooled survivor
count nearly flat from 3-sigma to 5-sigma (5/5/4 stars), because real
signal in that data sits far above any of these cuts (max observed sigma:
168.6) -- the cut is not doing fine statistical discrimination, so a
stricter value would buy no specificity while risking loss of a real but
modest candidate. This mirrors Carrigan (2009) and Griffith et al. (2015)
(see the literature-check Decision Log entry): neither paper used a
corrected significance level either: both cut on a physically-motivated or
categorical criterion, then manually vetted every surviving source
individually. This project's own scale (dozens of candidates, not
thousands) makes an analogous "cut wide, then vet every survivor by hand"
approach the intended follow-through here, not a shortcut being avoided --
this threshold should never be cited as look-elsewhere-corrected in any
writeup.

**single_band_significance_threshold_sigma = 5.0 (set 2026-07-22, researcher
sign-off) is the same triage-cut philosophy, deliberately NOT
significance_threshold_sigma scaled down.** Single-band-only stars
(qc_single_filter_detection==1) don't get the dual-band cross-check that
gives the primary 3.0 criterion its own credibility, so this needed its own
justification. Neither Carrigan (2009) nor Griffith et al. (2015) offers a
directly borrowable number (Carrigan's own resolution to an analogous
2-filter problem was to avoid a 2-point significance statistic entirely by
adding LRS spectroscopy, specifically because "the associated impossibility
of fitting a Planck distribution with just two filter points" made a
meaningful statistic impossible with only two; Griffith's method is
structurally multi-band via WISE colors and has no single-band tier to
compare against). Derived instead from a rough independence approximation:
the dual-band criterion's credibility comes from requiring BOTH bands to
independently clear 3 sigma (one-tailed P~1.35e-3 each, joint ~1.8e-6 under
independence); solving for the single one-tailed z giving that same tail
probability alone gives z~4.7, rounded up to 5.0 given known F770W/F1000W
flux-error correlation (shared PSF-fit method, shared diffuse-background
systematic -- Deferred item 6) that the independence approximation ignores.
Verified against real data before being set (not just derived on paper):
in the 273-star, 15-field trial, only 2/273 single-band stars even reach a
computed excess_sigma at all (the rest are disqualified earlier, chiefly
qc_poor_photosphere_fit); this value changes zero current results. See
config/pipeline_config.yaml's own comment and RESEARCH_CONTEXT.md Decision
Log for the full derivation. qc_single_band_candidate is kept as its own
flag, not folded into qc_candidate_preliminary -- a true dual-band candidate
and a single-band-only one are different kinds of claim (same reasoning as
output.py's two separate candidate/flagged-for-review tables).

**Stopgap contaminant flag (added 2026-07-22, retired same day -- see
DISQUALIFYING_STAR_FLAGS)**: the survivor-count check above found that ALL
5 real survivors across all three test fields belonged to a
`target_classification` that already provides a conventional astrophysical
explanation for genuine mid-IR excess ("Stellar Cluster; Young star
clusters" or "Star; Planetary nebulae nuclei") -- and that neither
photosphere.py's qc_pms_veiling_risk token list nor any existing flag
caught them. Two stopgaps were added ahead of pipeline/contaminants.py's
proper catalogue cross-matching: `is_stopgap_young_cluster` (still active,
see below) and `is_stopgap_evolved_star` (added 2026-07-22, Teff-refined
the same day, **retired 2026-07-22 once pipeline/contaminants.py's proper
`qc_evolved_star` existed and was verified** -- see that module's Decision
Log entries. `is_stopgap_evolved_star` is no longer defined in this module;
`qc_evolved_star` (contaminants.py, HR-diagram overluminosity, parallax-
S/N-gated) is the superseding, properly-derived check. Removing the
stopgap was confirmed behaviorally consistent for the one PN-TC-1 star
both mechanisms ever actually flagged (Teff=8968 K, parallax S/N=7.8) --
it remains disqualified overall (via qc_poor_photosphere_fit at the b1
level, and via qc_evolved_star once contaminants.py runs). See
config/pipeline_config.yaml's excess.stopgap_contaminant_tokens
(young_cluster only now) for the remaining token list and its provenance.

**Field-level-granularity refinement (2026-07-22): `target_classification`
turned out to be a MAST field/observation-level tag, identical for every
star in a pointing (confirmed empirically) -- so a blanket match
disqualifies an entire field, not just the actual contaminant. Two
different outcomes for the two original stopgaps, both checked against
real data, not assumed:**

- **`is_stopgap_evolved_star`** was refined with a cheap, already-available
  per-star signal (photosphere_teff, exonerating stars fit well below
  `hot_teff_min_k` -- see the Decision Log for the full reasoning) before
  being retired entirely once contaminants.py's proper `qc_evolved_star`
  existed. Kept here only as history; the function no longer exists in
  this module.
- **`is_stopgap_young_cluster` is NOT refined -- logged as an explicit,
  accepted blind spot instead**, after checking (not assuming) whether an
  analogous cheap per-star signal exists: Gaia parallax/proper-motion
  consistency against the field's own population is the theoretically
  correct approach (this is literally how real cluster-membership
  determination works), and it does show some real discriminating power in
  this project's own test data (e.g. one NGC-602 star simultaneously an
  outlier in both parallax (2.05 mas vs. a field of mostly <0.7 mas) and
  proper motion (pmra=7.24 vs. a field clustered ~0.4-1.8 mas/yr) -- an
  obvious foreground interloper). But a naive "sigma-clip around the
  field's own median" is NOT safe to ship as-is, for two reasons confirmed
  against real data, not assumed: (1) NGC-602 is at the SMC's ~62 kpc
  distance, where genuine members' expected parallax (~0.016 mas) is far
  below Gaia's precision floor for these faint sources -- parallax has
  essentially no discriminating power for real members there, only proper
  motion does, and only if the field's own PM consensus is trustworthy; (2)
  CONTROLFIELD's own 20-star Gaia-matched subsample shows no obviously
  dominant single clump in either parallax or proper motion at all (pmra
  spans -21.1 to -0.7 mas/yr with no clear majority) -- there may not even
  be a reliable "field consensus" to check against without a larger sample
  or literature-sourced bulk cluster motions. This is squarely the kind of
  literature/catalog-informed membership analysis
  pipeline/contaminants.py's proper design should do, not a hasty
  same-session addition. **Consequence, stated as the researcher
  requested**: this is not just a candidate-detection gap -- at archive
  scale, field-wide stopgap suppression in young-cluster-classified
  pointings will silently shrink and bias whatever "clean, no-excess"
  sample later characterizes this project's null result, since genuinely
  uncontaminated field interlopers sharing those pointings are exactly the
  useful null-result population being incidentally discarded by this
  stopgap's bluntness. Unresolved; revisit in pipeline/contaminants.py.

Key design decisions -- see RESEARCH_CONTEXT.md Decision Log (2026-07-22
entry) for the full discussion:

- Join mechanics: a0 (retriever.py), a1 (photosphere.py), and
  miri_photometry.py's output all share the same `star` dimension/
  coordinate by construction (same length, same order -- both downstream
  modules copy a0's `star` coord verbatim), so the join is a positional
  merge, not a lookup. Given this project's own history with a silent
  row-misalignment bug (retriever.py cross-match, 2026-07-15), this module
  asserts `star_id` equality across all three datasets before merging
  rather than trusting positional alignment silently (assert_star_aligned).
- Nothing is ever dropped: every star that reaches this stage keeps its
  row (NaN sigma + qc flags, not a shorter table), per the project's
  established flag-don't-drop convention.
- Disqualifying vs. caveat-only qc_* categorization (see
  DISQUALIFYING_STAR_FLAGS / DISQUALIFYING_BAND_FLAGS below): a star or
  band is excess-clean only if every disqualifying flag is 0. Notably:
    - qc_rj_extrapolated is disqualifying, not merely caveated -- these
      predictions are not yet scored at equal confidence to a native-grid
      prediction, per the still-unresolved validation prerequisite in
      RESEARCH_CONTEXT.md. Their raw excess_sigma_{band} is still reported
      (nothing is dropped), just never eligible for a "clean" candidate.
    - qc_ambiguous_gaia_match is disqualifying, not caveat-only, given this
      project's own cross-match-misattribution history (retriever.py,
      2026-07-15) -- an ambiguous match means the photometry feeding the
      photosphere fit might belong to the wrong star entirely.
    - qc_extinction_uncertain and qc_grid_disagreement are caveat-only
      (recorded, but do not disqualify): extinction-uncertain sources fall
      back to Av=0 in photosphere.py, which biases toward suppressing
      apparent excess (extinction only dims), not manufacturing it; grid
      disagreement is a secondary cross-check and Kurucz remains the
      recorded primary prediction regardless of it.
    - qc_psf_disagreement_faint_{band} is caveat-only: it is explicitly the
      case where photon noise plausibly explains the PSF/aperture
      disagreement, and that noise is already reflected in a larger
      observed_flux_{band}_err, so it is already "priced into" sigma.
      qc_psf_disagreement_complex_{band} (disagreement NOT explained by
      photon noise -- a real, uncaptured systematic) IS disqualifying.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import xarray as xr

from pipeline import __version__

logger = logging.getLogger(__name__)

# Star-level qc_* flags (from a0/a1) that disqualify a star from candidacy
# in every band, regardless of the excess significance itself. See module
# docstring for the per-flag reasoning.
DISQUALIFYING_STAR_FLAGS = (
    "qc_ambiguous_gaia_match",
    "qc_no_photosphere_grid",
    "qc_poor_photosphere_fit",
    "qc_possible_binary",
    "qc_pms_veiling_risk",
    "qc_rj_extrapolated",
    "qc_stopgap_young_cluster",
    # qc_stopgap_evolved_star retired 2026-07-22 -- superseded by
    # pipeline.contaminants.is_evolved_star_overluminous (qc_evolved_star),
    # a properly-derived, parallax-S/N-gated HR-diagram check. See module
    # docstring and RESEARCH_CONTEXT.md Decision Log.
)

# Per-band qc_*_{band} flags (from miri_photometry.py) that disqualify that
# specific band's excess measurement. qc_psf_aperture_disagreement_{band} is
# deliberately excluded -- it's the logical OR of _faint/_complex below, and
# only _complex (not explained by photon noise) is treated as disqualifying.
DISQUALIFYING_BAND_FLAGS = (
    "qc_no_mosaic_for_filter",
    "qc_source_off_mosaic",
    "qc_saturated",
    "qc_crowded_source",
    "qc_psf_fit_failed",
    "qc_psf_disagreement_complex",
)


# --- Join / alignment ------------------------------------------------------


def assert_star_aligned(a0_ds: xr.Dataset, a1_ds: xr.Dataset, miri_ds: xr.Dataset) -> None:
    """Raises AssertionError unless all three datasets' star_id arrays are
    identical, element-for-element. a0/a1/miri_photometry are expected to
    share the same `star` coordinate, order, and length by construction
    (photosphere.py and miri_photometry.py both copy a0's `star` coord
    verbatim) -- but given this project's own history with a silent
    row-misalignment bug (retriever.py cross-match, 2026-07-15), that
    assumption is checked explicitly here rather than trusted."""
    a0_ids = a0_ds["star_id"].values
    a1_ids = a1_ds["star_id"].values
    miri_ids = miri_ds["star_id"].values

    if not (a0_ids.shape == a1_ids.shape == miri_ids.shape):
        raise AssertionError(
            f"star dimension length mismatch: a0={a0_ids.shape}, "
            f"a1={a1_ids.shape}, miri_photometry={miri_ids.shape}"
        )
    if not np.array_equal(a0_ids, a1_ids):
        raise AssertionError("a0 and a1 star_id arrays are not aligned -- refusing to join")
    if not np.array_equal(a0_ids, miri_ids):
        raise AssertionError(
            "a0 and miri_photometry star_id arrays are not aligned -- refusing to join"
        )


# --- Stopgap contaminant classification (ahead of pipeline/contaminants.py) --


def _classification_matches(target_classification: str, tokens: list[str]) -> bool:
    """Same convention as photosphere.py's own classification check: exact
    match against any semicolon-separated component, not a raw substring
    search (duplicated here rather than imported -- two lines, not worth a
    cross-module dependency on a private helper)."""
    components = {c.strip() for c in str(target_classification).split(";")}
    return bool(components & set(tokens))


def is_stopgap_young_cluster(target_classification: str, config: dict) -> bool:
    """Stopgap only (see module docstring): catches young-cluster/PMS-
    association classifications that photosphere.py's qc_pms_veiling_risk
    token list does not match (e.g. 'Young star clusters', 'Stellar
    Cluster') -- distinct from qc_pms_veiling_risk, which is about veiling
    risk in the fit's own input bands, not about the excess measurement
    itself having a mundane explanation."""
    tokens = config["excess"]["stopgap_contaminant_tokens"]["young_cluster"]
    return _classification_matches(target_classification, tokens)


# is_stopgap_evolved_star retired 2026-07-22 -- superseded by
# pipeline.contaminants.is_evolved_star_overluminous (qc_evolved_star), a
# properly-derived, parallax-S/N-gated HR-diagram check. See module
# docstring and RESEARCH_CONTEXT.md Decision Log for the full history
# (added, Teff-refined, then retired, all the same day).


# --- Excess significance -----------------------------------------------------


def compute_excess_sigma(
    observed: np.ndarray,
    observed_err: np.ndarray,
    predicted: np.ndarray,
    predicted_err: np.ndarray,
) -> np.ndarray:
    """Signed excess significance: (observed - predicted) / combined error,
    assuming independent Gaussian errors -- defensible here because
    observed_err is photutils' photon-noise fit uncertainty
    (miri_photometry.py) and predicted_err comes from a completely separate
    profile-likelihood Teff scan over independent optical/near-IR
    photometry (photosphere.py); the two share no inputs.

    Both error terms are already known to be incomplete (see
    miri_photometry.py's and photosphere.py's own docstrings/comments) --
    this sigma is an approximation built from two already-approximate error
    bars, not a rigorous statistical significance. Positive = excess
    (observed brighter than predicted); negative = deficit. NaN wherever
    any input is non-finite or the combined error is non-positive.
    """
    observed = np.asarray(observed, dtype=float)
    observed_err = np.asarray(observed_err, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    predicted_err = np.asarray(predicted_err, dtype=float)

    combined_err = np.sqrt(observed_err**2 + predicted_err**2)
    with np.errstate(invalid="ignore", divide="ignore"):
        sigma = (observed - predicted) / combined_err
    valid = np.isfinite(sigma) & (combined_err > 0)
    return np.where(valid, sigma, np.nan)


# --- QC rollups ---------------------------------------------------------------


def compute_star_disqualified(a1_ds: xr.Dataset) -> np.ndarray:
    """Boolean OR of every DISQUALIFYING_STAR_FLAGS present in a1_ds."""
    n = a1_ds.sizes["star"]
    flag = np.zeros(n, dtype=bool)
    for name in DISQUALIFYING_STAR_FLAGS:
        if name in a1_ds:
            flag |= a1_ds[name].values.astype(bool)
    return flag


def compute_band_disqualified(miri_ds: xr.Dataset, band: str) -> np.ndarray:
    """Boolean OR of every DISQUALIFYING_BAND_FLAGS present in miri_ds for
    the given band."""
    n = miri_ds.sizes["star"]
    flag = np.zeros(n, dtype=bool)
    for base in DISQUALIFYING_BAND_FLAGS:
        name = f"{base}_{band}"
        if name in miri_ds:
            flag |= miri_ds[name].values.astype(bool)
    return flag


def build_disqualifying_flags_summary(
    flag_arrays: dict[str, np.ndarray], flag_names: list[str], n: int
) -> np.ndarray:
    """Per-star, comma-joined names of every disqualifying flag that fired
    (star-level or per-band) -- a diagnostic column so a non-candidate row
    is self-explanatory without manually scanning every boolean qc_*
    column.

    dtype width is computed from flag_names itself (every name + a comma
    per join), not a fixed guess -- a fixed "U256" here was found
    (2026-07-22, while checking FITS-compatibility for output.py) to
    silently truncate (numpy truncates fixed-width unicode arrays on
    assignment with no error) once enough flags fire on the same star:
    the worst case across this project's actual flag set is 475
    characters, already past 256, even though no star in this project's
    real test data has hit it yet. Computing the width from flag_names
    guarantees this can never silently under-size again as more bands or
    flags are added."""
    summaries: list[list[str]] = [[] for _ in range(n)]
    for name in flag_names:
        arr = flag_arrays.get(name)
        if arr is None:
            continue
        for i in np.flatnonzero(np.asarray(arr).astype(bool)):
            summaries[i].append(name)
    max_width = max(1, sum(len(name) for name in flag_names) + max(0, len(flag_names) - 1))
    return np.asarray([",".join(s) for s in summaries], dtype=f"U{max_width}")


# --- Assembly and output -------------------------------------------------------


def assemble_level_b1(
    a0_ds: xr.Dataset, a1_ds: xr.Dataset, miri_ds: xr.Dataset, config: dict
) -> xr.Dataset:
    """Joins a0 (star identity), a1 (predicted photosphere flux), and
    miri_photometry.py's output (observed flux) on the shared `star`
    dimension, and computes the excess significance, QC-clean rollups, and
    (when the respective threshold is set) qc_excess_significant_{band}/
    qc_candidate_preliminary (dual-band) and qc_single_band_candidate
    (single-band). Deliberately does NOT compute qc_anomalous_excess -- see
    module docstring."""
    assert_star_aligned(a0_ds, a1_ds, miri_ds)

    bands = config["excess"]["primary_bands"]
    n = a0_ds.sizes["star"]

    # Stopgap contaminant flag (see module docstring): computed from a0's
    # target_classification and folded into a1_ds (a local copy, not
    # mutating the caller's dataset) so compute_star_disqualified picks it
    # up via the normal DISQUALIFYING_STAR_FLAGS mechanism, with no separate
    # code path needed. (qc_stopgap_evolved_star retired 2026-07-22 --
    # superseded by pipeline.contaminants.qc_evolved_star.)
    a1_ds = a1_ds.copy()
    if "target_classification" in a0_ds:
        target_classification = a0_ds["target_classification"].values
        a1_ds["qc_stopgap_young_cluster"] = (
            "star",
            np.asarray(
                [int(is_stopgap_young_cluster(tc, config)) for tc in target_classification],
                dtype=np.int32,
            ),
        )

    data_vars: dict[str, tuple] = {
        "star_id": ("star", a0_ds["star_id"].values),
        "gaia_source_id": ("star", a0_ds["gaia_source_id"].values),
    }
    # Diagnostic context from a0, so a flagged row is self-explanatory
    # without re-opening a0 itself. qc_single_filter_detection in particular
    # is needed downstream to distinguish dual-band stars (eligible for the
    # both-bands-required primary criterion) from single-band-only stars
    # (their own, separate, stricter tier -- see module docstring).
    for name in ("target_classification", "gaia_ra", "gaia_dec", "qc_single_filter_detection"):
        if name in a0_ds:
            data_vars[name] = ("star", a0_ds[name].values)

    # Carry every upstream qc_*/value column from a1 and miri_photometry
    # through unchanged -- nothing here is dropped or recomputed.
    for name in a1_ds.data_vars:
        if name in ("star_id", "gaia_source_id"):
            continue
        data_vars[name] = ("star", a1_ds[name].values)
    for name in miri_ds.data_vars:
        if name in ("star_id", "gaia_source_id"):
            continue
        data_vars[name] = ("star", miri_ds[name].values)

    star_disqualified = compute_star_disqualified(a1_ds)
    data_vars["qc_star_disqualified"] = ("star", star_disqualified.astype(np.int32))

    for band in bands:
        observed = miri_ds[f"observed_flux_{band}"].values
        observed_err = miri_ds[f"observed_flux_{band}_err"].values
        predicted = a1_ds[f"predicted_flux_{band}"].values
        predicted_err = a1_ds[f"predicted_flux_{band}_err"].values
        data_vars[f"excess_sigma_{band}"] = (
            "star",
            compute_excess_sigma(observed, observed_err, predicted, predicted_err),
        )

        band_disqualified = compute_band_disqualified(miri_ds, band)
        data_vars[f"qc_band_disqualified_{band}"] = ("star", band_disqualified.astype(np.int32))
        data_vars[f"qc_excess_clean_{band}"] = (
            "star",
            (~star_disqualified & ~band_disqualified).astype(np.int32),
        )

    flag_names = list(DISQUALIFYING_STAR_FLAGS) + [
        f"{base}_{band}" for band in bands for base in DISQUALIFYING_BAND_FLAGS
    ]
    flag_arrays = {name: data_vars[name][1] for name in flag_names if name in data_vars}
    data_vars["disqualifying_flags"] = (
        "star",
        build_disqualifying_flags_summary(flag_arrays, flag_names, n),
    )

    # qc_excess_significant_{band}/qc_candidate_preliminary: only computed
    # once significance_threshold_sigma is set (see module docstring for
    # the 2026-07-22 threshold-choice reasoning -- a triage cut for manual
    # vetting, not a corrected statistical significance claim).
    # qc_candidate_preliminary requires BOTH configured bands significant,
    # and only applies to dual-band stars (qc_single_filter_detection==0)
    # -- single-band-only stars get their own, separate, more stringent
    # single_band_significance_threshold_sigma/qc_single_band_candidate tier
    # below instead.
    threshold = config["excess"].get("significance_threshold_sigma")
    if threshold is not None:
        significant = {}
        for band in bands:
            clean = data_vars[f"qc_excess_clean_{band}"][1].astype(bool)
            sigma = data_vars[f"excess_sigma_{band}"][1]
            sig = clean & np.isfinite(sigma) & (sigma >= threshold)
            data_vars[f"qc_excess_significant_{band}"] = ("star", sig.astype(np.int32))
            significant[band] = sig
        dual_band = ~data_vars["qc_single_filter_detection"][1].astype(bool)
        candidate = dual_band & np.logical_and.reduce([significant[b] for b in bands])
        data_vars["qc_candidate_preliminary"] = ("star", candidate.astype(np.int32))

    # qc_single_band_candidate: only computed once
    # single_band_significance_threshold_sigma is set (2026-07-22, see
    # module docstring for the derivation/sign-off). Applies only to
    # single-band-only stars (qc_single_filter_detection==1) -- for those,
    # a single-filter-detection star has exactly one band with real
    # observed flux (the other is always qc_band_disqualified_{band} via
    # qc_no_mosaic_for_filter, so qc_excess_clean_{band} is 0 there by
    # construction), so this is an OR across bands, not an AND like the
    # dual-band criterion above. Kept as its own flag, never folded into
    # qc_candidate_preliminary -- a true dual-band candidate and a
    # single-band-only one are different kinds of claim.
    single_threshold = config["excess"].get("single_band_significance_threshold_sigma")
    if single_threshold is not None:
        significant_single_band = []
        for band in bands:
            clean = data_vars[f"qc_excess_clean_{band}"][1].astype(bool)
            sigma = data_vars[f"excess_sigma_{band}"][1]
            significant_single_band.append(
                clean & np.isfinite(sigma) & (sigma >= single_threshold)
            )
        single_band = data_vars["qc_single_filter_detection"][1].astype(bool)
        single_band_candidate = single_band & np.logical_or.reduce(significant_single_band)
        data_vars["qc_single_band_candidate"] = ("star", single_band_candidate.astype(np.int32))

    ds = xr.Dataset(data_vars=data_vars, coords={"star": a0_ds["star"].values})
    for band in bands:
        ds[f"excess_sigma_{band}"].attrs["units"] = "dimensionless (sigma)"
        ds[f"excess_sigma_{band}"].attrs["note"] = (
            "Approximation built from two already-approximate error budgets "
            "(see pipeline.excess module docstring) -- not a rigorous "
            "statistical significance. Positive = excess, negative = deficit."
        )
    ds.attrs["pipeline_version"] = __version__
    ds.attrs["significance_threshold_sigma"] = str(
        config["excess"].get("significance_threshold_sigma")
    )
    ds.attrs["single_band_significance_threshold_sigma"] = str(
        config["excess"].get("single_band_significance_threshold_sigma")
    )
    ds.attrs["significance_threshold_note"] = (
        "Chosen to produce a reviewable shortlist consistent with precedent "
        "practice (Carrigan 2009; Griffith et al. 2015), NOT a corrected/"
        "look-elsewhere-adjusted statistical significance claim -- see "
        "pipeline.excess module docstring."
    )
    pending = []
    if config["excess"].get("single_band_significance_threshold_sigma") is None:
        pending.append("qc_single_band_candidate")
    pending.append("qc_anomalous_excess (needs pipeline/contaminants.py)")
    ds.attrs["note"] = (
        "Not yet computed: " + "; ".join(pending) + ". See pipeline.excess module docstring."
    )
    return ds


def save_level_b1(ds: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path)
    logger.info("Saved level b1 dataset to %s (%d stars)", path, ds.sizes["star"])


# --- Orchestration -------------------------------------------------------------


def run(
    config: dict,
    a0_path: Path,
    a1_path: Path,
    miri_path: Path,
    output_path: Path,
) -> xr.Dataset:
    """Runs the full excess-scoring stage: load a0/a1/miri_photometry ->
    assert star alignment -> compute excess significance + QC rollups ->
    save b1."""
    a0_ds = xr.open_dataset(a0_path)
    a1_ds = xr.open_dataset(a1_path)
    miri_ds = xr.open_dataset(miri_path)

    ds = assemble_level_b1(a0_ds, a1_ds, miri_ds, config)
    save_level_b1(ds, output_path)
    return ds
