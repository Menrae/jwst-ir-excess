"""
pipeline.retriever

Stage 1 of the jwst-ir-excess pipeline: raw archive data -> data level a0.

Queries the public JWST archive (MAST) for MIRI Level 3 imaging
observations, downloads the Level 3 mosaic and pipeline source catalog for
each, then cross-matches the MIRI source positions against Gaia DR3 and
2MASS, then pivots the result to one row per *star* (not per MIRI detection
-- a star imaged in both F770W and F1000W would otherwise appear as two
separate rows). The result is one xarray.Dataset (saved to NetCDF), carrying
the MIRI/Gaia/2MASS identifiers and photometry needed by later stages, plus
explicit qc_* match-quality flags.

Key design decisions, and why -- see RESEARCH_CONTEXT.md Decision Log
(2026-07-15 entries) for the full discussion:

- MAST serves both a Level 3 source catalog (_cat.ecsv, automated aperture
  photometry from the pipeline's source_catalog step) and the Level 3
  mosaic (_i2d.fits). Libralato et al. (2024, arXiv:2311.12145) show the
  automated _cat.ecsv photometry underperforms custom photometry and is not
  intended for high-precision point-source work. So _cat.ecsv positions are
  used here only to seed the archive search and the cross-match -- its
  photometry columns are carried through as reference/QC context, not as
  the excess-critical flux measurement. The photometry-extraction method to
  run on the _i2d mosaics is a separate, still-open design question for a
  later stage.
- Gaia DR3, 2MASS, and JWST were observed at very different epochs. Gaia
  positions are propagated (using proper motion) to the epoch of whichever
  catalog they're being matched against, rather than matching raw catalog
  coordinates. 2MASS's per-source Julian date (its 'JD' column) is used for
  this rather than a fixed representative survey epoch, since it's directly
  available from VizieR.
- Cross-match radii (0.25" MIRI-Gaia, 0.5" Gaia-2MASS) and their rationale
  are fixed config values, not derived here -- see pipeline_config.yaml.
- A cone search is run once per MIRI observation (covering the full
  imager field of view) rather than once per source, since the MIRI
  imager FOV (~1.2' x 1.9') is small and this cuts the number of Gaia/
  VizieR queries by roughly the number of sources per field.
- Ambiguous matches (more than one candidate within the configured radius)
  and non-matches are recorded as qc_* flags, never silently dropped.
- The per-detection cross-matched table is pivoted to one row per star
  (grouped by gaia_source_id, with unmatched sources kept as singleton
  groups) so downstream stages can assume one-row-per-star as an a0
  invariant rather than each re-deriving it. See pivot_to_one_row_per_star.
"""

from __future__ import annotations

import logging
from pathlib import Path

import astropy.units as u
import numpy as np
import xarray as xr
from astropy.coordinates import SkyCoord
from astropy.table import Table, vstack
from astropy.time import Time
from astroquery.gaia import Gaia
from astroquery.mast import Observations
from astroquery.vizier import Vizier

from pipeline import __version__

logger = logging.getLogger(__name__)

# Cone-search radius used to pull candidate Gaia/2MASS sources around each
# MIRI observation's field center, before any epoch propagation or precise
# cross-matching. Must comfortably exceed the MIRI imager FOV (~1.2' x 1.9')
# plus the largest proper motion we'd plausibly need to propagate over
# several decades; this is a query-efficiency parameter, not a scientific
# threshold, and is separate from the crossmatch_radius_arcsec values in
# pipeline_config.yaml that actually decide what counts as a match.
FIELD_CONE_RADIUS_ARCSEC = 90.0

GAIA_TABLE = "gaiadr3.gaia_source"
TWOMASS_VIZIER_CATALOG = "II/246"

