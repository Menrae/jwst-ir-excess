"""
pipeline.photosphere

Stage 3 of the jwst-ir-excess pipeline (see RESEARCH_CONTEXT.md for the
5-stage architecture): fits a stellar photosphere model to each star's
Gaia + 2MASS photometry (data level a0) and predicts the photosphere-only
flux expected at F770W/F1000W. -> data level a1. excess.py compares this
prediction against the observed MIRI flux, once the still-undesigned MIRI-
photometry-extraction stage (architecture item 2) produces it -- a1 has no
observed MIRI flux itself.

Key design decisions -- see RESEARCH_CONTEXT.md Decision Log (2026-07-20
entries) for the full discussion and live-verification results:

- Model grid varies by a rough Teff estimate from Gaia BP-RP (bucket
  selection only -- never the reported Teff, which comes from the fit
  itself):
    Teff >= grids.hot_teff_min_k:   Kurucz only (ck04models, via
                                    stsynphot/CDBS)
    in between:                    Kurucz default, PHOENIX cross-check
    Teff <= grids.cool_teff_max_k:  PHOENIX only (via expecto)
  The BP-RP -> Teff anchor table below is an approximate heuristic (rough
  Pecaut & Mamajek-like main-sequence colors, not independently re-verified
  point by point) used ONLY to pick a grid/bucket -- not a scientific Teff.
  A grids.cross_check_buffer_k-wide buffer around both boundaries widens
  where the cross-check runs, since a hard cutoff would apply it
  inconsistently to physically similar stars that straddle a boundary
  (confirmed non-issue re: iteration/oscillation -- bucket assignment is a
  one-shot decision from the initial color estimate, not a loop that could
  re-trigger reassignment after the fit refines Teff).
- Both grids confirmed queryable live in this environment 2026-07-20:
  Kurucz needs local grid files (auto-downloaded here, ~5 MB, solar
  metallicity subgrid only -- see ensure_kurucz_grid); PHOENIX fetches
  on-demand via expecto (no interpolation between grid nodes -- expecto
  snaps to the nearest node, confirmed from its own docstring).
- White dwarfs (target_classification contains a
  grids.target_classification_tokens.white_dwarf token) are not fit with
  either grid -- neither is appropriate physics -- and get
  qc_no_photosphere_grid instead of a wrong-physics fit. No predicted_flux_*
  is produced for these sources.
- T Tauri/protostar/protoplanetary-disk targets (target_classification
  tokens in target_classification_tokens.pms_veiling_risk) are still fit
  (a comparison baseline is needed) but flagged qc_pms_veiling_risk, since
  their near-IR photometry may already carry non-photospheric veiling/
  accretion excess the fit can't distinguish from a bare photosphere.
- Possible binaries (Gaia RUWE > binarity.ruwe_threshold, or a nonzero
  non_single_star flag) are fit, not excluded -- flagged qc_possible_binary,
  per the project's flag-don't-drop convention.
- Extinction: Av comes from the Bayestar19 3D dust map (dustmaps package),
  using Gaia parallax-derived distance + sky position, per literature
  precedent (Carrigan 2009; Wright et al. 2014; Griffith et al. 2015 --
  none of them fit extinction as a free SED parameter either; see Decision
  Log). NOT fit jointly with Teff. Bayestar (Pan-STARRS1-based) has NO
  coverage south of dec ~ -30 deg -- confirmed both empirically (a real
  southern MIRI target returned NaN) and from the package's own docstring.
  Sources with unusable parallax (missing/non-positive) OR outside the
  footprint OR a NaN map return get qc_extinction_uncertain, with Av left
  unset (NaN) rather than guessed. Queried with mode='best' + max_samples=0
  (maximum-posterior point estimate, not median-of-samples) -- a deliberate
  memory/point-estimate tradeoff, not an invisible default; see
  estimate_extinction and RESEARCH_CONTEXT.md.
- PHOENIX (Husser et al. 2013, via expecto) spectra only extend to ~5.5
  micron -- confirmed live, fully short of both MIRI bands -- so
  PHOENIX-primary (cool, Teff <= grids.cool_teff_max_k) stars get a
  Rayleigh-Jeans/blackbody-tail extrapolation instead of no prediction at
  all (see rj_extrapolation_spectrum), flagged qc_rj_extrapolated alongside
  qc_no_mid_ir_model_coverage (which stays 1 regardless -- the native grid
  still doesn't cover it). Quantified live 2026-07-20 across two archive
  samples: ~10% of Gaia-matched stars overall, concentrated up to ~68% in
  protostar/YSO-classified fields -- squarely the population this project
  cares about most, hence fixing this rather than deferring it. This
  extrapolation is NOT yet validated (see RESEARCH_CONTEXT.md: a named
  blocking prerequisite for excess.py) -- qc_rj_extrapolated sources must
  not be scored at equal confidence to a native-grid prediction until
  validated against real cool stars with known WISE/Spitzer mid-IR
  photometry.
- Reddening is applied to the full model spectrum (not just at each band's
  effective wavelength) using the Gordon et al. (2023) "G23" law via
  dust_extinction, chosen specifically because -- unlike Fitzpatrick (1999),
  which only covers ~0.1-3.3 micron -- G23 covers ~0.09-32 micron in one
  self-consistent law, spanning both the optical/near-IR fit bands and the
  mid-IR MIRI prediction bands without switching laws partway through
  (confirmed via dust_extinction's x_range attribute).
- The Bayestar map's native reddening unit is NOT literally E(B-V); the
  package docs say the conversion to extinction depends on the map version
  and requires coefficients from Green et al. (2019) Table 1.
  bayestar_to_av_coefficient below (2.742) is a commonly-cited approximate
  value for an Rv=3.1-like conversion, but has NOT been independently
  checked against that table -- flagged here rather than presented as
  final; revisit before trusting Av values in a writeup.
- Bandpass transmission curves for Gaia G/BP/RP, 2MASS J/H/Ks, and MIRI
  F770W/F1000W come from the SVO Filter Profile Service
  (astroquery.svo_fps.get_transmission_data), confirmed fast and reliable
  live 2026-07-20. Vega-system zero points for the six FIT bands (not
  needed for the two MIRI prediction bands, which are reported as flux
  density directly) are baked in as FIT_BAND_ZEROPOINT_JY below rather than
  queried at runtime: the zero-point lookup endpoint
  (SvoFps.get_filter_index) was found to be slow/timeout-prone for broad
  optical wavelength ranges during smoke testing, so these are static
  reference values fetched once and cited, not a live per-run dependency.
- The fit is 1-parameter nonlinear (Teff) plus one analytically-solved
  linear normalization (a magnitude-space additive offset -- the standard
  simplification that the free flux-normalization parameter is exactly a
  constant offset across all bands in magnitude space, so it doesn't need
  its own nonlinear search), at a fixed log_g (main-sequence assumption --
  known simplification, dwarfs/giants not distinguished; logged in
  RESEARCH_CONTEXT.md).
- qc_grid_disagreement (FGK cross-check bucket only) fires when
  |Teff_kurucz - Teff_phoenix| > max(grid_disagreement.abs_floor_k,
  grid_disagreement.rel_frac * Teff_kurucz). Kurucz remains the recorded
  a1 Teff/prediction regardless -- disagreement is surfaced for downstream
  review, not auto-resolved, consistent with how ambiguous Gaia/2MASS
  matches are handled in retriever.py.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import xarray as xr
from astropy.table import Table
from scipy.optimize import minimize_scalar

from pipeline import __version__

logger = logging.getLogger(__name__)

# --- Fit bands ---------------------------------------------------------------

FIT_BAND_NAMES = ["Gaia_G", "Gaia_BP", "Gaia_RP", "2MASS_J", "2MASS_H", "2MASS_Ks"]

FIT_BAND_SVO_ID = {
    "Gaia_G": "GAIA/GAIA3.G",
    "Gaia_BP": "GAIA/GAIA3.Gbp",
    "Gaia_RP": "GAIA/GAIA3.Grp",
    "2MASS_J": "2MASS/2MASS.J",
    "2MASS_H": "2MASS/2MASS.H",
    "2MASS_Ks": "2MASS/2MASS.Ks",
}

FIT_BAND_MAG_COL = {
    "Gaia_G": "gaia_phot_g_mean_mag",
    "Gaia_BP": "gaia_phot_bp_mean_mag",
    "Gaia_RP": "gaia_phot_rp_mean_mag",
    "2MASS_J": "twomass_Jmag",
    "2MASS_H": "twomass_Hmag",
    "2MASS_Ks": "twomass_Kmag",
}

FIT_BAND_MAG_ERR_COL = {
    "Gaia_G": None,  # Gaia DR3 mean-mag columns carry no per-source error
    "Gaia_BP": None,
    "Gaia_RP": None,
    "2MASS_J": "twomass_e_Jmag",
    "2MASS_H": "twomass_e_Hmag",
    "2MASS_Ks": "twomass_e_Kmag",
}
# Bands with no tabulated error (Gaia mean mags) fall back to this floor --
# a stated compromise, not a derived value; revisit if it turns out to
# systematically over/under-weight Gaia bands in the fit.
DEFAULT_MAG_ERR = 0.02

# Real bug found 2026-07-23 (see RESEARCH_CONTEXT.md, individual vetting
# of this project's first qc_candidate_preliminary hits): Gaia's G/BP/RP
# are three views of the same wide optical passband family -- G is close
# to redundant with BP+RP, so a fit using only these three provides
# barely more real constraint than ONE color (BP-RP) against the 2-free-
# parameter (Teff + normalization) model, not 3 independent points.
# Confirmed directly on two real candidates (HD-152249, SN2017gci): both
# were exactly this case, converging to a "good" chi2 that was close to
# mathematically guaranteed regardless of the star's true Teff. Grouped
# here so count_effective_bands can treat them as contributing at most 1
# combined effective band; 2MASS's J/H/Ks span a genuinely different
# wavelength baseline from Gaia and from each other, so each counts
# individually.
_CORRELATED_BAND_GROUPS = (
    ("Gaia_G", "Gaia_BP", "Gaia_RP"),
)


def count_effective_bands(observed_mags: dict[str, float]) -> int:
    """Counts genuinely independent photometric constraints available to
    fit_teff, not raw band count -- see _CORRELATED_BAND_GROUPS. Bands
    within the same correlated group count as at most 1 combined; every
    other band (currently: all three 2MASS bands) counts individually.
    Used for qc_starved_photosphere_fit (config:
    photosphere.min_effective_bands), a genuinely separate check from the
    existing n_available_bands < 2 gate above -- that gate catches "too
    little data to fit at all"; this one catches "technically fittable,
    but not meaningfully constrained".
    """
    grouped = {b for group in _CORRELATED_BAND_GROUPS for b in group}
    n = sum(
        1 for b in FIT_BAND_NAMES
        if b not in grouped and np.isfinite(observed_mags.get(b, np.nan))
    )
    for group in _CORRELATED_BAND_GROUPS:
        if any(np.isfinite(observed_mags.get(b, np.nan)) for b in group):
            n += 1
    return n

# Vega-system zero points (Jy), fetched from the SVO Filter Profile Service
# 2026-07-20 and baked in as static reference data -- see module docstring
# for why (the live zero-point-lookup endpoint proved unreliable for broad
# wavelength ranges; these six specific values were each confirmed with a
# narrow, successful per-filter query).
FIT_BAND_ZEROPOINT_JY = {
    "Gaia_G": 3228.7464752872,
    "Gaia_BP": 3552.0128903434,
    "Gaia_RP": 2554.9484277488,
    "2MASS_J": 1594.0,
    "2MASS_H": 1024.0,
    "2MASS_Ks": 666.8,
}

MIRI_BAND_SVO_ID = {
    "F770W": "JWST/MIRI.F770W",
    "F1000W": "JWST/MIRI.F1000W",
}

# --- Rough Teff estimate for grid/bucket selection only ----------------------

# Approximate (BP-RP, Teff) anchors for a main-sequence-like color-Teff
# relation (Pecaut & Mamajek 2013-like), recalled approximately rather than
# taken from a re-checked table -- fine for bucket selection (the actual
# reported Teff comes from the fit), NOT to be used or cited as a precise
# scientific Teff-color relation anywhere else.
_TEFF_ANCHOR_BP_RP = np.array([-0.35, -0.20, -0.05, 0.02, 0.16, 0.34, 0.46, 0.68, 0.82, 0.98, 1.38, 1.84, 3.15])
_TEFF_ANCHOR_TEFF = np.array([42000, 31500, 20000, 9700, 8080, 7220, 6510, 5930, 5610, 5240, 4410, 3870, 3000])


def rough_teff_from_bp_rp(bp_rp: float) -> float:
    """Approximate Teff from Gaia BP-RP color, for model-grid/bucket
    selection only -- see module docstring. Clipped to the anchor table's
    range at the extremes rather than extrapolated."""
    # np.interp requires ascending xp; _TEFF_ANCHOR_BP_RP already is.
    return float(np.interp(bp_rp, _TEFF_ANCHOR_BP_RP, _TEFF_ANCHOR_TEFF))


def select_grids(teff_rough: float, config: dict) -> tuple[str, list[str]]:
    """Returns (primary_grid, grids_to_fit). primary_grid's Teff/prediction
    is what's recorded in a1; grids_to_fit may include a second grid for
    the FGK cross-check (see qc_grid_disagreement)."""
    grids_cfg = config["photosphere"]["grids"]
    hot_min = grids_cfg["hot_teff_min_k"]
    cool_max = grids_cfg["cool_teff_max_k"]
    buffer = grids_cfg["cross_check_buffer_k"]

    if teff_rough >= hot_min:
        primary = "kurucz"
    elif teff_rough <= cool_max:
        primary = "phoenix"
    else:
        primary = "kurucz"  # FGK default

    cross_check = (cool_max - buffer) <= teff_rough <= (hot_min + buffer)
    if not cross_check:
        return primary, [primary]
    other = "phoenix" if primary == "kurucz" else "kurucz"
    return primary, [primary, other]


# --- Target classification gates ---------------------------------------------


def _classification_matches(target_classification: str, tokens: list[str]) -> bool:
    components = {c.strip() for c in str(target_classification).split(";")}
    return bool(components & set(tokens))


def is_white_dwarf(target_classification: str, config: dict) -> bool:
    tokens = config["photosphere"]["target_classification_tokens"]["white_dwarf"]
    return _classification_matches(target_classification, tokens)


def is_pms_veiling_risk(target_classification: str, config: dict) -> bool:
    tokens = config["photosphere"]["target_classification_tokens"]["pms_veiling_risk"]
    return _classification_matches(target_classification, tokens)


# --- Kurucz grid (stsynphot/CDBS) --------------------------------------------

CDBS_BASE_URL = "https://ssb.stsci.edu/trds/grid/ck04models"


def ensure_kurucz_grid(cdbs_dir: Path, metallicity_subdir: str = "ckp00") -> None:
    """Downloads the ck04models catalog.fits plus one metallicity
    subdirectory (solar, ckp00, by default -- kurucz_metallicity is fixed in
    config, see module docstring) if not already present locally. ~5 MB
    total. Mirrors retriever.py's own download-if-missing pattern."""
    import requests

    grid_dir = cdbs_dir / "grid" / "ck04models"
    catalog_path = grid_dir / "catalog.fits"
    subdir_path = grid_dir / metallicity_subdir
    if catalog_path.exists() and subdir_path.is_dir() and any(subdir_path.iterdir()):
        return

    grid_dir.mkdir(parents=True, exist_ok=True)
    subdir_path.mkdir(parents=True, exist_ok=True)

    logger.info("Kurucz ck04models grid not found locally; downloading to %s", grid_dir)
    catalog_resp = requests.get(f"{CDBS_BASE_URL}/catalog.fits", timeout=30)
    catalog_resp.raise_for_status()
    catalog_path.write_bytes(catalog_resp.content)

    index_resp = requests.get(f"{CDBS_BASE_URL}/{metallicity_subdir}/", timeout=30)
    index_resp.raise_for_status()
    filenames = sorted(set(re.findall(rf'{metallicity_subdir}_\d+\.fits', index_resp.text)))
    if not filenames:
        raise RuntimeError(
            f"No spectrum files found in {CDBS_BASE_URL}/{metallicity_subdir}/ -- "
            "the CDBS directory listing format may have changed."
        )
    for fname in filenames:
        resp = requests.get(f"{CDBS_BASE_URL}/{metallicity_subdir}/{fname}", timeout=30)
        resp.raise_for_status()
        (subdir_path / fname).write_bytes(resp.content)
    logger.info("Downloaded %d Kurucz ck04models/%s spectra", len(filenames), metallicity_subdir)


