"""
pipeline.miri_photometry

Stage 2 of the jwst-ir-excess pipeline (see RESEARCH_CONTEXT.md for the
5-stage architecture): extracts the actual observed F770W/F1000W
point-source flux for each star from the `_i2d` mosaics retriever.py
already downloaded. This is the excess-critical photometry -- excess.py
must NOT fall back to `_cat.ecsv`'s automated aperture photometry (see
RESEARCH_CONTEXT.md Decision Log, 2026-07-15, informed by Libralato et al.
2024) -- data level a0 -> this module's own dataset, joined by `star`
against a0/a1 in excess.py rather than folded back into a0 itself.

Key design decisions -- see RESEARCH_CONTEXT.md Decision Log (2026-07-21
entries) for the full discussion and live-verification results:

- **PRIMARY measurement is model-PSF fitting**, not aperture photometry:
  `stpsf` (the renamed `webbpsf`) generates a MIRI PSF; `photutils.psf`'s
  `ImagePSF` + `PSFPhotometry` fit it against the real mosaic at each
  star's known position. This is a simulated PSF, not an empirically-built
  one like Libralato et al.'s actual ePSF -- a real precision gap versus
  their method, stated plainly rather than presented as equivalent (see
  Decision Log). Careful aperture photometry (`aperture_flux_{band}`) is
  retained as a parallel per-source cross-check
  (`qc_psf_aperture_disagreement_{band}`), not the primary measurement.
- **`observed_flux_{band}` is EE-corrected, not a raw PSF-fit flux.** A
  live smoke test (2026-07-21) found the finite PSF-fit stamp misses real
  flux in MIRI's broad diffraction wings -- a systematic ~0.70-0.82x
  deficit relative to `_cat.ecsv`'s own aperture-corrected flux, present
  across every source tested, not a rare edge case. Left uncorrected this
  would silently bias every `observed_flux_{band}` low before excess.py
  ever compares it against a predicted photosphere flux -- exactly the
  wrong kind of error for an excess-detection pipeline (suppresses real
  excess, and can fabricate spurious deficits). Both `observed_flux_{band}`
  (PSF-fit) and `aperture_flux_{band}` (cross-check) are therefore
  multiplied by the same encircled-energy aperture-correction factor
  (`apcorr`) from the JWST pipeline's own CRDS APCORR reference file --
  the same file the pipeline's `source_catalog` step uses internally to
  produce `_cat.ecsv`'s `aper_total_flux`. Confirmed via an exact numerical
  round-trip against real archive data: `aper70_flux * apcorr(EE=0.7) ==
  aper_total_flux` to 4 significant figures for a real test star. The PSF
  stamp and the aperture cross-check both use the SAME EE-fraction row
  (radius, sky annulus, apcorr multiplier) from the same table, so the
  correction is not an ad hoc guess at the finite stamp's effective EE
  fraction -- it's tied directly to the one relationship that was actually
  validated against real data.
- **This module never reads `_cat.ecsv`.** Source positions come only from
  a0's `miri_ra_{band}`/`miri_dec_{band}` columns, which retriever.py
  already derived via a Gaia-anchored cross-match (`star_id`/
  `gaia_source_id`), not from `_cat.ecsv`'s `label` column. This is a
  deliberate, structural choice, not an oversight: `_cat.ecsv`'s `label` is
  a per-image, per-catalog detection index with NO cross-filter meaning
  (confirmed the hard way during the 2026-07-21 smoke test -- comparing
  "label 6" across F770W and F1000W catalogs turned out to compare two
  unrelated stars ~162 arcsec apart; see RESEARCH_CONTEXT.md's dedicated
  `label` gotcha entry). Never use `_cat.ecsv`'s `label` as a join key
  anywhere in this module, or downstream of it -- only `star_id`/
  `gaia_source_id` (as already established by retriever.py's
  `pivot_to_one_row_per_star`) or an explicit sky-position cross-match are
  safe.
- **`qc_psf_fit_failed_{band}` is not a hypothetical safeguard.** The
  2026-07-21 smoke test hit a real, independently-corroborated case: a
  source that fit cleanly in F770W failed to converge
  (`photutils.psf.PSFPhotometry`'s own `flags != 0`) in F1000W for the
  PN-TC-1 field (a real planetary nebula) -- and the pipeline's own
  automated `_cat.ecsv` catalog independently flagged the same position
  `is_extended=True` with a nonsensical negative `aper_total_flux`. Two
  independent measurements agreeing that a position isn't a clean point
  source in that band is exactly the case this flag exists to catch, not a
  defect in the chosen method. See `test_flags_indicate_fit_failure` for
  the pure-logic regression test and RESEARCH_CONTEXT.md for the full
  finding.
- **Reference-data provenance:** the CRDS APCORR reference file
  (`jwst_miri_apcorr_0014.fits`, pinned rather than queried live -- see
  `config/pipeline_config.yaml`) is `PEDIGREE INFLIGHT`, built from
  encircled-energy profiles measured with real flight data and normalized
  to infinity via WebbPSF (per the file's own `HISTORY`) -- a stronger
  basis than this module's own PSF-fit path, which IS purely `stpsf`-model
  based. `stpsf` itself auto-downloads its own reference data (~129 MB) on
  first use; this module does not override that caching behavior.
- **`qc_psf_aperture_disagreement_{band}` splits into
  `qc_psf_disagreement_faint_{band}` / `_complex_{band}`.** A three-field
  investigation (2026-07-21: PN-TC-1, a deliberately quiet CONTROLFIELD,
  and the dense NGC-602 cluster -- see RESEARCH_CONTEXT.md) found the
  disagreement rate varies 15-69% by field, tracking field character (not
  a miscalibrated threshold), and traced it to two physically distinct
  drivers: a faint/low-SNR marginal-detection population (dominant in
  PN-TC-1/CONTROLFIELD) and a bright/high-SNR population where the
  disagreement can't be explained by photon noise -- likely blending or a
  PSF-modeling mismatch, concentrated in NGC-602's dense cluster core
  (its single most extreme case: SNR=1425, obviously not noise-limited).
  `classify_disagreement` splits on SNR relative to
  `miri_photometry.disagreement.snr_threshold` (default 50.0) to make this
  distinction available without re-deriving the investigation.
  `qc_psf_aperture_disagreement_{band}` itself is unchanged -- kept as a
  general-purpose caution flag for backward compatibility (it's the
  logical OR of the two new sub-flags).
- **Known simplifications, stated rather than hidden** (see
  RESEARCH_CONTEXT.md for the full list): `qc_saturated_{band}` is a
  non-finite-pixel proxy, not true DQ-bit-based saturation detection (the
  `_i2d` mosaic carries no DQ extension); `qc_crowded_source_{band}` checks
  against other a0 stars sharing the same mosaic (Gaia-matched or not --
  retriever.py's pivot keeps unmatched detections as singleton a0 rows
  too), but not every raw MIRI detection outside a0's own population;
  `qc_psf_disagreement_faint`/`_complex`'s SNR discriminator uses
  `photutils.psf.PSFPhotometry`'s formal (photon-noise-only) fit
  uncertainty, which does not capture systematics like background
  structure or blending -- an imperfect proxy, not a full error budget;
  per-star mosaic I/O and PSF generation are not optimized for archive
  scale (same caveat as photosphere.py's per-star fit runtime).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import astropy.units as u
import numpy as np
import xarray as xr
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.stats import SigmaClip
from astropy.table import Table
from astropy.wcs import WCS

from pipeline import __version__

logger = logging.getLogger(__name__)


# --- APCORR reference file (CRDS) --------------------------------------------

APCORR_REFERENCE_FILENAME = "jwst_miri_apcorr_0014.fits"
APCORR_REFERENCE_URL = (
    "https://jwst-crds.stsci.edu/unchecked_get/references/jwst/" + APCORR_REFERENCE_FILENAME
)


def ensure_apcorr_reference(cache_dir: Path) -> Path:
    """Downloads the pinned CRDS MIRI imaging APCORR reference file if not
    already present locally (~23 KB). Mirrors photosphere.py's
    ensure_kurucz_grid download-if-missing pattern. See module docstring
    for why this is pinned rather than queried live via CRDS's JSON-RPC API."""
    import requests

    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / APCORR_REFERENCE_FILENAME
    if path.exists():
        return path
    logger.info("MIRI APCORR reference file not found locally; downloading to %s", path)
    resp = requests.get(APCORR_REFERENCE_URL, timeout=30)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def load_apcorr_table(path: Path) -> Table:
    return Table.read(path, hdu="APCORR")


