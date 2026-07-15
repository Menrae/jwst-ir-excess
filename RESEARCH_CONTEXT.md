# Research Context

This file is the living scientific record of the project: the questions we've
resolved, the ones still open, and the reasoning behind methodological
decisions. It is meant to be updated as we go, not written once and
forgotten -- when we make a decision in conversation that affects the
pipeline, it should get captured here.

## Project

**Title:** Searching for Anomalous Infrared Excess in Stars Observed by
JWST/MIRI: A Pipeline for Dyson Sphere Candidate Detection

**Researcher:** Undergraduate astronomy researcher, University of Washington
Seattle. Summer 2026 independent research project, intended for publication.

## Scientific Claim (kept deliberately modest)

We are **not** claiming to detect Dyson spheres. We are building a validated
anomaly-detection pipeline that flags stars with unexplained mid-IR excess
after exhaustive contaminant removal, and characterizing the statistical
properties of that population. A well-characterized null result is a
legitimate, publishable outcome. Any positive detection of genuinely
unexplained excess is a candidate for follow-up, not a claim of megastructure
detection.

## Why This Is Original

Prior IR-excess technosignature searches (Carrigan 2009 / IRAS; Griffith et
al. 2015 / WISE-G-HAT) used lower-sensitivity, lower-resolution IR data.
JWST/MIRI offers substantially better photometric sensitivity than Spitzer
IRAC at comparable wavelengths. A systematic pipeline-based search of the
growing public JWST MIRI archive for this signature has not been published
as of project start (July 2026) -- **this specific originality claim has not
yet been re-verified against current literature and should be checked before
it appears in any writeup.** Checked 2026-07-15: Project Hephaistos II
(arXiv:2405.02927, 2024, see literature table) runs a closely analogous
Gaia DR3 + 2MASS + WISE cross-match search but confirmed does NOT use
JWST/MIRI data, so it does not conflict with this claim -- though the full
paper should still be read (not just its abstract) before the claim is
finalized in any writeup, since this check was scoped to the instrument
question only.

## Key Prior Literature

| Reference | Relevance | Status |
|---|---|---|
| Carrigan (2009), ApJ 698, 2075 | First systematic IRAS Dyson sphere search; baseline methodology | Citation verified 2026-07-15; content not yet reviewed |
| Griffith et al. (2015), ApJS 217, 25 | G-HAT / WISE survey; most comprehensive prior search | Citation verified 2026-07-15; content not yet reviewed |
| Wright et al. (2014), ApJ 792, 26 | Theoretical framework for Dysonian SETI | Citation verified 2026-07-15; content not yet reviewed |
| ~~Lacy et al. (2023, 2024)~~ → Libralato et al. (2024), arXiv:2311.12145 | JWST/MIRI point-source photometry performance; informed the retriever.py decision to use `_i2d` mosaics rather than the pipeline's automated `_cat.ecsv` as the excess-critical photometry source (see Decision Log) | **Corrected 2026-07-15.** Original "Lacy et al." citation was an unverified scaffold placeholder -- no matching paper could be located after multiple targeted searches. Libralato et al. substituted as the paper actually used; content read (targeted, not full paper). Confidence: medium-high on Libralato et al.'s findings, low on whether it's the originally-intended reference |
| Jura (2003), ApJ 584, L91 | Debris disk IR excess contamination | **Confirmed mismatch 2026-07-15**: scoped specifically to *white dwarfs* (G29-38 tidal-disruption disk), not main-sequence stars. If this survey's contaminant framework only covers main-sequence targets, this citation should be dropped or kept only for a white-dwarf-specific contaminant subcategory, not used as the general debris-disk reference -- Kennedy & Wyatt (2013) below is the main-sequence-appropriate one |
| Kennedy & Wyatt (2013), MNRAS 433, 2334 | Debris disk statistics, prior contamination rate (main-sequence stars) | Citation verified 2026-07-15; content not yet reviewed |
| Project Hephaistos II, arXiv:2405.02927 (2024) | Gaia DR3 + 2MASS + WISE cross-match Dyson-sphere search -- close methodological precedent (NOT JWST/MIRI-based, confirmed 2026-07-15, so does not conflict with the originality claim below); 7 M-dwarf IR-excess candidates worth comparing against later | Abstract/methodology reviewed 2026-07-15 (confirms no JWST use); full paper not yet read |