# MAST's 'target_classification' field is a semicolon-separated set of tags
# (e.g. "Star; Protoplanetary disks; Protostars"). This is an INCLUSIVE
# allowlist of tags that mark a target as genuinely stellar/point-source,
# not an exclusion list -- see query_miri_observations for how missing or
# unrecognized classifications are handled (kept, not dropped).
#
# Rationale: pure efficiency, not scientific necessity. An archive-wide MIRI
# query without this filter pulls in MAST's much larger non-stellar imaging
# archive (galaxy surveys, deep fields, calibration flats) alongside actual
# stellar fields, wasting download/compute on fields that were always going
# to end up qc_no_gaia_match=1 downstream anyway. The filter is a data-
# selection efficiency step for the eventual methods section, not a claim
# that non-listed classifications are non-stellar -- the existing
# qc_no_gaia_match / qc_ambiguous_gaia_match QC flags already handle
# non-stellar contamination correctly regardless of what reaches them.
#
# The token list and the counts below were verified empirically against the
# live MAST archive (F770W/F1000W, calib_level=3, public) on 2026-07-15 --
# see RESEARCH_CONTEXT.md Decision Log. Several genuinely stellar fields are
# NOT tagged with a top-level 'Star' component (e.g. "ISM; Molecular gas;
# Pre-main sequence stars", "Stellar Cluster; Young star clusters",
# "Calibration; A stars"), so matching is done against ANY component of the
# semicolon-separated classification, not just the first.
STELLAR_TARGET_CLASSIFICATIONS = {
    "Star", "Protoplanetary disks", "Protostars", "Pre-main sequence stars",
    "Young stellar objects", "T Tauri stars", "White dwarfs", "Brown dwarfs",
    "A dwarfs", "B stars", "G dwarfs", "M dwarfs", "O stars", "A stars",
    "T dwarfs", "Y dwarfs", "WC stars", "Wolf-Rayet stars", "Supernovae",
    "Type Ia supernovae", "Type II supernovae", "Novae", "Circumstellar disks",
    "Proplyds", "Stellar Cluster", "Young star clusters", "Open star clusters",
    "OB associations", "Planetary nebulae",
}


# --- MIRI observation query and download -----------------------------------


def _is_stellar_or_unclassified(classification: str) -> bool:
    """True if a MAST target_classification string contains a
    STELLAR_TARGET_CLASSIFICATIONS token, or is missing/unclassified
    ('--', empty, or tagged 'Unidentified') -- ambiguous or incomplete
    classifications are kept, not excluded, per the allowlist rationale
    above."""
    s = str(classification).strip()
    if s in ("", "--"):
        return True
    components = {c.strip() for c in s.split(";")}
    if "Unidentified" in components:
        return True
    return bool(components & STELLAR_TARGET_CLASSIFICATIONS)


def query_miri_observations(filters: list[str]) -> Table:
    """Query MAST for public JWST/MIRI Level 3 imaging observations in the
    given filters, restricted to stellar/unclassified targets (see
    STELLAR_TARGET_CLASSIFICATIONS). Archive-wide: not restricted to any
    single target."""
    obs = Observations.query_criteria(
        obs_collection="JWST",
        instrument_name="MIRI/IMAGE",
        filters=filters,
        calib_level=3,
        dataproduct_type="image",
        dataRights="PUBLIC",
    )
    keep = np.array([_is_stellar_or_unclassified(c) for c in obs["target_classification"]])
    kept = obs[keep]
    logger.info(
        "Found %d public MIRI Level 3 imaging observations; kept %d "
        "(stellar-classified or unclassified/ambiguous), dropped %d "
        "as confidently non-stellar (target_classification allowlist)",
        len(obs), len(kept), len(obs) - len(kept),
    )
    return kept


def download_miri_products(obs_table: Table, download_dir: Path) -> Table:
    """Download the Level 3 mosaic (_i2d.fits) and source catalog (_cat.ecsv)
    for each observation. Returns the product table (with obs_id,
    productFilename, etc.) with the downloaded 'Local Path' merged in --
    Observations.download_products' own return value carries neither
    obs_id nor productFilename, only Local Path/Status/URL, so it can't be
    used on its own to find each observation's files back.

    productSubGroupDescription values ('I2D', 'CAT') and the need for an
    explicit calib_level=3 filter -- i2d.fits also exists as a per-exposure
    Level 2b product with the same subgroup label -- were verified
    empirically against the live MAST archive on 2026-07-15.
    """
    products = Observations.get_product_list(obs_table)
    mosaics = Observations.filter_products(
        products, productSubGroupDescription="I2D", calib_level=3
    )
    catalogs = Observations.filter_products(
        products, productSubGroupDescription="CAT", calib_level=3
    )
    keep = vstack([mosaics, catalogs])
    download_manifest = Observations.download_products(keep, download_dir=str(download_dir))

    local_path_by_filename = {
        Path(str(row["Local Path"])).name: str(row["Local Path"]) for row in download_manifest
    }
    keep["Local Path"] = [
        local_path_by_filename.get(str(fn), "") for fn in keep["productFilename"]
    ]
    return keep