def select_apcorr_row(table: Table, filt: str, subarray: str, ee_fraction: float) -> dict:
    """Returns the single APCORR table row (radius, apcorr multiplier, sky
    annulus) for the given filter/subarray/EE-fraction, as a plain dict.
    Raises if the reference file doesn't cover this combination -- an
    unexpectedly missing row should be loud, not silently NaN, since it
    would otherwise silently disable EE correction for that filter."""
    filters = np.char.strip(np.asarray(table["filter"]).astype(str))
    subarrays = np.char.strip(np.asarray(table["subarray"]).astype(str))
    mask = (
        (filters == filt)
        & (subarrays == subarray)
        & np.isclose(np.asarray(table["eefraction"], dtype=float), ee_fraction, atol=1e-6)
    )
    rows = table[mask]
    if len(rows) != 1:
        raise ValueError(
            f"Expected exactly 1 APCORR row for filter={filt!r}, subarray={subarray!r}, "
            f"eefraction={ee_fraction} -- found {len(rows)}. Reference file may not cover "
            "this filter/subarray/EE-fraction combination."
        )
    row = rows[0]
    return {
        "radius_px": float(row["radius"]),
        "apcorr": float(row["apcorr"]),
        "skyin_px": float(row["skyin"]),
        "skyout_px": float(row["skyout"]),
    }