**Note:** Existence of each citation above (author/year/journal) was checked
2026-07-15 via targeted search, but this is *not* the same as having read and
reviewed their content/findings -- only Libralato et al. has been read
(partially, targeted to one question) so far. Findings from the rest should
still not be assumed or cited until actually read.

## Pipeline Architecture (tsdat-inspired)

1. **Retriever** (`pipeline/retriever.py`) -- MAST (JWST/MIRI) + Gaia DR3 +
   2MASS ingestion. Raw data -> data level a0.
2. **Standardise** (`pipeline/photosphere.py`) -- Photosphere model fitting
   (Kurucz/PHOENIX/blackbody, TBD) to optical + near-IR photometry;
   extraction of mid-IR residuals. -> data level a1.
3. **Quality/anomaly** (`pipeline/excess.py`, `pipeline/contaminants.py`) --
   Excess significance scoring, contaminant cross-matching and
   classification, `qc_*` flag assignment. -> data level b1.
4. **Output** (`pipeline/output.py`) -- FITS catalogue, diagnostic figures,
   LaTeX table export.

Data moves between stages as `xarray.Dataset` objects saved to NetCDF. Every
QC decision is recorded as an explicit `qc_*` variable rather than by
silently dropping rows, so that the final candidate list is fully traceable
back through every contaminant check.

## Open Methodological Questions (must resolve before relevant code is written)

- [x] What MIRI photometry product(s) does MAST actually serve via
      `astroquery.mast` for point sources -- calibrated catalogue photometry,
      or only Level 3 mosaics requiring our own PSF photometry? **Resolved
      2026-07-15: both exist, but the automated catalogue is not adequate for
      excess-critical photometry -- see Decision Log.** Follow-on question
      (which photometry-extraction method to use on the `_i2d` mosaics) is
      still open and deferred to a later stage design discussion.
- [x] What cross-match radius is appropriate for Gaia DR3 / 2MASS / MIRI
      association, and how does it vary with field crowding? **Resolved
      2026-07-15 (initial values) -- see Decision Log.** Field-crowding
      dependence is handled via an ambiguous-match QC flag rather than a
      variable radius; revisit if that flag fires at a high rate.
- [ ] Which photosphere model (Kurucz, PHOENIX, or blackbody) is appropriate,
      and does the choice need to vary by spectral type?
- [ ] What excess significance threshold (in sigma) is defensible given the
      photometric uncertainty budget?
- [ ] Which reference catalogues will be used for each contaminant category
      (debris disks, variable stars, non-single-star flags, etc.)?
- [ ] Has a systematic MIRI-based IR-excess technosignature search actually
      not been published yet? (Re-verify closer to writeup time, since the
      archive and literature are both moving targets.)

## Decision Log

### 2026-07-15 -- MIRI photometry product & retriever.py scope

MAST serves both calibrated Level 3 point-source photometry (`_cat.ecsv`,
produced by the pipeline's automated `source_catalog` step -- aperture
photometry at 30/50/70% encircled-energy apertures plus isophotal/segment
photometry) and the underlying `_i2d.fits` mosaics, for MIRI imaging Level 3
associations. So we do not need to build a from-scratch PSF-photometry
pipeline just to get photometry at all. However, Libralato et al. (2024,
arXiv:2311.12145) built an independent effective-PSF (ePSF) photometry
pipeline for MIRI specifically because, in their words, "high-precision
astrometry and photometry are not currently performed by any step of the
JWST imager pipeline," and show the automated `_cat.ecsv` aperture photometry
underperforms custom photometry (broader, noisier color-magnitude sequence).

**Decision:** `retriever.py` fetches `_i2d` mosaics as the primary product
for the excess-critical bands (F770W, F1000W), not `_cat.ecsv`. The
`_cat.ecsv` catalog is still retrieved and kept as a discovery/target-list
aid (source positions for initial querying and sanity-checking), but is not
treated as the source of excess-critical photometry. The actual
photometry-extraction method to run on the `_i2d` mosaics (ePSF vs. careful
aperture photometry, etc.) is an open item deferred to a separate design
discussion when that stage is reached -- not resolved here, and not part of
`retriever.py`.

**Confidence:** medium-high that Libralato et al.'s finding is accurate
(read directly, targeted to this question). See literature-table correction
below regarding which paper this citation should actually be.