def get_kurucz_spectrum(teff: float, log_g: float, metallicity: float, cdbs_dir: Path):
    """Returns a synphot SourceSpectrum interpolated from the ck04models
    grid. Requires ensure_kurucz_grid to have been called first."""
    import os

    os.environ["PYSYN_CDBS"] = str(cdbs_dir)
    import stsynphot as stsyn

    return stsyn.grid_to_spec("ck04models", teff, metallicity, log_g)


# --- PHOENIX grid (expecto) ---------------------------------------------------


def get_phoenix_spectrum(teff: float, log_g: float):
    """Returns a synphot SourceSpectrum for the nearest PHOENIX (Husser et
    al. 2013) grid node -- expecto snaps to the nearest node rather than
    interpolating (confirmed from its own docstring, not assumed)."""
    import astropy.units as u
    import expecto
    from synphot import SourceSpectrum
    from synphot.models import Empirical1D

    sp1d = expecto.get_spectrum(T_eff=teff, log_g=log_g, cache=True)
    wave = sp1d.spectral_axis.to(u.AA)
    flux_flam = sp1d.flux.to(u.erg / u.s / u.cm**2 / u.AA, equivalencies=u.spectral_density(wave))
    return SourceSpectrum(Empirical1D, points=wave, lookup_table=flux_flam)