# --- PSF generation (stpsf) ---------------------------------------------------


@lru_cache(maxsize=None)
def _get_miri_psf_template(filt: str, fov_pixels: int) -> np.ndarray:
    """Returns a native-pixel-scale (DET_DIST, distortion-included),
    unit-normalized (sum=1) MIRI PSF stamp for `filt`, from `stpsf`.
    Confirmed live 2026-07-21 to match the `_i2d` mosaic's own WCS pixel
    scale to within ~0.1% for F770W/F1000W FULL-subarray data -- see
    RESEARCH_CONTEXT.md. `stpsf` manages its own reference-data caching
    (auto-downloads ~129 MB on first use); this function does not override
    that."""
    import stpsf

    m = stpsf.MIRI()
    m.filter = filt
    psf_hdul = m.calc_psf(fov_pixels=fov_pixels, oversample=1)
    template = psf_hdul["DET_DIST"].data.astype(float)
    return template / template.sum()


def stamp_half_width_px(radius_px: float, margin_px: int) -> int:
    """Half-width (pixels) of the PSF-fit stamp / fit_shape, sized to
    comfortably contain the EE-defining aperture radius plus a margin for
    the fit to have working room. Pure/deterministic -- see
    test_stamp_half_width_px."""
    return int(np.ceil(radius_px)) + margin_px


# --- Mosaic I/O (cached per path within one run) ------------------------------


def get_mosaic(path: str, cache: dict) -> dict:
    """Opens (or returns from cache) a mosaic's SCI/ERR arrays, WCS, and
    PIXAR_SR (sr/pixel, for converting MJy/sr -> Jy). Caches by path so a
    field with many stars doesn't reopen the same FITS file per star."""
    if path not in cache:
        hdul = fits.open(path)
        cache[path] = {
            "hdul": hdul,
            "sci": hdul["SCI"].data.astype(float),
            "err": hdul["ERR"].data.astype(float),
            "wcs": WCS(hdul["SCI"].header),
            "pixar_sr": float(hdul["SCI"].header["PIXAR_SR"]),
        }
    return cache[path]