def load_miri_catalog_sources(manifest: Table, obs_table: Table) -> Table:
    """Read every downloaded _cat.ecsv and combine into one table of MIRI
    point-source positions, one row per source, with the parent
    observation's metadata (filter, epoch, mosaic path) attached.

    _cat.ecsv photometry columns are kept as reference/QC context (see
    module docstring) -- not used as the excess-critical flux measurement.
    """
    obs_by_id = {row["obs_id"]: row for row in obs_table}
    all_sources = []

    for obs_id, obs_row in obs_by_id.items():
        filenames = manifest["productFilename"].astype(str)
        cat_rows = manifest[(manifest["obs_id"] == obs_id) & np.char.endswith(filenames, "cat.ecsv")]
        mosaic_rows = manifest[(manifest["obs_id"] == obs_id) & np.char.endswith(filenames, "i2d.fits")]
        if len(cat_rows) == 0:
            logger.warning("No _cat.ecsv downloaded for %s; skipping", obs_id)
            continue

        cat_path = cat_rows["Local Path"][0]
        mosaic_path = mosaic_rows["Local Path"][0] if len(mosaic_rows) else ""

        sources = Table.read(cat_path, format="ascii.ecsv")
        sources["obs_id"] = obs_id
        sources["filter"] = obs_row["filters"]
        sources["proposal_id"] = obs_row["proposal_id"]
        sources["mosaic_path"] = mosaic_path
        # Carried through for photosphere.py (white-dwarf grid skip,
        # qc_pms_veiling_risk) -- MAST's target_classification was
        # previously used only for the query-time stellar allowlist filter
        # and then discarded. It describes the whole pointing/target, not
        # the filter, so pivot_to_one_row_per_star treats it as star-level.
        sources["target_classification"] = str(obs_row["target_classification"])
        sources["miri_ra"] = sources["sky_centroid"].ra.deg
        sources["miri_dec"] = sources["sky_centroid"].dec.deg
        # t_min is the observation start in MJD; used as the astrometric
        # epoch for Gaia proper-motion propagation to the MIRI frame.
        sources["obs_epoch_mjd"] = float(obs_row["t_min"])
        # sky_centroid/sky_bbox_* are SkyCoord mixin columns -- fine in an
        # astropy Table, but xarray/NetCDF can't serialize them and they're
        # redundant with miri_ra/miri_dec (bbox corners aren't needed for
        # level a0; they're recoverable from the mosaic FITS WCS if needed
        # later).
        sources.remove_columns(
            ["sky_centroid", "sky_bbox_ll", "sky_bbox_ul", "sky_bbox_lr", "sky_bbox_ur"]
        )
        all_sources.append(sources)

    combined = vstack(all_sources, metadata_conflicts="silent")
    combined["source_row_id"] = np.arange(len(combined))
    logger.info(
        "Loaded %d MIRI point sources from %d observations",
        len(combined),
        len(all_sources),
    )
    return combined


# --- Cross-matching ----------------------------------------------------------


def _masked_values(col) -> np.ndarray:
    """Extract a plain float ndarray from an astropy (Masked)Column, with
    masked entries as NaN and any unit stripped -- Column.data is the raw
    numpy(.ma) array with no unit wrapper, unlike Column.filled(), which
    preserves the unit and would double it up if multiplied by an
    astropy.units quantity downstream."""
    return np.ma.filled(np.ma.asarray(col.data), np.nan).astype(float)


def _propagate(
    ra_deg: np.ndarray,
    dec_deg: np.ndarray,
    pmra_masyr: np.ndarray,
    pmdec_masyr: np.ndarray,
    ref_epoch: Time,
    target_epoch: Time,
) -> SkyCoord:
    """Propagate Gaia positions from ref_epoch to target_epoch using proper
    motion. Sources with no usable proper motion (masked/NaN, i.e. no valid
    Gaia astrometric solution) are left at their reference-epoch position
    rather than dropped -- their cross-match is then just less precise for
    any real motion between epochs, which the fixed crossmatch radius
    already has margin for (see pipeline_config.yaml)."""
    pmra_masyr = np.nan_to_num(pmra_masyr, nan=0.0)
    pmdec_masyr = np.nan_to_num(pmdec_masyr, nan=0.0)
    coords = SkyCoord(
        ra=ra_deg * u.deg,
        dec=dec_deg * u.deg,
        pm_ra_cosdec=pmra_masyr * u.mas / u.yr,
        pm_dec=pmdec_masyr * u.mas / u.yr,
        obstime=ref_epoch,
    )
    return coords.apply_space_motion(new_obstime=target_epoch)