def get_model_spectrum(grid: str, teff: float, config: dict):
    grids_cfg = config["photosphere"]["grids"]
    log_g = grids_cfg["fixed_log_g"]
    if grid == "kurucz":
        cdbs_dir = Path(grids_cfg["cdbs_dir"])
        return get_kurucz_spectrum(teff, log_g, grids_cfg["kurucz_metallicity"], cdbs_dir)
    if grid == "phoenix":
        return get_phoenix_spectrum(teff, log_g)
    raise ValueError(f"Unknown grid: {grid!r}")


# --- Bandpasses and reddening -------------------------------------------------


@lru_cache(maxsize=None)
def _get_bandpass(svo_id: str):
    import astropy.units as u
    from astroquery.svo_fps import SvoFps
    from synphot import SpectralElement
    from synphot.models import Empirical1D

    trans = SvoFps.get_transmission_data(svo_id)
    wave = np.asarray(trans["Wavelength"], dtype=float) * u.AA
    thru = np.asarray(trans["Transmission"], dtype=float)
    return SpectralElement(Empirical1D, points=wave, lookup_table=thru)


def redden_spectrum(source_spectrum, av: float, r_v: float):
    """Applies G23 (Gordon et al. 2023) reddening to the full spectrum --
    see module docstring for why G23 specifically (single law spanning
    both the optical/NIR fit bands and the MIRI prediction bands)."""
    import astropy.units as u
    from dust_extinction.parameter_averages import G23
    from synphot import SourceSpectrum
    from synphot.models import Empirical1D

    if av == 0.0:
        return source_spectrum

    ext = G23(Rv=r_v)
    wave = source_spectrum.waveset
    wave_inv_um = (1.0 / wave.to(u.micron).value)
    valid = (wave_inv_um >= ext.x_range[0]) & (wave_inv_um <= ext.x_range[1])
    flux = source_spectrum(wave).value
    factor = np.ones_like(flux)
    # Outside G23's valid range (~0.09-32 micron), leave unreddened -- none
    # of our bandpasses (0.32-11.5 micron) extend there, so this only
    # affects wavelengths that never enter a synthetic-photometry integral.
    factor[valid] = ext.extinguish(wave[valid], Av=av)
    return SourceSpectrum(Empirical1D, points=wave, lookup_table=flux * factor)