def close_mosaic_cache(cache: dict) -> None:
    for entry in cache.values():
        entry["hdul"].close()


def sky_to_pixel(ra_deg: float, dec_deg: float, wcs: WCS) -> tuple[float, float]:
    x, y = wcs.world_to_pixel(SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg))
    return float(x), float(y)


# --- Geometry / QC pure helpers ------------------------------------------------


def is_within_mosaic(x0: float, y0: float, shape: tuple[int, int], half_width: int) -> bool:
    ny, nx = shape
    return (half_width <= x0 <= nx - 1 - half_width) and (half_width <= y0 <= ny - 1 - half_width)


def has_nonfinite_pixel(sci: np.ndarray, x0: float, y0: float, half_width: int) -> bool:
    """KNOWN SIMPLIFICATION (see module docstring): a proxy for saturation,
    not true DQ-bit-based detection -- the `_i2d` mosaic carries no DQ
    extension to check directly."""
    ny, nx = sci.shape
    xlo, xhi = max(int(round(x0 - half_width)), 0), min(int(round(x0 + half_width)) + 1, nx)
    ylo, yhi = max(int(round(y0 - half_width)), 0), min(int(round(y0 + half_width)) + 1, ny)
    region = sci[ylo:yhi, xlo:xhi]
    return bool(region.size == 0 or np.any(~np.isfinite(region)))


def has_close_neighbor(
    x0: float, y0: float, other_positions: list[tuple[float, float]], min_separation_px: float
) -> bool:
    """KNOWN SIMPLIFICATION (see module docstring): checks only against
    other Gaia-matched a0 stars in the same mosaic, not every raw MIRI
    detection."""
    if not other_positions:
        return False
    dx = np.array([p[0] for p in other_positions]) - x0
    dy = np.array([p[1] for p in other_positions]) - y0
    return bool(np.any(np.hypot(dx, dy) < min_separation_px))


def flags_indicate_fit_failure(flags: int) -> bool:
    """True if photutils.psf.PSFPhotometry's own `flags` column indicates
    the fit did not converge cleanly (flags != 0 -- see photutils docs for
    the bit meanings). Validated live 2026-07-21 against a real case: a
    source that fit cleanly in F770W returned flags=12 in F1000W for the
    PN-TC-1 field, and the pipeline's own automated _cat.ecsv catalog
    independently flagged the same position is_extended=True with a
    negative aper_total_flux -- two independent measurements agreeing the
    position isn't a clean point source in that band. See
    RESEARCH_CONTEXT.md for the full finding."""
    return int(flags) != 0


def psf_aperture_disagreement(
    psf_flux_jy: float, aperture_flux_jy: float, abs_floor_jy: float, rel_frac: float
) -> bool:
    threshold = max(abs_floor_jy, rel_frac * abs(psf_flux_jy))
    return bool(np.isfinite(psf_flux_jy) and np.isfinite(aperture_flux_jy) and abs(psf_flux_jy - aperture_flux_jy) > threshold)