def crossmatch_gaia(miri_sources: Table, radius_arcsec: float) -> Table:
    """Cross-match each MIRI source against Gaia DR3, one cone search per
    MIRI observation (covering the field), propagating each candidate's
    Gaia position to the MIRI observation epoch before measuring separation.
    Adds Gaia columns plus qc_no_gaia_match / qc_ambiguous_gaia_match.

    Results are scattered back into pre-allocated arrays by each source's
    original row index (not appended in per-observation loop order, then
    reassigned positionally) -- the latter silently misattributes matches
    to the wrong source whenever the table holds more than one observation,
    since Python's set() does not iterate obs_id values in table row order.
    This was caught empirically (2026-07-15 smoke test) by a downstream
    2MASS cross-match that came back with implausibly zero matches; see
    RESEARCH_CONTEXT.md.
    """
    gaia_cols = [
        "source_id", "ra", "dec", "ref_epoch", "parallax", "parallax_error",
        "pmra", "pmra_error", "pmdec", "pmdec_error", "phot_g_mean_mag",
        "phot_bp_mean_mag", "phot_rp_mean_mag", "non_single_star", "ruwe",
    ]
    n = len(miri_sources)
    out_cols = {c: np.full(n, np.nan) for c in gaia_cols}
    # source_id is a ~19-digit integer primary key; float64 can only
    # represent integers exactly up to 2**53, so it must be kept as its
    # own int64 array (0 = no match; real Gaia DR3 source_ids are never 0)
    # rather than folded into the generic NaN-filled float columns above.
    gaia_source_id = np.zeros(n, dtype=np.int64)
    no_match = np.ones(n, dtype=bool)
    ambiguous = np.zeros(n, dtype=bool)

    obs_ids = np.asarray(miri_sources["obs_id"])
    for obs_id in np.unique(obs_ids):
        idx = np.flatnonzero(obs_ids == obs_id)
        field = miri_sources[idx]
        center = SkyCoord(
            ra=np.mean(field["miri_ra"]) * u.deg,
            dec=np.mean(field["miri_dec"]) * u.deg,
        )
        obs_epoch = Time(field["obs_epoch_mjd"][0], format="mjd")

        job = Gaia.launch_job(
            f"SELECT {', '.join(gaia_cols)} FROM {GAIA_TABLE} "
            f"WHERE 1=CONTAINS(POINT('ICRS', ra, dec), "
            f"CIRCLE('ICRS', {center.ra.deg}, {center.dec.deg}, "
            f"{FIELD_CONE_RADIUS_ARCSEC / 3600.0}))"
        )
        candidates = job.get_results()
        if len(candidates) == 0:
            continue  # leave as no_match=True / NaN for this field's rows

        candidate_pos = _propagate(
            candidates["ra"].data,
            candidates["dec"].data,
            _masked_values(candidates["pmra"]),
            _masked_values(candidates["pmdec"]),
            Time(candidates["ref_epoch"].data, format="jyear"),
            obs_epoch,
        )

        for local_i, global_i in enumerate(idx):
            source_pos = SkyCoord(
                ra=field["miri_ra"][local_i] * u.deg, dec=field["miri_dec"][local_i] * u.deg
            )
            sep = source_pos.separation(candidate_pos).arcsec
            within = np.where(sep <= radius_arcsec)[0]
            if len(within) == 0:
                continue

            best = within[np.argmin(sep[within])]
            for c in gaia_cols:
                if c == "source_id":
                    gaia_source_id[global_i] = candidates[c][best]
                else:
                    out_cols[c][global_i] = candidates[c][best]
            no_match[global_i] = False
            ambiguous[global_i] = len(within) > 1

    result = miri_sources.copy()
    result["gaia_source_id"] = gaia_source_id
    for c in gaia_cols:
        if c != "source_id":
            result[f"gaia_{c}"] = out_cols[c]
    result["qc_no_gaia_match"] = no_match.astype(np.int32)
    result["qc_ambiguous_gaia_match"] = ambiguous.astype(np.int32)
    return result