def synthetic_mag(source_spectrum, svo_id: str, zeropoint_jy: float) -> float:
    from synphot import Observation

    bandpass = _get_bandpass(svo_id)
    obs = Observation(source_spectrum, bandpass, binset=bandpass.waveset, force="extrap")
    flux_jy = obs.effstim(flux_unit="Jy").value
    return -2.5 * np.log10(flux_jy / zeropoint_jy)


def synthetic_flux_jy(source_spectrum, svo_id: str) -> float:
    from synphot import Observation

    bandpass = _get_bandpass(svo_id)
    obs = Observation(source_spectrum, bandpass, binset=bandpass.waveset, force="extrap")
    return float(obs.effstim(flux_unit="Jy").value)


# --- Extinction (Bayestar19) ---------------------------------------------------

_bayestar_query = None


def _get_bayestar_query(config: dict):
    global _bayestar_query
    if _bayestar_query is None:
        from dustmaps.bayestar import BayestarQuery, fetch

        ext_cfg = config["photosphere"]["extinction"]
        version = ext_cfg["dust_map"]
        try:
            _bayestar_query = BayestarQuery(version=version, max_samples=ext_cfg["max_samples"])
        except FileNotFoundError:
            logger.info("Bayestar dust map (%s) not found locally; downloading (~700 MB)", version)
            fetch(version=version)
            _bayestar_query = BayestarQuery(version=version, max_samples=ext_cfg["max_samples"])
    return _bayestar_query


def estimate_extinction(ra_deg: float, dec_deg: float, parallax_mas: float, config: dict) -> tuple[float, bool]:
    """Returns (av, qc_extinction_uncertain). Av is NaN when uncertain --
    no usable parallax, out of the Bayestar footprint (confirmed
    empirically 2026-07-20: no coverage south of dec ~ -30 deg), or a NaN
    map return for any other reason. NOT guessed in any of these cases."""
    if not np.isfinite(parallax_mas) or parallax_mas <= 0:
        return np.nan, True

    import astropy.units as u
    from astropy.coordinates import SkyCoord

    ext_cfg = config["photosphere"]["extinction"]
    distance_pc = 1000.0 / parallax_mas
    coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, distance=distance_pc * u.pc)
    query = _get_bayestar_query(config)
    # mode='best' (maximum-posterior point estimate) + max_samples=0, not
    # 'median' -- a deliberate tradeoff, not an invisible default. 'median'
    # requires loading the full posterior-samples array (confirmed live
    # 2026-07-20: ~6.2 GB peak even at max_samples=2, close to this
    # environment's limit); 'best' only needs the much smaller point-
    # estimate array, confirmed to drop peak memory to ~2.3 GB. This is a
    # different point estimate of the same posterior (maximum-posterior vs.
    # median of samples), not merely a performance switch -- but Av is
    # already treated cautiously everywhere else in this pipeline (never a
    # precise per-star correction, always paired with qc_extinction_uncertain
    # and, per RESEARCH_CONTEXT.md, an unverified map-to-Av coefficient), so
    # the expected impact of this choice is minor relative to those existing
    # caveats. Revisit if archive-scale runs show 'best' vs. 'median'
    # meaningfully changes which sources get flagged qc_high_extinction
    # downstream.
    map_value = float(query(coord, mode="best"))
    if not np.isfinite(map_value):
        return np.nan, True

    # NOT literally E(B-V) -- see module docstring re: this coefficient
    # being an approximate, not independently re-verified, conversion.
    bayestar_to_av_coefficient = 2.742
    av = map_value * bayestar_to_av_coefficient
    return av, False


# --- Fitting -------------------------------------------------------------------

_GRID_TEFF_BOUNDS = {
    # Confirmed live 2026-07-20 against the actual served grid files (not
    # assumed) -- see RESEARCH_CONTEXT.md.
    "kurucz": (3500.0, 50000.0),
    "phoenix": (2300.0, 12000.0),
}

# PHOENIX (Husser et al. 2013) grid Teff nodes -- expecto snaps to the
# nearest node rather than interpolating (confirmed from its own docstring),
# so unlike Kurucz/stsynphot (which interpolates and is cheap/local, no
# network cost per call), fitting against PHOENIX means the objective is
# actually a step function of Teff, not a continuous one. Running a
# continuous optimizer against it wastes evaluations (each a real network
# fetch of a new grid node, confirmed ~1-1.5s/node live 2026-07-20) probing
# points that fall between nodes for no benefit, and can also make a
# derivative-free continuous minimizer take more iterations than expected
# against a flat/stepped objective. So PHOENIX gets its own discrete local
# search instead (_discrete_local_search) -- confirmed via a live directory
# listing of the Göttingen server, not assumed: 100 K steps from 2300-7000 K,
# 200 K steps from 7000-12000 K.
PHOENIX_TEFF_NODES = np.array(
    list(range(2300, 7000, 100)) + list(range(7000, 12001, 200)), dtype=float
)


