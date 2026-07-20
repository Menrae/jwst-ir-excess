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
   2MASS ingestion, cross-match, and pivot to one row per star. Raw data ->
   data level a0.
2. **MIRI photometry extraction** (module TBD -- not yet designed) --
   Measures the actual observed F770W/F1000W point-source flux from the
   `_i2d` mosaics (ePSF vs. careful aperture photometry, method still open).
   **Added as its own stage 2026-07-20**, correcting a gap in the previous
   4-stage description: the Decision Log below (2026-07-15) already
   concluded `_cat.ecsv` aperture photometry is not adequate as
   excess-critical photometry (per Libralato et al. 2024), but no stage
   existed to produce the real replacement -- the architecture list simply
   didn't have a place for it. This stage's internals are an open design
   question (see below), deliberately not designed as part of the
   photosphere.py discussion that surfaced the gap. -> extends data level a0
   with observed MIRI flux, or a new intermediate level (TBD when designed).
3. **Standardise** (`pipeline/photosphere.py`) -- Photosphere model fitting
   (Kurucz/PHOENIX/blackbody, TBD, see Decision Log 2026-07-20 for grid
   accessibility findings) to optical + near-IR photometry; produces
   predicted mid-IR photosphere flux. -> data level a1.
4. **Quality/anomaly** (`pipeline/excess.py`, `pipeline/contaminants.py`) --
   Excess significance scoring (observed MIRI flux from stage 2 vs.
   predicted flux from stage 3), contaminant cross-matching and
   classification, `qc_*` flag assignment. -> data level b1.
5. **Output** (`pipeline/output.py`) -- FITS catalogue, diagnostic figures,
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
- [x] Which photosphere model (Kurucz, PHOENIX, or blackbody) is appropriate,
      and does the choice need to vary by spectral type? **Resolved and
      implemented 2026-07-20 in `pipeline/photosphere.py`** -- Kurucz
      (ck04models via stsynphot/CDBS) for Teff >= 8000 K and the FGK default,
      PHOENIX (Husser et al. 2013 via expecto) for Teff <= 3500 K, with a
      500 K cross-check buffer around both boundaries. See Decision Log for
      the fitting-strategy split this required (continuous search for
      Kurucz, discrete node-hopping for PHOENIX) and the newly-discovered
      PHOENIX mid-IR coverage gap.
- [ ] What excess significance threshold (in sigma) is defensible given the
      photometric uncertainty budget?
- [ ] Which reference catalogues will be used for each contaminant category
      (debris disks, variable stars, non-single-star flags, etc.)?
- [ ] Has a systematic MIRI-based IR-excess technosignature search actually
      not been published yet? (Re-verify closer to writeup time, since the
      archive and literature are both moving targets.)