def crossmatch_2mass(matched: Table, radius_arcsec: float) -> Table:
    """Cross-match each Gaia-matched source against 2MASS, propagating the
    Gaia position (with proper motion) to each 2MASS candidate's own
    per-source Julian date (2MASS VizieR 'JD' column) before measuring
    separation. Sources with qc_no_gaia_match=1 have no Gaia-anchored
    position to propagate and are skipped here (also flagged
    qc_no_2mass_match=1), consistent with matching 2MASS via Gaia rather
    than directly against MIRI positions.

    Results are scattered back by original row index -- see crossmatch_gaia
    docstring for why (the same misattribution bug applied here too).
    """
    # 2MASS/VizieR (II/246) columns: 'Qflg' is a 3-character per-band
    # (J/H/Ks) photometric quality string (e.g. "AAA"), not numeric --
    # handled alongside the '2MASS' designation as a string column below,
    # not folded into the float columns.
    string_cols = ["2MASS", "Qflg"]
    numeric_cols = ["RAJ2000", "DEJ2000", "Jmag", "e_Jmag", "Hmag", "e_Hmag",
                     "Kmag", "e_Kmag", "JD", "errMaj", "errMin", "errPA"]
    twomass_cols = string_cols + numeric_cols
    vizier = Vizier(catalog=TWOMASS_VIZIER_CATALOG, columns=["**"])
    vizier.ROW_LIMIT = -1

    n = len(matched)
    out_cols = {c: np.full(n, np.nan) for c in numeric_cols}
    string_out = {c: np.full(n, "", dtype="<U20") for c in string_cols}
    no_match = np.ones(n, dtype=bool)
    ambiguous = np.zeros(n, dtype=bool)

    obs_ids = np.asarray(matched["obs_id"])
    no_gaia = np.asarray(matched["qc_no_gaia_match"]).astype(bool)

    for obs_id in np.unique(obs_ids):
        idx = np.flatnonzero(obs_ids == obs_id)
        field = matched[idx]
        center = SkyCoord(
            ra=np.mean(field["miri_ra"]) * u.deg,
            dec=np.mean(field["miri_dec"]) * u.deg,
        )
        result = vizier.query_region(center, radius=f"{FIELD_CONE_RADIUS_ARCSEC} arcsec")
        candidates = result[0] if result else None
        if candidates is None or len(candidates) == 0:
            continue

        for local_i, global_i in enumerate(idx):
            if no_gaia[global_i]:
                continue  # no Gaia-anchored position to propagate

            gaia_pos = _propagate(
                np.array([field["gaia_ra"][local_i]]),
                np.array([field["gaia_dec"][local_i]]),
                np.array([field["gaia_pmra"][local_i]]),
                np.array([field["gaia_pmdec"][local_i]]),
                Time(field["gaia_ref_epoch"][local_i], format="jyear"),
                Time(candidates["JD"].data, format="jd"),
            )
            candidate_pos = SkyCoord(
                ra=candidates["RAJ2000"].data * u.deg,
                dec=candidates["DEJ2000"].data * u.deg,
            )
            sep = gaia_pos.separation(candidate_pos).arcsec
            within = np.where(sep <= radius_arcsec)[0]
            if len(within) == 0:
                continue

            best = within[np.argmin(sep[within])]
            for c in string_cols:
                string_out[c][global_i] = candidates[c][best]
            for c in numeric_cols:
                out_cols[c][global_i] = candidates[c][best]
            no_match[global_i] = False
            ambiguous[global_i] = len(within) > 1

    result = matched.copy()
    for c in string_cols:
        result[f"twomass_{c}"] = string_out[c]
    for c in numeric_cols:
        result[f"twomass_{c}"] = out_cols[c]
    result["qc_no_2mass_match"] = no_match.astype(np.int32)
    result["qc_ambiguous_2mass_match"] = ambiguous.astype(np.int32)
    return result


# --- Star-level pivot --------------------------------------------------------