def _model_mags_at_teff(grid: str, teff: float, av: float, r_v: float, config: dict, bands: list[str]) -> dict[str, float]:
    spectrum = get_model_spectrum(grid, teff, config)
    reddened = redden_spectrum(spectrum, av, r_v)
    return {b: synthetic_mag(reddened, FIT_BAND_SVO_ID[b], FIT_BAND_ZEROPOINT_JY[b]) for b in bands}


def fit_teff(
    grid: str,
    observed_mags: dict[str, float],
    observed_errs: dict[str, float],
    av: float,
    r_v: float,
    config: dict,
    start_teff: float,
) -> dict:
    """Fits Teff for a fixed grid/log_g/Av. The flux-normalization free
    parameter is solved analytically as the inverse-variance-weighted mean
    magnitude offset at each trial Teff (a constant additive offset in
    magnitude space across all bands is exactly equivalent to a
    multiplicative flux-scale factor) -- see module docstring.

    Kurucz: continuous bounded search (stsynphot interpolates the grid).
    PHOENIX: discrete node-hopping search (see PHOENIX_TEFF_NODES) --
    starting from start_teff (the same rough BP-RP estimate used for grid
    selection) rather than an arbitrary point, so the local search
    converges in a handful of steps instead of needing a wide scan.

    Returns dict with teff, teff_err, norm_delta_mag, chi2, reduced_chi2,
    n_bands_used.
    """
    bands = [b for b in observed_mags if np.isfinite(observed_mags[b])]
    weights = {b: 1.0 / observed_errs[b] ** 2 for b in bands}
    w_total = sum(weights.values())

    def chi2_at(teff: float) -> float:
        synth = _model_mags_at_teff(grid, teff, av, r_v, config, bands)
        resid = {b: observed_mags[b] - synth[b] for b in bands}
        delta = sum(weights[b] * resid[b] for b in bands) / w_total
        return sum(weights[b] * (resid[b] - delta) ** 2 for b in bands)

    if grid == "kurucz":
        bounds = _GRID_TEFF_BOUNDS[grid]
        result = minimize_scalar(chi2_at, bounds=bounds, method="bounded")
        best_teff = float(result.x)
        chi2_min = float(result.fun)
        teff_err = _profile_teff_err_continuous(chi2_at, best_teff, chi2_min, bounds)
    elif grid == "phoenix":
        best_teff, chi2_min, node_cache = _discrete_local_search(PHOENIX_TEFF_NODES, chi2_at, start_teff)
        teff_err = _profile_teff_err_discrete(PHOENIX_TEFF_NODES, node_cache, best_teff, chi2_min)
    else:
        raise ValueError(f"Unknown grid: {grid!r}")

    synth_best = _model_mags_at_teff(grid, best_teff, av, r_v, config, bands)
    resid_best = {b: observed_mags[b] - synth_best[b] for b in bands}
    delta_best = sum(weights[b] * resid_best[b] for b in bands) / w_total

    n_bands = len(bands)
    reduced_chi2 = chi2_min / max(n_bands - 1, 1)
    return {
        "teff": best_teff,
        "teff_err": teff_err,
        "norm_delta_mag": delta_best,
        "chi2": chi2_min,
        "reduced_chi2": reduced_chi2,
        "n_bands_used": n_bands,
    }


def _profile_teff_err_continuous(chi2_at, best_teff: float, chi2_min: float, bounds: tuple[float, float]) -> float:
    """Approximate 1-sigma Teff uncertainty via a delta-chi2=1 profile-
    likelihood scan (standard technique for a single fit parameter) -- not
    a full covariance-matrix propagation. Kurucz only (continuous grid)."""
    lo, hi = bounds
    half_widths = []
    for direction in (-1, 1):
        step = max(abs(best_teff) * 0.01, 10.0)
        teff = best_teff
        prev_teff, prev_chi2 = best_teff, chi2_min
        for _ in range(40):
            teff = teff + direction * step
            if teff <= lo or teff >= hi:
                half_widths.append(abs(teff - best_teff))
                break
            chi2 = chi2_at(teff)
            if chi2 - chi2_min >= 1.0:
                # linear interpolation between (prev_teff, prev_chi2) and (teff, chi2)
                frac = (1.0 - (prev_chi2 - chi2_min)) / (chi2 - prev_chi2)
                crossing = prev_teff + direction * step * frac
                half_widths.append(abs(crossing - best_teff))
                break
            prev_teff, prev_chi2 = teff, chi2
            step *= 1.3
        else:
            half_widths.append(abs(teff - best_teff))
    return float(np.mean(half_widths))


def _discrete_local_search(nodes: np.ndarray, chi2_at, start_teff: float) -> tuple[float, float, dict]:
    """Hill-climbs across a sorted array of discrete grid nodes from the
    node nearest start_teff, moving to whichever immediate neighbor
    improves chi2 until neither does. Assumes chi2(Teff) is unimodal across
    the grid (single photosphere fit, not a multi-component SED) -- a
    reasonable assumption here, not independently verified for every
    possible star. Returns (best_teff, chi2_min, cache) where cache maps
    node index -> chi2, so the error-bar estimate below can reuse every
    evaluation already made instead of re-querying the grid."""
    cache: dict[int, float] = {}

    def ev(i: int) -> float:
        if i not in cache:
            cache[i] = chi2_at(float(nodes[i]))
        return cache[i]

    cur = int(np.argmin(np.abs(nodes - start_teff)))
    while True:
        candidates = [j for j in (cur - 1, cur + 1) if 0 <= j < len(nodes)]
        best_j, best_val = cur, ev(cur)
        for j in candidates:
            v = ev(j)
            if v < best_val:
                best_j, best_val = j, v
        if best_j == cur:
            break
        cur = best_j
    return float(nodes[cur]), cache[cur], cache