def classify_disagreement(disagree: bool, snr: float, snr_threshold: float) -> tuple[bool, bool]:
    """Splits a `qc_psf_aperture_disagreement` flag into two physically
    distinct sub-flags, using the SNR-based discriminator derived from the
    2026-07-21 three-field investigation (see RESEARCH_CONTEXT.md):

    - `qc_psf_disagreement_faint`: SNR below `snr_threshold` -- photon
      noise plausibly explains the disagreement on its own (the dominant
      mechanism found in PN-TC-1 and CONTROLFIELD, where flagged sources
      were consistently 3-4x fainter with ~4x lower SNR than clean ones).
    - `qc_psf_disagreement_complex`: SNR at or above `snr_threshold`, OR
      SNR itself isn't computable (non-finite/zero error) -- photon noise
      alone cannot explain the disagreement, so something structural
      (blending, an unresolved companion, or PSF-modeling mismatch such as
      MIRI's known F770W/F560W cruciform gap) is the more likely driver.
      Concentrated in dense clusters (NGC-602) in the investigation, but
      not exclusively -- classified per-source, not per-field, since even
      PN-TC-1/CONTROLFIELD's flagged populations had a (smaller) high-SNR
      tail. The non-finite-SNR fallback errs toward this bucket rather than
      silently treating an uncomputable SNR as "faint."

    Returns (is_faint, is_complex) -- both False if `disagree` is False.
    Both booleans, not one tri-state flag, so a source can never end up
    ambiguous between "not disagreeing" and "disagreeing but unclassified."

    `snr_threshold` (config: miri_photometry.disagreement.snr_threshold,
    default 50.0) is a stated compromise grounded in real data, not a
    precisely derived boundary: PN-TC-1's entire flagged population (
    independently confirmed faint-driven, by consistently lower flux/SNR
    than clean sources in that field) topped out at SNR=29.2, while the
    real complex-driver example that motivated this split (NGC-602's
    brightest source, disagreement ratio 1.57x) had SNR=1425 -- two
    orders of magnitude apart. The exact cutoff in between is not
    rigorously derived, same status as `rel_frac`/`abs_floor_jy` above."""
    if not disagree:
        return False, False
    if not np.isfinite(snr):
        return False, True
    is_faint = snr < snr_threshold
    return is_faint, not is_faint


# --- Photometry (PSF fit + aperture cross-check) ------------------------------


def fit_psf_flux(
    sci: np.ndarray,
    err: np.ndarray,
    x0: float,
    y0: float,
    psf_template: np.ndarray,
    fit_shape: tuple[int, int],
    aperture_radius_px: float,
    skyin_px: float,
    skyout_px: float,
) -> dict:
    """Fits the given (unit-normalized) PSF template to the mosaic at
    (x0, y0) via photutils.psf.PSFPhotometry, with local background
    subtraction. Returns raw (native mosaic-unit, NOT EE-corrected) flux --
    the caller applies the EE/apcorr correction. Confirmed live 2026-07-21:
    without local background subtraction, raw fit flux ran ~2.3x the
    catalog's aperture flux for a real test source -- this is not optional."""
    from photutils.background import LocalBackground, MMMBackground
    from photutils.psf import ImagePSF, PSFPhotometry

    psf_model = ImagePSF(data=psf_template, flux=1.0, x_0=0.0, y_0=0.0, oversampling=1)
    init_params = Table()
    init_params["x"] = [x0]
    init_params["y"] = [y0]

    local_bkg = LocalBackground(
        inner_radius=skyin_px, outer_radius=skyout_px, bkg_estimator=MMMBackground()
    )
    phot = PSFPhotometry(
        psf_model,
        fit_shape=fit_shape,
        aperture_radius=aperture_radius_px,
        local_bkg_estimator=local_bkg,
    )
    result = phot(sci, error=err, init_params=init_params)
    return {
        "flux_fit": float(result["flux_fit"][0]),
        "flux_err": float(result["flux_err"][0]),
        "x_fit": float(result["x_fit"][0]),
        "y_fit": float(result["y_fit"][0]),
        "flags": int(result["flags"][0]),
    }


def aperture_flux_with_local_bkg(
    sci: np.ndarray, x0: float, y0: float, radius_px: float, skyin_px: float, skyout_px: float
) -> float:
    """Raw (native mosaic-unit, NOT EE-corrected) circular-aperture flux
    with local sky subtraction from a matched annulus -- the parallel
    cross-check to fit_psf_flux, using the SAME radius/skyin/skyout as the
    PSF-fit path (both come from the same APCORR table row)."""
    from photutils.aperture import ApertureStats, CircularAnnulus, CircularAperture, aperture_photometry

    aperture = CircularAperture((x0, y0), r=radius_px)
    annulus = CircularAnnulus((x0, y0), r_in=skyin_px, r_out=skyout_px)
    bkg_stats = ApertureStats(sci, annulus, sigma_clip=SigmaClip(sigma=3.0))
    bkg_per_pixel = float(bkg_stats.median)
    phot_table = aperture_photometry(sci, aperture)
    raw_sum = float(phot_table["aperture_sum"][0])
    return raw_sum - bkg_per_pixel * aperture.area