def pivot_to_one_row_per_star(sources: Table, filters: list[str]) -> Table:
    """Collapse the per-(MIRI detection, filter) table into one row per
    *star*, so that photosphere.py and excess.py can assume one-row-per-star
    as an a0 invariant rather than each doing their own grouping.

    Without this, a star observed in both F770W and F1000W produces two
    separate a0 rows (one per filter), each independently cross-matched --
    unusable for a stage that needs both MIRI bands for the same star
    side by side. See RESEARCH_CONTEXT.md Decision Log (2026-07-20).

    Grouping key: 'star_id' = gaia_source_id for sources with a Gaia match
    (qc_no_gaia_match == 0). Sources with NO Gaia match cannot be grouped by
    gaia_source_id == 0 -- that would incorrectly merge every unmatched
    detection in the table into a single "star". Each unmatched detection is
    instead given its own unique negative sentinel key
    (-(source_row_id + 1), guaranteed unique and disjoint from real Gaia
    source_ids, which are always positive) so it becomes a singleton row.

    Columns are split into:
    - star-level (gaia_*, twomass_*, qc_* match flags): identical across
      every row in a group by construction (they were looked up via the
      shared Gaia match), so the first row's value is kept, not suffixed.
    - filter-level (everything else -- miri_ra/dec, obs_id, proposal_id,
      mosaic_path, obs_epoch_mjd, source_row_id, and the raw _cat.ecsv
      photometry columns): suffixed with the filter name (e.g. miri_ra_F770W)
      and pivoted wide. A star with a detection in only one of the
      configured filters gets NaN in the other filter's columns --
      explicit, not dropped -- and qc_single_filter_detection is set.

    Known simplification: if a star was somehow observed more than once in
    the *same* filter (e.g. two different proposals targeting it), only the
    first (by source_row_id) detection is kept per (star, filter) pair --
    logged, not silently dropped -- rather than picking the best or keeping
    both. Revisit if this fires at a non-negligible rate in the real
    archive; not expected to be common but not verified absent either.
    """
    df = sources.to_pandas()

    has_gaia = ~df["qc_no_gaia_match"].astype(bool)
    df = df.assign(
        star_id=np.where(
            has_gaia,
            df["gaia_source_id"].astype(np.int64),
            -(df["source_row_id"].astype(np.int64) + 1),
        )
    )

    dup_mask = df.duplicated(subset=["star_id", "filter"], keep="first")
    if dup_mask.any():
        logger.warning(
            "%d MIRI source rows were duplicate (star_id, filter) pairs -- "
            "same star observed more than once in the same filter. Keeping "
            "only the first (by source_row_id) per pair.",
            int(dup_mask.sum()),
        )
        df = df.loc[~dup_mask]

    star_level_cols = [
        c for c in df.columns
        if c == "gaia_source_id"
        or c == "target_classification"
        or c.startswith(("gaia_", "twomass_", "qc_"))
    ]
    filter_level_cols = [
        c for c in df.columns if c not in star_level_cols and c not in ("star_id", "filter")
    ]

    star_frame = df.groupby("star_id", sort=False)[star_level_cols].first()
    filter_frame = df.set_index(["star_id", "filter"])[filter_level_cols].unstack("filter")
    filter_frame.columns = [f"{col}_{filt}" for col, filt in filter_frame.columns]

    n_filters_present = df.groupby("star_id")["filter"].nunique()

    pivoted = star_frame.join(filter_frame, how="outer")
    pivoted["qc_single_filter_detection"] = (
        n_filters_present.reindex(pivoted.index) < len(filters)
    ).astype(np.int32)
    pivoted = pivoted.reset_index()

    result = Table.from_pandas(pivoted)
    result["star_row_id"] = np.arange(len(result))
    logger.info(
        "Pivoted %d MIRI detections (filters: %s) into %d star-level rows "
        "(%d with a detection in only one filter)",
        len(df), ",".join(filters), len(result),
        int(pivoted["qc_single_filter_detection"].sum()),
    )
    return result


# --- Assembly and output -----------------------------------------------------