def _profile_teff_err_discrete(nodes: np.ndarray, cache: dict, best_teff: float, chi2_min: float) -> float:
    """Discrete analogue of the delta-chi2=1 profile-likelihood error: walks
    outward from the best node in each direction (reusing cached
    evaluations where the local search already visited them) until chi2
    crosses chi2_min + 1, linearly interpolating between the last two
    nodes. Floors at half the local node spacing, since that's the grid's
    own resolution limit regardless of how well-constrained the fit is."""
    best_i = int(np.argmin(np.abs(nodes - best_teff)))

    half_widths = []
    for direction in (-1, 1):
        i = best_i
        prev_chi2 = chi2_min
        crossed = False
        while 0 <= i + direction < len(nodes):
            i += direction
            if i not in cache:
                # Not visited by the local search -- treat the boundary of
                # what was actually explored as the uncertainty edge rather
                # than triggering more (potentially networked) evaluations
                # just to refine an error bar.
                half_widths.append(abs(nodes[i] - best_teff))
                crossed = True
                break
            chi2 = cache[i]
            if chi2 - chi2_min >= 1.0:
                frac = (1.0 - (prev_chi2 - chi2_min)) / (chi2 - prev_chi2)
                node_spacing = abs(nodes[i] - nodes[i - direction])
                crossing = nodes[i - direction] + direction * node_spacing * frac
                half_widths.append(abs(crossing - best_teff))
                crossed = True
                break
            prev_chi2 = chi2
        if not crossed:
            half_widths.append(abs(nodes[i] - best_teff))
    node_spacing_here = np.min(np.diff(nodes)) if len(nodes) > 1 else 100.0
    return float(max(np.mean(half_widths), node_spacing_here / 2.0))


def has_mid_ir_coverage(grid: str) -> bool:
    """PHOENIX (Husser et al. 2013, via expecto) spectra only extend to
    ~5.5 micron -- confirmed live 2026-07-20 -- fully short of BOTH MIRI
    bands (F770W starts at 6.2 micron), i.e. genuinely disjoint, not just a
    thin extrapolation margin (synphot raises DisjointError outright, it
    doesn't silently extrapolate). Kurucz (ck04models) spans into the far-IR
    and covers both MIRI bands. This means any star whose PRIMARY grid is
    PHOENIX (Teff <= grids.cool_teff_max_k, i.e. cool dwarfs/giants/brown
    dwarfs) has no NATIVE photosphere-predicted MIRI flux -- see
    rj_extrapolation_spectrum for the substitute used instead, and
    RESEARCH_CONTEXT.md for why that substitute is not yet equal-confidence
    to a native grid prediction (qc_rj_extrapolated)."""
    return grid == "kurucz"


# Wavelength window (micron) used to anchor the RJ/blackbody extrapolation
# to the PHOENIX model's own flux -- the reddest slice of its available
# range (~5.5 micron edge), averaged rather than a single point to reduce
# numerical noise from the model's native wavelength sampling.
_RJ_ANCHOR_WINDOW_UM = (5.0, 5.5)


def rj_extrapolation_spectrum(teff: float, config: dict):
    """Builds a substitute spectrum for PHOENIX-primary stars whose native
    grid doesn't reach the MIRI bands (see has_mid_ir_coverage): a pure
    blackbody at the fit's own Teff, scaled so its flux matches the
    UNREDDENED PHOENIX model's own flux at the reddest window it actually
    computes (_RJ_ANCHOR_WINDOW_UM), rather than an independently-normalized
    blackbody. This keeps continuity with the actually-computed part of the
    spectrum and only extrapolates the last ~1.4-2x in wavelength, in the
    regime (Rayleigh-Jeans tail) where a blackbody is the weakest
    approximation of all the ways it could be wrong -- but real cool-star
    atmospheres can still have molecular opacity structure (e.g. water
    vapor bands) that persists into the mid-IR and a pure blackbody won't
    capture. See RESEARCH_CONTEXT.md: qc_rj_extrapolated sources are a
    named prerequisite for excess.py, not yet validated against real cool
    stars with known mid-IR photometry, and must not be treated as
    equal-confidence to a native grid prediction until that validation
    produces a real error-inflation factor.

    Returns a raw (unreddened, not yet normalized-to-observed) synphot
    SourceSpectrum, in the same convention as get_model_spectrum -- caller
    still applies redden_spectrum and the norm_delta_mag flux scale.
    """
    import astropy.units as u
    from synphot import SourceSpectrum
    from synphot.models import BlackBody1D, Empirical1D

    phoenix_spectrum = get_model_spectrum("phoenix", teff, config)
    wave = phoenix_spectrum.waveset
    lo, hi = _RJ_ANCHOR_WINDOW_UM
    window = (wave >= lo * u.micron) & (wave <= hi * u.micron)
    anchor_wave = wave[window]
    phoenix_anchor_flux = float(np.mean(phoenix_spectrum(anchor_wave).value))

    blackbody = SourceSpectrum(BlackBody1D, temperature=teff)
    bb_anchor_flux = float(np.mean(blackbody(anchor_wave).value))
    shape_match_scale = phoenix_anchor_flux / bb_anchor_flux

    # SourceSpectrum(BlackBody1D, ...)'s own default .waveset is NOT fixed
    # -- it shrinks as Teff rises (confirmed live: ~9.1 micron upper bound
    # at 3500 K vs MIRI's own 11.5 micron upper edge, and it gets narrower
    # still for any higher Teff, e.g. the perturbed teff+teff_err used for
    # error propagation below). redden_spectrum re-tabulates onto
    # source_spectrum.waveset, so leaving this as the raw analytic
    # BlackBody1D would silently truncate the reddened spectrum's
    # wavelength coverage and risk exactly the kind of DisjointError this
    # function exists to avoid (confirmed live -- this crashed for a real
    # cool-bucket star before this fix). Re-tabulating onto a fixed,
    # Teff-independent grid wide enough for both MIRI bands with margin
    # (0.3-15 micron) fixes this regardless of Teff.
    extrap_wave = np.geomspace(0.3, 15.0, 2000) * u.micron
    scaled_flux = blackbody(extrap_wave).value * shape_match_scale
    return SourceSpectrum(Empirical1D, points=extrap_wave, lookup_table=scaled_flux)