# --- Per-star, per-filter orchestration ---------------------------------------


def extract_flux_for_filter(
    star_index: int,
    row: dict,
    filt: str,
    apcorr_row: dict,
    neighbor_index_by_mosaic: dict[str, list[tuple[int, float, float]]],
    config: dict,
    mosaic_cache: dict,
) -> dict:
    """Extracts observed MIRI flux for one star, one filter. Returns a dict
    of unsuffixed column -> value (the caller suffixes with `_{filt}`).
    `observed_flux` is the PRIMARY, EE-corrected PSF-fit measurement (see
    module docstring); `aperture_flux` is the EE-corrected cross-check.

    Source position comes ONLY from `row[f"miri_ra_{filt}"]`/
    `row[f"miri_dec_{filt}"]` (a0, already Gaia-cross-matched by
    retriever.py) -- this function never opens or references `_cat.ecsv`,
    by construction (see module docstring re: the `label` gotcha)."""
    cfg = config["miri_photometry"]
    out: dict = {}

    ra = row.get(f"miri_ra_{filt}", np.nan)
    dec = row.get(f"miri_dec_{filt}", np.nan)
    mosaic_path = str(row.get(f"mosaic_path_{filt}", "") or "")

    def _empty(**qc_overrides):
        d = {
            "qc_no_mosaic_for_filter": 0,
            "qc_source_off_mosaic": 0,
            "qc_saturated": 0,
            "qc_crowded_source": 0,
            "qc_psf_fit_failed": 0,
            "qc_psf_aperture_disagreement": 0,
            "qc_psf_disagreement_faint": 0,
            "qc_psf_disagreement_complex": 0,
            "observed_flux": np.nan,
            "observed_flux_err": np.nan,
            "aperture_flux": np.nan,
            "x_fit": np.nan,
            "y_fit": np.nan,
        }
        d.update(qc_overrides)
        return d

    if not (np.isfinite(ra) and np.isfinite(dec)) or not mosaic_path:
        return _empty(qc_no_mosaic_for_filter=1)

    mosaic = get_mosaic(mosaic_path, mosaic_cache)
    x0, y0 = sky_to_pixel(ra, dec, mosaic["wcs"])

    radius_px = apcorr_row["radius_px"]
    apcorr_mult = apcorr_row["apcorr"]
    skyin_px, skyout_px = apcorr_row["skyin_px"], apcorr_row["skyout_px"]
    half_width = stamp_half_width_px(radius_px, cfg["fov_margin_px"])

    if not is_within_mosaic(x0, y0, mosaic["sci"].shape, half_width):
        return _empty(qc_source_off_mosaic=1)

    out = _empty()
    out["qc_saturated"] = int(has_nonfinite_pixel(mosaic["sci"], x0, y0, half_width))

    neighbors = neighbor_index_by_mosaic.get(mosaic_path, [])
    other_positions = [(nx, ny) for (idx, nx, ny) in neighbors if idx != star_index]
    out["qc_crowded_source"] = int(
        has_close_neighbor(x0, y0, other_positions, cfg["crowding"]["min_separation_px"])
    )

    fit_shape = (2 * half_width + 1, 2 * half_width + 1)
    psf_template = _get_miri_psf_template(filt, 2 * half_width + 1)
    psf_result = fit_psf_flux(
        mosaic["sci"], mosaic["err"], x0, y0, psf_template, fit_shape,
        aperture_radius_px=radius_px, skyin_px=skyin_px, skyout_px=skyout_px,
    )
    out["qc_psf_fit_failed"] = int(flags_indicate_fit_failure(psf_result["flags"]))
    out["x_fit"] = psf_result["x_fit"]
    out["y_fit"] = psf_result["y_fit"]

    pixar_sr = mosaic["pixar_sr"]
    native_to_jy = pixar_sr * 1e6  # MJy/sr -> Jy/px, at PIXAR_SR sr/px

    # PRIMARY measurement: PSF-fit flux, EE-corrected (apcorr_mult) -- see
    # module docstring for why this multiplication is required, not optional.
    out["observed_flux"] = psf_result["flux_fit"] * native_to_jy * apcorr_mult
    out["observed_flux_err"] = abs(psf_result["flux_err"] * native_to_jy * apcorr_mult)

    # Cross-check: aperture flux, EE-corrected with the SAME apcorr_mult
    # (same table row -- radius/skyin/skyout/apcorr all matched to the
    # PSF-fit path above, not independently chosen).
    aperture_flux_native = aperture_flux_with_local_bkg(
        mosaic["sci"], x0, y0, radius_px, skyin_px, skyout_px
    )
    out["aperture_flux"] = aperture_flux_native * native_to_jy * apcorr_mult

    disagreement_cfg = cfg["disagreement"]
    disagree = psf_aperture_disagreement(
        out["observed_flux"], out["aperture_flux"],
        disagreement_cfg["abs_floor_jy"], disagreement_cfg["rel_frac"],
    )
    out["qc_psf_aperture_disagreement"] = int(disagree)

    # Splits the disagreement into two physically distinct sub-flags -- see
    # classify_disagreement's docstring and RESEARCH_CONTEXT.md (2026-07-21,
    # three-field investigation) for why a single flag conflated two
    # different regimes: a faint/low-SNR/marginal-detection population, and
    # a bright/high-SNR population where the disagreement can't be
    # explained by photon noise and is more likely blending or a PSF-
    # modeling mismatch. qc_psf_aperture_disagreement above is kept exactly
    # as before for backward-compatible use as a general caution flag.
    snr = abs(out["observed_flux"]) / out["observed_flux_err"] if out["observed_flux_err"] > 0 else np.nan
    is_faint, is_complex = classify_disagreement(disagree, snr, disagreement_cfg["snr_threshold"])
    out["qc_psf_disagreement_faint"] = int(is_faint)
    out["qc_psf_disagreement_complex"] = int(is_complex)
    return out