def _coerce_object_column_for_netcdf(name: str, arr: np.ndarray) -> np.ndarray:
    """netCDF4 has no native bool dtype. A `_cat.ecsv`-derived column that
    mixes masked/missing values with Python bool (e.g. `is_extended`) is
    dtype=object here -- np.asarray succeeds either way, but
    Dataset.to_netcdf later raises "unsupported dtype for netCDF4
    variable: bool" if EVERY star happens to have a real True/False value
    (no missing entries to dilute the array's resolved dtype away from
    pure bool). Confirmed live (2026-07-22, GD153 -- a small field where
    every star's is_extended_{band} was determined) that this reproduces
    reliably and had never been caught before because PN-TC-1/
    CONTROLFIELD/NGC-602's own samples each happened to have at least one
    star missing a value in every such column -- a works-by-luck case, not
    a verified-safe one. Fixed generically (any bool-valued object column,
    not hardcoded to is_extended specifically): cast to float64
    (1.0/0.0/NaN), matching how contaminants.py's
    compute_background_galaxy_flag already reads this exact column
    (`np.isfinite(vals) & (vals != 0)`)."""
    if arr.dtype != object:
        return arr
    non_null = [v for v in arr if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if non_null and all(isinstance(v, (bool, np.bool_)) for v in non_null):
        return np.array(
            [np.nan if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v) for v in arr],
            dtype=float,
        )
    return arr


def assemble_level_a0(star_table: Table, config: dict, filters: list[str]) -> xr.Dataset:
    """Pack the pivoted star-level table into an xarray.Dataset (data level
    a0), one row per star (see pivot_to_one_row_per_star). String columns
    are cast explicitly since NetCDF has no native string type; bool-valued
    object columns are coerced to float (see _coerce_object_column_for_netcdf);
    units are recorded as variable attrs rather than embedded in column
    names."""
    ds = xr.Dataset(
        data_vars={
            name: ("star", _coerce_object_column_for_netcdf(name, np.asarray(star_table[name])))
            for name in star_table.colnames
        },
        coords={"star": star_table["star_row_id"].data},
    )
    for f in filters:
        # A field with detections in only SOME of the configured filters
        # (confirmed real, not hypothetical: -BET-PIC and
        # NGC-1266-BACKGROUND, both F770W-only with zero F1000W
        # observations -- 2026-07-22 trial batch) never gets
        # miri_ra_{f}/miri_dec_{f} columns for the missing filter at all --
        # pivot_to_one_row_per_star's unstack("filter") only creates
        # columns for filters actually present in the input rows. Guard
        # rather than assume every configured filter has a column.
        if f"miri_ra_{f}" not in ds.data_vars:
            continue
        ds[f"miri_ra_{f}"].attrs["units"] = "deg"
        ds[f"miri_dec_{f}"].attrs["units"] = "deg"
    ds["gaia_ra"].attrs["units"] = "deg"
    ds["gaia_dec"].attrs["units"] = "deg"
    ds["gaia_pmra"].attrs["units"] = "mas/yr"
    ds["gaia_pmdec"].attrs["units"] = "mas/yr"
    ds["gaia_parallax"].attrs["units"] = "mas"
    ds.attrs["pipeline_version"] = __version__
    ds.attrs["mast_query_filters"] = ",".join(config["retriever"]["mast"]["filters"])
    ds.attrs["gaia_crossmatch_radius_arcsec"] = config["retriever"]["gaia"]["crossmatch_radius_arcsec"]
    ds.attrs["twomass_crossmatch_radius_arcsec"] = config["retriever"]["twomass"]["crossmatch_radius_arcsec"]
    return ds


def save_level_a0(ds: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path)
    logger.info("Saved level a0 dataset to %s (%d stars)", path, ds.sizes["star"])


# --- Orchestration ------------------------------------------------------------


def run(config: dict, download_dir: Path, output_path: Path) -> xr.Dataset:
    """Run the full retriever stage: query -> download -> cross-match -> save."""
    filters = config["retriever"]["mast"]["filters"]
    gaia_radius = config["retriever"]["gaia"]["crossmatch_radius_arcsec"]
    twomass_radius = config["retriever"]["twomass"]["crossmatch_radius_arcsec"]

    obs_table = query_miri_observations(filters)
    manifest = download_miri_products(obs_table, download_dir)
    miri_sources = load_miri_catalog_sources(manifest, obs_table)
    gaia_matched = crossmatch_gaia(miri_sources, gaia_radius)
    fully_matched = crossmatch_2mass(gaia_matched, twomass_radius)
    star_table = pivot_to_one_row_per_star(fully_matched, filters)

    ds = assemble_level_a0(star_table, config, filters)
    save_level_a0(ds, output_path)
    return ds