def predict_miri_flux(grid: str, teff: float, norm_delta_mag: float, av: float, r_v: float, config: dict) -> tuple[dict[str, float], bool]:
    """Predicted photosphere flux density (Jy) at each MIRI band, for the
    best-fit (grid, teff, norm, Av). Returns (predicted, is_rj_extrapolated)
    -- is_rj_extrapolated is True whenever the grid has no native MIRI
    coverage (see has_mid_ir_coverage) and rj_extrapolation_spectrum was
    used as a substitute instead."""
    is_rj_extrapolated = not has_mid_ir_coverage(grid)
    spectrum = rj_extrapolation_spectrum(teff, config) if is_rj_extrapolated else get_model_spectrum(grid, teff, config)
    reddened = redden_spectrum(spectrum, av, r_v)
    scale = 10 ** (-norm_delta_mag / 2.5)
    predicted = {band: scale * synthetic_flux_jy(reddened, svo_id) for band, svo_id in MIRI_BAND_SVO_ID.items()}
    return predicted, is_rj_extrapolated


# --- Per-star orchestration ---------------------------------------------------


def fit_star(row: dict, config: dict) -> dict:
    """Runs the full photosphere fit for one star (one row of the a0 star
    table, as a plain dict of column -> value). Returns a dict of a1
    column -> value for this star; see assemble_level_a1 for the schema."""
    out: dict = {}

    target_classification = row.get("target_classification", "")
    if is_white_dwarf(target_classification, config):
        out["qc_no_photosphere_grid"] = 1
        out["qc_pms_veiling_risk"] = 0
        out["qc_possible_binary"] = 0
        out["qc_grid_disagreement"] = 0
        out["qc_extinction_uncertain"] = 0
        out["qc_poor_photosphere_fit"] = 0
        out["qc_starved_photosphere_fit"] = 0
        out["qc_no_mid_ir_model_coverage"] = 0
        out["qc_rj_extrapolated"] = 0
        out["photosphere_teff"] = np.nan
        out["photosphere_teff_err"] = np.nan
        out["photosphere_model_grid"] = ""
        out["photosphere_av"] = np.nan
        out["chi2"] = np.nan
        out["reduced_chi2"] = np.nan
        out["n_bands_used"] = 0
        out["n_effective_bands"] = 0
        for band in MIRI_BAND_SVO_ID:
            out[f"predicted_flux_{band}"] = np.nan
            out[f"predicted_flux_{band}_err"] = np.nan
        return out
    out["qc_no_photosphere_grid"] = 0

    out["qc_pms_veiling_risk"] = int(is_pms_veiling_risk(target_classification, config))

    ruwe = row.get("gaia_ruwe", np.nan)
    non_single_star = row.get("gaia_non_single_star", np.nan)
    ruwe_threshold = config["photosphere"]["binarity"]["ruwe_threshold"]
    high_ruwe = np.isfinite(ruwe) and ruwe > ruwe_threshold
    flagged_non_single = np.isfinite(non_single_star) and non_single_star != 0
    out["qc_possible_binary"] = int(high_ruwe or flagged_non_single)

    av, extinction_uncertain = estimate_extinction(
        row["gaia_ra"], row["gaia_dec"], row.get("gaia_parallax", np.nan), config
    )
    out["qc_extinction_uncertain"] = int(extinction_uncertain)
    out["photosphere_av"] = av
    av_for_fit = 0.0 if not np.isfinite(av) else av
    r_v = config["photosphere"]["extinction"]["r_v"]

    observed_mags = {b: row.get(FIT_BAND_MAG_COL[b], np.nan) for b in FIT_BAND_NAMES}
    observed_errs = {
        b: (row.get(FIT_BAND_MAG_ERR_COL[b], np.nan) if FIT_BAND_MAG_ERR_COL[b] else np.nan)
        for b in FIT_BAND_NAMES
    }
    for b in FIT_BAND_NAMES:
        if not np.isfinite(observed_errs[b]) or observed_errs[b] <= 0:
            observed_errs[b] = DEFAULT_MAG_ERR

    n_available_bands = sum(1 for b in FIT_BAND_NAMES if np.isfinite(observed_mags[b]))
    n_effective_bands = count_effective_bands(observed_mags)
    out["n_effective_bands"] = n_effective_bands
    if n_available_bands < 2:
        # Not enough photometry to constrain both Teff and normalization
        # (e.g. no Gaia match at all -- qc_no_gaia_match upstream already
        # explains why). Not a grid-choice problem, so qc_no_photosphere_grid
        # stays 0; qc_poor_photosphere_fit=1 marks the fit as untrustworthy
        # rather than attempting one with too little data to constrain it.
        # qc_starved_photosphere_fit=1 too -- <2 raw bands is trivially also
        # <min_effective_bands, no fit was even attempted here.
        out["qc_grid_disagreement"] = 0
        out["photosphere_teff"] = np.nan
        out["photosphere_teff_err"] = np.nan
        out["photosphere_model_grid"] = ""
        out["chi2"] = np.nan
        out["reduced_chi2"] = np.nan
        out["n_bands_used"] = n_available_bands
        out["qc_poor_photosphere_fit"] = 1
        out["qc_starved_photosphere_fit"] = 1
        out["qc_no_mid_ir_model_coverage"] = 0
        out["qc_rj_extrapolated"] = 0
        for band in MIRI_BAND_SVO_ID:
            out[f"predicted_flux_{band}"] = np.nan
            out[f"predicted_flux_{band}_err"] = np.nan
        return out

    bp_rp = row.get("gaia_phot_bp_mean_mag", np.nan) - row.get("gaia_phot_rp_mean_mag", np.nan)
    teff_rough = rough_teff_from_bp_rp(bp_rp) if np.isfinite(bp_rp) else 5500.0
    primary_grid, grids_to_fit = select_grids(teff_rough, config)

    fits = {
        g: fit_teff(g, observed_mags, observed_errs, av_for_fit, r_v, config, start_teff=teff_rough)
        for g in grids_to_fit
    }
    primary_fit = fits[primary_grid]

    qc_grid_disagreement = 0
    if len(fits) > 1:
        other_grid = [g for g in fits if g != primary_grid][0]
        disagreement_cfg = config["photosphere"]["grid_disagreement"]
        threshold = max(disagreement_cfg["abs_floor_k"], disagreement_cfg["rel_frac"] * primary_fit["teff"])
        if abs(primary_fit["teff"] - fits[other_grid]["teff"]) > threshold:
            qc_grid_disagreement = 1
    out["qc_grid_disagreement"] = qc_grid_disagreement

    out["photosphere_teff"] = primary_fit["teff"]
    out["photosphere_teff_err"] = primary_fit["teff_err"]
    out["photosphere_model_grid"] = primary_grid
    out["chi2"] = primary_fit["chi2"]
    out["reduced_chi2"] = primary_fit["reduced_chi2"]
    out["n_bands_used"] = primary_fit["n_bands_used"]

    # qc_starved_photosphere_fit (set 2026-07-23, see module docstring for
    # count_effective_bands/_CORRELATED_BAND_GROUPS): a genuinely separate
    # check from qc_poor_photosphere_fit below -- a starved fit (e.g. 3
    # correlated Gaia-only bands against a 2-free-parameter model) can
    # report an excellent reduced_chi2 while still being essentially
    # unconstrained, so a good chi2 alone does not clear this gate.
    min_effective_bands = config["photosphere"]["min_effective_bands"]
    out["qc_starved_photosphere_fit"] = int(n_effective_bands < min_effective_bands)

    poor_fit_threshold = config["photosphere"]["poor_fit_reduced_chi2_threshold"]
    out["qc_poor_photosphere_fit"] = int(primary_fit["reduced_chi2"] > poor_fit_threshold)

    out["qc_no_mid_ir_model_coverage"] = int(not has_mid_ir_coverage(primary_grid))

    predicted, is_rj_extrapolated = predict_miri_flux(
        primary_grid, primary_fit["teff"], primary_fit["norm_delta_mag"], av_for_fit, r_v, config
    )
    out["qc_rj_extrapolated"] = int(is_rj_extrapolated)
    # Predicted-flux uncertainty via a simple 1-sigma Teff perturbation
    # (linear propagation would need the fit Jacobian; this reuses the
    # profile-likelihood teff_err already computed instead of a second
    # estimator) -- an approximation, not a full error budget. For
    # qc_rj_extrapolated stars this captures Teff sensitivity only, NOT the
    # additional systematic from approximating the photosphere as a
    # blackbody in the extrapolated region -- see rj_extrapolation_spectrum
    # docstring and RESEARCH_CONTEXT.md: these error bars are a lower bound
    # until the WISE/Spitzer validation produces a real inflation factor.
    predicted_hi, _ = predict_miri_flux(
        primary_grid,
        primary_fit["teff"] + primary_fit["teff_err"],
        primary_fit["norm_delta_mag"],
        av_for_fit,
        r_v,
        config,
    )
    for band in MIRI_BAND_SVO_ID:
        out[f"predicted_flux_{band}"] = predicted[band]
        out[f"predicted_flux_{band}_err"] = abs(predicted_hi[band] - predicted[band])

    return out