# --- Neighbor index (crowding) ------------------------------------------------


def build_neighbor_index(a0_ds: xr.Dataset, filt: str, mosaic_cache: dict) -> dict[str, list]:
    """For a given filter, maps mosaic_path -> [(star_index, x_px, y_px), ...]
    for every a0 star with a finite position in that filter -- used by
    extract_flux_for_filter's qc_crowded_source check. Built once per
    filter per run, not per star, to avoid re-deriving pixel positions for
    every star in a shared field."""
    index: dict[str, list] = {}
    if f"miri_ra_{filt}" not in a0_ds.data_vars:
        # A field with zero detections in this filter (confirmed real:
        # -BET-PIC/NGC-1266-BACKGROUND are F770W-only -- see
        # RESEARCH_CONTEXT.md 2026-07-22) has no miri_ra_{filt}/
        # miri_dec_{filt}/mosaic_path_{filt} columns at all, not just
        # NaN-filled ones. extract_flux_for_filter's own row.get(...,
        # np.nan) already degrades gracefully per-star (returns
        # qc_no_mosaic_for_filter=1); this function needs the same
        # degradation since it indexes a0_ds directly rather than a
        # per-row dict.
        return index

    ra = a0_ds[f"miri_ra_{filt}"].values
    dec = a0_ds[f"miri_dec_{filt}"].values
    mosaic_path = a0_ds[f"mosaic_path_{filt}"].values

    for i in range(len(ra)):
        if not (np.isfinite(ra[i]) and np.isfinite(dec[i])):
            continue
        path = str(mosaic_path[i] or "")
        if not path:
            continue
        mosaic = get_mosaic(path, mosaic_cache)
        x, y = sky_to_pixel(float(ra[i]), float(dec[i]), mosaic["wcs"])
        index.setdefault(path, []).append((i, x, y))
    return index


