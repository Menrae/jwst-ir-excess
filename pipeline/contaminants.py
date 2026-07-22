"""
pipeline.contaminants

Stage 4b of the jwst-ir-excess pipeline (see RESEARCH_CONTEXT.md for the
5-stage architecture): joins a0 (Gaia astrometry/photometry + the pipeline's
own source-catalogue morphology diagnostics) onto excess.py's b1 output,
and computes the contaminant qc_* flags that must be False (alongside
significant excess) for the eventual qc_anomalous_excess composite. ->
data level b2.

STATUS: implements 5 of 6 planned categories -- Tiers 1, 2, and the first
Tier-3 item (qc_debris_disk_candidate) of the priority ordering agreed
2026-07-22 (see RESEARCH_CONTEXT.md Decision Log):

- qc_evolved_star: HR-diagram overluminosity-for-Teff (AGB stars/evolved
  giants are intrinsically mid-IR bright -- not evidence of a
  megastructure). Directly validated against real data before being
  proposed as Tier 1: all 12 real photosphere_teff fits sharing PN-TC-1's
  blanket "Planetary nebulae nuclei" classification tag came back at
  4500-9000 K (2026-07-22 finding) -- exactly the overluminosity check this
  category performs. Gates on parallax S/N (see
  is_evolved_star_overluminous) after a real PN-TC-1 run caught several
  faint/distant sources getting flagged from parallax noise alone. Properly
  supersedes excess.py's Teff-only is_stopgap_evolved_star, which was
  retired the same day once this was verified. Needs no new archive query:
  Gaia parallax/parallax_error/phot_g_mean_mag (a0) and photosphere_teff
  (already carried through b1) are all already in hand.
- qc_background_galaxy: reuses a0's is_extended_{band} (the pipeline's own
  automated source_catalog morphology classification, already fetched by
  retriever.py and already sitting unused) -- is_extended already did real,
  independent corroborating work elsewhere in this project (the
  qc_psf_fit_failed case for PN-TC-1's genuinely extended source,
  2026-07-21). Needs no new archive query either.
- qc_known_variable: cross-match against Gaia DR3's own variability
  pipeline output (gaiadr3.vari_summary -- confirmed live/queryable
  2026-07-22, same Gaia TAP service retriever.py already uses, keyed by the
  same gaia_source_id already in hand). THE FIRST live-network-dependent
  check in this module -- see query_gaia_variability, kept separate from
  the pure/testable compute_known_variable_flag so unit tests never touch
  the network (same convention as retriever.py/photosphere.py: live
  services are smoke-tested, not mocked).
- qc_binary_companion_contamination: a deliberate passthrough of the
  already-implemented qc_possible_binary (photosphere.py, carried through
  b1), NOT new detection logic -- checked live 2026-07-22 that Gaia's NSS
  orbit-solution tables catch zero cases RUWE/non_single_star miss (0/500
  in a real sample), so building a second, parallel binary-detection
  mechanism would only risk the ambiguous-flag situation this passthrough
  avoids. See Decision Log.
- qc_debris_disk_prime / qc_debris_disk_reserved: position cross-match
  against Cotten & Song (2016), ApJS 225, 15, "A Comprehensive Census of
  Nearby Infrared Excess Stars" -- found via a time-boxed catalog search
  (5-candidate budget, resolved in 2; Kennedy & Wyatt 2013 was ruled out
  the same day as a luminosity-function study, not a per-star catalogue;
  SIMBAD's own object-type vocabulary has no debris-disk-specific entry at
  all, checked live). Split into two SEPARATE flags (researcher's decision,
  2026-07-22), same pattern as miri_photometry.py's
  qc_psf_disagreement_faint/_complex split -- table3 ("Prime", 505 stars,
  higher-confidence) vs. table4 ("Reserved", 1257 stars, lower-confidence)
  are genuinely different confidence tiers and must not be silently
  collapsed into one boolean. Both are disqualifying for now, but kept
  distinguishable so the Reserved tier's strictness can be reconsidered
  later at archive scale without redesigning the flag. THE SECOND live-
  network-dependent category in this module -- see fetch_debris_disk_catalog,
  kept separate from the pure crossmatch_debris_disk_catalog function.

- qc_cluster_member_confirmed / qc_confirmed_field_star: the Milky Way
  half of the young-cluster/PMS gap. Cross-matches gaia_source_id against
  Cantat-Gaudin et al. (2020), A&A 640, A1, "Painting a portrait of the
  Galactic disc with its stellar clusters" (VizieR J/A+A/640/A1, "nodup"
  members table -- ~2000 open clusters, keyed by Gaia DR2 source_id, with
  per-star membership probability). Too large to bulk-download (timed out
  at ROW_LIMIT=-1); queried instead via VizieR's TAP service with a
  targeted `GaiaDR2 IN (...)` clause, same efficient pattern as
  query_gaia_variability. THE THIRD live-network-dependent category in
  this module. `qc_cluster_member_confirmed` is a genuine, specific
  disqualifying signal in its own right (stronger than excess.py's coarse
  field-wide qc_stopgap_young_cluster) and feeds qc_contaminant_flagged_partial.
  `qc_confirmed_field_star` is different in kind -- POSITIVE evidence a
  star is an ordinary Galactic field interloper, NOT gating on its own,
  used only to construct the qc_*_refined columns below that override
  qc_stopgap_young_cluster's contribution to b1's composite where evidence
  supports it. Explicitly the Milky Way half only -- see the extragalactic
  gap noted below, unchanged.

All flags above run over the FULL b1 population, not just the excess-showing
shortlist (researcher's decision, 2026-07-22): this project's null-result
claim needs the "clean" sample's actual composition characterized, not
assumed clean by default just because a star didn't clear the significance
threshold.

**qc_*_refined columns (qc_excess_clean_refined_{band},
qc_excess_significant_refined_{band}, qc_candidate_preliminary_refined):**
excess.py's b1 composite (qc_star_disqualified, qc_excess_clean_{band},
qc_candidate_preliminary) is already fully computed by the time
contaminants.py runs, and this module deliberately never mutates b1's own
columns (every b1 column is carried through unchanged elsewhere in this
module too) -- so a downstream, more-precise finding (qc_confirmed_field_star)
cannot retroactively change b1's own composite in place. Instead, this
module recomputes an ADDITIVE, clearly-named parallel composite: identical
to b1's own logic, except qc_stopgap_young_cluster's contribution to
star-level disqualification is overridden (not counted) wherever
qc_confirmed_field_star provides positive evidence. Every other b1-level
disqualifying reason (qc_ambiguous_gaia_match, qc_no_photosphere_grid,
qc_poor_photosphere_fit, qc_possible_binary, qc_pms_veiling_risk,
qc_rj_extrapolated, and all per-band flags) applies exactly as before --
this is a targeted, single-flag override, not a wholesale recomputation.

NOT yet implemented (queued, remaining Tier 3, see RESEARCH_CONTEXT.md
priority ordering -- explicitly deferred, not just unstarted):
- qc_photometric_artifact (blocked on real per-source
  position-to-multiple-exposure WCS remapping against Level 2 _cal.fits DQ
  arrays -- confirmed live that these products exist, but not a small ask)
- Young-cluster/PMS, extragalactic half (confirmed 9 real cases in NGC-602
  depend solely on excess.py's qc_stopgap_young_cluster; no SMC/LMC-specific
  membership catalogue identified -- Cantat-Gaudin (2020) above is a
  Milky Way open-cluster catalogue only and structurally cannot cover
  NGC-602's SMC population; this half remains genuinely open)

qc_anomalous_excess itself remains uncomputed until all six categories
exist -- this module produces qc_contaminant_flagged_partial (the OR of
whichever categories ARE implemented so far), explicitly named and
documented as partial so it is never mistaken for the final composite.

Key design decisions -- see RESEARCH_CONTEXT.md Decision Log (2026-07-22
entries) for the full discussion:

- qc_evolved_star's expected main-sequence absolute-G-magnitude-vs-Teff
  relation (_MS_ANCHOR_TEFF/_MS_ANCHOR_ABS_G below) reuses the SAME Teff
  anchor points as photosphere.py's own _TEFF_ANCHOR_TEFF (Pecaut &
  Mamajek-like main-sequence values) for consistency across the codebase --
  recalled approximately, not independently re-verified point-by-point,
  same status as that table. Fine for a first-pass overluminosity check,
  NOT to be cited as a precise scientific relation.
- Extinction is deliberately NOT applied when computing absolute G
  magnitude here, even though photosphere_av is available for some stars.
  This is a stated, directionally-safe simplification: skipping the
  correction makes a real, reddened giant's inferred M_G fainter (i.e.
  LESS overluminous than it truly is), which under-flags rather than
  over-flags -- the same safe direction already established for
  qc_extinction_uncertain's Av=0 fallback, not a new risk. Also avoids
  stacking a second unverified reddening coefficient on top of the
  already-flagged, unverified Bayestar-to-Av conversion.
- Absence of information is not evidence: a star with no Gaia parallax, no
  G magnitude, or no photosphere_teff fit gets qc_evolved_star=False (not
  flagged), not a guess.
- is_background_galaxy_candidate is deliberately coarse (is_extended in any
  measured band, nothing more) for this first pass -- a0 also carries
  sharpness_{band}/roundness_{band}/ellipticity_{band}/semimajor_sigma_{band}
  (all unused here), which could refine this in a later pass, but were not
  folded in now to keep Tier 1 to what was actually asked for.
- Join mechanics/alignment: same convention as excess.py --
  assert_star_aligned checks a0 and b1's star_id arrays are identical
  before merging, given this project's own history with a silent
  row-misalignment bug (retriever.py, 2026-07-15). Every b1 column is
  carried through unchanged; nothing is dropped.
- qc_evolved_star gates on parallax quality (parallax/parallax_error >=
  min_parallax_over_error) before trusting any derived distance/magnitude --
  added mid-implementation after a real PN-TC-1 run surfaced several faint,
  distant sources with fractional parallax errors up to 165% getting
  flagged purely from parallax noise (see is_evolved_star_overluminous
  docstring). Caught and fixed before reporting real numbers, not after --
  same discipline as every other real-data check in this project. General
  lesson (not parallax-specific): any derived quantity from INVERTING a
  measured quantity with real error (parallax->distance here; the same
  shape of problem applies to flux->magnitude or any other 1/x-type
  transform) needs an explicit S/N gate on the measured input, not just a
  finite/non-null check.
- qc_known_variable's Gaia query is a single bulk query (source_id IN (...))
  over the whole population being checked, not one query per star -- but
  this is NOT scaled beyond a modest source list; at full archive scale a
  bulk table upload/cross-match would be more appropriate than one large IN
  clause. Fine for this project's current test scale (dozens to low
  hundreds of stars), stated as a known limitation, not silently assumed
  to scale.
- qc_binary_companion_contamination is intentionally NOT new detection
  logic (see Decision Log, 2026-07-22, Question 1): Gaia's NSS orbit-
  solution tables were checked live against 500 real confirmed binaries and
  caught zero cases RUWE/non_single_star already miss. Building a second,
  parallel binary check here would only add ambiguity about which flag is
  authoritative -- a passthrough avoids that, consistent with retiring
  excess.py's redundant evolved-star stopgap the same day for the same
  reason.
- Debris-disk crossmatch position source: a0's gaia_ra/gaia_dec only (not
  miri_ra_{band}) -- non-Gaia-matched singleton detections have no reliable
  position to cross-match on anyway and are already heavily disqualified
  via qc_poor_photosphere_fit regardless, so this is not a meaningful
  coverage gap.
- Debris-disk crossmatch radius (contaminants.debris_disk.crossmatch_radius_arcsec,
  2.0 arcsec) is a STATED COMPROMISE, not a derived value -- same status as
  retriever.py's 2MASS crossmatch radius. Deliberately more generous than
  this project's Gaia-MIRI (0.25") or Gaia-2MASS (0.5") radii: Cotten &
  Song (2016)'s positions come from Tycho-2 (epoch ~1991) cross-correlated
  with AllWISE, with NO per-star proper motion available to propagate
  forward to our own stars' Gaia epoch (2016.0) -- unlike the Gaia-2MASS
  crossmatch, which DOES propagate epochs (a real bug was caught there,
  2026-07-15, from skipping exactly this step). 2.0" is generous enough to
  tolerate a few decades of untreated proper motion for most field stars
  without being reckless -- the ambiguous-match count (see
  crossmatch_debris_disk_catalog) is the mechanism relied on to surface
  where this compromise breaks down, same role it plays in retriever.py's
  own crossmatches. Revisit if the ambiguous-match rate turns out high at
  archive scale.
- qc_confirmed_field_star's parallax-S/N gate (contaminants.cluster_membership.min_parallax_over_error,
  same value/convention as evolved_star's gate) does double duty: it is
  both the usual "don't trust a noisy inverted parallax" guard (see the
  general S/N-gate lesson logged 2026-07-22) AND, as a side effect,
  structurally the Galactic/extragalactic discriminator this project
  already established it needed to be (2026-07-22 Tier 3 sequencing entry:
  CONTROLFIELD confirmed Galactic via measurable parallax, NGC-602
  confirmed SMC-distance via parallax below Gaia's precision floor). A
  genuinely extragalactic star's true parallax is ~20x below typical Gaia
  measurement error at these distances and will essentially never clear
  a S/N>=5 bar -- so this check can never exonerate an NGC-602-like star,
  not because of an explicit distance cut, but as a natural consequence of
  the same statistical gate already used elsewhere. Not independently
  re-derived for this specific purpose; noted as a fortunate, checked
  consequence, not assumed without the earlier verification behind it.
- Cantat-Gaudin (2020) is keyed by Gaia DR2 source_id; this project's own
  gaia_source_id comes from Gaia DR3. The two are the same integer for the
  large majority of sources (DR3 largely preserves DR2 source_ids), but
  this is a stated, known limitation -- NOT independently verified to be
  perfect for every source in this project's own sample. Revisit if a
  cross-DR mismatch is ever suspected (e.g. a star that should plausibly
  be a member showing up as qc_confirmed_field_star instead).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import xarray as xr

from pipeline import __version__
from pipeline.excess import DISQUALIFYING_STAR_FLAGS

logger = logging.getLogger(__name__)


# --- Join / alignment ------------------------------------------------------


def assert_star_aligned(a0_ds: xr.Dataset, b1_ds: xr.Dataset) -> None:
    """Raises AssertionError unless a0 and b1's star_id arrays are
    identical, element-for-element. Same convention and reasoning as
    excess.py's assert_star_aligned (retriever.py row-misalignment
    precedent, 2026-07-15) -- checked explicitly rather than trusted."""
    a0_ids = a0_ds["star_id"].values
    b1_ids = b1_ds["star_id"].values
    if a0_ids.shape != b1_ids.shape:
        raise AssertionError(
            f"star dimension length mismatch: a0={a0_ids.shape}, b1={b1_ids.shape}"
        )
    if not np.array_equal(a0_ids, b1_ids):
        raise AssertionError("a0 and b1 star_id arrays are not aligned -- refusing to join")


# --- qc_evolved_star: HR-diagram overluminosity-for-Teff --------------------

# Same Teff anchor points as photosphere.py's _TEFF_ANCHOR_TEFF (rough
# Pecaut & Mamajek-like main-sequence values, recalled approximately rather
# than taken from a re-checked table -- see module docstring), each paired
# with a rough main-sequence absolute G magnitude.
_MS_ANCHOR_TEFF = np.array(
    [3000, 3870, 4410, 5240, 5610, 5930, 6510, 7220, 8080, 9700, 20000, 31500, 42000]
)
_MS_ANCHOR_ABS_G = np.array(
    [11.5, 8.8, 7.3, 5.9, 5.0, 4.4, 3.5, 2.5, 1.9, 0.65, -1.6, -3.6, -5.5]
)


def expected_ms_abs_g(teff: float) -> float:
    """Rough main-sequence absolute G magnitude for a given Teff -- see
    module docstring. Clipped at the anchor table's range, not
    extrapolated (same convention as photosphere.py's rough_teff_from_bp_rp)."""
    return float(np.interp(teff, _MS_ANCHOR_TEFF, _MS_ANCHOR_ABS_G))


def absolute_g_mag(phot_g_mean_mag: float, parallax_mas: float) -> float:
    """Distance-modulus absolute G magnitude from Gaia parallax. NOT
    extinction-corrected -- see module docstring for why that's a
    deliberate, directionally-safe simplification. NaN if parallax is
    non-finite/non-positive or phot_g_mean_mag is non-finite (no distance
    -> no absolute magnitude, not a guess)."""
    if not np.isfinite(parallax_mas) or parallax_mas <= 0 or not np.isfinite(phot_g_mean_mag):
        return np.nan
    distance_pc = 1000.0 / parallax_mas
    return phot_g_mean_mag - 5.0 * np.log10(distance_pc) + 5.0


def is_evolved_star_overluminous(
    photosphere_teff: float,
    phot_g_mean_mag: float,
    parallax_mas: float,
    parallax_error_mas: float,
    config: dict,
) -> bool:
    """True if the star is significantly MORE luminous than expected for a
    main-sequence dwarf at its own fitted Teff -- the standard HR-diagram
    giant/subgiant discriminator (a giant has a much larger radius than a
    dwarf at the same Teff, hence much higher luminosity). Returns False
    (not flagged, not guessed) if photosphere_teff, phot_g_mean_mag, or
    parallax_mas is unusable -- absence of information is not evidence of
    being evolved.

    Gates on parallax quality (parallax/parallax_error >=
    contaminants.evolved_star.min_parallax_over_error) before trusting a
    derived distance/magnitude at all -- added after a real-data check
    (2026-07-22, PN-TC-1) found several faint, distant sources with
    fractional parallax errors up to 165% getting flagged as "overluminous"
    purely from parallax noise (inverting a noisy parallax to get a
    distance is a well-known bias: it systematically manufactures apparent
    overluminosity/distance for intrinsically ordinary stars). A low-S/N
    parallax is treated as unusable, same as a missing one -- not silently
    trusted just because it happens to be finite."""
    if not np.isfinite(photosphere_teff):
        return False
    min_parallax_snr = config["contaminants"]["evolved_star"]["min_parallax_over_error"]
    if (
        not np.isfinite(parallax_mas)
        or not np.isfinite(parallax_error_mas)
        or parallax_error_mas <= 0
        or (parallax_mas / parallax_error_mas) < min_parallax_snr
    ):
        return False
    m_g = absolute_g_mag(phot_g_mean_mag, parallax_mas)
    if not np.isfinite(m_g):
        return False
    expected_m_g = expected_ms_abs_g(photosphere_teff)
    overluminosity_mag = expected_m_g - m_g  # positive = actually brighter than expected
    threshold = config["contaminants"]["evolved_star"]["overluminosity_mag_threshold"]
    return bool(overluminosity_mag > threshold)


# --- qc_background_galaxy: existing a0 morphology columns -------------------


def compute_background_galaxy_flag(a0_ds: xr.Dataset, bands: list[str]) -> np.ndarray:
    """Boolean, per-star: True if a0's is_extended_{band} (the pipeline's
    own automated source_catalog morphology classification) is True in ANY
    measured band. Coarse and non-specific -- "extended" doesn't
    distinguish a background galaxy from a blend, nebula, or artifact (see
    module docstring) -- supporting evidence, not a validated galaxy
    classifier. NaN (band not measured) counts as no evidence, not
    "extended"."""
    n = a0_ds.sizes["star"]
    flag = np.zeros(n, dtype=bool)
    for band in bands:
        col = f"is_extended_{band}"
        if col in a0_ds:
            vals = a0_ds[col].values
            flag |= np.isfinite(vals) & (vals != 0)
    return flag


# --- qc_known_variable: Gaia DR3's own variability pipeline -----------------


def query_gaia_variability(source_ids: np.ndarray) -> set[int]:
    """Returns the subset of source_ids present in Gaia DR3's own
    variability catalogue (gaiadr3.vari_summary -- confirmed live and
    queryable 2026-07-22, same TAP service retriever.py already uses).
    Existence in this table means Gaia's own variability pipeline produced
    a classification/statistics result for this source (any of the
    in_vari_* categories -- eclipsing binary, long-period variable,
    rotation modulation, etc.), regardless of which specific type -- any
    hit is sufficient for "known variable" here. THE FIRST live-network
    call in this module -- kept separate from compute_known_variable_flag
    (the pure/testable part) so unit tests never touch the network, same
    convention as this project's other live-service dependencies
    (stsynphot/expecto/dustmaps/astroquery.svo_fps are smoke-tested, not
    mocked). A single bulk query, not one per star -- see module docstring
    for the scalability caveat (fine at this project's current test scale,
    not yet scaled to the full archive)."""
    from astroquery.gaia import Gaia

    ids = sorted({int(s) for s in source_ids if s != 0})
    if not ids:
        return set()
    id_list = ",".join(str(i) for i in ids)
    job = Gaia.launch_job(f"SELECT source_id FROM gaiadr3.vari_summary WHERE source_id IN ({id_list})")
    result = job.get_results()
    return {int(s) for s in result["source_id"]}


def compute_known_variable_flag(gaia_source_id: np.ndarray, variable_source_ids: set[int]) -> np.ndarray:
    """Boolean, per-star: True if gaia_source_id is a member of
    variable_source_ids (see query_gaia_variability). Pure/testable,
    deliberately separated from the live Gaia query itself. Sources with
    gaia_source_id==0 (no Gaia match, per retriever.py's sentinel
    convention) are never flagged -- there is nothing to look up."""
    return np.asarray(
        [int(sid) != 0 and int(sid) in variable_source_ids for sid in gaia_source_id], dtype=bool
    )


# --- qc_binary_companion_contamination: passthrough of qc_possible_binary ----


def compute_binary_companion_contamination_flag(b1_ds: xr.Dataset) -> np.ndarray:
    """Passthrough of the already-implemented qc_possible_binary
    (photosphere.py, carried through into b1 by excess.py) -- deliberately
    NOT new detection logic. Checked live 2026-07-22 (see
    RESEARCH_CONTEXT.md Decision Log, Question 1) that Gaia's NSS
    orbit-solution tables catch zero cases RUWE/non_single_star already
    miss (0/500 in a real sample) -- the marginal value found (a
    luminosity-ratio refinement for ~22% of an already-narrow subset) was
    judged too thin to justify a second, parallel binary-detection
    mechanism, which would only risk ambiguity about which flag is
    authoritative."""
    return b1_ds["qc_possible_binary"].values.astype(bool)


# --- qc_debris_disk_prime / qc_debris_disk_reserved: Cotten & Song (2016) ----

DEBRIS_DISK_PRIME_TABLE = "J/ApJS/225/15/table3"
DEBRIS_DISK_RESERVED_TABLE = "J/ApJS/225/15/table4"


def fetch_debris_disk_catalog():
    """Fetches Cotten & Song (2016), ApJS 225, 15, "A Comprehensive Census
    of Nearby Infrared Excess Stars" from VizieR (confirmed live and
    queryable 2026-07-22 -- see RESEARCH_CONTEXT.md Decision Log for the
    time-boxed catalog search that selected this source over Kennedy &
    Wyatt 2013). Returns (prime_table, reserved_table) -- table3 (505 rows,
    higher-confidence "Prime" candidates) and table4 (1257 rows,
    lower-confidence "Reserved" candidates), both with RAJ2000/DEJ2000 in
    sexagesimal string format (confirmed live -- no decimal-degree column
    is provided by this catalog, unlike some others). THE SECOND live-
    network call in this module -- kept separate from the pure
    crossmatch_debris_disk_catalog function so unit tests never touch the
    network, same convention as query_gaia_variability."""
    from astroquery.vizier import Vizier

    v = Vizier(columns=["*"])
    v.ROW_LIMIT = -1
    prime = v.get_catalogs(DEBRIS_DISK_PRIME_TABLE)[0]
    reserved = v.get_catalogs(DEBRIS_DISK_RESERVED_TABLE)[0]
    return prime, reserved


def crossmatch_debris_disk_catalog(
    star_ra: np.ndarray, star_dec: np.ndarray, catalog_table, radius_arcsec: float
) -> tuple[np.ndarray, np.ndarray]:
    """Position cross-match of (star_ra, star_dec) [decimal degrees] against
    catalog_table's RAJ2000/DEJ2000 (sexagesimal strings -- parsed with
    unit=(hourangle, deg)). Returns (matched, ambiguous) boolean arrays,
    same length as star_ra: matched[i] is True if star i has at least one
    catalog entry within radius_arcsec; ambiguous[i] is True if MORE than
    one entry falls within the radius -- same convention as retriever.py's
    qc_ambiguous_gaia_match/qc_ambiguous_2mass_match (surfaces where the
    stated-compromise radius breaks down, doesn't silently resolve to a
    single "closest" match). Stars with non-finite ra/dec, or an empty
    catalog_table, are never matched (pure/testable, no network access)."""
    from astropy.coordinates import SkyCoord
    from astropy import units as u

    n = len(star_ra)
    matched = np.zeros(n, dtype=bool)
    ambiguous = np.zeros(n, dtype=bool)
    if len(catalog_table) == 0:
        return matched, ambiguous

    valid = np.isfinite(star_ra) & np.isfinite(star_dec)
    if not np.any(valid):
        return matched, ambiguous

    valid_indices = np.flatnonzero(valid)
    star_coords = SkyCoord(ra=star_ra[valid] * u.deg, dec=star_dec[valid] * u.deg)
    cat_coords = SkyCoord(
        ra=catalog_table["RAJ2000"], dec=catalog_table["DEJ2000"], unit=(u.hourangle, u.deg)
    )
    # NOTE (verified empirically 2026-07-22, not assumed from memory of the
    # docs -- an initial version got this backwards and was caught by its
    # own unit test): SkyCoord.search_around_sky(self, other, seplimit)
    # returns (idx1, idx2, sep2d, dist3d) where idx1 indexes `other` (the
    # ARGUMENT) and idx2 indexes `self` -- the reverse of what the method
    # name/signature suggests at a glance. So idx_in_star_coords is the
    # SECOND return value here, not the first.
    _, idx_in_star_coords, _, _ = star_coords.search_around_sky(cat_coords, radius_arcsec * u.arcsec)
    counts = np.bincount(idx_in_star_coords, minlength=len(star_coords))

    matched[valid_indices] = counts > 0
    ambiguous[valid_indices] = counts > 1
    return matched, ambiguous


# --- qc_cluster_member_confirmed / qc_confirmed_field_star: Cantat-Gaudin (2020) --

CLUSTER_MEMBERSHIP_TAP_URL = "https://tapvizier.cds.unistra.fr/TAPVizieR/tap"
CLUSTER_MEMBERSHIP_TABLE = '"J/A+A/640/A1/nodup"'


def query_cluster_membership(gaia_source_id: np.ndarray) -> set[int]:
    """Returns the subset of gaia_source_id present in Cantat-Gaudin et al.
    (2020), A&A 640, A1's open-cluster membership catalogue (VizieR
    J/A+A/640/A1, "nodup" members table -- confirmed live 2026-07-22, the
    Milky Way half of the young-cluster/PMS gap). This table (~2000
    clusters, likely millions of members) is too large to bulk-download
    (a full-table fetch timed out at ROW_LIMIT=-1) -- queried instead via
    VizieR's TAP service (confirmed live) with a targeted
    `GaiaDR2 IN (...)` clause over just the source_ids being checked, same
    efficient pattern as query_gaia_variability's bulk query. THE THIRD
    live-network call in this module -- kept separate from the pure
    per-star flag functions below so unit tests never touch the network.
    Keyed by Gaia DR2 source_id -- see module docstring for the stated,
    unverified DR2/DR3 source_id compatibility assumption."""
    from pyvo.dal import TAPService

    ids = sorted({int(s) for s in gaia_source_id if s != 0})
    if not ids:
        return set()
    id_list = ",".join(str(i) for i in ids)
    tap = TAPService(CLUSTER_MEMBERSHIP_TAP_URL)
    result = tap.search(
        f"SELECT GaiaDR2 FROM {CLUSTER_MEMBERSHIP_TABLE} WHERE GaiaDR2 IN ({id_list})"
    ).to_table()
    return {int(s) for s in result["GaiaDR2"]}


def compute_cluster_member_confirmed_flag(gaia_source_id: np.ndarray, member_source_ids: set[int]) -> np.ndarray:
    """Boolean, per-star: True if gaia_source_id is a confirmed member of a
    known open cluster/young association per query_cluster_membership -- a
    genuine, specific disqualifying signal in its own right, stronger
    evidence than excess.py's coarse, field-wide qc_stopgap_young_cluster."""
    return np.asarray(
        [int(sid) != 0 and int(sid) in member_source_ids for sid in gaia_source_id], dtype=bool
    )


def is_confirmed_field_star(
    gaia_source_id: int,
    parallax_mas: float,
    parallax_error_mas: float,
    member_source_ids: set[int],
    config: dict,
) -> bool:
    """True if there is positive evidence this star is an ordinary Galactic
    field star, not a genuine cluster/association member -- i.e. safe to
    exonerate from excess.py's coarse qc_stopgap_young_cluster (see the
    qc_*_refined columns in assemble_level_b2). Requires BOTH: (1) a
    trustworthy parallax (parallax/parallax_error >= min_parallax_over_error
    -- same S/N-gate pattern as is_evolved_star_overluminous; see module
    docstring for why this also structurally rules out ever exonerating a
    genuinely extragalactic star, without a separate distance cut); (2) NOT
    found in Cantat-Gaudin et al. (2020)'s membership catalogue. Absence of
    a trustworthy parallax is NOT evidence either way -- returns False (not
    confirmed), same "absence of information is not evidence" principle
    used throughout this module."""
    min_snr = config["contaminants"]["cluster_membership"]["min_parallax_over_error"]
    if not np.isfinite(parallax_mas) or not np.isfinite(parallax_error_mas) or parallax_error_mas <= 0:
        return False
    if (parallax_mas / parallax_error_mas) < min_snr:
        return False
    return int(gaia_source_id) not in member_source_ids


# --- Assembly and output -------------------------------------------------------


def assemble_level_b2(
    a0_ds: xr.Dataset,
    b1_ds: xr.Dataset,
    config: dict,
    variable_source_ids: set[int],
    debris_disk_prime_table,
    debris_disk_reserved_table,
    cluster_member_source_ids: set[int],
) -> xr.Dataset:
    """Joins a0 onto b1 (excess.py's output) and computes the contaminant
    qc_* flags implemented so far. Runs over the full b1 population, not
    just excess-showing candidates -- see module docstring. Carries every
    b1 column through unchanged.

    variable_source_ids, the two debris-disk catalog tables, and
    cluster_member_source_ids must all be resolved by the caller (run() --
    via query_gaia_variability, fetch_debris_disk_catalog, and
    query_cluster_membership, all live network calls) BEFORE calling this
    function -- kept out of this function deliberately so it stays fully
    offline-testable, same convention as the rest of this module."""
    assert_star_aligned(a0_ds, b1_ds)

    bands = config["excess"]["primary_bands"]
    data_vars: dict[str, tuple] = {name: ("star", b1_ds[name].values) for name in b1_ds.data_vars}

    teff = b1_ds["photosphere_teff"].values
    g_mag = a0_ds["gaia_phot_g_mean_mag"].values
    parallax = a0_ds["gaia_parallax"].values
    parallax_error = a0_ds["gaia_parallax_error"].values
    evolved = np.asarray(
        [
            is_evolved_star_overluminous(t, g, p, p_err, config)
            for t, g, p, p_err in zip(teff, g_mag, parallax, parallax_error)
        ]
    )
    data_vars["qc_evolved_star"] = ("star", evolved.astype(np.int32))

    background_galaxy = compute_background_galaxy_flag(a0_ds, bands)
    data_vars["qc_background_galaxy"] = ("star", background_galaxy.astype(np.int32))

    known_variable = compute_known_variable_flag(b1_ds["gaia_source_id"].values, variable_source_ids)
    data_vars["qc_known_variable"] = ("star", known_variable.astype(np.int32))

    binary_contamination = compute_binary_companion_contamination_flag(b1_ds)
    data_vars["qc_binary_companion_contamination"] = ("star", binary_contamination.astype(np.int32))

    radius_arcsec = config["contaminants"]["debris_disk"]["crossmatch_radius_arcsec"]
    star_ra = a0_ds["gaia_ra"].values
    star_dec = a0_ds["gaia_dec"].values
    prime_matched, prime_ambiguous = crossmatch_debris_disk_catalog(
        star_ra, star_dec, debris_disk_prime_table, radius_arcsec
    )
    reserved_matched, reserved_ambiguous = crossmatch_debris_disk_catalog(
        star_ra, star_dec, debris_disk_reserved_table, radius_arcsec
    )
    data_vars["qc_debris_disk_prime"] = ("star", prime_matched.astype(np.int32))
    data_vars["qc_debris_disk_reserved"] = ("star", reserved_matched.astype(np.int32))
    data_vars["qc_ambiguous_debris_disk_match"] = (
        "star",
        (prime_ambiguous | reserved_ambiguous).astype(np.int32),
    )

    gaia_source_id = b1_ds["gaia_source_id"].values
    cluster_member = compute_cluster_member_confirmed_flag(gaia_source_id, cluster_member_source_ids)
    data_vars["qc_cluster_member_confirmed"] = ("star", cluster_member.astype(np.int32))

    confirmed_field_star = np.asarray(
        [
            is_confirmed_field_star(sid, p, p_err, cluster_member_source_ids, config)
            for sid, p, p_err in zip(gaia_source_id, parallax, parallax_error)
        ]
    )
    data_vars["qc_confirmed_field_star"] = ("star", confirmed_field_star.astype(np.int32))

    # qc_*_refined: an ADDITIVE parallel composite (see module docstring) --
    # identical to b1's own qc_star_disqualified/qc_excess_clean_{band}/
    # qc_candidate_preliminary logic, except qc_stopgap_young_cluster's
    # contribution is overridden wherever qc_confirmed_field_star provides
    # positive evidence. Never mutates b1's own columns (carried through
    # unchanged above).
    star_flags_excl_young_cluster = [
        f for f in DISQUALIFYING_STAR_FLAGS if f != "qc_stopgap_young_cluster"
    ]
    n = b1_ds.sizes["star"]
    star_disqualified_excl_yc = np.zeros(n, dtype=bool)
    for name in star_flags_excl_young_cluster:
        if name in b1_ds:
            star_disqualified_excl_yc |= b1_ds[name].values.astype(bool)
    young_cluster_flag = (
        b1_ds["qc_stopgap_young_cluster"].values.astype(bool)
        if "qc_stopgap_young_cluster" in b1_ds
        else np.zeros(n, dtype=bool)
    )
    star_disqualified_refined = star_disqualified_excl_yc | (young_cluster_flag & ~confirmed_field_star)
    data_vars["qc_star_disqualified_refined"] = ("star", star_disqualified_refined.astype(np.int32))

    significance_threshold = config["excess"].get("significance_threshold_sigma")
    significant_refined_by_band = {}
    for band in bands:
        band_disqualified = b1_ds[f"qc_band_disqualified_{band}"].values.astype(bool)
        clean_refined = ~star_disqualified_refined & ~band_disqualified
        data_vars[f"qc_excess_clean_refined_{band}"] = ("star", clean_refined.astype(np.int32))

        if significance_threshold is not None:
            sigma = b1_ds[f"excess_sigma_{band}"].values
            significant_refined = clean_refined & np.isfinite(sigma) & (sigma >= significance_threshold)
            data_vars[f"qc_excess_significant_refined_{band}"] = (
                "star",
                significant_refined.astype(np.int32),
            )
            significant_refined_by_band[band] = significant_refined

    if significance_threshold is not None and "qc_single_filter_detection" in b1_ds:
        dual_band = ~b1_ds["qc_single_filter_detection"].values.astype(bool)
        candidate_refined = dual_band & np.logical_and.reduce(
            [significant_refined_by_band[b] for b in bands]
        )
        data_vars["qc_candidate_preliminary_refined"] = ("star", candidate_refined.astype(np.int32))

    # Partial composite: only reflects the categories implemented so far --
    # explicitly named and documented as such, never to be mistaken for the
    # eventual qc_anomalous_excess (needs all six categories, see module
    # docstring). qc_confirmed_field_star is deliberately EXCLUDED here --
    # it is positive exonerating evidence, not a contaminant flag.
    flagged_partial = (
        evolved
        | background_galaxy
        | known_variable
        | binary_contamination
        | prime_matched
        | reserved_matched
        | cluster_member
    )
    data_vars["qc_contaminant_flagged_partial"] = ("star", flagged_partial.astype(np.int32))

    ds = xr.Dataset(data_vars=data_vars, coords={"star": b1_ds["star"].values})
    ds.attrs["pipeline_version"] = __version__
    ds.attrs["evolved_star_overluminosity_mag_threshold"] = config["contaminants"]["evolved_star"][
        "overluminosity_mag_threshold"
    ]
    ds.attrs["debris_disk_crossmatch_radius_arcsec"] = radius_arcsec
    ds.attrs["note"] = (
        "qc_contaminant_flagged_partial is the OR of every contaminant signal implemented "
        "so far (qc_evolved_star, qc_background_galaxy, qc_known_variable, "
        "qc_binary_companion_contamination, qc_debris_disk_prime/_reserved, "
        "qc_cluster_member_confirmed) -- still 'partial' in the sense that mattered when "
        "this attr was first named: qc_photometric_artifact and the young-cluster/PMS "
        "extragalactic half remain unimplemented (see RESEARCH_CONTEXT.md priority "
        "ordering, 2026-07-22 Decision Log). qc_anomalous_excess remains uncomputed. "
        "qc_confirmed_field_star is deliberately NOT included here -- it is positive "
        "exonerating evidence, not a contaminant flag; see qc_*_refined columns instead."
    )
    return ds


def save_level_b2(ds: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path)
    logger.info("Saved level b2 dataset to %s (%d stars)", path, ds.sizes["star"])


# --- Orchestration -------------------------------------------------------------


def run(config: dict, a0_path: Path, b1_path: Path, output_path: Path) -> xr.Dataset:
    """Runs the contaminant-flagging stage implemented so far: load a0/b1 ->
    query Gaia variability + fetch the debris-disk catalog + query the
    Milky Way cluster-membership catalog (live network calls) -> assert
    star alignment -> compute qc_evolved_star/qc_background_galaxy/
    qc_known_variable/qc_binary_companion_contamination/
    qc_debris_disk_prime/_reserved/qc_cluster_member_confirmed/
    qc_confirmed_field_star (+ qc_*_refined) -> save b2."""
    a0_ds = xr.open_dataset(a0_path)
    b1_ds = xr.open_dataset(b1_path)

    variable_source_ids = query_gaia_variability(b1_ds["gaia_source_id"].values)
    prime_table, reserved_table = fetch_debris_disk_catalog()
    cluster_member_source_ids = query_cluster_membership(b1_ds["gaia_source_id"].values)

    ds = assemble_level_b2(
        a0_ds,
        b1_ds,
        config,
        variable_source_ids,
        prime_table,
        reserved_table,
        cluster_member_source_ids,
    )
    save_level_b2(ds, output_path)
    return ds