### 2026-07-15 -- Literature table citation verification pass

While researching the above, ran an existence-check search pass (author /
year / journal, not a full read) on every entry in the "Key Prior Literature"
table, prompted by discovering that "Lacy et al. (2023, 2024)" did not
correspond to any locatable paper. Findings:

- **"Lacy et al. (2023, 2024)"** -- could not locate a matching paper despite
  multiple targeted searches. Concluded this was an unverified placeholder
  citation left over from the initial project scaffold, not a citation that
  had actually been confirmed. Replaced in the literature table with
  Libralato et al. (2024), arXiv:2311.12145, which is on-topic and is the
  paper actually used to inform the retriever-scope decision above.
- **Carrigan (2009), Griffith et al. (2015), Wright et al. (2014), Kennedy &
  Wyatt (2013)** -- all confirmed to exist under their stated citations
  (author/year/journal match). Content still not yet reviewed.
- **Jura (2003)** -- confirmed to exist, but it is specifically a white-dwarf
  debris-disk paper (G29-38), which may not be the right fit for a
  main-sequence-star contaminant framework. Flagged for a closer look during
  the actual literature review, not assumed correct as-is.
- **New reference found incidentally:** Project Hephaistos II (arXiv:2405.02927,
  2024) runs a closely analogous Gaia DR3 + 2MASS + WISE cross-match Dyson
  sphere search. Added to the literature table; bears directly on the
  originality claim and should be read before that claim is finalized.

### 2026-07-15 -- Cross-match radii

Agreed values: **MIRI-Gaia 0.25″**, **Gaia-2MASS 0.5″**, both applied after
propagating Gaia DR3 positions (with proper motion) to the epoch of the
catalog being matched against, rather than matching raw catalog coordinates
directly. Ambiguous multi-matches (more than one candidate within the
radius) are flagged via a QC variable rather than auto-resolved or dropped.

1. The MIRI-Gaia value is based on Libralato et al.'s reported ~1-3 mas
   post-`tweakreg` astrometric accuracy for MIRI (JWST Stage 3 aligns
   absolute astrometry to Gaia by default), with margin added for residual
   detector-edge distortion and epoch-propagation error.
2. The Gaia-2MASS value is a fixed compromise, not a validated constant: the
   2MASS Explanatory Supplement (§4.9) gives positional uncertainty ranging
   from ~80-100 mas (bright, Ks<14) to ~250 mas (faint, Ks~16) -- more than a
   factor of 2 across the catalog. 0.5″ is a single starting radius chosen to
   cover most of that range without flooding crowded fields with ambiguous
   matches. It is a deliberate simplification, not a researched threshold,
   and should be revisited if it turns out to be systematically too tight
   for faint sources or too loose in crowded fields.
3. Because of point 2, the ambiguous-match QC flag isn't just a safety net --
   it's the mechanism relied on to surface where this fixed radius breaks
   down, since a magnitude- or crowding-dependent radius was deliberately not
   implemented upfront.

### 2026-07-15 -- Row-misalignment bug in retriever.py cross-match (caught pre-merge)

While smoke-testing `crossmatch_gaia`/`crossmatch_2mass` against live data
(2-3 real MIRI observations at a time), the 2MASS cross-match came back with
implausibly zero matches for sources in a young-stellar-object field
(Ophiuchus protostars) where near-IR detections should be common. Digging
in rather than assuming the field just had poor coverage (per project
convention 2) surfaced the actual cause: both cross-match functions grouped
MIRI sources by observation using `for obs_id in set(miri_sources["obs_id"])`,
then built the matched-Gaia/2MASS columns as plain Python lists appended in
that per-field loop order, and finally assigned them back onto
`miri_sources.copy()` **positionally** (`result[f"gaia_{c}"] = out_cols[c]`).
Python's `set()` does not iterate in table row order, so as soon as a batch
spanned more than one observation, the loop-order list and the original
row order diverged, and each source silently received another source's
match data -- no exception, no warning, just wrong numbers attached to the
right-looking rows. This is exactly the kind of silent-corruption failure
mode that's dangerous precisely because it doesn't crash: a downstream
excess calculation would have quietly compared some sources' MIRI flux
against a different star's Gaia/2MASS photometry.