# --- Assembly and output -------------------------------------------------------


def assemble_level_a1(a0_ds: xr.Dataset, config: dict) -> xr.Dataset:
    """Runs fit_star for every star in the a0 Dataset and packs the results
    into an xarray.Dataset (data level a1), one row per star (same 'star'
    dimension/coordinate as a0)."""
    n = a0_ds.sizes["star"]
    rows = []
    for i in range(n):
        row = {name: a0_ds[name].values[i] for name in a0_ds.data_vars}
        rows.append(fit_star(row, config))
        if (i + 1) % 25 == 0 or (i + 1) == n:
            logger.info("Fit %d/%d stars", i + 1, n)

    # Union of keys across all rows, not just rows[0] -- every fit_star
    # branch is expected to return the same keys, but deriving the schema
    # from a single row would silently drop a column if some branch ever
    # drifts out of sync (e.g. a new flag added to one branch but not
    # another) rather than erroring, which is exactly the kind of silent
    # gap this project's qc_* convention exists to avoid.
    columns = {c for r in rows for c in r}
    data_vars = {}
    for col in columns:
        values = [r.get(col, np.nan) for r in rows]
        if col == "photosphere_model_grid":
            data_vars[col] = ("star", np.asarray(values, dtype="U16"))
        elif col.startswith("qc_"):
            # int32, matching retriever.py's qc_* flag convention
            data_vars[col] = ("star", np.asarray(values, dtype=np.int32))
        else:
            data_vars[col] = ("star", np.asarray(values, dtype=float))

    ds = xr.Dataset(data_vars=data_vars, coords={"star": a0_ds["star"].values})
    ds["star_id"] = ("star", a0_ds["star_id"].values)
    ds["gaia_source_id"] = ("star", a0_ds["gaia_source_id"].values)
    ds["photosphere_teff"].attrs["units"] = "K"
    ds["photosphere_teff_err"].attrs["units"] = "K"
    ds["photosphere_av"].attrs["units"] = "mag"
    for band in MIRI_BAND_SVO_ID:
        ds[f"predicted_flux_{band}"].attrs["units"] = "Jy"
        ds[f"predicted_flux_{band}_err"].attrs["units"] = "Jy"
    ds.attrs["pipeline_version"] = __version__
    ds.attrs["kurucz_grid"] = config["photosphere"]["grids"]["kurucz_grid"]
    ds.attrs["dust_map"] = config["photosphere"]["extinction"]["dust_map"]
    ds.attrs["reddening_law"] = "G23 (Gordon et al. 2023)"
    return ds


def save_level_a1(ds: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path)
    logger.info("Saved level a1 dataset to %s (%d stars)", path, ds.sizes["star"])


# --- Orchestration -------------------------------------------------------------


def run(config: dict, a0_path: Path, output_path: Path) -> xr.Dataset:
    """Runs the full photosphere stage: load a0 -> ensure grids -> fit every
    star -> save a1."""
    cdbs_dir = Path(config["photosphere"]["grids"]["cdbs_dir"])
    ensure_kurucz_grid(cdbs_dir)

    a0_ds = xr.open_dataset(a0_path)
    a1_ds = assemble_level_a1(a0_ds, config)
    save_level_a1(a1_ds, output_path)
    return a1_ds