# --- Assembly and output -------------------------------------------------------


def _suffix_column(key: str, filt: str) -> str:
    """Suffixes a column name with its filter, matching photosphere.py's
    `predicted_flux_{band}_err` convention (filter BEFORE `_err`, not
    after) -- e.g. `observed_flux_err` -> `observed_flux_F770W_err`, not
    `observed_flux_err_F770W`."""
    if key.endswith("_err"):
        return f"{key[:-len('_err')]}_{filt}_err"
    return f"{key}_{filt}"


def assemble_miri_photometry(a0_ds: xr.Dataset, apcorr_table: Table, config: dict) -> xr.Dataset:
    """Runs flux extraction for every star, every configured filter, and
    packs the results into an xarray.Dataset sharing a0's `star` coordinate
    -- no formal data-level letter assigned (see RESEARCH_CONTEXT.md);
    joined by excess.py against a0/a1 via `star`/`gaia_source_id`."""
    cfg = config["miri_photometry"]
    filters = config["retriever"]["mast"]["filters"]
    subarray = cfg["apcorr"]["subarray"]
    target_ee = cfg["target_ee_fraction"]

    apcorr_rows = {
        filt: select_apcorr_row(apcorr_table, filt, subarray, target_ee) for filt in filters
    }

    mosaic_cache: dict = {}
    neighbor_index = {filt: build_neighbor_index(a0_ds, filt, mosaic_cache) for filt in filters}

    n = a0_ds.sizes["star"]
    rows = []
    for i in range(n):
        row = {name: a0_ds[name].values[i] for name in a0_ds.data_vars}
        out: dict = {}
        for filt in filters:
            filt_out = extract_flux_for_filter(
                i, row, filt, apcorr_rows[filt], neighbor_index[filt], config, mosaic_cache
            )
            out.update({_suffix_column(k, filt): v for k, v in filt_out.items()})
        rows.append(out)
        if (i + 1) % 25 == 0 or (i + 1) == n:
            logger.info("Extracted MIRI photometry for %d/%d stars", i + 1, n)

    close_mosaic_cache(mosaic_cache)

    columns = {c for r in rows for c in r}
    data_vars = {}
    for col in columns:
        values = [r.get(col, np.nan) for r in rows]
        if col.startswith("qc_"):
            data_vars[col] = ("star", np.asarray(values, dtype=np.int32))
        else:
            data_vars[col] = ("star", np.asarray(values, dtype=float))

    ds = xr.Dataset(data_vars=data_vars, coords={"star": a0_ds["star"].values})
    ds["star_id"] = ("star", a0_ds["star_id"].values)
    ds["gaia_source_id"] = ("star", a0_ds["gaia_source_id"].values)
    for filt in filters:
        ds[f"observed_flux_{filt}"].attrs["units"] = "Jy"
        ds[f"observed_flux_{filt}_err"].attrs["units"] = "Jy"
        ds[f"aperture_flux_{filt}"].attrs["units"] = "Jy"
    ds.attrs["pipeline_version"] = __version__
    ds.attrs["apcorr_reference_file"] = APCORR_REFERENCE_FILENAME
    ds.attrs["target_ee_fraction"] = target_ee
    return ds


def save_miri_photometry(ds: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path)
    logger.info("Saved MIRI photometry dataset to %s (%d stars)", path, ds.sizes["star"])


# --- Orchestration -------------------------------------------------------------


def run(config: dict, a0_path: Path, output_path: Path) -> xr.Dataset:
    """Runs the full MIRI photometry-extraction stage: ensure APCORR
    reference -> load a0 -> extract flux for every star/filter -> save."""
    apcorr_path = ensure_apcorr_reference(Path(config["miri_photometry"]["apcorr"]["cache_dir"]))
    apcorr_table = load_apcorr_table(apcorr_path)

    a0_ds = xr.open_dataset(a0_path)
    ds = assemble_miri_photometry(a0_ds, apcorr_table, config)
    save_miri_photometry(ds, output_path)
    return ds