**How it was caught:** an explicit post-hoc sanity check -- computing the
on-sky separation between each source's own `miri_ra/dec` and its assigned
`gaia_ra/dec` (and `gaia_ra/dec` vs `twomass_RAJ2000/DEJ2000`) -- showed
several hundred arcsec of "separation" for supposedly-matched pairs, wildly
outside both the crossmatch radius and any plausible proper-motion/epoch
effect. That's what exposed the misattribution; without that check, the bug
would have produced a NetCDF file that looked complete and plausible.

**Fix:** both functions now pre-allocate output arrays sized to the full
input table and scatter each match back by explicit row index
(`np.flatnonzero(obs_ids == obs_id)` per observation, indexed assignment),
never relying on loop-order matching table-row-order. Re-verified with the
same separation sanity check: matched miri-gaia and gaia-2mass pairs now
fall within their respective configured radii (0.25″ / 0.5″) once epoch
propagation is applied, and well outside them (hundreds of mas to >1″) when
compared using each catalog's raw, un-propagated epoch -- which also
incidentally confirms the epoch-propagation step is doing real, necessary
work rather than being a no-op.

**Takeaway for future pipeline stages:** any per-group loop (by observation,
by field, by anything) that reassigns results onto a table via a different
grouping than the table's own row order is a standing risk for this same
failure mode. Prefer scatter-by-explicit-index over append-then-reassign
whenever the two orderings aren't provably identical.

### 2026-07-15 -- target_classification allowlist for MIRI observation query

An archive-wide MIRI query with no target-type filter pulls in MAST's full
non-stellar MIRI imaging archive (galaxy surveys, deep fields, calibration
flats) alongside genuine stellar fields -- confirmed by hitting `A1068-OFF`
(a galaxy-cluster field) during random smoke-test sampling. The cross-match
step already handles this correctly in principle (non-stellar sources just
get `qc_no_gaia_match=1` and drop out downstream), but downloading and
processing thousands of irrelevant fields to extract effectively zero
stellar targets is wasteful.

**Decision:** `query_miri_observations` now filters on MAST's
`target_classification` field using `STELLAR_TARGET_CLASSIFICATIONS`, an
**inclusive allowlist** (not an exclusion list) of classification tokens
that mark a target as genuinely stellar/point-source. Critically, targets
with a *missing or ambiguous* classification (empty, `"--"`, or tagged only
`"Unidentified"`) are also kept, not dropped -- the allowlist only excludes
classifications MAST has confidently and specifically marked as non-stellar
(`Galaxy`, `Clusters of Galaxies`, `Solar System`, calibration-only fields
like `Calibration; Telescope/sky background`). Anything that slips through
on a label we didn't anticipate still falls through to the existing
`qc_no_gaia_match` / `qc_ambiguous_gaia_match` downstream QC rather than
being silently dropped at the query stage.

This is a **data-selection efficiency step, not a scientific necessity** --
worth stating plainly for the eventual methods section, since it changes
what gets downloaded but not (by design) what counts as a valid candidate.

Vocabulary and counts verified empirically against the live MAST archive
(F770W/F1000W, calib_level=3, public) on 2026-07-15, total 2515
observations:

- **978** kept via a stellar-allowlist token (e.g. `Star`, `Protoplanetary
  disks`, `Protostars`, `White dwarfs`, `T Tauri stars`, `A dwarfs`, etc.)
- **191** kept as ambiguous/unclassified (`--`, empty, or `Unidentified`)
- **1346** dropped as confidently non-stellar -- dominated by `Galaxy;
  Field galaxies` (218), `Galaxy; Spiral galaxies` (210), `Calibration;
  Telescope/sky background` (133), `Calibration; External flat field` (66),
  and various AGN/starburst/high-z galaxy tags, plus `Clusters of Galaxies`
  and `Solar System` (asteroids, planets)

Notably, several genuinely stellar fields are **not** tagged with a
top-level `Star` component at all -- e.g. `ISM; Molecular gas; Pre-main
sequence stars` (29 observations), `Stellar Cluster; Young star clusters`
(16), `Calibration; A stars` (16, spectrophotometric standard stars
administratively filed under calibration). A naive "classification starts
with Star" check would have wrongly excluded all of these, which is why the
allowlist matches against *any* component of the semicolon-separated
classification string, not just the first.