- [x] **(Added 2026-07-20)** How should extinction/reddening be handled in
      the photosphere fit? **Resolved and implemented 2026-07-20**: Av from
      the Bayestar19 3D dust map (Gaia parallax distance + sky position),
      per the literature precedent (Carrigan 2009; Wright et al. 2014;
      Griffith et al. 2015 -- see Decision Log). Two caveats confirmed live
      during implementation that affect how much this can be trusted: (1)
      no coverage south of dec ~ -30 deg (Pan-STARRS1-based -- confirmed
      both empirically and from the package's own docstring), handled via
      `qc_extinction_uncertain`; (2) the map's native unit needs an
      unverified conversion coefficient to reach Av -- see Decision Log,
      flagged rather than presented as final.
- [ ] **(Added 2026-07-20)** What method should the new MIRI photometry
      extraction stage (architecture item 2, above) use to measure observed
      F770W/F1000W point-source flux from the `_i2d` mosaics -- ePSF
      (Libralato et al. 2024 style) vs. careful aperture photometry?
      Explicitly deferred: this needs its own design discussion, not decided
      alongside photosphere.py.
- [ ] **(Added 2026-07-20)** White dwarfs pass the retriever's
      `STELLAR_TARGET_CLASSIFICATIONS` allowlist, but neither Kurucz nor
      PHOENIX atmosphere grids are appropriate for them (both assume
      main-sequence/giant opacity physics) -- WD-specific grids (e.g.
      Koester models) would be needed and no source for these has been
      identified yet. **Handling implemented 2026-07-20** (skip the fit,
      `qc_no_photosphere_grid=1`, in `pipeline/photosphere.py`), but the
      underlying gap -- no actual WD photosphere model available -- remains
      unresolved; WD targets currently just never get a candidate
      assessment at all, rather than a wrong one.
- [x] T Tauri stars, protostars, and other protoplanetary-disk targets in
      the sample are pre-main-sequence objects that often already show
      near-IR excess (veiling/accretion) in the very optical+near-IR bands
      the photosphere fit uses as its input. **Resolved and implemented
      2026-07-20**: still fit (a comparison baseline is needed), flagged via
      `qc_pms_veiling_risk` in `pipeline/photosphere.py` based on
      `target_classification` tokens -- the flag surfaces the risk for
      downstream review, it doesn't correct for veiling.
- [x] **(Added 2026-07-20, discovered during photosphere.py
      implementation)** PHOENIX (Husser et al. 2013, via `expecto`) spectra
      only extend to ~5.5 micron -- confirmed live, not assumed -- fully
      short of BOTH MIRI bands (F770W starts at 6.2 micron; `synphot` raises
      a hard `DisjointError`, it does not silently extrapolate). **Mitigated
      2026-07-20** via `rj_extrapolation_spectrum` (Rayleigh-Jeans/blackbody
      tail anchored to the PHOENIX model's own flux at its reddest computed
      wavelength) -- `qc_rj_extrapolated` is set alongside
      `qc_no_mid_ir_model_coverage` (which stays 1: the native grid still
      doesn't cover it) and `predicted_flux_*` is now populated rather than
      NaN. **Not fully resolved**: this is a substitute, not a validated
      prediction -- see the excess.py blocking prerequisite below. Measured
      impact (see Decision Log): ~10% of Gaia-matched stars across live test
      samples, concentrated up to ~68% in protostar/YSO-classified fields --
      the population this project cares about most, per the researcher's
      own read of these numbers.
- [ ] **(Added 2026-07-20)** **BLOCKING PREREQUISITE FOR excess.py**:
      `qc_rj_extrapolated` sources must not be scored at equal confidence to
      a native-grid prediction in excess.py's significance calculation.
      This requires validating the Rayleigh-Jeans/blackbody-tail
      extrapolation (`rj_extrapolation_spectrum`) against real cool stars
      with existing WISE/Spitzer mid-IR photometry (known non-excess M
      dwarfs), to produce an actual error-inflation factor (or widened
      error bar) to apply to `predicted_flux_*_err` for these sources.
      Not yet done. Until it is, `predicted_flux_*_err` for
      `qc_rj_extrapolated` sources should be treated as a lower bound, and
      excess.py must not silently treat it as a full error budget.
- [ ] **(Added 2026-07-20, discovered during photosphere.py
      implementation)** Per-star fit runtime is significant: a single star
      needing both the Kurucz default and PHOENIX cross-check took ~50-130 s
      in this environment (excluding the one-time ~16 s Bayestar map load),
      dominated by the profile-likelihood error-bar scan re-evaluating
      synthetic photometry many times. Fine for the ~13-40 star smoke tests
      run so far, but at archive scale (the retriever's live query found
      ~1000+ stellar-classified observations) this would take hours to a
      day-plus in its current form. Not optimized here -- needs a follow-up
      pass (e.g. vectorizing the band-magnitude computation, caching
      spectra more aggressively across stars with similar Teff, or reducing
      the error-bar scan's resolution) before running at full scale.
- [ ] **(Added 2026-07-20, known simplifications carried into the
      implementation, not newly discovered but worth restating here)**
      `photosphere.py` fixes `log_g=4.5` (main-sequence assumption -- giants
      and dwarfs are not distinguished) and Kurucz metallicity to solar
      (`ckp00` subgrid only, out of the 8 metallicity subgrids CDBS serves)
      for every star. Neither is scientifically validated per-star; both
      are stated compromises analogous to the 2MASS crossmatch radius,
      not derived choices. Revisit if a metal-poor or evolved-giant
      subpopulation turns out to matter for the final candidate list.

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

### 2026-07-20 -- retriever.py: pivot to one row per star

Discovered while scoping photosphere.py's design: `assemble_level_a0` (as of
2026-07-15) produced one row per (MIRI detection, filter) pair, not one row
per star, because `load_miri_catalog_sources` builds its table from
per-observation `_cat.ecsv` files and each observation is single-filter. A
star imaged in both F770W and F1000W therefore produced two independent a0
rows, each with its own separately-derived Gaia/2MASS cross-match --
unusable for photosphere.py (needs one Teff fit per star) or excess.py
(needs both MIRI bands for the same star side by side).

**Decision:** this is fixed in `retriever.py` (not deferred to
photosphere.py), via a new `pivot_to_one_row_per_star` function called at
the end of `run()`, before `assemble_level_a0`. Grouping key is
`gaia_source_id` for sources with a Gaia match; sources with no Gaia match
(`gaia_source_id == 0` for all of them) are each kept as their own singleton
group via a unique negative sentinel key, rather than being incorrectly
merged into one "star" by grouping on the literal value 0. Columns are split
into star-level (`gaia_*`, `twomass_*`, `qc_*` match flags -- identical
across a group by construction) and filter-level (everything else, e.g.
`miri_ra`, `aper_total_flux`, `obs_id` -- suffixed per filter, e.g.
`aper_total_flux_F770W`). A star with a detection in only one configured
filter gets NaN in the other filter's columns plus
`qc_single_filter_detection`, rather than a shorter row. The xarray
dimension is renamed from `source` to `star` accordingly.

**Known simplification, logged not silently handled:** if a star was
observed more than once in the *same* filter (different proposals
targeting it), only the first detection (by `source_row_id`) is kept per
(star, filter) pair, with a warning logged -- not the best-SNR detection,
and not both. Not expected to be common but not verified absent either;
revisit if it fires at a meaningful rate.

**Verification:** tested against live MAST/Gaia/2MASS data (not just
synthetic), the same way the rest of retriever.py was verified on
2026-07-15. Queried the live archive, found proposal 4706 (target
"PN-TC-1") has exactly one F770W and one F1000W observation of the same
field -- downloaded both `_cat.ecsv` catalogs (42 raw detections total),
ran the full cross-match + pivot chain, and confirmed 2 real stars
(`gaia_source_id` 5954912202490425728 and 5954912374289120896) correctly
merged into single rows with both filters' columns populated
(`qc_single_filter_detection == 0`), while the remaining 38 detections
(most with no Gaia match, since PN-TC-1 is a planetary nebula field rather
than a dense stellar field) each became their own singleton star row.
Also confirmed the assembled dataset round-trips through NetCDF
(`assemble_level_a0` -> `save_level_a0` -> `xr.open_dataset`) with the new
`star` dimension. High confidence this fix behaves correctly on real
archive data, not just the synthetic case it was first written against.

### 2026-07-20 -- Photosphere model grid accessibility (smoke test)

Before deciding a model-selection scheme for photosphere.py, tested whether
Kurucz, PHOENIX, and SVO's theoretical spectra service are actually usable
in this environment, rather than assuming any of them work -- the same
verify-before-relying-on-it approach used for MAST/Gaia access in
retriever.py.

- **Kurucz (ATLAS9/`ck04models`) via `stsynphot` + CDBS:** `stsynphot`
  installs cleanly (`pip install stsynphot`), but requires local grid files
  under a `PYSYN_CDBS` directory -- it is not a live query API.
  Initially concerning because STScI's full CDBS bundle
  (`synphot5.tar.gz` etc.) is ~2.3 GB, but the `ck04models` grid alone is
  served as individual small FITS files (`catalog.fits`, ~400 KB, plus
  ~76 files of ~70 KB each per metallicity subdirectory, ~40 MB total for
  the whole grid) -- so a scoped download of just this grid is cheap.
  Confirmed working end-to-end: fetched `catalog.fits` plus one spectrum
  (`ckp00_5750.fits`) from `https://ssb.stsci.edu/trds/grid/ck04models/`,
  set `PYSYN_CDBS`, and successfully called
  `stsynphot.grid_to_spec('ck04models', 5750, 0.0, 4.5)`. **Confidence:
  high** -- tested live, not just import-checked.
- **PHOENIX (Husser et al. 2013) via `expecto`:** installs cleanly, and
  `expecto.get_spectrum(T_eff=5750, log_g=4.5, cache=True)` successfully
  fetched a full-resolution spectrum on demand from the Göttingen server (no
  manual grid setup needed, unlike stsynphot/CDBS). Per-spectrum download is
  ~19 MB (cached by astropy afterward) -- larger per-file than Kurucz, but
  each star only needs one (or a few, for interpolation) grid-node fetch,
  and the grid is coarse enough that many stars in an archive-wide sample
  will share cached nodes. **Confidence: high** -- tested live.
- **SVO theoretical spectra service:** the base URL responds (HTTP 200),
  but repeated attempts at plausible SSAP-style query endpoints
  (`ssap.php` with `model=`/`fteff=`/`flogg=` parameters, guessed from
  general SVO conventions) returned empty results, and no working query
  endpoint could be found without official API documentation in hand.
  **Confidence: low / unconfirmed.** Not recommended as a candidate given
  two other options are already confirmed working -- would need actual SVO
  documentation to revisit, not further guessing.

**Implication for photosphere.py:** both Kurucz-via-stsynphot and
PHOENIX-via-expecto are viable, confirmed-working options, so the
model-selection-by-spectral-type scheme can be built on either without an
unverified dependency risk. `requirements.txt`'s existing `synphot>=1.3`
line should be supplemented with `stsynphot` and `expecto` once the design
is finalized.

### 2026-07-20 -- Extinction/reddening: literature precedent

Before choosing between fitting extinction jointly or pulling it from a 3D
dust map, checked how the three key prior IR-excess technosignature
searches handled it, per project convention of building on precedent rather
than deciding from first principles.

- **Carrigan (2009):** fit blackbodies directly to IRAS LRS spectra/colors
  (100-600 K range for the waste-heat blackbody itself); did not perform any
  quantitative dereddening step. Instead, treated heavy reddening as a
  **confusion/false-positive signature**: the best Dyson-sphere candidates
  in the sample turned out, on inspection, to be reddened/dusty objects
  (heavily extinguished stars, protostars, Mira variables, AGB stars,
  planetary nebulae) and were vetoed as such, not corrected and kept.
- **Wright et al. (2014), G-HAT II (Framework, Strategy, and First
  Result):** also does not fit extinction as a free parameter. Relies on
  (a) **spatial masking** -- using known Galactic dust/star-formation
  distribution to exclude regions where heavily-extinguished sources are
  expected, rather than correcting individual sources, and (b) **parallax**
  as an independent discriminator (no detectable parallax => likely a
  distant/background contaminant rather than a genuine nearby candidate) --
  a strategy only fully available to us now via Gaia, which these papers
  mostly predate.
- **Griffith et al. (2015), G-HAT III (Reddest Extended Sources in WISE):**
  also no explicit dereddening or extinction-fitting step found; uses
  color cuts (`W2-W3 < 2`, `W3-W4 <= 1`) to remove foreground stellar
  contamination and relies on visual vetting/classification for the
  remaining reddened-object confusion, consistent with Carrigan's framing.
  (Note: this paper's own subject -- extended/extragalactic sources -- is a
  less direct analogue to our point-source stellar case than Wright et al.
  2014's framework paper; treat this finding as secondary confirmation, not
  primary.)

**Confidence: medium-high** that none of the three fit extinction as a free
SED parameter (consistent finding across independently-fetched full-text
sections of all three), **medium** on completeness of coverage (fetched via
targeted extraction, not a full read of each paper).

**Pattern across all three:** extinction is treated as an **alternative
explanation for apparent excess to be excluded/vetted**, not a nuisance
parameter to fit and discard. None of them had access to Gaia-quality
parallax + modern 3D dust maps, which is the main thing that's changed.

**Proposed approach (to be confirmed in the photosphere.py design
discussion):** given the precedent's consistent theme -- extinction as a
confusable alternative explanation, not something to silently correct away
-- and given this project's own established convention of explicit `qc_*`
flags over silent correction, propose: use a 3D dust map (e.g. `dustmaps`
with Bayestar/Green et al.) with Gaia parallax-derived distance + sky
position as the primary Av estimate feeding the photosphere fit (a genuine
improvement over 2009-2015 precedent, made possible by data that didn't
exist then), but *also* carry forward the precedent's core lesson as an
explicit `qc_high_extinction` (and/or `qc_extinction_uncertain` for
poor-parallax sources) flag into `excess.py`/`contaminants.py`, so any
excess candidate sitting behind significant dust is still surfaced for the
same kind of manual discrimination these three papers relied on -- not
auto-cleared just because a numeric Av correction was applied. No joint-fit
(Av as a free SED parameter alongside Teff) is proposed, since none of the
three precedent papers do this and it would be poorly constrained by only
6 photometric points.

### 2026-07-20 -- photosphere.py implemented; dustmaps/bandpass smoke tests; PHOENIX mid-IR gap discovered

Before implementing, smoke-tested `dustmaps`/Bayestar19 and
`astroquery.svo_fps` live, the same way Kurucz/PHOENIX/SVO were tested
earlier this session:

- **Bayestar19 (dustmaps):** installs and downloads cleanly (~728 MB via
  Harvard Dataverse, ~40 s here). Querying it live against a real matched
  MIRI source's position/distance returned NaN; a real northern test
  coordinate returned a sensible value -- and the package's own docstring
  confirms why: "The maps cover the Pan-STARRS 1 footprint (dec > -30 deg)".
  Peak memory during loading was ~6.2 GB even at `max_samples=2` (the
  lightest setting), close to this environment's ~6.6 GB limit -- flagged
  as an operational risk, not fixed. **Confidence: high that it works;
  medium on whether it'll fit comfortably in a more memory-constrained
  production environment.**
- **astroquery.svo_fps:** `get_transmission_data` (fetch a filter's
  transmission curve by ID) is fast and reliable for all 8 needed bands
  (Gaia G/BP/RP, 2MASS J/H/Ks, MIRI F770W/F1000W). `get_filter_index`
  (used to look up a band's Vega-system zero point by wavelength range) is
  NOT reliable for broad ranges -- timed out querying the Gaia G band's
  effective-wavelength neighborhood, apparently because that range overlaps
  a huge number of other instruments' filters in SVO's database. **Decision:**
  the six needed zero points (Gaia G/BP/RP, 2MASS J/H/Ks -- MIRI bands don't
  need one, see below) were fetched once via narrow per-band queries and
  baked into `photosphere.py` as static reference values (`FIT_BAND_ZEROPOINT_JY`),
  not re-queried at runtime.
- **Reddening law:** planned to use Fitzpatrick (1999) via `dust_extinction`,
  but its valid range is only ~0.1-3.3 micron -- doesn't reach either MIRI
  band at all. Switched to Gordon et al. (2023) "G23", which covers
  ~0.09-32 micron in one self-consistent law spanning both the fit bands
  and the MIRI prediction bands, confirmed via `dust_extinction`'s own
  `x_range` attribute and a live test showing physically sensible
  extinction values (including the expected ~9.7 micron silicate-feature
  dip relative to 7.7 micron).
- **Fitting strategy split (Kurucz vs. PHOENIX):** `expecto` confirmed (from
  its own docstring) to snap to the nearest PHOENIX grid node rather than
  interpolate, unlike `stsynphot`'s Kurucz interpolation. Running a
  continuous optimizer against PHOENIX would waste evaluations probing
  between nodes and could behave poorly against what's actually a step
  function. So Kurucz gets a continuous bounded search
  (`scipy.optimize.minimize_scalar`) and PHOENIX gets a discrete
  hill-climbing local search over its known grid nodes (confirmed via a
  live directory listing of the Göttingen server: 100 K steps 2300-7000 K,
  200 K steps 7000-12000 K), seeded from the same rough BP-RP Teff estimate
  used for grid/bucket selection.
- **PHOENIX mid-IR coverage gap (discovered during implementation, not
  anticipated in the design discussion):** PHOENIX spectra only extend to
  ~5.5 micron -- confirmed by actually trying to synthesize MIRI-band flux
  from one and hitting `synphot.exceptions.DisjointError` (the spectrum and
  F770W bandpass don't overlap at all, not even at the edges). This means
  every PHOENIX-primary (cool, Teff <= 3500 K) star currently gets **no**
  predicted MIRI flux -- `qc_no_mid_ir_model_coverage=1`, `predicted_flux_*`
  left NaN rather than crashing or guessing via extrapolation. Added as its
  own Open Methodological Question above; this is a real gap affecting a
  whole Teff range, not a rare edge case.
- **Bayestar-to-Av conversion:** the package's own docs say converting its
  native reddening unit to Av/E(B-V) requires coefficients from Green et
  al. (2019) Table 1, which were not independently looked up here. A
  commonly-cited approximate value (2.742) is used and clearly flagged in
  the code as unverified against that table -- not presented as final.
- **Verification:** ran the full retriever -> photosphere chain against the
  same live PN-TC-1 archive data used to verify the retriever.py pivot
  fix -- 13 real Gaia-matched stars (of 40 total pivoted rows), covering
  fully-matched (6-band), partially-matched (3-band), and unmatched (0-1
  band) sources. All handled without crashing: real Teff fits (~4500-5000 K,
  consistent with the sample's colors) with sensible predicted MIRI flux
  for fully-matched stars, NaN photosphere_teff + qc_poor_photosphere_fit=1
  for the <2-band case (a guard added after this was found to have no
  handling -- division by zero in the fit's weighting otherwise), and
  correct qc_extinction_uncertain=1 for this specific field (dec ~ -46,
  outside Bayestar's footprint, consistent with the dust-map finding
  above). White-dwarf skip and PHOENIX cool-bucket paths were additionally
  verified with synthetic test rows (not present in the live sample used).
- **Performance:** not optimized -- see the new Open Methodological
  Question above on per-star runtime. Fine for verification at this scale,
  not yet fine for a full archive run.

### 2026-07-20 -- Quantifying and mitigating the PHOENIX mid-IR coverage gap

Before deciding whether the gap above was a caveat-for-the-paper or a
fix-now issue, quantified it against live archive data rather than
guessing:

- **PN-TC-1 (13 Gaia-matched stars): 0/13 (0%)** land in the PHOENIX/cool
  bucket -- this field is dominated by K-type field stars (BP-RP ~1.0-1.3,
  Teff ~4500-5200 K). Not representative on its own (a single
  planetary-nebula field, not a young/low-mass survey).
- Pulled a second live sample: 18 additional real archive observations
  spanning A dwarfs, G dwarfs, M-dwarf/YSO fields, T Tauri/protoplanetary-
  disk fields, and protostar (HOPS) fields -- 244 Gaia-matched stars,
  **25/244 (10.2%)** in the cool bucket, highly concentrated:
  Protostars/YSO (HOPS) fields 17/25 (68%), G dwarfs 4/23 (17%), A dwarfs
  2/8 (25%), M-dwarf/YSO fields 1/150 (0.7%, dominated by FGK field stars
  sharing the pointing with the actual M-dwarf target), T Tauri/
  protoplanetary-disk fields 1/37 (3%).
- Also notable: 3 observations explicitly classified "Brown dwarfs"
  produced **zero** Gaia matches at all -- these substellar targets are
  typically too faint optically, so they fail at `qc_no_gaia_match` before
  ever reaching the PHOENIX-coverage question. The true cool/substellar
  population is therefore somewhat undercounted by
  `qc_no_mid_ir_model_coverage` alone (some of it never reaches the
  photosphere fit at all).
- Real archive-wide `target_classification` breakdown (1176 kept
  observations) confirms non-trivial representation of YSO/protostar/
  brown-dwarf categories (~230+ observations), so ~10% is a reasonable
  order-of-magnitude estimate archive-wide, not just a PN-TC-1 artifact --
  with real field-to-field variance from ~0% to ~68%.

**Decision (researcher's call, 2026-07-20):** fix now, not defer, given the
68% concentration in protostar/YSO-classified fields -- squarely the
population this project cares about most. Implemented
`rj_extrapolation_spectrum` (see module docstring and the Open
Methodological Questions entries above) the same day. Verified against the
real cool-bucket stars from the diverse sample above (25 stars, live
`fit_star` calls, not just bucket-assignment logic): see results appended
below.

### 2026-07-20 -- Bayestar memory: mode='best' + max_samples=0

Switched `estimate_extinction`'s Bayestar query from `mode='median'`
(`max_samples=2`) to `mode='best'` (`max_samples=0`), after confirming
`mode='best'` uses only the maximum-posterior point-estimate array and
never touches the (much larger) posterior-samples array at all. Confirmed
live: peak memory dropped from ~6.2 GB to ~2.3 GB, load time from ~16.7 s
to ~10-12 s, and spot-checked values stayed sensible (north in-footprint:
finite E(B-V)-like value; south, out-of-footprint: NaN, unchanged).

This is a **documented tradeoff, not an invisible default**: 'best'
(maximum a posteriori) and 'median' (of posterior samples) are different
point estimates of the same probabilistic dust map, and can differ for a
skewed posterior. Accepted because Av is already treated cautiously
throughout this pipeline -- never a precise per-star correction, always
paired with `qc_extinction_uncertain`, and already carrying an unverified
map-to-Av conversion coefficient (see the 2026-07-20 grid-accessibility
entry above) -- so the expected incremental impact of this specific choice
is minor relative to those existing caveats. Revisit if archive-scale runs
show 'best' vs. 'median' meaningfully changes which sources would be
flagged for high extinction downstream.

### 2026-07-20 -- RJ extrapolation verification against real cool-bucket stars: bug found and fixed

Ran `fit_star` on all 25 real cool-bucket stars identified in the diverse
18-observation sample above (not just synthetic test rows). The first
attempt crashed on the 3rd star with `synphot.exceptions.DisjointError`,
inside the new RJ-extrapolation path -- caught by this verification, not
shipped silently.

**Root cause:** `synphot.SourceSpectrum(BlackBody1D, temperature=teff)`'s
own default `.waveset` is Teff-DEPENDENT and shrinks as Teff rises
(confirmed live: ~13.9 micron upper bound at 2300 K, but only ~9.1 micron
at 3500 K, ~3.2 micron at 10000 K). `redden_spectrum` re-tabulates onto
`source_spectrum.waveset`, so the reddened blackbody's wavelength coverage
silently truncated to whatever the raw BlackBody1D model's native grid
happened to be at that specific Teff -- fully disjoint from F770W
(6.2-9.3 micron) once Teff exceeded ~5100 K. This was reachable in
practice, not just in principle: the fitted Teff for a "cool-bucket" star
can end up well above 3500 K if the initial BP-RP-based rough estimate was
imprecise (the fit itself isn't re-bucketed after refinement, per the
existing design), and the `teff + teff_err` perturbation used for error
propagation pushes it further still.

**Fix:** `rj_extrapolation_spectrum` now re-tabulates the scaled blackbody
onto a fixed, Teff-independent wavelength grid (0.3-15 micron,
`np.geomspace`, 2000 points) before returning it, rather than leaving it on
the raw analytic model's own shrinking native grid.

**Verification after the fix:** all 25/25 real cool-bucket stars succeeded,
zero crashes, spanning fitted Teff 2300-7000 K (including several values
well beyond the ~5100 K threshold that crashed before: 5300, 5700, 6200,
6300, 7000 K) -- confirmed live, not just re-tested at the one value that
failed.

**Final breakdown requested by the researcher, confirmed via real
`fit_star` calls (not just bucket-assignment logic):**

| Sample | Gaia-matched stars | `qc_no_mid_ir_model_coverage=1` | `qc_rj_extrapolated=1` |
|---|---|---|---|
| PN-TC-1 | 13 | 0 (0%) | 0 |
| Diverse 18-obs sample | 244 | 25 (10.2%) | 25 (all 25, confirmed via live fit) |
| Combined | 257 | 25 (9.7%) | 25 |

`qc_no_mid_ir_model_coverage` and `qc_rj_extrapolated` are identical in
every case observed so far, as designed (every no-native-coverage star
gets the substitute). All 25 previously-NaN `predicted_flux_F770W`/
`predicted_flux_F1000W` values are now real numbers -- the gap is closed
for these stars, subject to the still-open validation prerequisite above
(these numbers are not yet equal-confidence to a native-grid prediction).

**Side observation, not a new bug:** several of the 25 stars' PHOENIX-fit
Teff came back well above the 3500 K cool-bucket boundary (up to 7000 K)
-- i.e., the rough BP-RP estimate that assigned them to the PHOENIX bucket
was significantly off for these specific stars. This is a known
consequence of two already-agreed design choices interacting (bucket
assignment from a coarse color estimate; no re-bucketing after the fit
refines Teff) rather than a new issue, but it does mean some fraction of
the `qc_rj_extrapolated` population might, on their true fitted Teff, have
gotten a native Kurucz prediction if they had been bucketed differently.
Not resolved here -- worth keeping in mind when interpreting the ~10%
figure, since it's an upper-bound-ish estimate of the population that
*needs* RJ extrapolation, not a precise one.
