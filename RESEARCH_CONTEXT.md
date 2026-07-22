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
2. **MIRI photometry extraction** (`pipeline/miri_photometry.py` --
   implemented and verified 2026-07-21; see Decision Log) --
   Measures the actual observed F770W/F1000W point-source flux from the
   `_i2d` mosaics. **Added as its own stage 2026-07-20**, correcting a gap in
   the previous 4-stage description: the Decision Log below (2026-07-15)
   already concluded `_cat.ecsv` aperture photometry is not adequate as
   excess-critical photometry (per Libralato et al. 2024), but no stage
   existed to produce the real replacement -- the architecture list simply
   didn't have a place for it. **Design resolved 2026-07-21** (see Decision
   Log): model-PSF fitting via `stpsf` + `photutils.psf`, with aperture
   photometry as a parallel cross-check, both corrected via the CRDS APCORR
   reference file. **Implemented and verified end-to-end against real
   PN-TC-1 archive data 2026-07-21** (see Decision Log) -- the primary
   EE-corrected PSF-fit flux (`observed_flux_{band}`) matches
   `_cat.ecsv`'s `aper_total_flux` to ~1-2% for QC-clean sources, resolving
   the pre-correction ~0.70-0.82x deficit. -> outputs its own dataset
   sharing a0/a1's `star` coordinate (observed MIRI flux), joined by
   excess.py rather than folded back into a0 itself.
   (Kurucz/PHOENIX/blackbody, TBD, see Decision Log 2026-07-20 for grid
   accessibility findings) to optical + near-IR photometry; produces
   predicted mid-IR photosphere flux. -> data level a1.
4. **Quality/anomaly** (`pipeline/excess.py` -- implemented and verified
   2026-07-22 (see Decision Log); `pipeline/contaminants.py` -- not yet
   built) -- Excess significance scoring (observed MIRI flux from stage 2
   vs. predicted flux from stage 3), contaminant cross-matching and
   classification, `qc_*` flag assignment. -> data level b1.
   `excess.py` runs before `contaminants.py`, not the reverse (see Decision
   Log) -- it produces continuous `excess_sigma_{band}` and QC-based
   `qc_excess_clean_{band}`/`qc_star_disqualified` now, but deliberately
   does not yet compute a boolean "is this significant" flag or the final
   `qc_anomalous_excess` (both still blocked -- see Open Methodological
   Questions below).
5. **Output** (`pipeline/output.py`) -- FITS catalogue, diagnostic figures,
   LaTeX table export.

Data moves between stages as `xarray.Dataset` objects saved to NetCDF. Every
QC decision is recorded as an explicit `qc_*` variable rather than by
silently dropping rows, so that the final candidate list is fully traceable
back through every contaminant check.

## Recurring Methodological Pattern: Unverified Index/Ordering Assumptions

Worth naming explicitly, in one place, rather than leaving as separate bug
writeups scattered across the Decision Log that happen to rhyme: this
project has now hit the **same underlying failure class five times**, in
five different stages, involving five different systems (a language
primitive, a JWST pipeline product's own file format, an astropy method,
matplotlib, and LaTeX/`pdflatex`). Each time, code assumed an index, an
ordering, a join key, or (in the two most recent instances) a rendering
system's ability to handle an unbounded-length/variable-shaped string
behaved a particular way based on a name, a signature, or a doc's apparent
meaning -- without empirically checking that assumption against the actual
runtime behavior -- and each time the assumption was wrong in a way that
produced either silently corrupted data, a caught loud failure, or a
silently broken (but not crashing) rendered artifact.

1. **`retriever.py` cross-match row-misalignment (2026-07-15).**
   `crossmatch_gaia`/`crossmatch_2mass` grouped MIRI sources by observation
   using `for obs_id in set(miri_sources["obs_id"])`, then reassigned
   matched columns back onto the original table **positionally**. The
   assumption: iterating a `set()` preserves the table's own row order.
   It doesn't. Once a batch spanned more than one observation, matches
   silently attached to the wrong star -- no exception, no warning, a
   NetCDF file that looked complete and plausible while being wrong. Found
   only because an explicit post-hoc separation sanity check was run.
2. **`_cat.ecsv`'s `label` column instability (2026-07-21).** `label` was
   assumed to be a stable, cross-filter source identifier (same physical
   star, same label, across F770W and F1000W catalogs from the same
   field). It is actually a per-image, per-catalog detection index with no
   cross-filter meaning at all. Reusing "label 6" across both filters
   compared two physically unrelated stars ~162 arcsec apart, producing a
   nonsensical flux ratio that only made sense once checked directly
   against `sky_centroid`.
3. **`SkyCoord.search_around_sky`'s return-order assumption (2026-07-22).**
   Assumed, from the method's signature/apparent documentation, that
   `self.search_around_sky(other, seplimit)` returns `(idx_into_self,
   idx_into_other, sep2d, dist3d)`. Verified empirically (not assumed) that
   the actual return order is the reverse: the first index array indexes
   `other` (the argument), the second indexes `self`. Caught by a unit
   test before any real data was touched -- the one instance of this
   pattern that did NOT reach real data first, because a test happened to
   exercise the ambiguous-match case (more catalog entries than stars)
   where getting the order wrong produces an immediate, loud shape-mismatch
   error rather than a silent misattribution.
4. **`matplotlib`'s `fig.text(..., wrap=True)` caption-wrapping assumption
   (2026-07-22, `output.py`'s `plot_sed`).** Assumed, from the `wrap=True`
   keyword's apparent meaning, that matplotlib would wrap long caption text
   at the figure boundary on its own. It doesn't reliably -- the first real
   render (CONTROLFIELD star index 13's own long `disqualifying_flags`
   list) ran straight off the right edge of the figure, cut off mid-word.
   Caught only by actually opening the rendered PNG, not by any automated
   test (all of which used short synthetic flag strings that never
   exercised the long-string case). Fixed with explicit `textwrap.wrap`
   plus inserting spaces after commas so the wrapper had real word
   boundaries to break on.
5. **LaTeX `tabular`'s plain `l` column-width assumption (2026-07-22,
   `output.py`'s `write_flagged_for_review_table`).** Assumed a plain `l`
   column would be an adequate width for `disqualifying_flags`. `pdflatex`
   compiled without a hard error, but the first actually-compiled-and-
   rendered PDF (CONTROLFIELD's flagged-for-review table, star index 13's
   row among others) showed the column running straight off the page edge
   for any row with a long flag list -- caught only by rendering the `.tex`
   to a PDF and visually inspecting it, the same discipline that caught
   case 4, in a different typesetting system. Fixed with a `p{5.5cm}`
   paragraph column plus the identical comma-to-", " fix used for case 4,
   for the identical reason (LaTeX's line breaker, like matplotlib's text
   wrapper, needs real whitespace to break on -- a comma-joined string with
   no spaces is one unbreakable "word" either way).

**The common thread**: none of these were logic errors in this project's
own scientific code -- they were unverified assumptions about how
*external* systems (Python's `set()` iteration, a JWST pipeline product's
own column semantics, an astropy method's argument order, matplotlib's
text layout, LaTeX's line breaker) actually handle data whose length,
shape, or order isn't fixed in advance, each treated as obvious/safe
without being checked. Two flavors of the same lesson, not two unrelated
bug classes: cases 1-3 are *ordering/indexing* assumptions (does this
external step preserve or return data in the order/identity I assumed);
cases 4-5 are *variable-length-content* assumptions (can this external
rendering system correctly lay out a string whose length I didn't bound in
advance). Three of the five produced silent, plausible-looking wrong
output (cases 1, 2, and 4/5's "compiles/renders without error, wrong on the
page"); only case 3 was caught before touching real data, and only because
a test happened to construct exactly the input shape that turns the wrong
assumption into an immediate crash rather than a quiet corruption. That is
not a property to rely on going forward.

**Standing rule this project has converged on, worth stating explicitly
because it is now supported by five independent occurrences, not
one**: any time code relies on *how* an external library, file format,
rendering system, or language primitive orders, indexes, joins, or lays
out data of unbounded or variable shape -- not just *whether* it returns
the right values -- that behavior should be verified directly (a small
isolated check against real or synthetic data, or -- for cases 4-5 --
actually looking at the rendered output rather than checking the file was
merely written) rather than inferred from a name, a signature, or a
docstring's apparent meaning. This is a stricter bar than this project's
general "verify before relying on it" convention (already applied
consistently to live services like Kurucz/PHOENIX/dustmaps/MAST) -- it
specifically targets *ordering/indexing/layout* semantics, which are easy
to get subtly wrong in a way that either fails silently (cases 1, 2) or
fails loudly only if you happen to construct a test input that exposes it
(case 3), or renders wrong without any error at all (cases 4, 5). Worth
citing as a methods-adjacent footnote in the eventual paper's discussion of
data-quality control, not just an internal engineering note -- it is
direct, repeated evidence for why this project's qc_* flag-and-verify
discipline, and its "actually look at the rendered output" discipline for
figures/tables specifically, both exist in the first place.

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
      photometric uncertainty budget? **Partially resolved 2026-07-22**:
      `pipeline/excess.py` now computes continuous `excess_sigma_{band}`
      unconditionally (not blocked -- see Decision Log), but the two
      boolean thresholds (`excess.significance_threshold_sigma` for the
      both-bands-required primary criterion, and the new
      `excess.single_band_significance_threshold_sigma` for
      `qc_single_filter_detection` stars -- see Decision Log for why a
      separate, stricter single-band tier was chosen over including these
      stars at the two-band bar or excluding them from candidacy entirely)
      remain `null` pending the literature check below. **Literature check
      done 2026-07-22** (Carrigan 2009; Griffith et al. 2015 -- full text
      read of both, high confidence; see Decision Log): neither paper uses
      a Bonferroni/FDR-style multiple-testing correction for their
      published method; both instead rely on hard structural/categorical
      cuts followed by exhaustive manual visual vetting of every surviving
      source. **Still not resolved**: the actual sigma value(s) and whether
      to adopt an analogous "cut hard, then manually vet every survivor"
      strategy instead of/alongside a corrected significance level --
      that's the follow-up decision this literature check was meant to
      inform, not itself the decision.
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
- [x] **(Added 2026-07-20)** What method should the new MIRI photometry
      extraction stage (architecture item 2, above) use to measure observed
      F770W/F1000W point-source flux from the `_i2d` mosaics -- ePSF
      (Libralato et al. 2024 style) vs. careful aperture photometry?
      Explicitly deferred: this needs its own design discussion, not decided
      alongside photosphere.py. **Resolved 2026-07-21** (researcher's
      decision, see Decision Log): model-PSF fitting (`stpsf` +
      `photutils.psf.PSFPhotometry`, using `stpsf`'s `GriddedPSFModel`), not
      a true empirical ePSF and not aperture-only. Careful aperture
      photometry is retained as a parallel per-source cross-check
      (`qc_psf_aperture_disagreement`), not as the primary measurement.
- [x] **(Added 2026-07-21) BLOCKING PREREQUISITE FOR writing the MIRI
      photometry-extraction module**: two items from the 2026-07-21 design
      discussion were unverified and needed to be smoke-tested (or sourced)
      before implementation starts, not assumed. **Both resolved 2026-07-21
      -- see items (1) and (2) below and the corresponding Decision Log
      entries. No implementation has been written yet.** --
      (1) **Resolved 2026-07-21** (see Decision Log, end-to-end smoke test
      entry): `photutils.psf.PSFPhotometry` does run against a real
      `_i2d.fits` mosaic at real catalog source positions, using an
      `stpsf`-generated PSF. Resolving this surfaced two follow-on
      requirements that weren't anticipated in the design discussion --
      local background subtraction is required (raw fit flux ran 2.3x high
      without it), and even with it, PSF-fit flux ran systematically
      ~0.70-0.82x the catalog's aperture flux across all successfully-fit
      test sources, plausibly because the finite PSF-stamp size used
      (`fov_pixels=15`, ~1.65") doesn't capture all of MIRI's real,
      broad-winged PSF -- i.e. the PSF-fit flux likely needs its own
      EE-style correction, not just the aperture cross-check. Folded into
      item 2 below, which now covers both flux paths.
      (2) **Resolved 2026-07-21** (see Decision Log, "Encircled-energy
      calibration source found" entry): this was originally scoped only as
      needed for the aperture-photometry cross-check, then severity-upgraded
      the same day once the smoke test showed it's also needed for the
      PRIMARY PSF-fit flux measurement (finite-PSF-stamp bias, systematic
      ~0.70-0.82x, not a one-off -- see item 1). The source is the JWST
      pipeline's own CRDS `apcorr` reference file (`jwst_miri_apcorr_0014.fits`,
      current best reference confirmed live via CRDS's JSON-RPC API against
      the live operational context, not guessed), which round-tripped a
      known real test star's own `aper_total_flux` to 4 significant figures
      -- high confidence. **Both blocking items for this module are now
      cleared; no implementation has been written yet.**
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
- [x] **(Added 2026-07-20)** **BLOCKING PREREQUISITE FOR excess.py**:
      `qc_rj_extrapolated` sources must not be scored at equal confidence to
      a native-grid prediction in excess.py's significance calculation.
      **Handled 2026-07-22** (researcher's decision, option A over a
      stopgap inflation factor -- see Decision Log): `qc_rj_extrapolated`
      is one of `pipeline.excess.DISQUALIFYING_STAR_FLAGS`, so these stars
      can never satisfy `qc_excess_clean_{band}`/any future candidate
      composite; their raw `excess_sigma_{band}` is still computed and
      reported as a diagnostic (nothing dropped), per the project's
      flag-don't-drop convention. **The underlying gap is NOT resolved**:
      this still requires validating the Rayleigh-Jeans/blackbody-tail
      extrapolation (`rj_extrapolation_spectrum`) against real cool stars
      with existing WISE/Spitzer mid-IR photometry (known non-excess M
      dwarfs), to produce an actual error-inflation factor -- not yet done,
      and no placeholder factor was invented in its place. Revisit if that
      validation study happens: at that point excess.py's exclusion could
      be relaxed to an inflated-error scoring instead.
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
- [ ] **(Added 2026-07-22, surfaced during the contaminants.py design
      discussion, but this is a `pipeline/miri_photometry.py` question, not
      a contaminants.py one -- logged here explicitly so it doesn't fall
      through the gap between the two modules' Decision Log entries.)**
      Diffuse nebular/extended emission in the local-background annulus
      (`skyin_px`/`skyout_px`, `MMMBackground`) is NOT a one-directional
      bias the way `qc_extinction_uncertain` is (see the 2026-07-22
      "Directional check" Decision Log entry below excess.py's section):
      depending on whether the annulus samples brighter or fainter nebular
      structure than the star's own position, `observed_flux_{band}` could
      be biased low (safe) OR high (could manufacture spurious excess).
      Not yet investigated at the pixel level for any real candidate star
      (the two PN-TC-1 excess_sigma_F770W values, 7.77 and 4.04, are the
      concrete case this matters for). Would need a `qc_*` flag in
      `miri_photometry.py` (not `excess.py`/`contaminants.py`) checking
      annulus uniformity/structure around each source, or at minimum a
      manual pixel-cutout inspection of specific candidates near resolved
      nebulosity before trusting their sigma values.

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

### 2026-07-21 -- MIRI photometry-extraction stage: method design discussion

Design discussion for architecture item 2 (MIRI photometry extraction),
explicitly deferred at photosphere.py's design time (see 2026-07-20 entries
above) to its own discussion. Three candidate methods were considered:

- **True empirical ePSF (Libralato et al. 2024's actual method):** build the
  PSF from bright, isolated stars present in each field, per Anderson &
  King-style methodology. Most faithful to the cited precedent, but
  requires enough suitable stars *per field* to construct the PSF at all --
  and retriever.py's own pivot verification (2026-07-20 entry above) showed
  this project's fields are often point-source-poor (PN-TC-1: only 2 real
  Gaia-matched stars out of 40 detections, most fields singleton-dominated).
  Genuinely stellar targets observed by MIRI are typically isolated
  point-source targets, not dense clusters, so a per-field empirical PSF is
  frequently infeasible here even before counting the implementation cost
  of replicating a paper's custom fitting pipeline.
- **Careful aperture photometry (own aperture choice, not `_cat.ecsv`'s):**
  simple and fast to implement via `photutils.aperture`, but this is
  methodologically the same category of approach (aperture photometry) that
  Libralato et al. found underperforms for high-precision point-source work
  -- the exact finding that drove the 2026-07-15 decision to not treat
  `_cat.ecsv` as excess-critical photometry in the first place. Doing our
  own aperture photometry doesn't escape that critique, even with better
  aperture/background choices.
- **Model-PSF fitting (`stpsf` + `photutils.psf`):** a simulated PSF, not an
  empirically-built one, but fit via PSF-fitting rather than raw aperture
  summation -- methodologically closer to Libralato's PSF-fitting approach
  than plain aperture photometry, without requiring a per-field empirical
  PSF our sample can't reliably support.

**Decision (researcher's call, 2026-07-21):** model-PSF fitting is primary.
`stpsf` (the renamed `webbpsf`) generates a MIRI PSF; `stpsf.MIRI().psf_grid()`
returns a spatially-varying `GriddedPSFModel`-compatible grid, which
`photutils.psf.PSFPhotometry`/`IterativePSFPhotometry` consume directly --
this is the standard, documented photutils workflow for JWST PSF
photometry, not a bespoke integration. Careful aperture photometry (with an
encircled-energy aperture correction) is retained as a **parallel per-source
cross-check**, not the primary measurement -- flagged
`qc_psf_aperture_disagreement` if the two diverge, following the same
flag-don't-silently-trust pattern as `qc_grid_disagreement` in
photosphere.py.

**Explicit acknowledgment: this is a real precision gap versus Libralato et
al.'s method, not a free substitute.** A model PSF from `stpsf` does not
capture actual per-field, per-epoch PSF variation the way an empirical PSF
built from real stars in that exact field/epoch does (focus drift, real
optical-path deviations from the as-built/as-flown telescope vs. the
modeled one). This should be stated plainly as a methodological limitation
in any writeup, not presented as equivalent to Libralato et al.'s ePSF
photometry -- it is the same tradeoff in kind as the Bayestar
`mode='best'` vs `'median'` and PHOENIX RJ-extrapolation caveats already
logged elsewhere in this file: a deliberate, stated compromise driven by
what's actually feasible against this specific dataset, not a claim of
equal precision to the literature precedent.

**Smoke test performed before deciding (live, not assumed):**
`pip install stpsf` installed cleanly; `stpsf.MIRI()` auto-downloaded its
reference data (~129 MB, to `~/data/stpsf-data` in this environment) on
first use with no manual step, much smaller than Bayestar's ~700 MB;
`calc_psf(oversample=2, fov_pixels=21)` for F770W completed in ~8.9 s and
returned a sensible 42x42 array at the expected pixel scale (0.0555
arcsec/px, oversampled from MIRI's ~0.11 arcsec/px). `psf_grid` and the
`photutils.psf` classes (`GriddedPSFModel`, `PSFPhotometry`,
`IterativePSFPhotometry`, `EPSFBuilder`) were confirmed to exist and import
cleanly (`photutils` 3.0.0, already installed). **Confidence: high** that
the toolchain exists and works in isolation (PSF generation, grid export,
photutils class availability) -- **not yet confirmed** end-to-end against
real mosaic data; see the two blocking items below.

**Explicitly NOT yet verified -- logged as blocking prerequisites for
writing the module, not just open notes** (see corresponding Open
Methodological Questions entry, added 2026-07-21):

1. `photutils.psf.PSFPhotometry` has not been run against a real `_i2d.fits`
   mosaic with a real source's pixel position -- only PSF generation in
   isolation (`calc_psf`, `psf_grid`) has been tested live. Whether the full
   fitting workflow (WCS-based sky-to-pixel conversion, initial position/
   flux guesses, fit convergence, group/blend handling) behaves sensibly
   against real MIRI mosaic data is unconfirmed.
2. The source of the encircled-energy calibration values needed for the
   aperture-photometry cross-check's aperture correction (CRDS vs. JDox vs.
   elsewhere) has not been identified or fetched.

Per project convention (verify before relying on it, as with Kurucz/
PHOENIX/SVO/Bayestar in photosphere.py and MAST/Gaia/2MASS in retriever.py),
neither item is assumed to work -- both must be resolved (or, if they turn
out to be blocking, force a re-opened design discussion) before
implementation of this module starts. Step 2, next: a real `PSFPhotometry`
smoke test against the PN-TC-1 field (the same live archive data already
used to verify retriever.py and photosphere.py).

### 2026-07-21 -- End-to-end PSFPhotometry smoke test against real PN-TC-1 data (blocking item 1)

Re-downloaded the same PN-TC-1 (proposal 4706, target `PN-TC-1`, obs
`jw04706-o009_t008_miri_f770w/f1000w-brightsky`) F770W/F1000W `_i2d.fits`
mosaics and `_cat.ecsv` catalogs used to verify retriever.py/photosphere.py
(not re-used from any cache -- none was found locally, so this was a fresh
live MAST download), then ran `photutils.psf.PSFPhotometry` with an
`stpsf`-generated MIRI PSF (`ImagePSF`, `DET_DIST` extension, native
0.1109"/px, matched to the mosaic's own confirmed 0.1108"/px WCS pixel
scale) against real sources at real catalog positions -- not synthetic
data. This resolves blocking item 1 (the toolchain does run end-to-end
against real data) but surfaces two real, unanticipated findings that
change what the module needs to do, not just confirming it works:

1. **Local background subtraction is required, not optional.**
   `PSFPhotometry` without a `local_bkg_estimator` returned a flux 2.3x the
   catalog's `aper_total_flux` for the first test source (label 6, F770W,
   aper_total_flux=1.568e-3 Jy) -- the fit window includes real, substantial
   local background (~350-450 MJy/sr against a ~900 MJy/sr peak, confirmed
   from the actual pixel cutout, not assumed), and an unsubtracted PSF fit
   absorbs it into the flux. Adding `photutils.background.LocalBackground`
   (`MMMBackground`, inner/outer radius 8/14 px) brought the ratio to 0.82
   for that source.
2. **Even with background subtraction, PSF-fit flux runs systematically low
   (~0.70-0.82x the catalog aperture flux) across all 3 successfully-fit
   sources tested (2 in F770W, 1 in F1000W on the same physical star as one
   of the F770W sources, cross-matched by sky position -- see the dedicated
   `label` gotcha entry immediately below for why that cross-match had to
   be done by sky position, not by catalog `label`).** Plausible cause, not
   yet confirmed: the `fov_pixels=15` (~1.65") PSF stamp used here is finite
   and MIRI's real PSF has broad diffraction wings extending well beyond
   that, so a fixed-size PSF stamp is missing real flux the same way an
   aperture without an encircled-energy correction would be. **Severity:
   this is not a minor refinement to the aperture cross-check -- it means
   the module's PRIMARY measurement (PSF-fit flux) is itself missing an
   EE-style correction, and left uncorrected would silently ship every
   `observed_flux_*` value biased low by ~20-30% before excess.py ever
   compares it against a predicted photosphere flux.** In an
   excess-detection pipeline, a systematic downward bias on the observed
   side is not neutral -- it suppresses genuine excess and could also
   create spurious *deficits*, so this cannot be treated as a secondary
   cross-check concern. Folded into blocking item 2 (see Open Methodological
   Questions above, severity upgraded 2026-07-21) -- it now covers both flux
   paths, not just the aperture cross-check it was originally scoped for.

**A second, genuine (non-bug) finding, from a corrected re-run after fixing
the `label` mistake described below:** the fit did not converge
(`flags=12`) for the same physical source in F1000W. This was not a
`PSFPhotometry` failure in isolation -- the pipeline's own automated
`_cat.ecsv` catalog independently reports a negative `aper_total_flux`
(-3.85e-3 Jy) and `is_extended=True` for the same position in F1000W, and
the raw pixel cutout shows a central dip rather than a point-source peak
(consistent with real extended/nebular structure, plausible given the
target is an actual planetary nebula, not a clean point-source field).
**Conclusion: this specific source is not describable as a point source in
F1000W, and both the existing automated pipeline and the new PSF-fit
approach agree on that independently** -- this is exactly the kind of case
`qc_psf_fit_failed` (already scoped in the 2026-07-21 design discussion
above) needs to catch and flag rather than silently reporting a fitted
number, not a defect in the chosen method.

**Net effect on blocking item 1:** resolved -- the toolchain works
end-to-end against real mosaic data, real catalog-derived positions, and
real WCS conversion (confirmed to agree with the catalog's own
`xcentroid`/`ycentroid` to ~1e-6 px). **NOT resolved, and severity-upgraded,
carried forward into blocking item 2:** the EE-correction question now
applies to the PSF-fit path -- this module's primary, load-bearing
measurement -- not just the aperture cross-check it was originally scoped
for. Until the encircled-energy calibration source (CRDS vs. JDox vs.
elsewhere) is identified, neither flux measurement in this module can be
trusted at better than the ~10-30% level, and that error is systematic
(one-directional, low), not random -- it would not average out across the
sample.

### 2026-07-21 -- Gotcha: `_cat.ecsv` `label` is not a stable cross-filter source identifier

Discovered while running the F1000W leg of the PSFPhotometry smoke test
above: the first attempt reused "label 6" from the F1000W `_cat.ecsv`
directly, assuming it referred to the same physical star as F770W's
label 6 (since both catalogs came from the same field/pointing). It does
not. `label` is a per-image, per-catalog detection index assigned
independently by each observation's own `source_catalog` run -- it has no
cross-filter meaning at all. This produced a nonsensical 0.26 flux ratio
that only made sense once `sky_centroid` was checked directly: F770W
label 6 and F1000W label 6 are different physical stars, ~0.045 deg
(~162 arcsec) apart on sky, far outside any plausible match radius. Fixed
by cross-matching the F770W source's actual sky coordinate through the
F1000W mosaic's WCS instead of reusing the label.

**Why this gets its own entry instead of staying a side note:** this is
exactly the same class of failure as the retriever.py row-misalignment bug
(2026-07-15 entry above) -- a silent, non-crashing mismatch between two
tables that "looks" aligned (same label, same field) but isn't, unless
explicitly checked. It's also a trap this project is now positioned to hit
again: excess.py's entire job is joining per-filter observed flux
(this stage) against per-star predicted flux (photosphere.py a1) and the
existing per-filter a0/a1 columns (`observed_flux_{band}`,
`predicted_flux_{band}`), and any later ad-hoc analysis or notebook that
reaches back into a raw `_cat.ecsv` for a cross-check or plot is at risk of
the same mistake if it joins on `label` instead of `star_id`/
`gaia_source_id` or an explicit sky-position cross-match.

**Rule going forward:** never use `_cat.ecsv`'s `label` column as a join
key across filters/observations, in this module or anywhere downstream
(notebooks included) -- only `star_id`/`gaia_source_id` (post-pivot,
per retriever.py's `pivot_to_one_row_per_star`) or an explicit sky-position
cross-match are safe. This module's design should extract flux by
converting each star's already-known `miri_ra_{filter}`/`miri_dec_{filter}`
(from a0) through the target mosaic's own WCS, never by re-matching against
`_cat.ecsv` `label` values.

### 2026-07-21 -- Encircled-energy calibration source found: CRDS APCORR reference file (blocking item 2 resolved)

Tracked down the source for the encircled-energy/aperture-correction values
needed by both the aperture cross-check and (per the smoke test above) the
primary PSF-fit flux measurement. Verified live, not assumed from
documentation alone:

- **Source:** the JWST calibration pipeline's own APCORR reference file
  (CRDS reference type `apcorr`), the same file the pipeline's
  `source_catalog` step uses internally to produce `_cat.ecsv`'s
  `aper30/50/70_flux` -> `aper_total_flux` correction. FITS format,
  `BINTABLE` extension `APCORR`, columns `filter`, `subarray`,
  `eefraction`, `radius` (pixels), `apcorr` (multiplicative factor, >1),
  `skyin`/`skyout` (sky-annulus radii, pixels) -- confirmed by fetching and
  inspecting the actual file, not just its documented schema.
- **Current best reference identified via CRDS's own JSON-RPC API** (not
  guessed): `get_default_context` against `https://jwst-crds.stsci.edu/json/`
  returned the live operational context `jwst_1535.pmap`; `get_best_references`
  against that context with realistic MIRI/F770W/FULL header parameters
  returned `jwst_miri_apcorr_0014.fits` as the currently active MIR_IMAGE
  apcorr reference (superseding older versions found by guessing sequential
  filenames, e.g. 0005/0008/0010, which were earlier or wrong-mode
  candidates -- 0006/0007/0012 turned out to be MRS/coronagraphy apcorr
  files with a different schema, not MIR_IMAGE). Downloadable directly over
  plain HTTPS (`https://jwst-crds.stsci.edu/unchecked_get/references/jwst/
  jwst_miri_apcorr_0014.fits`, no authentication), and readable with
  `astropy.io.fits` alone -- neither the `crds` nor `jwst` pipeline packages
  (both confirmed NOT installed in this environment) are needed to use it.
- **Provenance (from the file's own header, not asserted):** `PEDIGREE
  INFLIGHT 2022-05-25 2024-06-02`; `HISTORY` states the aperture corrections
  "were computed starting from encircled-energy profiles measured with
  flight LVL-3 data and normalized to infinity using WebbPSF" -- i.e.
  anchored to real in-flight measurements, not a purely simulated
  correction, which is a stronger basis than the module's own PSF-fit path
  (that one *is* purely `stpsf`-model-based, per the 2026-07-21 design
  discussion above).
- **Confirmed live for F770W and F1000W specifically:** both filters have 7
  rows each (`FULL` subarray, EE fractions 0.2-0.8 in steps of 0.1) with
  distinct radius/apcorr/skyin/skyout values (e.g. F770W EE=0.7: radius
  4.22 px, apcorr 1.442; F1000W EE=0.7: radius 4.60 px, apcorr 1.453) --
  the two prediction bands this whole pipeline cares about are both
  covered, not just assumed to be by analogy from other filters.
- **Closed-loop verification against the same real PN-TC-1 test star used
  in the PSFPhotometry smoke test above:** `aper70_flux (0.0010871 Jy) x
  apcorr(EE=0.7) (1.442304) = 0.0015680 Jy`, versus the catalog's own
  `aper_total_flux = 0.0015680 Jy` for that exact star -- **ratio 1.0000 to
  4 significant figures.** This isn't circumstantial (matching filenames/
  descriptions) -- it's a direct numerical reproduction of the automated
  pipeline's own published total-flux value from this reference file's
  numbers, which is about as strong a confirmation as this kind of check
  can give without reading the `source_catalog` step's source code
  directly.

**Confidence: high.** This is the correct, current, in-flight-calibrated
source for both F770W and F1000W, confirmed via (1) live CRDS best-
reference lookup against the actual operational context rather than a
guessed filename, (2) the file's own schema matching the documented APCORR
format, and (3) an exact numerical round-trip against real archive data
independent of anything CRDS-side. Remaining uncertainty is scoped, not
open-ended: how to translate this table (built for circular-aperture
photometry) into a correction for the model-PSF fit's finite-stamp flux is
an implementation detail, not resolved here -- but the raw ingredients
(the real EE-vs-radius curve for both bands) are now in hand. Worth noting
as a sanity-checking data point for that implementation step: the PSF
stamp used in the smoke test above (`fov_pixels=15`, ~7.5 px radius) falls
between this table's EE=0.7 (radius ~4.2-4.6 px) and EE=0.8 (radius
~6.7-8.9 px) rows for both filters -- consistent with, and a good
independent explanation for, the ~0.70-0.82x flux deficit actually measured
in that smoke test, not merely a coincidence.

**Net effect:** blocking item 2 (Open Methodological Questions above) is
resolved -- the encircled-energy calibration source has been identified,
confirmed live, and validated end-to-end against real data. Both blocking
items for this module are now cleared. Per the researcher's standing
instruction, no implementation of the MIRI photometry-extraction module has
been written yet.

### 2026-07-21 -- `pipeline/miri_photometry.py` implemented and verified against real PN-TC-1 data

Implemented the module per the 2026-07-21 design discussion, then verified
by re-running the actual real-data chain: reused retriever.py's own
functions (not a reimplementation) to rebuild a live a0 dataset for
PN-TC-1 (same 40 stars as the earlier retriever.py/photosphere.py
verifications), then ran `miri_photometry.run()` against it end-to-end.

**Design decisions carried through into the code, not just the docs:**

- `observed_flux_{band}` (the PSF-fit measurement) is EE-corrected by
  construction -- the multiplication by the APCORR table's `apcorr` value
  happens directly in `extract_flux_for_filter`, with an inline comment at
  the exact multiplication ("PRIMARY measurement: PSF-fit flux,
  EE-corrected... see module docstring for why this multiplication is
  required, not optional") and the same point made at module-docstring
  level, so a future reader doesn't need to reconstruct this session's
  history to know which flux is corrected.
- The module never opens `_cat.ecsv` at all -- positions come only from
  a0's `miri_ra_{band}`/`miri_dec_{band}`/`mosaic_path_{band}` columns,
  which are already keyed by `star_id`/`gaia_source_id` via retriever.py's
  Gaia-anchored cross-match. The `label`-instability trap is closed
  structurally, not by a convention someone has to remember.
- `qc_psf_fit_failed_{band}` uses photutils' own `flags != 0` check
  (`flags_indicate_fit_failure`), with a dedicated regression test
  (`test_flags_indicate_fit_failure_nonzero_flags`) pinned to `flags=12`,
  the exact value observed for the real extended PN-TC-1 source in the
  original smoke test.

**Bug caught before the first successful run (self-caught, not
user-caught):** `assemble_miri_photometry` initially passed the whole
per-filter neighbor-index dict (`mosaic_path -> [(star_index, x, y), ...]`)
into `extract_flux_for_filter` instead of the list for that star's own
mosaic -- `ValueError: too many values to unpack`, since the function tried
to iterate the dict's keys as `(idx, nx, ny)` tuples. Fixed by renaming the
parameter to `neighbor_index_by_mosaic` and looking up
`.get(mosaic_path, [])` inside the function, after `mosaic_path` is known.

**Second bug caught before the first successful run:** the generic
`f"{k}_{filt}"` column-suffixing produced `observed_flux_err_F770W`
instead of `observed_flux_F770W_err` -- inconsistent with
photosphere.py's established `predicted_flux_{band}_err` convention
(filter before `_err`, not after), and immediately surfaced as a `KeyError`
when setting units attrs on the expected column name. Fixed with a small
`_suffix_column` helper (filter-before-`_err`), unit-tested
(`test_suffix_column_puts_filter_before_err_suffix`).

**Live run against real PN-TC-1 data (40 stars, both filters), 14.3 s
total** (fast because PSF templates and mosaic files are cached once per
run, not per star):

1. **The aperture cross-check reproduces `_cat.ecsv`'s `aper_total_flux`
   EXACTLY -- ratio 1.0000 for every single one of the 41 star/filter
   combinations tested (28 F770W + 13 F1000W), not just the one star
   checked during the earlier CRDS-source-finding verification.** This is
   strong, broad confirmation that the EE-correction methodology itself
   (radius/sky-annulus/apcorr all from the same APCORR table row) is
   correct, independent of anything PSF-fit-specific.
2. **The PRIMARY PSF-fit measurement (`observed_flux_{band}`), restricted
   to QC-clean sources (`qc_psf_fit_failed==0` AND
   `qc_psf_aperture_disagreement==0`): median ratio to `aper_total_flux` =
   1.0155 (F770W, n=14), 1.0023 (F1000W, n=4).** This is the direct answer
   to the instruction's core question -- the pre-correction 0.70-0.82x
   deficit found in the original 3-star smoke test is resolved for the
   population that would actually reach excess.py unflagged, to within a
   few percent.
3. **New finding, not visible in the original 3-star smoke test (which
   only tested bright sources): for fainter and/or flagged sources, the
   PSF-fit-to-catalog ratio has real, substantial scatter (as low as 0.32,
   as high as 37 for one very-low-flux source where both measurements are
   close to noise) -- but this population is exactly what
   `qc_psf_fit_failed`/`qc_psf_aperture_disagreement` catch.** Of the 41
   star/filter combinations, 19 were flagged by one or both QC flags; the
   ratio distribution for the *unflagged* 18 is the tight ~1.00-1.02 result
   in point 2. This is read as the QC design working as intended (catching
   exactly the population where the finite-stamp/local-fit approach is
   less trustworthy), not as a failure of the EE correction -- but the
   disagreement rate (19/41, ~46%) is much higher than anticipated from the
   original 3-star test, and is a real, measured data point that should
   inform whether `disagreement.rel_frac` (currently 0.2, a stated
   compromise) needs revisiting once more fields are tested.
4. **Regression check on `qc_psf_fit_failed`:** the same real extended
   source from the original smoke test (`gaia_source_id
   5954912374289120896`, RA/Dec 266.39707/-46.08996, exact match) was
   independently re-identified by the full module and again produced
   `qc_psf_fit_failed_F1000W=1` (with `aper_total_flux` and
   `observed_flux` both near-zero/negative for that band) -- the same
   real, independently-corroborated (by `_cat.ecsv`'s own `is_extended`
   flag) non-point-source case is caught correctly by the actual
   implementation, not just the scratch smoke-test script.

**Status:** `pipeline/miri_photometry.py` implemented, unit-tested (17 fast
tests covering APCORR lookup, stamp geometry, QC-flag logic, and aperture
photometry against a synthetic known-flux array -- PSF-fitting itself is
smoke-tested live only, per the same convention as photosphere.py's
stsynphot/expecto/dustmaps code), and verified end-to-end against real
PN-TC-1 archive data. `config/pipeline_config.yaml` and `requirements.txt`
updated accordingly (`photutils>=3.0`, `stpsf>=2.2`).

### 2026-07-21 -- `qc_psf_aperture_disagreement` rate investigated against two more real fields: genuine population, not threshold miscalibration

PN-TC-1 alone showed a `qc_psf_aperture_disagreement` rate of ~46-69%
across the two bands -- much higher than the original 3-star smoke test
implied. Two explanations were live: (1) the flag is correctly catching a
genuinely large faint/marginal population in real data, or (2) `rel_frac`
(0.2, a stated compromise from the initial design) was calibrated on too
small a sample and is over-flagging otherwise-fine sources. Tested against
two more real archive fields chosen for contrasting stellar
density/faintness profiles, the same way the PHOENIX cool-bucket gap was
quantified with the 18-observation diverse sample (2026-07-20 entries
above): **CONTROLFIELD** (`jw03523-o004_t003`, a deliberately quiet/sparse
comparison field, 306 a0 stars) and **NGC-602** (`jw02662-o004_t001`, a
genuine dense young star-forming cluster in the SMC, 1095 a0 stars) --
chosen via a live MAST `target_classification` survey, not assumed.
`miri_photometry.run()` was run end-to-end on both (via the same real
retriever.py chain used for PN-TC-1, not synthetic data).

**Disagreement rate by field** (excluding `qc_psf_fit_failed` sources):

| Field | F770W | F1000W |
|---|---|---|
| PN-TC-1 (planetary nebula) | 50.0% (14/28) | 69.2% (9/13) |
| CONTROLFIELD (quiet/sparse) | 16.3% (25/153) | 15.4% (26/169) |
| NGC-602 (dense young cluster) | 47.2% (318/674) | 40.3% (176/437) |
| **Combined** | **38.4%** (550/1432) | |

**This alone is evidence against explanation (2).** A miscalibrated global
threshold would over-flag at a roughly similar rate everywhere, regardless
of field content -- instead the rate spans 15% to 69%, tracking field
character (a field deliberately chosen to be quiet has the lowest rate by
a wide margin) in exactly the way a threshold correctly responding to real
photometric difficulty would.

**Per-field flagged-vs-clean comparison** (done per-field, not pooled --
pooling conflates NGC-602's intrinsically fainter/more-distant population
with the flag's actual behavior):

| Field | flagged/clean aperture-flux ratio | flagged SNR (median) | clean SNR (median) | flagged crowded% | clean crowded% |
|---|---|---|---|---|---|
| PN-TC-1 | 0.38x (flagged fainter) | 12.0 | 47.8 | 57% | 44% |
| CONTROLFIELD | 0.29x (flagged fainter) | 57.4 | 238.1 | 34% | 30% |
| NGC-602 | **2.52x (flagged BRIGHTER)** | **46.4 (higher)** | 30.7 | **36% (lower)** | 51% |

**PN-TC-1 and CONTROLFIELD both show an unambiguous, strong "flagged =
genuinely fainter/lower-SNR" pattern** -- flagged sources are 3-4x fainter
and have 4x lower formal SNR than clean sources in both fields
independently. This directly supports explanation (1) for these two
fields: the flag is catching real marginal detections, not being
over-tight.

**NGC-602 shows the OPPOSITE pattern** -- flagged sources are brighter,
higher-SNR, and *less* often near another a0 star (by the existing
`qc_crowded_source` metric) than clean ones. This doesn't fit either of the
two original hypotheses cleanly, so it was investigated further rather
than left as noise: printing raw pixel cutouts around the 4 brightest
flagged NGC-602 sources showed the brightest one (obs=3.15e-3 Jy, by far
the brightest source measured in any of the three fields) has a visibly
non-clean, mildly asymmetric core in its 15x15 px cutout -- consistent
with either an unresolved companion/blend (plausible in a dense young
cluster, where mass segregation puts the brightest members in the most
crowded sub-regions -- a real effect the existing `qc_crowded_source`
metric, keyed to *other a0 stars* rather than PSF morphology, would not
necessarily catch) or the MIRI F770W/F560W "cruciform" PSF-modeling gap
already noted in this file's APCORR search (2026-07-21, "known to be
incomplete... ~3% additional uncertainty") becoming more prominent for
bright sources specifically. **Not conclusively distinguished between
these two mechanisms** -- both are plausible and not mutually exclusive --
but importantly, PN-TC-1's own brightest star (1.91e-3 Jy) sits at
rel_diff=0.181, just under the 0.2 threshold, consistent with (not
disproving) a similar bright-source effect being present but weaker there.

**Decisive check: is the population "just above threshold" (rel_diff in
[0.20, 0.30), n=94, 85 from NGC-602) a genuinely marginal population, or
clean/high-SNR sources caught on a technicality?** Its median SNR (38.5) is
much closer to the clearly-bad population's (rel_diff >= 0.50: SNR 26.7)
than to the clearly-clean population's (rel_diff < 0.10: SNR 133.5) -- a
>3x gap from "clean." **No evidence of a cluster of otherwise-healthy,
high-SNR sources sitting just over the cutoff.** The rel_diff distribution
across all three fields combined is a smooth, continuously-decaying
long tail, not bimodal -- consistent with a graded, photon-noise/
photometric-complexity-driven continuum (expected astrophysically), not a
population artificially split by an arbitrary cutoff.

**Conclusion: no evidence supports retuning `rel_frac` (0.2), and it was
NOT changed.** The evidence points to explanation (1) -- the flag is
catching a real, field-dependent marginal/complex-photometry population --
with a nuance not anticipated by either original hypothesis: "marginal"
has (at least) two distinct real drivers, not one. Faintness/low-SNR
dominates in PN-TC-1 and CONTROLFIELD; bright-source photometric
complexity (possible blending or cruciform-related PSF mismatch,
unresolved) dominates NGC-602's high rate instead. The ~38% combined rate
is a real, now-measured statistic (worth keeping for the methods section,
per the researcher's framing) rather than an artifact to engineer away.
**Caveat on the SNR metric used throughout this analysis:** it's
`|observed_flux| / observed_flux_err`, where `observed_flux_err` is only
`photutils.psf.PSFPhotometry`'s formal (photon-noise) fit uncertainty --
it does NOT capture systematics like background structure or blending, so
it's a weak/incomplete proxy for "how marginal is this detection" and its
failure to cleanly separate flagged/clean in NGC-602 is not strong evidence
against a genuine-difficulty explanation there; the direct pixel-level
brightness/crowding evidence is more informative for that field.

**Not done here, flagged as a follow-on if the NGC-602 mechanism ever needs
to be pinned down precisely:** distinguishing blending from a cruciform PSF
gap would need either a higher-resolution look at whether the asymmetry is
compact (blend) or diffuse/plus-shaped (cruciform), or cross-checking
against `_cat.ecsv`'s own `is_extended`/`sharpness` columns for these
specific sources -- not required to resolve the retuning question this
investigation was scoped to answer, so not pursued further now.

### 2026-07-21 -- `qc_psf_aperture_disagreement` split into `qc_psf_disagreement_faint`/`_complex`

The three-field investigation above found `qc_psf_aperture_disagreement`
was catching two physically distinct populations under one flag: a
faint/low-SNR marginal-detection population (dominant in PN-TC-1 and
CONTROLFIELD) and a bright/high-SNR population where photon noise cannot
explain the disagreement (concentrated in NGC-602's dense cluster). Since
these have different implications for a downstream reader (a sensitivity
limit vs. real PSF complexity/a possible unresolved companion) and matter
differently for excess.py's YSO-field candidates specifically, split the
flag rather than leaving a future analysis to re-derive the distinction.

**Implementation** (`pipeline/miri_photometry.py:classify_disagreement`):
per disagreeing star, compute `SNR = |observed_flux| / observed_flux_err`
(`photutils.psf.PSFPhotometry`'s own formal, photon-noise-only fit
uncertainty) and split on `miri_photometry.disagreement.snr_threshold`
(new config key, default 50.0):
- `qc_psf_disagreement_faint`: SNR below threshold.
- `qc_psf_disagreement_complex`: SNR at/above threshold, OR SNR itself
  isn't computable (zero/NaN `observed_flux_err`) -- an uncomputable SNR
  errs toward "needs a closer look," not toward silently assuming
  noise-limited.
- `qc_psf_aperture_disagreement` is unchanged (kept for backward
  compatibility as a general caution flag) -- it is exactly the logical OR
  of the two new sub-flags, verified as an invariant (see below).

**`snr_threshold=50.0` is a stated compromise, not a precisely derived
boundary** -- same status as `rel_frac`/`abs_floor_jy` above. It's grounded
in two real numbers from the investigation, not picked arbitrarily:
PN-TC-1's entire flagged population (independently confirmed faint-driven
by consistently lower flux/SNR than that field's own clean sources) topped
out at SNR=29.2; the real complex-driver example that motivated this split
in the first place -- NGC-602's brightest source, which still disagreed by
36% despite being the brightest source measured across all three fields --
had SNR=1425. 50.0 sits comfortably below that 1425 and only modestly above
29.2, but the exact value in between has no principled derivation and
should be revisited if a future field's data suggests it's drawing the
line in the wrong place.

**Verification:** re-ran the real PN-TC-1 chain end-to-end (fresh
retriever.py -> miri_photometry.py, not reusing cached mosaics) after the
change. Checked three invariants hold on the live output for both bands:
(1) `qc_psf_aperture_disagreement == OR(faint, complex)` for all 40 stars,
(2) `faint` and `complex` are never both set, (3) neither sub-flag is ever
set when the parent flag is 0. All held. As expected from the
investigation (PN-TC-1's flagged population was independently confirmed
purely faint-driven, max SNR 29.2), **all 23 flagged stars (14 F770W + 9
F1000W) classified as `qc_psf_disagreement_faint`, zero as `_complex`** --
consistent with, not just assumed from, the field-level finding above.

**Docs updated to match:** `config/pipeline_config.yaml` (new
`snr_threshold` key, with the same grounding numbers restated inline);
`config/quality_config.yaml` (added entries for every `miri_photometry`
qc_* flag -- this file had not been updated when the module was
implemented earlier in the day, so `qc_no_mosaic_for_filter`,
`qc_source_off_mosaic`, `qc_saturated`, `qc_crowded_source`, and
`qc_psf_fit_failed` are now documented there for the first time alongside
the two new split flags, closing that gap rather than leaving it wider);
`pipeline/miri_photometry.py`'s module docstring. Also corrected a
pre-existing inaccuracy noticed while touching this docstring/config:
`qc_crowded_source` was documented as checking only Gaia-matched a0 stars,
but retriever.py's pivot keeps non-Gaia-matched detections as singleton a0
rows too, so the check already covers all of a0's population -- the docs
undersold what the flag actually does; fixed in both
`pipeline/miri_photometry.py` and `config/pipeline_config.yaml`.

**Status:** `pipeline/miri_photometry.py` stage is complete --
`excess.py` can now consume `observed_flux_{band}`, and its precision can
be discriminated per-source via `qc_psf_disagreement_faint`/`_complex`
without re-deriving this investigation.

### 2026-07-22 -- excess.py design discussion: join mechanics, disqualifying/caveat-only categorization, and the excess.py-before-contaminants.py dependency direction

Before writing `pipeline/excess.py`, walked through the design in plain
language (per project convention: no implementation before the
methodological reasoning is discussed and agreed). Full detail lives in the
conversation itself; key resolved points, all now implemented:

- **Join mechanics:** confirmed by reading `retriever.py`/`photosphere.py`/
  `miri_photometry.py` directly that a0, a1, and the miri_photometry output
  all share the same `star` dimension/coordinate, same length, same row
  order -- both downstream modules copy a0's `star` coord verbatim rather
  than re-deriving it. So the join is a positional merge, not a lookup.
  Given this project's own history with a silent row-misalignment bug
  (retriever.py cross-match, 2026-07-15), `excess.py` does not merely trust
  this -- `assert_star_aligned` explicitly checks `star_id` equality across
  all three datasets before merging and raises if it ever doesn't hold.
- **Nothing is dropped:** confirmed every branch of `fit_star`
  (photosphere.py) and `extract_flux_for_filter` (miri_photometry.py)
  always returns a full row (NaN + a qc flag on failure, never a missing
  row) -- so a "star missing from one of the three" case never actually
  arises; `excess.py` follows the same convention rather than filtering.
- **Excess statistic:** `excess_sigma_{band} = (observed - predicted) /
  sqrt(observed_err**2 + predicted_err**2)`, signed (positive = excess).
  Defensible as an independent-error combination because the two error
  terms come from genuinely independent machinery with no shared inputs
  (photutils' photon-noise fit uncertainty vs. photosphere.py's
  profile-likelihood Teff-perturbation error) -- but both are already
  self-documented as incomplete (photon-noise-only; not a full SED-fit
  error budget), so this sigma is explicitly an approximation built from
  two already-approximate error bars, not presented as a rigorous
  statistical significance.
- **qc_rj_extrapolated (researcher's decision):** option A -- excluded from
  any candidate composite entirely (added to
  `pipeline.excess.DISQUALIFYING_STAR_FLAGS`), raw sigma still reported as
  a diagnostic. Rejected option B (a stopgap unvalidated inflation factor)
  since, unlike this project's other "stated compromise, not derived"
  thresholds (`rel_frac`, `abs_floor_k`, etc.), there is no real number
  behind it yet at all -- inventing one would be qualitatively different
  from compromising on an imprecise one. See the updated Open
  Methodological Questions entry above.
- **qc_ambiguous_gaia_match (researcher's decision):** disqualifying, not
  caveat-only, given the retriever.py cross-match-misattribution history
  (2026-07-15) -- an ambiguous match means the fit's input photometry might
  belong to the wrong star entirely.
- **Both-bands-vs-either-band (researcher's decision):** neither alone.
  The primary composite (not yet implemented -- see below) will require
  BOTH bands independently significant when both were measured, with
  `qc_single_filter_detection` stars getting their own, separate, stricter
  single-band threshold and a distinct `qc_single_band_candidate` marker,
  rather than being silently included at the two-band bar or silently
  dropped from candidacy. The actual stricter single-band value is
  deferred to the same literature check as the primary threshold (see
  below and `config/pipeline_config.yaml`'s new
  `single_band_significance_threshold_sigma` key).
- **Disqualifying vs. caveat-only, full categorization implemented as
  `DISQUALIFYING_STAR_FLAGS`/`DISQUALIFYING_BAND_FLAGS` in
  `pipeline/excess.py`** (see that module's docstring for the complete,
  per-flag reasoning): disqualifying = `qc_ambiguous_gaia_match`,
  `qc_no_photosphere_grid`, `qc_poor_photosphere_fit`, `qc_possible_binary`,
  `qc_pms_veiling_risk`, `qc_rj_extrapolated` (star-level), and
  `qc_no_mosaic_for_filter`, `qc_source_off_mosaic`, `qc_saturated`,
  `qc_crowded_source`, `qc_psf_fit_failed`, `qc_psf_disagreement_complex`
  (per-band). Caveat-only (recorded, not gating): `qc_extinction_uncertain`
  (verified in code that uncertain sources fall back to `av_for_fit=0.0`,
  which biases toward *suppressing* apparent excess, not manufacturing it
  -- directionally safe for this search), `qc_grid_disagreement` (Kurucz
  stays the recorded prediction regardless), and
  `qc_psf_disagreement_faint_{band}` (photon-noise-explained, and that
  noise is already reflected in a larger `observed_flux_{band}_err`, so
  it's already priced into sigma without a separate gate).
- **excess.py-before-contaminants.py, not the reverse:**
  `quality_config.yaml`'s own `qc_anomalous_excess` definition requires six
  contaminant flags that don't exist yet (`pipeline/contaminants.py` is
  unwritten), so the literal final flag can't be computed today regardless.
  But `excess.py` doesn't need `contaminants.py` to do its own job (only
  needs `observed_flux`/`predicted_flux`, both already available), and
  there's an efficiency argument for this order too: `contaminants.py`'s
  external-catalogue cross-matching is expensive and only worth running
  against stars `excess.py` has already identified as excess-clean and
  excess-showing. So `excess.py` produces a preliminary,
  contaminant-flag-independent QC rollup now; the true `qc_anomalous_excess`
  will be assembled once `contaminants.py` exists and reads this stage's
  output, not the other way around.

**Implemented:** `pipeline/excess.py` (`assert_star_aligned`,
`compute_excess_sigma`, `compute_star_disqualified`/
`compute_band_disqualified`, `build_disqualifying_flags_summary`,
`assemble_level_b1`, `save_level_b1`, `run`), 21 new fast unit tests in
`tests/test_excess.py` (all passing, full 55-test suite passing), and
corresponding `config/quality_config.yaml`/`config/pipeline_config.yaml`
documentation for the new qc_* flags and the two new (still-null)
threshold config keys. **Deliberately NOT implemented yet** (both
confirmed still-blocked, not overlooked): `qc_excess_significant_{band}`/
`qc_candidate_preliminary`/`qc_single_band_candidate` (need the threshold
values below) and `qc_anomalous_excess` (needs `pipeline/contaminants.py`).

### 2026-07-22 -- Literature check: Carrigan (2009) / Griffith et al. (2015) significance thresholds and multiple-testing handling

Before setting `excess.significance_threshold_sigma`, checked what
threshold(s) the two key precedent papers actually used and how they
handled multiple-testing/look-elsewhere effects at their own archive
scale -- same precedent-check discipline used to resolve the extinction
question (2026-07-20). Both papers' full text was read directly (not just
abstracts): Carrigan (2009) via the arXiv PDF (arXiv:0811.2376, all pages,
tables, and figure captions); Griffith et al. (2015) via the arXiv PDF
(arXiv:1504.03418, full ~130,000-character extracted text, Introduction
through Conclusions). **Confidence: high** on both papers' own selection
pipelines and numbers. One caveat: Griffith et al. repeatedly defers to
"Paper II" (Wright et al. 2014a) for the deeper justification of some
parameter choices (e.g., why γ specifically) -- that paper itself was not
read directly here, only Griffith's summary of it, so anything attributed
to "Paper II" below is secondary-source knowledge.

**1. Quantitative threshold used:** Neither paper uses an Nσ-on-predicted-flux
cut analogous to what this project is considering.
- **Carrigan (2009):** the operative cut was a blackbody **fit-quality**
  statistic -- unweighted least-squares (unLSQ) < 0.25 (Table 1: 65 -> 22
  sources) -- not a flux-excess sigma. Sigma language does appear, but only
  to *reject* sources with contaminating spectral lines ("lines could still
  be seen down to 2-3 sigma above a blackbody distribution... a serious
  Dyson Sphere candidate would have to have a high statistical significance
  compared to any other possible explanation"), the opposite use case from
  this project's excess-detection sigma. Everything upstream of that was
  categorical cuts on IRAS metadata (quality flags, temperature range,
  spectral class, ID type), and the actual final step was a **subjective
  0-3 expert rating** per surviving source, not a formal statistic.
- **Griffith et al. (2015):** the operative cut is on a physically-motivated
  derived parameter, **gamma >= 0.25** (fraction of a galaxy's stellar
  luminosity re-radiated as MIR "waste heat" under a maximally-conservative
  dust-free template, from the AGENT formalism of Paper II) -- this is what
  defines both the ~4,000-source visual-review set and the final 563-source
  "Platinum Sample." Explicitly a generously inclusive round number chosen
  well above the paper's own stated formal-detectability floor ("values of
  gamma of a few percent would be detectable as an anomalous MIR excess"),
  not a value calibrated against a false-positive/sigma budget. Hard color
  cuts (W2-W3 < 2, W3-W4 <= 1) were used earlier, but only to strip obvious
  stellar contaminants before the gamma cut, not as the excess-flagging
  threshold itself.

**2. Multiple-testing / look-elsewhere handling:** **neither paper applies
anything resembling Bonferroni correction, FDR control, or an explicit
"expected false positives at this cut, given N sources" calculation to
their final published method.** Both instead sidestep the problem
procedurally: hard structural/categorical cuts to shrink the sample, then
**exhaustive manual/visual vetting of every single surviving source**,
ending in a subjective rating rather than a corrected significance level.
- Carrigan comes closest to this project's own reasoning, but only in an
  **abandoned preliminary method** he explicitly replaces: for a
  filter-only temperature cut, he reasons "a 3-sigma peak in one bin might
  have required about 25 sources. This suggested that less than one in
  10,000 of the IRAS sources could potentially be a Dyson Sphere" -- a
  genuine look-elsewhere-style estimate, but not applied to the final
  published cuts. His actual defense against false positives for the final
  16-source table is direct manual scanning against SIMBAD/2MASS/MSX/DIRBE
  (eliminating ~80% of a 1,527-source sample by itself) plus individual
  case-by-case review -- no sample-size-adjusted threshold for the final
  set, and zero confirmed candidates (all 16 got a plausible conventional
  explanation on manual review).
- Griffith et al. state their false-positive strategy explicitly: false
  positives are controlled by **sample selection** (restricting to
  resolved/extended sources, where common contaminant classes structurally
  can't appear -- "extended sources have the lowest false positive rate"),
  not by a post-hoc statistical correction on the ~10^5-10^6-source starting
  scale. Their actual pipeline: quality-flag/coordinate/color cuts
  (202,851 -> 75,846) -> **visual classification by eye of every one of
  those 75,846 sources** into 5 categories using color images -> gamma>=0.25
  cut (~3,145) -> **individual manual inspection and letter-grade (A-F) of
  every one of the ~4,000 gamma>=0.25 survivors** via a custom GUI with
  multiwavelength cutouts and literature/SIMBAD lookups -> 563-source
  Platinum Sample. The only "false positive rate" figure in the paper
  (~50%) is a narrow cross-validation statistic for one extendedness proxy,
  unrelated to multiple-testing correction for the excess search itself.

**3. Automated-cut -> visual-vetting pipeline (both papers, for reference):**
Carrigan: 245,889 -> [quality/temperature/class/IDTYPE categorical cuts] ->
1,527 -> **manual scan** -> 295 -> further manual elimination -> 65 ->
unLSQ<0.25 -> 22 -> "somewhat interesting" 16 -> "most interesting" 3 ->
0 confirmed (all explained). Griffith: 202,851 -> [quality/coordinate/color
cuts] -> 75,846 -> **visual classification of every source** -> W3 Extended
Gold Sample ~31,600 -> gamma>=0.25 -> 3,145 -> manual contaminant removal ->
2,779 -> classify Extended/Point-galaxy/Point-star/Junk -> 1,296 Extended ->
gamma>0.25 in best system -> 563 Platinum Sample (+ separately, all ~4,000
gamma>=0.25 sources individually letter-graded, 3 grade-A "new to science"
sources flagged for follow-up).

**Implication for this project's threshold decision (not decided here --
this check was scoped to inform that decision, not make it, per the
researcher's explicit instruction):** the precedent from both key prior
searches is "cut hard structurally, then manually vet every survivor
individually," not "pick a corrected significance level and trust it
statistically." This is directly relevant to the ~1000+-star,
up-to-2-band scale this project operates at -- a bare sigma cut without
either a look-elsewhere correction or an equivalent manual-vetting
commitment would be a real departure from both precedents, not a neutral
default. Worth deciding explicitly, once `excess.significance_threshold_sigma`
is set, whether this project adopts an analogous "hard cut + individually
vet every survivor" philosophy (feasible at this project's much smaller
candidate scale than Carrigan/Griffith's) rather than leaning on a
Bonferroni/FDR correction that neither precedent paper used.

### 2026-07-22 -- Survivor-count check at candidate sigma cuts (3/4/5): real data, and a live replication of Carrigan's own finding

**IMPORTANT CAVEAT, added after the fact at the researcher's explicit
request -- read this before the numbers below:** this is a **positive-control
result, not a general false-positive-rate measurement.** All three fields
(PN-TC-1, CONTROLFIELD, NGC-602) were deliberately chosen in earlier
sessions for reasons unrelated to this check (PN-TC-1: first live-verified
field; CONTROLFIELD: a deliberately quiet/sparse *photometric* comparison
field for the miri_photometry.py disagreement-rate investigation; NGC-602: a
genuine dense young cluster for the same investigation) -- none were random
draws from typical sky, and (as the entry below itself discovers) all three
turn out to be fields whose *entire* MAST `target_classification` is a
young-cluster or planetary-nebula tag. **"0/80 ordinary stars flagged"
would be a wrong takeaway from this entry** -- it is not evidence about the
background false-positive rate on ordinary field stars, because none of the
~80 stars tested were drawn from a population expected to be "ordinary" in
the first place. What this entry DOES show: the pipeline correctly flags
real circumstellar-dust/young-star excess in fields chosen (for other
reasons) to contain exactly that. A genuine false-positive-rate estimate
would require a field/sample chosen specifically for target_classification
diversity representative of the full archive, which this check did not do.

Before setting `excess.significance_threshold_sigma`, the researcher asked
for an empirical estimate of how many stars would survive as clean,
sigma-significant candidates at a few candidate cuts, based on real archive
data -- not a synthetic guess. Ran the actual `retriever -> photosphere ->
miri_photometry -> excess` chain (reusing the real `run()`/`assemble_*`
functions, no reimplementation) against the same three fields already
characterized in this project:

- **PN-TC-1**: run to full completion (40 a0 rows, 13 Gaia-matched --
  reproduced the known reference numbers from the 2026-07-20/21 entries
  before trusting any new output, per this project's own convention).
- **CONTROLFIELD**: capped at the first 20 of 42 true Gaia-matched stars
  (by `star` order), to bound runtime given the ~50-130s/star photosphere
  fit cost -- NOT the full field, reported as a labeled subsample.
- **NGC-602**: capped at the first 20 of 56 true Gaia-matched stars, same
  reason and same caveat.

**Bug caught and fixed while doing this:** `pipeline/excess.py` was not
carrying `qc_single_filter_detection` through from a0, despite that flag
being exactly what's needed to separate dual-band from single-band-only
stars for this analysis (and for the future `qc_single_band_candidate`
tier). Fixed (`assemble_level_b1` now copies it through, like
`target_classification`/`gaia_ra`/`gaia_dec`), regression-tested
(`test_assemble_level_b1_carries_through_qc_single_filter_detection`).

**Survivor counts** (clean AND excess_sigma >= cut; dual-band requires
BOTH F770W and F1000W to independently clear the cut; single-band-only
stars use their one measured band):

| Field (N tested) | Dual-band survivors (3/4/5 sigma) | Single-band survivors (3/4/5 sigma, band) |
|---|---|---|
| PN-TC-1 (40 rows, 2 dual-band, 38 single-band) | 0 / 0 / 0 (of 2 dual-band stars) | 2 / 2 / 1 (F770W only) |
| CONTROLFIELD (20 of 42 Gaia-matched, 19 dual-band, 1 single-band) | 1 / 1 / 1 (of 19 dual-band stars) | 0 / 0 / 0 |
| NGC-602 (20 of 56 Gaia-matched, 10 dual-band, 10 single-band) | 0 / 0 / 0 (of 10 dual-band stars) | 2 / 2 / 2 (F770W only) |
| **Pooled (80 rows tested, 31 dual-band + 49 single-band)** | **1 / 1 / 1** | **4 / 4 / 3** |

Pooled total surviving as "clean and >= cut" across ~80 real stars: **5 at
3-sigma, 5 at 4-sigma, 4 at 5-sigma** -- i.e. essentially flat across this
whole cut range, because the surviving stars' actual sigma values are far
above 5 (see below), not marginal cases hovering near the cutoffs tested.

**Critical qualitative finding, from inspecting every survivor's own
`target_classification` (not just counting them) -- exactly the kind of
manual look the Carrigan/Griffith literature check (above) said neither
paper skipped:**

- The one CONTROLFIELD dual-band survivor (star_id 5258785483680276352,
  Teff~3642 K) shows observed/predicted ~4.6x in F770W (sigma=168.6) and
  ~3.4x in F1000W (sigma=79.0) -- an enormous, obviously-real (not a
  marginal statistical fluctuation) flux excess. Its `target_classification`
  is **"Stellar Cluster; Young star clusters."** A second CONTROLFIELD star
  (5258785445017206784, Teff~3659 K) shows a smaller but still tight ~31%
  F770W excess (sigma=20.9, F1000W sigma=2.86, so it does not clear the
  dual-band bar) -- same target_classification.
- Both PN-TC-1 single-band survivors have `target_classification` **"Star;
  Planetary nebulae nuclei"** -- i.e. the exposed, still mid-IR-bright
  central star of an actual planetary nebula, a textbook source of real
  circumstellar-dust excess.
- Both NGC-602 single-band survivors (sigma 18.5 and 8.0 in F770W) again
  have `target_classification` **"Stellar Cluster; Young star clusters"**
  (NGC-602 is a genuine young star-forming cluster in the SMC).

**Every single automatically-flagged "candidate" found across all three
fields, at every cut tested (3 through 5 sigma), belongs to a
`target_classification` that already provides a conventional astrophysical
explanation for real mid-IR excess (evolved/PN circumstellar dust, or
young-cluster disk/accretion excess) -- zero are "boring" field
main-sequence stars, where an unexplained excess would actually be
surprising.** This is a live, concrete replication of Carrigan (2009)'s own
stated experience ("the best Dyson Sphere candidates in the sample turned
out, on inspection, to be reddened/dusty objects... and were vetoed as
such") using this project's own real data and real pipeline, not just
literature precedent -- strong evidence for the researcher's lean toward a
manual-vetting philosophy (see the entry above): an automated sigma cut
alone, even a high one, does not by itself separate real
technosignature-relevant anomalies from mundane evolved/young-star
astrophysics, at least in this small sample.

**Two concrete, currently-unaddressed gaps this surfaced** (not fixed
here -- flagged for contaminants.py or a follow-up photosphere.py config
change):
1. `photosphere.py`'s `qc_pms_veiling_risk` token list
   (`pipeline_config.yaml`'s `target_classification_tokens.pms_veiling_risk`)
   does not match "Young star clusters"/"Stellar Cluster" text at all
   (its tokens are "Protoplanetary disks", "Protostars", "Pre-main sequence
   stars", "Young stellar objects", "T Tauri stars", "Proplyds",
   "Circumstellar disks") -- every young-cluster candidate found above
   slipped through this check with `qc_pms_veiling_risk=0`, undetected.
2. There is currently no flag anywhere in the pipeline for planetary-nebula
   nuclei specifically -- neither `qc_no_photosphere_grid` (white-dwarf-only)
   nor any contaminant category catches them; both PN-TC-1 candidates got a
   full, unflagged Kurucz/PHOENIX fit despite not being physically
   appropriate targets for either grid (a PN nucleus is not on the main
   sequence). This is squarely in scope for `contaminants.py`'s planned
   `agb_or_evolved_giant` category, which does not exist yet.

**Other data points, not yet acted on:** CONTROLFIELD's `qc_poor_photosphere_fit`
rate in this 20-star subsample was surprisingly high (16/20) -- worth
another look once a larger sample is fit, but not investigated further
here (out of scope for this check). NGC-602's `qc_no_mosaic_for_filter_F1000W`
rate in its subsample (9/20) was also unexpectedly high -- possibly a
footprint mismatch between the F770W/F1000W pointings in that field: noted,
not investigated.

**Not done here, deliberately**: no archive-wide extrapolation. The three
fields/subsamples tested total 80 star-rows, nowhere near archive scale
(~1000+ stellar-classified MIRI observations exist per the retriever.py
query), and the two capped fields are labeled subsamples (20 of 42, 20 of
56), not full-field results. This check answers "what does a threshold cut
find in real data we already have," not "how many candidates exist
archive-wide" -- extrapolating the latter from this sample size would not
be defensible. Per-star tables saved for reference (scratch/session-local,
not checked into the repo): `b1_PN-TC-1_table.csv`, `b1_CONTROLFIELD_table.csv`,
`b1_NGC-602_table.csv`.

**Status:** this is the survivor-count estimate the researcher asked for
before picking `excess.significance_threshold_sigma` -- the actual threshold
value and the manual-vetting-vs-statistical-correction methodological
choice are still open, follow-up decisions, not made here.

### 2026-07-22 -- Threshold set to 3.0; stopgap contaminant flags implemented; re-run confirms zero survivors (with an important granularity caveat)

Following the survivor-count check above, the researcher made two decisions
and asked for a stopgap fix plus a re-run before calling `excess.py`'s
scaffolding done:

1. **`significance_threshold_sigma = 3.0`**, framed explicitly as a triage
   cut for a manually-vetted shortlist -- NOT a look-elsewhere/Bonferroni-
   corrected statistical significance claim -- since the survivor count was
   nearly flat from 3-sigma to 5-sigma (real signal sits far above either
   cut, max observed 168.6), so a stricter value buys no discriminating
   power while risking loss of a real but modest candidate. This is now
   implemented in `pipeline/excess.py` (`qc_excess_significant_{band}`,
   `qc_candidate_preliminary` -- the latter requires BOTH configured bands
   significant AND `qc_single_filter_detection==False`) and documented with
   the same framing in the module docstring, `config/pipeline_config.yaml`,
   and `config/quality_config.yaml`, per the researcher's explicit
   instruction that this reasoning must appear in all three places and must
   never be described as a corrected statistical significance.
   `single_band_significance_threshold_sigma`/`qc_single_band_candidate`
   remain null/not computed -- the researcher's message set only the primary
   threshold this round, and explicitly reiterated (again) that the
   single-band tier needs its own, separately-justified, stricter value,
   not a scaled-down copy of 3.0.
2. **Two stopgap contaminant flags** (`pipeline.excess.is_stopgap_young_cluster`/
   `is_stopgap_evolved_star`, both added to `DISQUALIFYING_STAR_FLAGS`):
   `target_classification` exact-component match (same convention as
   photosphere.py's `is_pms_veiling_risk`/`is_white_dwarf`) against a narrow,
   session-verified token list (`config/pipeline_config.yaml`'s new
   `excess.stopgap_contaminant_tokens`) -- "Young star clusters"/"Stellar
   Cluster" for the young-cluster flag, "Planetary nebulae nuclei" for the
   evolved-star flag. Explicitly NOT a systematic vocabulary sweep (unlike
   retriever.py's `STELLAR_TARGET_CLASSIFICATIONS` allowlist) and NOT a
   substitute for `pipeline/contaminants.py`'s eventual proper catalogue
   cross-matching, which will supersede it.

**Re-ran the join/scoring step (not the full archive chain -- photosphere.py
and miri_photometry.py weren't touched, so their cached a1/miri_photometry
outputs for all three fields were reused as-is; only `excess.run()` was
re-executed, which is fast: no archive queries or model fits, just a NetCDF
join and numpy arithmetic) against the same three fields:**

| Field | `qc_star_disqualified` | `qc_candidate_preliminary` (dual-band) | `qc_excess_significant_{band}` (any star) |
|---|---|---|---|
| PN-TC-1 (40 stars) | 40/40 | 0/2 dual-band stars | 0/40 either band |
| CONTROLFIELD (20 stars) | 20/20 | 0/19 dual-band stars | 0/20 either band |
| NGC-602 (20 stars) | 20/20 | 0/10 dual-band stars | 0/20 either band |

**Zero survivors, confirmed** -- the outcome the researcher wanted to see
before calling this scaffolding done.

**Important mechanism finding, worth being precise about (discovered while
verifying the result, not assumed):** `target_classification` is a MAST
*observation/proposal-level* tag, identical for **every star in a field**,
not a per-star property. Confirmed directly: all 40 PN-TC-1 a0 rows carry
the exact string `"Star; Planetary nebulae nuclei"`; all 306 CONTROLFIELD
rows and all 1095 NGC-602 rows (checked at the TRUE full-field count, not
just this session's capped subsamples) carry `"Stellar Cluster; Young star
clusters"` -- one unique value per field, no variation at all. This traces
back to `retriever.py`'s `load_miri_catalog_sources`
(`sources["target_classification"] = str(obs_row["target_classification"])`),
which copies the observation's own classification onto every source
detected in it.

**Consequence, stated plainly:** the stopgap flags, as designed and as
literally requested (target_classification substring/component matching),
disqualify an ENTIRE FIELD wholesale once its target classification matches
-- not just the specific stars that are individually cluster members or
PN-nucleus-adjacent. Any ordinary, unrelated field star that happened to be
observed in the same pointing as a young cluster or planetary nebula would
also be disqualified by this stopgap, with no way (using only this
metadata field) to distinguish a genuine cluster member from an innocent
bystander in the same frame. This is a real, accepted limitation of the
stopgap approach, not a bug: it is exactly the kind of per-star
position/kinematics-aware discrimination that `pipeline/contaminants.py`'s
eventual proper catalogue cross-matching is meant to provide, and that a
target_classification-substring stopgap structurally cannot. Zero survivors
in this specific check is therefore consistent with either "the stopgap
correctly suppressed contaminated stars" or "the stopgap over-suppressed an
entire field, some of which might not individually deserve it" -- this
check cannot distinguish those two on its own, and the three test fields
happening to be wholesale-flaggable (see the positive-control caveat on the
entry above) means this particular re-run cannot exercise the
"partially-flagged field" case at all. Worth keeping in mind at archive
scale: fields NOT classified as young-cluster/PN will be unaffected by this
stopgap either way, and a field that IS so classified will have its entire
population suppressed by this mechanism, correctly or not on a per-star
basis.

**Verification:** all 63 tests pass (7 new tests added for the stopgap
functions, the significance/candidate computation, and the both-bands-vs-
single-band-exclusion logic -- see `tests/test_excess.py`).

**Status:** `pipeline/excess.py` scaffolding is now, per the researcher's
own framing, in a state to call "done" for this phase -- continuous
`excess_sigma_{band}`, the disqualifying/caveat-only QC categorization
(now including the two stopgap flags), `qc_excess_significant_{band}`/
`qc_candidate_preliminary` at a documented, honestly-framed threshold, and a
verified zero-survivor result on the same real data that originally
produced 5 false leads. Remaining open items, unchanged in kind from
before: `single_band_significance_threshold_sigma`/`qc_single_band_candidate`
(needs its own value), `pipeline/contaminants.py` (needs to exist before
`qc_anomalous_excess` can be assembled), and the field-level-granularity
limitation of the stopgap flags noted above (contaminants.py's job to fix
properly). **Superseded same day, see the entry immediately below** --
the researcher asked whether the field-level-granularity limitation could
be cheaply addressed before accepting it, which turned out to have a real,
partial answer.

### 2026-07-22 -- Field-level-granularity limitation investigated: cheap per-star fix found for planetary nebulae, none found (yet) for young clusters

The researcher asked, before accepting the field-level-granularity
limitation above as-is: is there a cheap, already-available star-level
signal (using only what's already in a0/a1, no new archive query) that
could distinguish likely cluster/PN members from field interlopers sharing
the same pointing? Framed explicitly: a rough consistency check would beat
field-wide suppression, since MIRI pointings are targeted (not random sky),
so field stars serendipitously sharing a frame with a cluster/nebula are
exactly the uncontaminated population most useful for this project's
null-result baseline -- and if nothing cheap exists, that should be logged
as a blind spot affecting null-result completeness, not just candidate
detection.

**Checked both categories against real data, not assumed:**

- **Planetary nebulae: yes, a cheap signal exists and was verified.**
  photosphere.py already computes `photosphere_teff` per star -- genuine PN
  nuclei are exposed post-AGB cores, typically tens of thousands of K, far
  hotter than even `photosphere.grids.hot_teff_min_k` (8000 K, the existing
  Kurucz-only bucket boundary). Checked the real PN-TC-1 data directly: of
  the 13 Gaia-matched stars sharing that field's blanket "Planetary nebulae
  nuclei" tag, 12 have a finite fitted Teff, and **all 12 fit at 4500-9000
  K** -- nowhere near a real nucleus's expected temperature. This is strong,
  concrete evidence that these are ordinary field stars caught in the same
  frame, not the actual nucleus (which -- also worth noting -- may not even
  be Gaia-matched at all, if it's too hot/blue or extinguished for Gaia's
  optical bandpass; this doesn't identify the true nucleus, only exonerates
  stars that clearly aren't it).
- **Young star clusters: no cheap fix found -- checked, not assumed, and
  logged as an explicit blind spot instead of silently accepted.** Gaia
  parallax/proper-motion consistency against the field's own population is
  the theoretically right approach (real astronomical cluster-membership
  work is built on exactly this), and it shows genuine signal in this
  project's own data -- e.g. one NGC-602 star is simultaneously an outlier
  in both parallax (2.05 mas vs. a field mostly under 0.7 mas) and proper
  motion (pmra=7.24 mas/yr vs. a field clustered ~0.4-1.8 mas/yr), an
  unambiguous foreground interloper. But a naive "sigma-clip around the
  field's own median" is not safe to ship, for two reasons confirmed
  against the real capped-subsample data (not assumed): (1) NGC-602 sits at
  the SMC's ~62 kpc distance, where genuine members' expected parallax
  (~0.016 mas) is far below Gaia's precision floor for these faint sources
  (measured parallax_error values in this subsample: ~0.05-0.99 mas) --
  parallax has ~no discriminating power for real members there, only proper
  motion does, and only if the field's own PM consensus is trustworthy; (2)
  CONTROLFIELD's own 20-star Gaia-matched subsample shows no single
  dominant clump in either parallax or proper motion at all (pmra spans
  -21.11 to -0.67 mas/yr with no obvious majority) -- there may not even be
  a reliable "field consensus" to check against from this sample alone,
  without a larger sample or literature-sourced bulk cluster proper motions
  to corroborate against. This is squarely the kind of literature/catalog-
  informed membership analysis `pipeline/contaminants.py`'s real design
  should do (e.g. cross-matching against published cluster membership
  catalogs or bulk kinematics), not a same-session addition attempted
  without that grounding.

**Implemented:** `is_stopgap_evolved_star` (`pipeline/excess.py`) now takes
`photosphere_teff` as an argument and exonerates a star from the flag if it
has a real, finite fitted Teff below `hot_teff_min_k` -- reusing an
already-existing config value, not inventing a new threshold. A star with
NO fit (no Gaia match, or a skipped fit) is NOT exonerated -- deliberately
conservative, since a genuinely hot, compact nucleus could plausibly be too
optically faint/blue for Gaia to have matched at all, so absence of a fit
must not be read as absence of a nucleus. `is_stopgap_young_cluster` was
deliberately left unrefined.

**One further caveat surfaced while implementing this, not addressed here
(out of scope for what was asked):** correctly exonerating a cool-Teff star
from "is this the hot nucleus itself" says nothing about whether that star
sits inside or near the nebula's own resolved, diffuse dust/gas emission,
which could bias `miri_photometry.py`'s small local-background annulus
(8-14 px) -- a different contamination mechanism that neither
`qc_crowded_source` (point-source-distance based) nor `qc_saturated` (a
NaN-pixel proxy) is designed to catch. Not investigated further; flagged
honestly rather than silently assumed away.

**Re-verified against the same real PN-TC-1/CONTROLFIELD/NGC-602 data**
(re-ran only `excess.run()` -- photosphere.py/miri_photometry.py outputs
were unchanged and reused):

| Field | `qc_stopgap_evolved_star` before -> after | `qc_star_disqualified` before -> after | `qc_excess_significant_F770W` before -> after |
|---|---|---|---|
| PN-TC-1 (40 stars) | 40/40 -> 29/40 | 40/40 -> 32/40 | 0/40 -> 2/40 |
| CONTROLFIELD (20 stars) | 0/20 -> 0/20 (never applicable) | 20/20 -> 20/20 | 0/20 -> 0/20 |
| NGC-602 (20 stars) | 0/20 -> 0/20 (never applicable) | 20/20 -> 20/20 | 0/20 -> 0/20 |

Exactly as predicted: the two PN-TC-1 stars with real, cool Teff fits
(4513 K and 4927 K -- the same two originally found in the very first
survivor-count check) are correctly exonerated and resurface as
`qc_excess_significant_F770W`. **They do NOT resurface as
`qc_candidate_preliminary`**, because both are
`qc_single_filter_detection==True` (no F1000W mosaic coverage) --
`qc_candidate_preliminary` requires the dual-band criterion regardless, and
the single-band tier (`qc_single_band_candidate`) remains uncomputed
(`single_band_significance_threshold_sigma` still null). PN-TC-1's
`qc_star_disqualified` count (32/40) returns to exactly its pre-stopgap
baseline (driven by `qc_poor_photosphere_fit` for the <2-band/non-Gaia-
matched majority of the field) -- confirming the blanket evolved-star flag
was adding no real information for this field beyond what was already
correctly gated. CONTROLFIELD/NGC-602 are entirely unaffected (as
expected: neither field was ever "Planetary nebulae nuclei" classified),
and remain fully suppressed via the still-unrefined `qc_stopgap_young_cluster`.

**Status:** the researcher's question had a real, mixed answer -- a
legitimate cheap fix for the planetary-nebula case (implemented and
verified), and a genuine, checked-not-assumed blind spot for the
young-cluster case (logged, not fixed). Per the researcher's framing, this
does not block moving forward; `pipeline/contaminants.py` is where the
young-cluster gap should be properly closed via real catalogue/kinematic
cross-matching.

### 2026-07-22 -- Directional check on the diffuse-nebular-background caveat: NOT one-directional like qc_extinction_uncertain

Following up on the diffuse-nebular-emission-in-the-local-background-annulus
caveat raised (unprompted) in the entry above, the researcher asked for the
same kind of directional check that resolved `qc_extinction_uncertain`
(confirmed then: falling back to Av=0 biases toward suppressing apparent
excess, never manufacturing it -- safe to leave caveat-only). Checked the
actual mechanism in `miri_photometry.py:extract_flux_for_filter`
(`photutils.background.LocalBackground` with `MMMBackground` -- the
standard mode-based estimator, mode ~= 3*median - 2*mean -- computes a
background level from an annulus (`skyin_px`/`skyout_px`, from the same
APCORR table row used for the EE correction) around each source and
subtracts it during both the PSF fit and the aperture cross-check).

**Conclusion: unlike extinction, this does NOT have a single safe
direction, and that is the honest answer, not a hedge.** Extinction has a
clean, monotonic physical argument (dust only ever dims, never brightens),
so Av=0 always underestimates dimming -- one direction, always. Diffuse
nebular contamination depends on local nebular structure relative to where
the annulus happens to sample, which has no such guarantee:

- Annulus samples smoother/brighter nebular emission than what's directly
  under the star -> background over-estimated -> over-subtraction ->
  `observed_flux` biased LOW -> suppresses excess (same safe direction as
  extinction).
- Star sits on a brighter clump/filament of the nebula while the
  surrounding annulus samples relatively fainter structure (plausible --
  real planetary nebulae are clumpy/filamentary, not smooth) -> background
  under-estimated -> under-subtraction -> `observed_flux` biased HIGH ->
  could manufacture spurious excess (the dangerous direction).

**Confidence:** low that a universally safe direction exists here (moderate-
to-high confidence the mechanism itself is real and non-negligible near
resolved nebular structure, but the sign is genuinely position/geometry-
dependent, not derivable from a general physical argument the way
extinction's is). **Classification: a "could be quietly inflating
candidates near nebulae" gap, not a "safe to defer" gap** -- meaningfully
different from qc_extinction_uncertain's status, and this distinction
should not get flattened into "same kind of caveat" in any future summary
or writeup. Directly relevant to how much to trust the two PN-TC-1
excess_sigma_F770W values (7.77, 4.04) specifically -- not verified here,
but the concrete, cheap next step (not done in this pass) would be
inspecting the actual pixel cutouts around those two stars' annuli, the
same kind of check that resolved the NGC-602 bright-source question
earlier in this project (2026-07-21 entry). Not investigated further this
session -- logged as an open verification item, not fixed or dismissed.

### 2026-07-22 -- contaminants.py design discussion: recon, two research questions resolved, priority ordering

Before any `pipeline/contaminants.py` implementation (per project convention
and the module's own docstring), walked through the design for all six
planned categories plus the young-cluster/PMS gap identified during the
excess.py work. Full discussion in conversation; key findings and decisions
below, two of which required live verification rather than assumption.

**Recon: two categories turned out to need no new archive query at all,**
because retriever.py/photosphere.py already fetch the relevant data and
just don't use it yet:
- `qc_background_galaxy`: `a0` already carries `is_extended_{band}`,
  `sharpness_{band}`, `roundness_{band}`, `ellipticity_{band}`,
  `semimajor_sigma_{band}`/`semiminor_sigma_{band}` (the pipeline's own
  `source_catalog` morphology diagnostics) -- `is_extended` is already
  doing real work elsewhere (it independently corroborated the
  `qc_psf_fit_failed` case for PN-TC-1's real extended source, 2026-07-21).
- `qc_evolved_star`: `a0` has Gaia parallax (-> distance -> absolute
  magnitude) and `a1` has `photosphere_teff` -- an HR-diagram
  luminosity-vs-Teff overluminosity check needs no new catalog. This would
  properly supersede the `is_stopgap_evolved_star` Teff-only proxy added to
  `excess.py` earlier today. Caveat carried over: `photosphere.py`'s fixed
  `log_g=4.5` means the Teff feeding this check is measured under
  main-sequence physics even for real giants -- a known, already-logged
  simplification, not a new problem, but directly relevant to this specific
  check's inputs.

**Question 1 (researcher's decision: check whether Gaia's NSS solution
tables or a WDS cross-match catch real cases RUWE/non_single_star miss;
build a supersession if genuine value, a light passthrough if thin) --
RESOLVED, checked live, not assumed:**

Queried `gaiadr3.nss_two_body_orbit` (confirmed live, queryable via the same
Gaia TAP service retriever.py already uses, keyed by `source_id`) against
500 real confirmed-orbit binaries, joined to `gaia_source.non_single_star`/
`ruwe`:
- **0/500** had `non_single_star==0` -- every confirmed NSS orbit is already
  covered by the existing flag. No missed detections.
- **249/500 (49.8%)** had `ruwe<=1.4` despite a confirmed orbit -- RUWE
  alone would miss about half of these; `non_single_star` is doing real,
  necessary work in the existing OR-based `qc_possible_binary` logic
  (confirms the current design choice, not just an assumption).
- **0/500** had BOTH `non_single_star==0` AND `ruwe<=1.4` -- i.e. the
  existing `qc_possible_binary` (RUWE>1.4 OR non_single_star!=0) misses
  NOTHING that a confirmed NSS orbit would have caught.
- `g_luminosity_ratio` (companion brightness ratio -- directly relevant to
  "could this companion plausibly contribute mid-IR flux") is populated for
  108/500 (21.6%) of confirmed-orbit sources, with real, sensible values
  (0.03-0.67 in the sample pulled) -- genuine data, but narrow coverage
  (roughly a fifth of an already-smaller subset of all `qc_possible_binary`
  hits, since most flagged stars never get a full two-body orbit solution
  at all).
- WDS (Washington Double Star Catalog, resolved visual binaries) confirmed
  queryable live via VizieR (`B/wds`, same service as the 2MASS
  cross-match) -- but a resolved, nearby companion contributing blended
  MIRI flux is exactly what `qc_crowded_source` (miri_photometry.py) already
  checks directly from real MIRI-frame pixel separations, which is more
  direct evidence than an external visual-double-star catalog lookup for
  this specific concern. Not pursued further given that overlap.

**Decision: light passthrough/rename, not new detection logic.** The NSS
tables add zero new detections (0/500) -- the marginal value found
(luminosity-ratio refinement for ~22% of an already-narrow subset) is thin
per the researcher's own stated bar, not "genuine marginal value."
`qc_binary_companion_contamination` in `contaminants.py` should consume/
rename the existing `qc_possible_binary` rather than reimplementing
detection logic. (Possible, narrower future enhancement, not pursued now:
using `g_luminosity_ratio` where populated to distinguish "companion bright
enough to matter" from "companion too faint to matter" within the
already-flagged population -- a refinement of severity, not detection.)

**Question 2 (researcher's decision: check Kennedy & Wyatt 2013 directly,
not just its existing citation-table annotation) -- RESOLVED, confirmed via
the paper's own abstract, not a secondary source:**

Fetched the arXiv abstract (arXiv:1305.6607) directly. **Confirmed: NOT
usable as a `qc_debris_disk_candidate` cross-match catalog**, exactly as
suspected from the citation table's own "statistics"/"rate" phrasing. The
paper's own words: "the first characterisation of the 12um warm dust
('exo-Zodi') **luminosity function**... focussing on the dustiest systems
that can be identified by WISE" -- a population-demographics/luminosity-
function study (occurrence rates: ~1% for young <120 Myr systems, ~1-in-
10,000 for old >1 Gyr systems like the one named example, BD+20 307),
reporting "six new warm dust candidates" but as a narrow, curated
extreme-tail sample used to constrain a luminosity function, not a
systematic, broad catalog intended for cross-matching arbitrary stars.
Only two specific stars are named in the abstract (BD+20 307, HD15407).
**Consequence:** `qc_debris_disk_candidate` needs a different source before
implementation -- a VizieR debris-disk compilation catalog or a SIMBAD
object-type query (e.g. debris-disk/IR-excess-typed objects) -- neither
identified or verified yet. This remains genuinely open, not resolved by
this check (the check only ruled OUT the existing citation, it did not
find a replacement).

**Decision 3 confirmed (diffuse-nebular-background is a `miri_photometry.py`
follow-up, not a contaminants.py category)**: logged as its own item in the
Open Methodological Questions section above, cross-referenced from both
this entry and the 2026-07-22 "Directional check" entry, so it does not
fall through the gap between modules as the researcher asked.

**Decision 2 (population scope) confirmed, not re-litigated here**: the
cheap checks (`qc_background_galaxy`, `qc_evolved_star`, `qc_known_variable`)
run over the full `b1` population; expensive steps (debris-disk cross-match,
cluster-membership catalogs, DQ-array position-remapping) are reserved for
the excess-showing shortlist only.

**Priority/feasibility ordering across all six categories plus the
young-cluster/PMS gap, requested explicitly to sequence deliberately
against remaining summer time rather than build in arbitrary order:**

- **Tier 1 -- cheap, and already shown to matter against real archive data
  this session:**
  - `qc_evolved_star` (HR-diagram luminosity-vs-Teff): directly validated by
    the PN-TC-1 finding earlier today (all 12 real Teff-fit stars sharing
    that field's blanket PN-nucleus tag came back at 4500-9000 K -- exactly
    the overluminosity-for-Teff check this category needs, already proven
    relevant on real data, not hypothetical).
  - `qc_background_galaxy` (existing `is_extended`/morphology columns):
    `is_extended` already independently corroborated a real `qc_psf_fit_failed`
    case in this project's own verified data (2026-07-21).
- **Tier 2 -- cheap, verified accessible, but not yet run against real
  numbers:**
  - `qc_known_variable` (`gaiadr3.vari_summary`/`vari_classifier_result`):
    confirmed live and queryable this session, same archive/join key
    already in use, but not yet checked against any of this project's real
    matched stars to see what actually gets flagged.
  - `qc_binary_companion_contamination`: effectively free -- a rename/
    passthrough of the already-implemented, already-validated
    `qc_possible_binary`, per Question 1 above. Listed here rather than
    Tier 1 only because it's consolidation, not a new check.
- **Tier 3 -- genuinely expensive or currently blocked:**
  - `qc_photometric_artifact`: Level 2 `_cal.fits` products WITH real DQ
    arrays confirmed to exist for this project's own test proposals
    (verified live, e.g. proposal 4706), but require real per-source
    position-to-multiple-exposure WCS remapping (a Level 3 mosaic combines
    several Level 2 exposures) -- the same class of bug this project has
    been burned by twice already (retriever.py row-misalignment,
    miri_photometry.py's `_cat.ecsv` `label` gotcha). Blocked on careful
    design, not on data availability.
  - `qc_debris_disk_candidate`: blocked pending an actual usable catalog --
    Kennedy & Wyatt (2013) ruled out this session (Question 2 above); a
    VizieR compilation or SIMBAD object-type query needs identifying and
    live-verifying before this can even be designed, let alone built.
  - Young-cluster/PMS association (still no category in
    `contaminants.categories` at all): the most structurally complex of the
    seven -- needs TWO different catalog sources depending on whether the
    field is a Milky Way open cluster (well-served by Gaia-based catalogs
    like Cantat-Gaudin) or an extragalactic system like NGC-602/the SMC
    (a different, far less standardized catalog situation, and exactly why
    the parallax-based stopgap-refinement attempt failed for that field
    earlier today).

**Status:** no implementation yet, per the researcher's explicit
instruction -- this entry resolves the two research questions and the
priority ordering the researcher asked for; what to build first is the
next decision.

### 2026-07-22 -- pipeline/contaminants.py implemented (Tier 1: qc_evolved_star, qc_background_galaxy); parallax-quality bug caught and fixed before reporting real numbers

Implemented the two Tier-1 categories from the priority ordering above,
built together per the researcher's instruction (independent checks, but
share the same b1-population join/integration work, and testing them
jointly gives a coherent first look at how much they actually reshape the
"clean" sample -- more useful than either flag in isolation).

**`qc_evolved_star`** (`pipeline.contaminants.is_evolved_star_overluminous`):
standard HR-diagram giant/dwarf discriminator -- a star is flagged if its
Gaia-parallax-based absolute G magnitude is brighter than the expected
main-sequence value at its own fitted `photosphere_teff` by more than
`contaminants.evolved_star.overluminosity_mag_threshold` (2.5 mag, ~10x
luminosity, a stated compromise). The expected-magnitude relation
(`_MS_ANCHOR_TEFF`/`_MS_ANCHOR_ABS_G`) reuses the same Teff anchor points as
photosphere.py's own `_TEFF_ANCHOR_TEFF` for consistency, with rough
Pecaut & Mamajek-like M_G values -- recalled approximately, not
independently re-verified, same status as that table. No new archive
query needed (Gaia parallax/phot_g_mean_mag from a0, photosphere_teff
already carried through b1).

**`qc_background_galaxy`** (`pipeline.contaminants.compute_background_galaxy_flag`):
reuses a0's `is_extended_{band}` (the pipeline's own automated
`source_catalog` morphology classification, already fetched by
retriever.py, previously unused) -- True in any measured band. No new
archive query needed either.

Both run over the full `b1` population (researcher's decision, 2026-07-22),
not just the excess-showing shortlist.

**Bug caught mid-implementation, before trusting any real number (same
discipline as every other real-data check in this project):** the first
real run against PN-TC-1 flagged 6/40 stars as `qc_evolved_star` --
surprisingly high. Inspecting the actual numbers (not just accepting the
count) found several of the 6 had fractional parallax errors up to 165%
(e.g. parallax=0.062+-0.103 mas) -- essentially noise, not a real distance.
Inverting a low-signal-to-noise parallax to compute a distance/absolute
magnitude is a well-known statistical bias (it systematically manufactures
apparent overluminosity/distance for intrinsically ordinary stars, since
noise scatters low-parallax measurements preferentially toward smaller
values). **Fixed before reporting**: `is_evolved_star_overluminous` now
gates on `parallax_mas/parallax_error_mas >=
contaminants.evolved_star.min_parallax_over_error` (5.0, i.e. fractional
error <=20% -- a standard convention in Gaia-based work, same status as
photosphere.py's RUWE>1.4 threshold) before trusting any derived magnitude
at all. A low-S/N parallax is now treated as unusable, same as a missing
one. Re-ran after the fix: PN-TC-1's count dropped from 6/40 to 1/40 --
the one survivor (Teff=8968 K, parallax S/N=7.8, G=11.27) has a clean,
trustworthy parallax and a real overluminosity signal, unlike the 5 that
were dropped.

**General principle worth restating for future checks (researcher's
request), not specific to parallax:** any time a derived quantity is
computed by INVERTING a directly-measured quantity that carries real
measurement error (parallax -> distance is the case here, but the same
shape of problem applies to e.g. flux -> magnitude for very faint/noisy
detections, or any 1/x-type transform), the derived quantity needs an
explicit signal-to-noise gate on the measured input BEFORE being trusted --
not just a finite/non-null check. A finite-but-noisy input is not the same
as a reliable one, and naively propagating it can systematically bias the
derived quantity in one direction (here: toward spurious overluminosity),
not just add symmetric scatter. Watch for this pattern specifically
wherever a future check reaches for `1/x`, `log(x)`, or any other
non-linear transform of a Gaia/photometric quantity that has its own
`_error` column sitting right next to it in the same table.

**Real numbers, all three fields, after the fix** (PN-TC-1 in full, 40
rows; CONTROLFIELD/NGC-602 the same labeled 20-star Gaia-matched
subsamples used throughout this project -- see the positive-control
caveat earlier in this log for why these three fields are not a random
sky sample):

| Field (n) | `qc_evolved_star` | `qc_background_galaxy` | either flag | previously `qc_excess_clean_{band}`, now newly disqualified |
|---|---|---|---|---|
| PN-TC-1 (40) | 1/40 | 19/40 | 19/40 | 0 (F770W: 0 of 7 previously-clean; F1000W: 0 of 1) |
| CONTROLFIELD (20) | 0/20 | 0/20 | 0/20 | 0 (both bands: 0 of 0 previously-clean) |
| NGC-602 (20) | 0/20 | 0/20 | 0/20 | 0 (both bands: 0 of 0 previously-clean) |

**Interpretation, not just the count:** `qc_background_galaxy` fires
broadly in PN-TC-1 (19/40, a real, physically sensible finding -- PN-TC-1
is a genuine planetary nebula field, so extended/non-point morphology
among the many non-Gaia-matched MIRI-only detections near it is expected,
not a bug; confirmed `is_extended` really is 0 across the board for
CONTROLFIELD/NGC-602's quieter/less-nebular Gaia-matched populations,
ruling out a silent no-op). But checking WHICH stars: every one of the 19
already carried `qc_poor_photosphere_fit` (mostly non-Gaia-matched
detections, trivially <2 fit bands) and the pre-existing
`qc_stopgap_evolved_star` from excess.py -- so this flag, in this specific
test data, is fully redundant with gates that already existed BEFORE
contaminants.py, adding zero NEW disqualifications. **The headline number
the researcher asked for: across all three fields tested, zero stars that
were previously `qc_excess_clean_{band}` get newly disqualified by either
Tier-1 flag.** For this specific (small, non-representative-by-design,
positive-control) test data, Tier 1 doesn't change the "clean" sample's
composition at all -- it's confirmatory, not yet incremental, here. That
is itself informative for the null-result question the researcher framed
this around: it's evidence these two checks aren't (in this sample)
quietly re-admitting anything that was wrongly excluded, nor are they
catching something that had slipped through -- but a 40+20+20-star,
positive-control-selected sample is too small and non-representative to
conclude these flags are low-yield in general; that can only be assessed
at archive scale.

**Note, not yet acted on:** `qc_evolved_star` (contaminants.py's proper
implementation) and excess.py's `is_stopgap_evolved_star` (the Teff-only
proxy) now both exist and both fired for the same star (index 34,
PN-TC-1). Whether to retire/relax the stopgap now that a proper version
exists is an open follow-up decision, not made here.

**Verification:** 85 tests pass total (20 new in `tests/test_contaminants.py`,
including a dedicated regression test for the parallax-S/N gate pinned to
the real PN-TC-1 failure mode found above).

**Status:** Tier 1 complete and verified against real data. Tier 2
(`qc_known_variable`, `qc_binary_companion_contamination` passthrough) and
Tier 3 (`qc_photometric_artifact`, `qc_debris_disk_candidate`,
young-cluster/PMS) remain queued in the priority order agreed above.

### 2026-07-22 -- excess.py's is_stopgap_evolved_star retired, superseded by contaminants.py's qc_evolved_star

The stopgap was explicitly framed as temporary when added earlier the same
day (ahead of pipeline/contaminants.py existing "for real") -- once
contaminants.py's `qc_evolved_star` existed and was verified, the
researcher called for retiring it rather than keeping both (avoiding the
same redundant/ambiguous-flag risk already avoided by making
`qc_binary_companion_contamination` a passthrough of `qc_possible_binary`
instead of a second parallel binary flag).

**Before making the change**, checked the researcher's own stated
assumption ("should be unchanged, since both fired on the same star")
against the real PN-TC-1 data rather than taking it on faith: confirmed
star index 34 (Teff=8968 K) is the only star either mechanism ever
actually flagged, and it has a trustworthy parallax (S/N=7.8) under
`qc_evolved_star`'s own gate -- the assumption held. (Briefly worth noting:
the two ORIGINAL "significant, cool-Teff, single-band" excess candidates
found earlier this session, Teff 4513 K/4927 K, were NOT part of this
comparison -- both had already been exonerated by the stopgap's own
Teff-based refinement hours earlier, unrelated to today's retirement.)

**Removed:** `is_stopgap_evolved_star` (function, docstring, and its
`config["excess"]["stopgap_contaminant_tokens"]["evolved_star"]` token
list) from `pipeline/excess.py` entirely -- not just removed from
`DISQUALIFYING_STAR_FLAGS`, since a computed-but-unused column would be
exactly the ambiguous/redundant situation being avoided. `is_stopgap_young_cluster`
is untouched (still the only mechanism for that gap; contaminants.py has
no young-cluster category yet). Updated: module docstring (both in
`pipeline/excess.py` and `config/pipeline_config.yaml`'s
`stopgap_contaminant_tokens` comment) to note the retirement and point at
`qc_evolved_star` as the superseding check;
`config/quality_config.yaml`'s `qc_stopgap_evolved_star` entry replaced
with a `status: RETIRED` notice (kept, not deleted, so the file's own
history stays legible) rather than removed outright.

**Re-verified against real data after the swap** (re-ran
`excess.run()` + `contaminants.run()` for all three fields):
- `qc_stopgap_evolved_star` no longer appears in `b1` output at all.
- Star 34's overall disqualification in `b1` is unchanged
  (`qc_star_disqualified=1`), now attributed to `qc_poor_photosphere_fit`/
  `qc_psf_fit_failed_F1000W` alone (the stopgap's own contribution was
  redundant with these, confirming its removal changes nothing for this
  star) -- and it is still caught at the `b2` level via `qc_evolved_star`/
  `qc_contaminant_flagged_partial`.
- `qc_excess_clean_{band}` counts in `b1` for PN-TC-1 are byte-for-byte
  unchanged from before the swap (F770W: 7/40, F1000W: 1/40) -- confirming
  the retirement changed nothing observable in this test data, exactly as
  predicted.
- `qc_evolved_star`/`qc_background_galaxy` counts in `b2` are also
  unchanged (1/40, 19/40) -- expected, since they never depended on the
  retired stopgap.

**General principle logged** (researcher's request, not specific to this
one bug): see the addendum added to the parallax-S/N-gate entry above --
any derived quantity computed by inverting a directly-measured quantity
with real error needs an explicit S/N gate on the input, not just a
finite/non-null check, before being trusted.

**Verification:** 83 tests pass (3 obsolete `is_stopgap_evolved_star`
tests removed, 1 renamed, 1 new regression test added confirming the
retired flag no longer appears in `b1` output).

**Status:** Tier 1 fully settled (implemented, bug-fixed, and now the
excess.py/contaminants.py overlap resolved). Moving to Tier 2.

### 2026-07-22 -- Tier 2 implemented: qc_known_variable, qc_binary_companion_contamination

Implemented the two Tier-2 categories from the priority ordering.

**`qc_known_variable`** (`pipeline.contaminants.query_gaia_variability` +
`compute_known_variable_flag`): cross-matches against `gaiadr3.vari_summary`
(Gaia DR3's own variability-pipeline output, confirmed live/queryable
earlier today) via a single bulk `source_id IN (...)` query -- existence in
that table (any `in_vari_*` category) is sufficient to flag. **The first
live-network call in `pipeline/contaminants.py`** -- deliberately split
into a live-query function and a separate pure/testable per-star flag
function, so `assemble_level_b2`'s unit tests stay network-free (same
convention as this project's other live-service dependencies -- smoke-
tested, not mocked). Not scaled beyond a modest source list (a single IN
clause, not a bulk table upload) -- stated as a known limitation for
archive scale, not silently assumed to generalize.

**`qc_binary_companion_contamination`** (`pipeline.contaminants.compute_binary_companion_contamination_flag`):
a deliberate passthrough of the already-implemented `qc_possible_binary`
(photosphere.py, carried through `b1`) -- NOT new detection logic, per the
resolution of Question 1 in the design-discussion entry above (Gaia's NSS
orbit tables caught 0/500 cases RUWE/non_single_star already miss).

Both run over the full `b1` population, same as Tier 1.

**Real numbers, all three fields** (same fields/subsamples as every other
check in this log):

| Field (n) | `qc_known_variable` | `qc_binary_companion_contamination` | either, newly disqualified from previously-clean |
|---|---|---|---|
| PN-TC-1 (40) | 1/40 | 0/40 | 0 |
| CONTROLFIELD (20) | 0/20 | 0/20 | 0 |
| NGC-602 (20) | 0/20 | 0/20 | 0 |

**The one `qc_known_variable` hit (PN-TC-1, gaia_source_id 5954912374289120896)
is the SAME star as Tier 1's one `qc_evolved_star` hit (index 34, Teff=8968 K).**
A star that is simultaneously overluminous for its Teff AND independently
flagged by Gaia's own variability pipeline is a coherent, physically
plausible combination (not two unrelated coincidental hits) -- lends
further, independent credibility to that star being something genuinely
unusual, on top of the parallax-S/N-gated overluminosity signal alone. This
star was already disqualified in `b1` before any contaminants.py category
existed (`qc_poor_photosphere_fit`, `qc_psf_fit_failed_F1000W`), so --
consistent with the Tier 1 finding -- **zero new disqualifications from
either Tier-2 flag in any field tested.** Same interpretation caveat as
Tier 1 applies: confirmatory, not incremental, in this specific small,
positive-control-selected sample; not evidence these flags are low-yield
at archive scale.

**Verification:** 88 tests pass (14 new: `compute_known_variable_flag`,
`compute_binary_companion_contamination_flag`, and updated assembly tests
covering all four Tier 1+2 flags together). `query_gaia_variability`
itself is exercised only via the live real-data run above, not unit-tested
(same convention as retriever.py's/photosphere.py's other live-service
calls).

**Status:** Tiers 1 and 2 complete (4 of 6 contaminant categories
implemented and verified against real data). Tier 3
(`qc_photometric_artifact`, `qc_debris_disk_candidate`, young-cluster/PMS)
remains queued, each blocked on a real, identified prerequisite (see the
priority-ordering entry above) rather than simply not-yet-started.

### 2026-07-22 -- Tier 3 sequencing decided: effort estimates, one prior corrected with data, two items explicitly deferred

Before touching any Tier 3 code, gave the researcher effort/complexity
estimates for all three remaining items, checked the researcher's own
stated prior against real data rather than accepting it at face value, and
verified one live fact that changed the cost picture. Full estimates below;
this entry also records the two items now explicitly deferred, with the
specific numbers behind that decision (so "deferred" reads as a scoped,
quantified limitation for the eventual paper, not a vague gap).

**Effort estimates given:**
- `qc_photometric_artifact`: medium-high (2-4 days). Level 2 `_cal.fits`
  products with real DQ arrays confirmed to exist for this project's test
  proposals; the L3 product's own ASN file lists which L2 exposures
  contributed (not a blind search), but still requires per-exposure WCS
  remapping, DQ bit interpretation (the `jwst`/`crds` packages are not
  installed in this environment, confirmed earlier -- bit values would need
  hardcoding from public docs and live verification, not just trusting
  memory), and combination logic across possibly-multiple contributing
  exposures -- the same *class* of problem (position/index mapping across
  files) that produced two real bugs earlier in this project (retriever.py
  row-misalignment; miri_photometry.py's `_cat.ecsv` `label` gotcha), so
  real testing time was budgeted on top of the core implementation, not
  just the happy-path estimate. Correction to the researcher's framing: not
  *only* a refinement of `qc_saturated` -- persistence/cosmic-ray-jump DQ
  flags leave no NaNs at all, so they are currently invisible to any
  existing check, a genuinely new detection capability, not just a more
  precise version of an existing one. Cost/value ratio still judged worst
  of the three.
- `qc_debris_disk_candidate`: uncertain, split into two very different
  pieces. Integration (once a catalog exists) is cheap -- the same position
  cross-match pattern already built three times in this codebase (Gaia,
  2MASS, and conceptually this). Catalog discovery is the real cost driver
  and was checked live before estimating (not assumed): SIMBAD's own
  `otypedef` table has ZERO object types with "disk" in the description --
  queried directly, ruling out the cleanest candidate path. The remaining
  path (a VizieR-hosted survey compilation, e.g. something in the spirit of
  the Herschel DEBRIS survey found in the earlier literature search --
  targeted, volume-limited, named-star surveys, unlike Kennedy & Wyatt's
  demographic framing) is plausible but unverified. Estimated 1-2 days if a
  good catalog turns up quickly, more if several false starts occur (the
  same shape of risk that burned the original Kennedy & Wyatt citation).
- Young-cluster/PMS: **researcher's stated prior ("hasn't produced an
  actual false positive... that wasn't already caught by qc_evolved_star or
  the field-level stopgap") checked against real data and found to
  understate the scale, not wrong on the narrow technical claim.** Checked
  directly whether `qc_evolved_star` (the proper HR-diagram check) would
  catch any of the young-cluster candidates independent of the blanket
  stopgap: **it catches zero of them** -- not even the 168.6-sigma
  CONTROLFIELD case -- which makes physical sense (circumstellar disk
  emission adds flux on top of an otherwise-normal photosphere; it doesn't
  make the star itself overluminous the way a real evolved giant is, a
  different physical mechanism entirely). Counting the full real data (not
  just the originally-reported "5 survivors"): **24 stars across
  CONTROLFIELD (15) and NGC-602 (9) show real, statistically significant
  excess signal (sigma_F770W >= 3, several in the hundreds) that depends
  entirely on the blunt, field-wide `qc_stopgap_young_cluster` flag** --
  nothing else in the pipeline touches them. This is the dominant
  contamination category in 2 of the 3 test fields, not a marginal edge
  case, even though (consistent with the researcher's narrow claim) no NEW
  slip-through false positive has been observed.
  **Cost-relevant fact checked live, not assumed**: CONTROLFIELD's own
  Gaia parallax distribution (0.06-1.4 mas, implying distances of
  714-8788 pc) confirms it is a genuine MILKY WAY system, unlike NGC-602's
  confirmed SMC distance (~62 kpc, parallax ~0.016 mas, below Gaia's
  precision floor). This means a Milky Way open-cluster membership catalog
  (Cantat-Gaudin-style, Gaia-based, plausibly VizieR-hosted -- moderate-
  high confidence such a catalog exists and is queryable, similar
  confidence level to how the NSS/WDS/vari_summary tables turned out to be
  earlier today, but not yet verified) would properly resolve **15 of the
  24 stars** (CONTROLFIELD's), leaving only NGC-602's **9 SMC-related
  stars** as a genuinely open problem -- no confident catalog candidate
  identified for SMC/LMC-specific cluster membership, and this may not have
  a bounded solution within this project's summer scope at all.
  **CORRECTION (see the dedicated 2026-07-22 implementation entry below,
  "Milky Way young-cluster/PMS fix implemented"): once actually built and
  checked against real data, this fix resolved only 2 of the 24 stars, not
  15 -- the "15" estimate did not account for the fact that the specific
  15 CONTROLFIELD stars showing real signal are disproportionately faint,
  cool stars with parallax measurements too noisy to clear this project's
  own S/N-gate convention. Do not cite the 15/24 figure without reading
  that later entry.**

**Decision (researcher's call, 2026-07-22): sequence Tier 3 deliberately,
not in the order originally written.**
1. `qc_debris_disk_candidate` first -- highest scientific priority (the
   literature's primary confounder for genuine mid-IR excess), time-boxed
   given the catalog-discovery risk just confirmed (see the next entry for
   the actual time-box and outcome).
2. Young-cluster/PMS, **Milky Way half only** -- cheap (1-2 days), fixes
   15 of the 24 real cases found above. A genuinely different, harder
   problem (the SMC/extragalactic half) is being split off, not folded into
   the same estimate.
3. **Explicitly deferred, logged here as scoped future work, not a vague
   gap**:
   - `qc_photometric_artifact` (DQ remapping) -- highest engineering cost,
     real precedent-bug risk (see estimate above), narrowest genuinely-new
     coverage of the three items considered.
   - Young-cluster/PMS **extragalactic half** -- affects a confirmed,
     quantified **9 stars** in NGC-602 (of this project's real test data)
     that will remain solely dependent on the blunt `qc_stopgap_young_cluster`
     flag. No SMC/LMC-specific membership catalog has been identified;
     revisit only if a specific, verifiable source is found later, not by
     attempting a naive parallax/PM-based fix (already checked and found
     unsafe for exactly this population, see the 2026-07-22 entry earlier
     in this log on why NGC-602's parallax lacks discriminating power at
     that distance).

**Status:** no Tier 3 code written yet. Starting on `qc_debris_disk_candidate`
next, time-boxed per the researcher's explicit instruction -- see the
following entry for the outcome.

### 2026-07-22 -- Debris disk catalog search: time-boxed, real catalog found within budget

Per the researcher's explicit instruction: time-boxed the catalog search to
a fixed budget of 5 candidate sources before falling back to the Milky Way
young-cluster fix (or deferring debris disk too). **Outcome: found within
budget (2 of 5 candidates checked, both usable) -- did not need to fall
back.**

**Candidate 1/5 -- SIMBAD object-type query**: already ruled out live in
the prior entry (zero `otypedef` entries mention "disk"). Counted against
the budget since it was checked as part of this same search, not free.

**Candidate 2/5 (of the live search) -- Da Costa et al. (2017), ApJ 837, 15,
"On the Incidence of WISE Infrared Excess Among Solar Analog, Twin, and
Sibling Stars"**: found via `Vizier.find_catalogs("infrared excess main
sequence")`, confirmed via VizieR schema (`J/ApJ/837/15/table1`) AND the
paper's own abstract (fetched live, not assumed): 216 named Sun-like stars
with per-star, per-WISE-band excess-significance columns (`chi12`, `chi22`
-- literally an excess-sigma analog to this project's own `excess_sigma_{band}`),
real positions, SIMBAD cross-reference names. Confirmed genuinely per-star
(unlike Kennedy & Wyatt), but narrow in scope (216 stars, solar-analogs
specifically).

**Candidate 3/5 -- Cotten & Song (2016), ApJS 225, 15, "A Comprehensive
Census of Nearby Infrared Excess Stars"**: found via a follow-up VizieR
search prompted by this title turning up in the same web search as Da
Costa. **This is the stronger candidate, recommended as primary.**
Confirmed live via VizieR (`J/ApJS/225/15`, 4 tables):
- `table3` ("Prime IR excess stars from the literature and Tycho-2
  cross-correlation with AllWISE"): **505 rows**, named stars (HR/HD/TYC
  identifiers), RA/Dec, spectral type, stellar Teff/radius, dust
  temperature/radius for one- and two-temperature-component disk fits,
  distance, SIMBAD cross-reference.
- `table4` ("Reserved IR excess stars..."): **1257 rows**, same schema, a
  lower-confidence second tier.
- `table5`: multi-wavelength photometry per star (WISE, IRAS, MIPS, PACS,
  SPIRE) for both tables' stars.
- **1762 total named, positioned, individually-classified IR-excess
  candidate stars** -- explicitly a census/compilation of specific objects
  from the literature, not a demographic/luminosity-function study (the
  exact failure mode that ruled out Kennedy & Wyatt). Real RA/Dec means
  this cross-matches via the SAME position-cross-match pattern already
  built three times in this codebase (Gaia, 2MASS, and now this), not a
  new integration mechanism.

**Decision: adopt Cotten & Song (2016) as the primary source for
`qc_debris_disk_candidate`** (position cross-match against `table3`+`table4`,
"Prime" vs. "Reserved" tier possibly worth carrying through as a
confidence-graded sub-flag rather than collapsing to one boolean -- not yet
designed, this entry records the catalog decision only). Da Costa et al.
(2017) kept as a noted secondary/cross-check option given its narrower,
more targeted (solar-analog) scope, not required for the primary
implementation.

**Not yet done**: no crossmatch code written, no live query against this
project's actual archive stars run yet, no design discussion for how
"Prime" vs. "Reserved" tiers map to a qc_* flag (e.g. one flag with two
confidence levels vs. two separate flags) -- reporting the catalog-search
outcome back to the researcher before proceeding, per their explicit
instruction to report back either way before continuing.

**Status:** catalog search resolved well within the 5-candidate budget (2
checks after the SIMBAD dead-end). No fallback to the Milky Way
young-cluster fix was needed. Awaiting researcher confirmation before
designing/implementing the actual cross-match.

### 2026-07-22 -- qc_debris_disk_prime/qc_debris_disk_reserved implemented; a real search_around_sky bug caught by its own unit test; real numbers reported

Implemented the cross-match against Cotten & Song (2016) (`pipeline.contaminants.fetch_debris_disk_catalog`
+ `crossmatch_debris_disk_catalog`), split into two separate flags per the
researcher's decision -- `qc_debris_disk_prime` (table3, 505 stars) and
`qc_debris_disk_reserved` (table4, 1257 stars), same pattern as
miri_photometry.py's `qc_psf_disagreement_faint`/`_complex` split. Both
disqualifying, both folded into `qc_contaminant_flagged_partial`. A third,
non-gating diagnostic (`qc_ambiguous_debris_disk_match`) follows
retriever.py's `qc_ambiguous_gaia_match`/`qc_ambiguous_2mass_match`
convention -- surfaces when more than one catalogue entry falls within the
crossmatch radius, rather than silently resolving to a "closest" match.
Crossmatch radius (`contaminants.debris_disk.crossmatch_radius_arcsec`,
2.0") is a stated compromise, more generous than this project's other
crossmatch radii (Gaia-MIRI 0.25", Gaia-2MASS 0.5") because Cotten & Song's
positions (Tycho-2 x AllWISE, epoch ~1991) have no per-star proper motion
to propagate forward to our stars' Gaia epoch (2016.0), unlike the
Gaia-2MASS crossmatch, which does propagate epochs.

**Real bug caught by its own unit test, before any real data was touched
(exactly the discipline this project has followed throughout, but this
time the test itself did the catching, not a manual real-data spot-check):**
the first implementation of `crossmatch_debris_disk_catalog` assumed
`SkyCoord.search_around_sky`'s documented return order (idx1 indexes
`self`, idx2 indexes the argument) without verifying it. `test_crossmatch_debris_disk_catalog_ambiguous_when_multiple_hits`
(1 star, 2 coincident catalog entries) failed immediately with a shape
mismatch. Checked directly in isolation rather than guessing further: **the
actual runtime behavior is the reverse of the documented-sounding order**
-- `star_coords.search_around_sky(cat_coords, radius)` returns `(idx1,
idx2, ...)` where `idx1` indexes `cat_coords` (the ARGUMENT) and `idx2`
indexes `star_coords` (self). Fixed by using the second return value as
the star-index array, with an inline comment recording the verified
(not assumed) semantics so a future reader doesn't have to rediscover this.
This is exactly the kind of index/array-order confusion this project has
been bitten by before (retriever.py row-misalignment; miri_photometry.py's
`label` gotcha) -- caught here by the unit test before it ever reached real
data, which is the system working as intended.

**Real numbers, all three fields** (same fields/subsamples as every other
check in this log):

| Field (n) | `qc_debris_disk_prime` | `qc_debris_disk_reserved` | `qc_ambiguous_debris_disk_match` | newly disqualified from previously-clean |
|---|---|---|---|---|
| PN-TC-1 (40) | 0/40 | 0/40 | 0/40 | 0 |
| CONTROLFIELD (20) | 0/20 | 0/20 | 0/20 | 0 |
| NGC-602 (20) | 0/20 | 0/20 | 0/20 | 0 |

**Zero matches everywhere -- verified this is a genuine null result, not a
silent bug**, by computing the actual closest separation between every
Gaia-matched star in each field and the nearest Cotten & Song entry
(`SkyCoord.match_to_catalog_sky`, independent of the crossmatch function
being verified): PN-TC-1's closest approach is 173.9 arcmin, CONTROLFIELD's
is 11.5 arcmin, NGC-602's is 314.7 arcmin -- all 3-5 orders of magnitude
farther than the 2.0" crossmatch radius. Not a near-miss pattern that would
suggest a radius or position-parsing problem; a clean, physically sensible
non-overlap: Cotten & Song's targets are bright, nearby stars from general
all-sky (Tycho-2/WISE) surveys, unrelated by construction to this
project's three JWST MIRI pointings (a planetary-nebula follow-up, a
deliberately quiet control field, and an SMC cluster) -- there was never a
strong prior reason to expect overlap with these three specific fields.

**Verification:** 93 tests pass (12 new: `fetch_debris_disk_catalog` is
NOT unit-tested, live-verified only via the real run above, same
convention as this module's other network calls; `crossmatch_debris_disk_catalog`
and the full `assemble_level_b2` integration are covered offline with
synthetic catalog tables).

**Status:** all three planned Tier 3 pieces for this session are now
resolved: debris disk implemented and verified (this entry); Milky Way
young-cluster fix queued next; photometric artifact and the extragalactic
young-cluster half remain the two explicitly deferred items logged
earlier in this session, unchanged.

### 2026-07-22 -- Milky Way young-cluster/PMS fix implemented; earlier "15/24" impact estimate corrected with real numbers

Implemented the Milky Way half of the young-cluster/PMS gap:
`qc_cluster_member_confirmed` (a genuine disqualifying signal -- confirmed
membership in a known open cluster) and `qc_confirmed_field_star`
(positive, non-gating evidence of NOT being a member), both cross-matched
by `gaia_source_id` against Cantat-Gaudin et al. (2020), A&A 640, A1
("Painting a portrait of the Galactic disc with its stellar clusters,"
VizieR `J/A+A/640/A1`, "nodup" members table -- confirmed live, ~2000
Milky Way open clusters keyed by Gaia DR2 source_id with per-star
membership probability). The full members table is too large to
bulk-download (timed out at `ROW_LIMIT=-1`, likely millions of rows) --
queried instead via VizieR's own TAP service (`tapvizier.cds.unistra.fr`,
confirmed live) with a targeted `GaiaDR2 IN (...)` clause over just this
project's own star IDs, the same efficient pattern as
`query_gaia_variability`. THE THIRD live-network call in `contaminants.py`.

**Architecture note, decided before writing code**: `excess.py`'s `b1`
composite (`qc_star_disqualified`, `qc_excess_clean_{band}`,
`qc_candidate_preliminary`) is already fully computed by the time
`contaminants.py` runs, and this module's own convention is to never mutate
a column an earlier stage produced. So this fix could not retroactively
"un-disqualify" a star in `b1` itself. Instead, `contaminants.py` computes
an ADDITIVE parallel composite (`qc_star_disqualified_refined`,
`qc_excess_clean_refined_{band}`, `qc_excess_significant_refined_{band}`,
`qc_candidate_preliminary_refined`) that is identical to `b1`'s own logic
except `qc_stopgap_young_cluster`'s contribution is overridden specifically
where `qc_confirmed_field_star` provides positive evidence -- every other
disqualifying reason (star-level or per-band) still applies unchanged.
`excess.py`'s own `qc_stopgap_young_cluster` was NOT retired (unlike the
evolved-star stopgap) -- it is still the only signal covering the
extragalactic case, which this fix does not address.

**The parallax S/N gate (same convention/threshold as `qc_evolved_star`,
5.0) does useful double duty here, verified, not assumed**: because a
genuinely extragalactic star's true parallax sits ~20x below Gaia's
measurement error at that distance, it will essentially never clear a
S/N>=5 bar -- so `qc_confirmed_field_star` structurally can never exonerate
an SMC-like star, without needing a separate explicit distance cut. This
was checked as a real consequence of the existing gate, not assumed.

**Real numbers, all three fields:**

| Field (n) | `qc_cluster_member_confirmed` | `qc_confirmed_field_star` | F770W newly clean (refined) | F1000W newly clean (refined) |
|---|---|---|---|---|
| PN-TC-1 (40) | 0/40 | 4/40 | 0 | 0 |
| CONTROLFIELD (20) | 0/20 | 3/20 | 1 | 1 |
| NGC-602 (20) | 0/20 | 1/20 | 1 | 1 |

Zero confirmed cluster members anywhere -- none of this project's stars
appear in Cantat-Gaudin's catalogue at all (not itself surprising; these
are JWST MIRI targets, not a sample selected for known-cluster overlap).

**Correcting the earlier effort estimate with real data, as this project's
convention requires:** the 2026-07-22 Tier 3 sequencing entry estimated
this fix would resolve "15 of the 24" real-signal stars found depending
solely on the young-cluster stopgap. **The actual number is 2 (one in
CONTROLFIELD, one in NGC-602), not 15.** Investigated why, rather than
just reporting the smaller number: the 15/24 estimate was based on
CONTROLFIELD's OVERALL Gaia-matched parallax range (0.06-1.4 mas, implying
714-8788 pc, confirming it as Galactic) -- but the SPECIFIC 15 stars
showing real excess signal are disproportionately the coolest, faintest
stars in the sample (Teff mostly 2800-3830 K), and faint stars have
correspondingly poor Gaia parallax precision. Checked directly: of
CONTROLFIELD's 15 real-signal stars, parallax S/N ranges from -1.27 to
5.25 -- 14 of 15 fail the same S/N>=5 gate this project has consistently
required before trusting any parallax-derived conclusion (several have
S/N consistent with zero or formally negative, common for faint/distant
sources). Only one star clears the bar.

**This is not a flaw in the fix -- it is the same rigor already applied
elsewhere in this project working as intended, on data that happens not
to support a confident conclusion for most of these specific stars.** The
pipeline correctly declines to assert "confirmed field star" when the
underlying parallax measurement doesn't support it, exactly as it declined
to trust noisy parallaxes for the evolved-star check earlier the same day.
The two stars that DO get exonerated (CONTROLFIELD star index 9, NGC-602
star index 12) both show negative excess_sigma_F770W (deficits, -1.26 and
-3.05) -- correctly recognized as ordinary, non-excess field stars now
properly counted in the null-result baseline rather than miscounted as
"contaminated" by a stopgap that didn't actually apply to them, but NOT
new excess candidates.

**One striking case checked and clarified, not left ambiguous**:
CONTROLFIELD star index 13 (Teff=3000 K) has real, enormous signal in
BOTH bands (excess_sigma_F770W=108.8, excess_sigma_F1000W=94.3) and IS
confirmed as a field star (parallax S/N=5.25, just clearing the bar) --
but it does NOT become clean/refined, because it carries THREE OTHER,
independent disqualifying reasons unrelated to cluster membership
(`qc_poor_photosphere_fit`, `qc_rj_extrapolated`, and
`qc_crowded_source_{band}` in both bands). The young-cluster fix worked
exactly as designed here (correctly stopped contributing to this star's
disqualification) -- it simply isn't the only reason this star is flagged.
This specific star is worth a manual look given the sigma values (crowding
and RJ-extrapolation are both real, substantive, independently-logged
caveats already), but resolving those is out of scope for this fix.

**Verification:** 104 tests pass (11 new: `compute_cluster_member_confirmed_flag`,
`is_confirmed_field_star`, and dedicated scenarios for the refined
composite -- exonerating a confirmed field star, NOT exonerating a
confirmed cluster member, matching the original when young-cluster was
never flagged, and confirming the refined columns are absent when the
significance threshold isn't set. `query_cluster_membership` itself is
NOT unit-tested, live-verified only via the real run above).

**Status:** Milky Way half implemented, verified, and its real (modest)
impact honestly quantified -- correcting the earlier estimate rather than
letting it stand unchallenged. Photometric artifact and the extragalactic
young-cluster half remain the two explicitly deferred Tier 3 items, logged
earlier in this session with their own quantified numbers, unchanged by
this entry.

### 2026-07-22 -- CONTROLFIELD star index 13 (Gaia 5258785479377301248): full diagnostic walkthrough, pixel-level, of the most interesting single case this pipeline has surfaced

Requested by the researcher: a full manual look at this star (identified
in the previous entry as confirmed-field-star with real signal in both
bands, disqualified only by reasons unrelated to cluster membership),
including the actual pixel cutout, not just the summary tables.

**Identity/astrometry (a0):** Gaia source_id 5258785479377301248,
RA=153.842, Dec=-56.990. G=19.47 (faint), BP=21.02, RP=18.11. Parallax
1.400+-0.267 mas (S/N=5.25, just clears the confirmed-field-star bar).
RUWE=0.976, non_single_star=0 (clean, no binary flag).

**The apparent signal:** observed/predicted = 1.319 in F770W (31.9%
excess) and 1.308 in F1000W (30.8% excess) -- strikingly close to
identical in both bands. Reaches sigma~100+ in both bands because the
*predicted*-side error is tiny (0.26%/0.24%), not because the excess
fraction itself is large. PSF-fit and aperture photometry agree tightly
in both bands (0.7% and 6.9% apart) -- the flux measurement itself is
internally consistent, not a fitting artifact.

**Why it's disqualified, three independent reasons, all checked directly:**

1. **Photosphere fit quality, independent of anything mid-IR:**
   reduced_chi2=44.6 (~9x the qc_poor_photosphere_fit threshold of 5.0),
   despite all 6 optical/near-IR bands being available (n_bands_used=6).
   `qc_grid_disagreement=1` too. The PHOENIX model at the fitted Teff
   (3000 K) simply does not describe this star's SED well -- the baseline
   the "excess" is measured against is itself questionable on its own
   terms, before mid-IR enters the picture at all.
2. **The mid-IR prediction is the still-unvalidated RJ-extrapolation:**
   Teff=3000 K is deep in PHOENIX-primary territory (well below
   cool_teff_max_k=3500 K), and PHOENIX doesn't reach MIRI wavelengths --
   `predicted_flux_{band}` for this star comes from
   `rj_extrapolation_spectrum`, the blackbody-tail substitute this project
   has never validated against real cool stars with known WISE/Spitzer
   photometry (the original 2026-07-20 blocking prerequisite, still open --
   see the consolidated Deferred to Future Work section below). This star
   is a live, concrete instance of exactly that unresolved gap.
3. **A REAL, resolved neighbor, confirmed directly in the pixel data, not
   inferred from the crowding flag alone.** Pulled the actual `_i2d.fits`
   cutouts (both bands, mosaics still on disk from this session's live
   downloads) around the star's own fitted PSF centroid: a second, clearly
   separated point source is visible ~1.25 arcsec away in BOTH bands (not
   blended into the target's core -- there is a real flux dip between the
   two peaks). Cross-checked against a0: this is a genuine, separately
   Gaia-matched star (source_id 5258785483678423680, nn_dist_F770W=11.31 px
   matches the visual separation exactly), with its OWN catalogued flux of
   4.64e-5 Jy in F770W. **The star's own excess flux (2.94e-5 Jy) is 63% of
   this neighbor's total flux** -- a quantitatively plausible amount for a
   modest leak from the neighbor's broad MIRI PSF wings into the local-
   background annulus used for the target's own flux extraction (the same
   general failure mode already flagged, directionally, as an open
   question for `miri_photometry.py` -- see Deferred to Future Work).
   Contamination from a neighbor's wings would naturally produce a roughly
   ACHROMATIC excess (scales with the neighbor's own brightness, not with
   any dust color) -- consistent with the oddly-similar 31.9%/30.8%
   fractions actually observed; genuine circumstellar dust emission would
   more typically show real wavelength dependence.

**Assessment (researcher's own framing, not overclaimed here): not a
confirmed candidate, but not nothing either.** Three independent,
concrete reasons to distrust this as genuine excess, one of them
(neighbor contamination) with an actual quantitative mechanism pointed to
directly in the pixel data -- but NOT confirmed via real PSF-subtraction/
deblending analysis, which was not attempted here. This is exactly the
"flag for individual manual review, do not auto-resolve" case this
project's whole significance-threshold philosophy (Carrigan/Griffith,
2026-07-22 entries above) is built around. Logged as such; not pursued
further in this pass.

### 2026-07-22 -- Real bug caught while checking FITS-compatibility ahead of output.py's design: disqualifying_flags silent truncation risk

Before starting the output.py design discussion, checked whether `b2`'s
schema (79 columns, including three fixed-width string columns) would
actually round-trip through a FITS binary table cleanly -- a natural
verification step given output.py's whole job is producing that file.
Found a real, if latent, bug in the process: `excess.py`'s
`build_disqualifying_flags_summary` used a fixed `dtype="U256"` for the
per-star comma-joined flag summary. Computed the actual worst case (every
`DISQUALIFYING_STAR_FLAGS`/`DISQUALIFYING_BAND_FLAGS` name, comma-joined):
**475 characters** -- already past 256. Confirmed live that numpy
silently truncates a fixed-width unicode array on assignment with no
error (`np.zeros(1, dtype='U10')` assigned a 47-character string silently
keeps only the first 10). No star in this project's real test data has
ever fired enough flags simultaneously to hit this (the worst real case
seen is a handful of flags, well under 256 chars), so this has not
corrupted any real output yet -- but it is a genuine, silent-data-loss
risk for a more heavily-flagged star at archive scale, exactly the kind
of failure mode this project's own qc_* philosophy exists to avoid.

**Fixed:** the dtype width is now computed from `flag_names` itself
(sum of every name's length plus one comma per join) rather than a fixed
guess, so it can never silently under-size again regardless of how many
bands or flags get added later. Regression test added, using a
deliberately long synthetic flag-name list (not this project's real,
currently-under-256 flag set) so the test keeps catching the bug even if
the real flag set never grows enough to trigger it on its own.

**Verification:** 105 tests pass (1 new, pinned to a string longer than
the old fixed width).

### 2026-07-22 -- pipeline/output.py: FITS catalogue + per-star SED plots implemented, verified against real data (including two real rendering bugs caught by actually looking at the output)

Implemented the first piece of output.py, per the researcher's staged
request (build the SED plot first, check in before the other two
figures): `should_have_sed_figure` (selection logic), `plot_sed`
(rendering), `generate_sed_figures` (orchestration + `has_sed_figure`
tracking), `assemble_catalogue`/`save_catalogue` (the FITS catalogue).

**Inputs:** just `a0` + `b2` -- `b2` already carries forward everything
from `a1`/`miri_photometry`/`b1` (79 columns in real data), so output.py
doesn't touch the intermediate files directly, matching the "join
identity + latest stage" pattern `excess.py`/`contaminants.py` both
already use. Pulled `gaia_parallax`/`gaia_parallax_error`/
`gaia_phot_g_mean_mag` in from `a0` specifically (the direct inputs to
`qc_evolved_star`'s own math, not otherwise carried through anywhere) so
the catalogue is self-explanatory without reopening `a0`.

**Naming decision (researcher's explicit call, made deliberately, not by
default):** `qc_candidate_preliminary_refined` is kept as the literal FITS/
table column name, not shortened to a friendlier public name. The
"preliminary"/"refined" qualifiers are the load-bearing part of the name
for a project with a deliberately modest Scientific Claim -- a shorter
alias would risk exactly the overclaiming this project has avoided
everywhere else. The FITS header carries a `COMMENT` stating plainly that
this is NOT the final `qc_anomalous_excess` and naming what's still
missing, verified live to actually write and wrap correctly in a real FITS
header (not assumed).

**A real, structural FITS bug found and fixed before it reached real
output, not after:** checked (as part of verifying output.py's own design,
before writing the implementation) whether `b2`'s string columns would
round-trip through a FITS binary table cleanly. They do NOT, for empty
strings specifically: confirmed live that astropy's FITS writer converts
an empty string (`""`) to a MASKED value on read-back, not a real empty
string (`np.zeros(1, dtype='U10')` assigned an empty string reads back as
masked, not `''`). This matters directly for this project's own data:
`disqualifying_flags==""` (a clean star) and `photosphere_model_grid==""`
(a skipped white-dwarf fit) both use empty string as their "nothing here"
convention elsewhere in this pipeline -- writing them straight to FITS
would make "clean" and "genuinely unknown/absent" indistinguishable to
anyone reading the file directly, a real information-loss risk for
exactly the kind of self-contained, downloadable artifact this stage
exists to produce. **Fixed:** `assemble_catalogue` now replaces any empty
string, in any string-dtype column (detected generically via
`pd.api.types.is_string_dtype`, not hardcoded to the two columns known
to matter today), with an explicit `"(none)"` placeholder before writing.
Regression test added.

**A second bug caught only by actually looking at the rendered image, not
just checking the file existed:** the first real run (CONTROLFIELD star
index 13's own SED plot -- see the dedicated walkthrough entry above) had
its `disqualifying_flags` caption run straight off the right edge of the
figure, cut off mid-word (`...qc_crowded_source_F10` with the rest
missing). matplotlib's own `wrap=True` on `fig.text` was found not to
reliably wrap at the figure boundary. Fixed by wrapping the caption
explicitly with `textwrap.wrap` before handing matplotlib a string, with
the bottom margin sized to the actual number of wrapped lines. A second,
smaller issue from the same fix (the flags string has commas but no
spaces, so textwrap's `break_long_words` fallback still split mid-flag-
name) was also caught the same way and fixed by inserting spaces after
each comma before wrapping, giving textwrap real word boundaries to break
on. Neither of these would have been caught by a test that only checked
"did a PNG file get written" -- both required opening the actual image.

**Real numbers, all three fields** (SED figures generated / total stars):

| Field | Stars with an SED figure | Total stars |
|---|---|---|
| PN-TC-1 | 8 | 40 |
| CONTROLFIELD | 19 | 20 |
| NGC-602 | 13 | 20 |

CONTROLFIELD's 19/20 is not a bug -- consistent with everything already
logged about this field (widespread `qc_rj_extrapolated`, poor photosphere
fits, and crowding compounding into a large fraction of stars showing
`|excess_sigma|>=3` in at least one band, most already explained by known,
logged issues rather than novel signal).

**Verification:** 119 tests pass (14 new in `tests/test_output.py`,
covering selection logic, real plot rendering via matplotlib's Agg
backend -- treated as a deterministic offline operation and tested
directly, not smoke-tested only, unlike this project's genuinely
live-service dependencies -- and the FITS round-trip/masking regression).
Manually inspected the rendered PNGs for CONTROLFIELD star index 13 (the
dedicated walkthrough case), a single-band PN-TC-1 star (confirms the
missing-band point is cleanly omitted, not an error), and confirmed the
caption wraps correctly after the fix.

**Status:** FITS catalogue and per-star SED plots complete and verified.
Population `excess_sigma` scatter and the HR diagram are queued next,
pending the researcher's review of the SED plots (this entry) -- per
their explicit request to check in before building those two. LaTeX
candidate table also still queued.

### 2026-07-22 -- pipeline/output.py: population `excess_sigma` scatter plot and HR diagram implemented, verified against real data (one real rendering bug, one import smell caught before shipping)

Implemented the remaining two of the three planned figures:
`plot_excess_sigma_scatter` (population `excess_sigma_F770W` vs.
`excess_sigma_F1000W`, marked by star-level status: gold star for
`qc_candidate_preliminary_refined`, blue circle for clean-but-not-a-
candidate, gray X for disqualified, with reference lines at
+/-`significance_threshold_sigma`) and `plot_hr_diagram`
(`photosphere_teff` vs. `absolute_g_mag`, with the `expected_ms_abs_g`
reference curve overlaid and `qc_evolved_star` highlighted in red).
Both wired into `output.run()`.

**Caught before shipping, not after:** the first draft of
`plot_hr_diagram` imported `contaminants._MS_ANCHOR_TEFF` directly to
size the reference curve's Teff range -- a private, underscore-prefixed
constant from another module. Caught this myself on review and replaced
it with a fixed `np.geomspace(2000, 45000, 200)` range instead, since
`expected_ms_abs_g` already clips at its own table's boundaries -- no
need to reach into `contaminants.py`'s internals to get a sensible range.

**A real bug caught only by looking at the rendered image:** the first
real run (CONTROLFIELD's scatter plot) was nearly unreadable on a linear
scale -- a few extreme outliers (`excess_sigma` up to ~977) squashed the
rest of the population into an unreadable cluster at the origin, and the
+/-3-sigma reference lines were invisible against that scale. Fixed by
switching both axes to `symlog`, with `linthresh=significance_threshold_sigma`
(falling back to 1.0 if the threshold is unset) so the linear region
around zero -- where the reference lines and most of the population sit
-- stays readable while the heavy tail still fits on the same axes.
Re-rendered and confirmed: all points visible, both the positive-excess
and negative-deficit clusters distinguishable, reference lines clear.
This would not have been caught by a test that only checked the PNG got
written -- the earlier synthetic-fixture tests all passed on both the
linear and symlog versions since none of their fabricated values were
extreme enough to expose the problem.

**Verification, all three fields, actually inspected (not just
file-existence-checked):**

- **CONTROLFIELD scatter:** readable after the symlog fix; both
  clusters and reference lines visible.
- **PN-TC-1 scatter:** only 2 of 40 stars plotted (38 excluded for
  missing one band's sigma) -- consistent with, not contradicting,
  everything already logged about PN-TC-1's population being
  predominantly single-filter detections; this figure structurally
  cannot show single-band-only stars, a known and accepted design
  consequence, not a bug.
- **NGC-602 scatter:** 11 of 20 stars excluded (missing a band); the 9
  plotted points span the readable range cleanly on the symlog axes,
  no candidates (n=0), one clean point, eight disqualified.
- **All three HR diagrams:** axes correctly inverted in both dimensions
  (hot-to-cool left-to-right, bright-to-faint top-to-bottom), the
  `expected_ms_abs_g` reference curve renders as a smooth, physically
  sensible track across the full Teff range, and `qc_evolved_star`
  highlighting is visually correct in every field. PN-TC-1's HR diagram
  is the clearest confirmation: its single `qc_evolved_star` case (the
  one real, trustworthy overluminous star found after the parallax S/N
  gate fix -- see the earlier Tier-1 entry) renders as a red star sitting
  clearly above and to the left of the main-sequence curve, exactly
  where a genuinely overluminous star should fall, with all 11 other
  plotted stars sitting near the cool main-sequence track as expected.
  CONTROLFIELD and NGC-602 both show `qc_evolved_star` n=0, consistent
  with a control field and a young cluster respectively having no
  legitimately evolved population.

**Verification:** 20/20 tests pass in `tests/test_output.py` (8 new,
covering both figures against synthetic population fixtures
`_synthetic_b2_population`/`_synthetic_a0_population`); 125 tests pass
project-wide.

**Status:** all three output.py figures (SED plots, population scatter,
HR diagram) and the FITS catalogue are complete and verified against
real data for all three test fields. LaTeX candidate table is the one
remaining output.py artifact.

### 2026-07-22 -- pipeline/output.py: two LaTeX tables implemented and verified, including an actual compiled-PDF inspection that caught a real column-wrapping bug

Implemented the final output.py artifact: `write_candidate_table`
(one row per `qc_candidate_preliminary_refined` star) and
`write_flagged_for_review_table` (one row per star disqualified by
`qc_star_disqualified_refined` whose raw `excess_sigma` is still notable
in either band -- the general, automated form of the CONTROLFIELD star
index 13 walkthrough), both built on a shared `_write_star_table`
renderer so the two tables' column set, escaping, and empty-table
placeholder behavior can't drift apart independently. Refactored
`should_have_sed_figure`'s "is this star's raw signal notable" check
into `_notable_by_raw_sigma` so `select_flagged_for_review_rows` reuses
the identical logic rather than a second copy.

**Design call carried through from the researcher's earlier proposal
(not vetoed, then explicitly confirmed by this session's request):**
two separate tables, not one with a status column -- a true
`qc_candidate_preliminary_refined` hit and a disqualified-but-notable
signal are different kinds of claim, and merging them risked blurring
exactly the distinction this project has been careful about everywhere
else (`qc_candidate_preliminary_refined`'s own naming decision, the
FITS `COMMENT` caveat).

**Requirement 1 -- graceful degradation to an explicit placeholder,
confirmed rendered, not just trusted:** ran `write_candidate_table`
against real `b2` for all three fields (PN-TC-1, CONTROLFIELD,
NGC-602), all of which have zero `qc_candidate_preliminary_refined`
hits. All three `.tex` files render a single
`\multicolumn{5}{c}{No candidates in this sample.}` row rather than an
empty or missing file -- confirmed both in the raw `.tex` text and in
the compiled PDF (Table 1 and Table 3 in the rendered preview).

**Requirement 2 -- CONTROLFIELD star 13 in the flagged-for-review
table, confirmed with real numbers:** `write_flagged_for_review_table`
against real CONTROLFIELD `b2` produces 19 rows; star_id
`5258785479377301248` (star index 13, the dedicated pixel-level
walkthrough case) appears with sigma=108.82/94.25 and
`disqualifying_flags` = `qc_poor_photosphere_fit, qc_rj_extrapolated,
qc_stopgap_young_cluster, qc_crowded_source_F770W,
qc_crowded_source_F1000W` fully visible, not truncated.

**A real bug caught only by actually compiling the .tex to a PDF and
looking at it, not by checking the file was non-empty:** the first
version used a plain `l` column for `disqualifying_flags`. `pdflatex`
compiled without error, but the compiled page showed the flags column
running straight off the right edge of the page for any row with a
long flag list (confirmed visually: CONTROLFIELD's flagged-for-review
table, star 13's own row among others) -- `pdflatex`'s "Overfull \hbox"
warning flagged this too, but the researcher's own standard here is to
look at the rendered output, not just trust a clean exit code. Same
underlying class of bug as `plot_sed`'s caption-clipping issue found
earlier this stage, in a different rendering technology. **Fixed:**
changed the `disqualifying_flags` column to a `p{5.5cm}` paragraph
column (native to LaTeX's `tabular` environment, no extra package
needed) so it wraps within the table itself, and -- same fix pattern as
`plot_sed`'s caption -- replaced `,` with `, ` in the flags string
before escaping, giving the paragraph column real whitespace break
points instead of one unbroken comma-joined "word" that LaTeX's line
breaker can't split. Recompiled and re-inspected: all rows wrap
cleanly within the page margin, no more overfull-hbox warnings, star
13's full 5-flag list readable across multiple wrapped lines.

**Verification:** 133 tests pass project-wide (28 in
`tests/test_output.py`, 8 new: `select_candidate_rows`,
`select_flagged_for_review_rows` matching a star-13-style fixture case,
both tables' placeholder-degradation paths, escaping, and a
"well-formed LaTeX `table` environment" structural check). Beyond unit
tests: actually ran `pdflatex` against the real generated `.tex` files
for CONTROLFIELD and PN-TC-1 (assembled into one preview document via
`\input`), rendered the resulting PDF to PNG with PyMuPDF, and visually
inspected every page -- catching the column-wrapping bug above, which
no unit test (all using short synthetic flag strings) would have
caught.

**Status:** output.py is now fully complete -- FITS catalogue, all
three figures, and both LaTeX tables are implemented and verified
against real data for all three test fields.

### 2026-07-22 -- Moderate-scale (15-field) trial run: scope agreed, a real retriever.py bug caught by a smoke test before the multi-hour run, one fix, then launched

Before running the pipeline at moderate archive scale (15 fresh fields,
none overlapping PN-TC-1/CONTROLFIELD/NGC-602), agreed scope with the
researcher first, same process as every prior stage: field list
(stratified, not random, chosen from a live 1179-observation/691-target
archive-wide `query_miri_observations` call -- reasoning: this
checkpoint's stated goals, output.py diversity and runtime/memory
profiling, need code-path/category coverage more than aggregate-
statistic realism, and several relevant categories are rare enough
archive-wide -- e.g. 5 planetary-nebula targets, 2 novae, 4 circumstellar-
dust targets out of 691 -- that a blind random draw of 15 could plausibly
miss them entirely), success criteria (no crashes, per-stage runtime +
peak RSS + disk usage, an aggregate category-flag distribution, real bugs
reported same as always), and fresh (not cached) downloads for realism.

**Runtime estimate, from real current measurements, not guesses:**
photosphere.py (the known, previously-logged bottleneck) costs ~33s/star
on CONTROLFIELD's real 20-star sample measured live just before this run
(668.8s total, including a ~12s one-time Bayestar load) -- confirming the
2026-07-20 "hours to day-plus at archive scale" concern is real, not
theoretical. Since dense fields in the proposed list (e.g. NGC-346, a
real massive SMC cluster) could otherwise have hundreds-to-thousands of
raw detections, each field's `a0` is capped to 20 stars before
photosphere/miri_photometry/excess/contaminants/output (matching the
precedent already set for CONTROLFIELD/NGC-602's own capped 20-star
samples), keeping the estimate bounded: ~13 min/field (photosphere
~11 min + retriever download/crossmatch ~1-2 min + miri_photometry/
excess/contaminants/output combined ~30s, all individually measured live)
x 15 fields ~ **up to ~3-3.5 hours, likely less** -- a live GD153 smoke
test (below) showed photosphere finishing in under a second when a
field's raw detections mostly lack real Gaia matches (no expensive fit
triggered), so CONTROLFIELD's 33s/star is closer to a worst case than a
typical case for the sparser/calibration-standard fields in this list.
Recommended, and adopted: run in the background, not a single sitting.

**A real bug caught by a smoke test, before committing to a multi-hour
unattended run, not during it:** ran the full chain on one field (GD153)
capped to 2 stars first, specifically to catch exactly this kind of
problem cheaply. It crashed: `save_level_a0`'s `ds.to_netcdf(path)` raised
`ValueError: unsupported dtype for netCDF4 variable: bool`.

**Root cause:** `assemble_level_a0` builds every column generically via
`np.asarray(star_table[name])`, with no per-column type handling.
`is_extended_{band}` (an `_cat.ecsv`-sourced morphology flag, mixing
missing/masked entries with Python `True`/`False`) resolves to
dtype=`object`. Confirmed directly (isolated reproduction, not just
inferred): an object array of **all** `True`/`False` values (no NaN
present) makes `to_netcdf` raise this exact error; the same array with
even one NaN mixed in, or all-NaN, writes fine. This had never been hit
before because PN-TC-1/CONTROLFIELD/NGC-602's own samples each happened
to have at least one star with a missing `is_extended_{band}` value,
diluting the array away from a pure-bool resolution -- a **works-by-luck
case that was never actually verified safe**. GD153 (a bright, cleanly-
detected calibration standard) was the first field this project has run
where every star's `is_extended_{band}` was determined, exposing it.

**Fix:** `_coerce_object_column_for_netcdf` (new, in `retriever.py`)
casts any object-dtype column whose non-null values are all
`bool`/`np.bool_` to float64 (`1.0`/`0.0`/`NaN`) -- generic, not
hardcoded to `is_extended` specifically, in case another `_cat.ecsv`
column shows the same pattern later. Matches how
`contaminants.py`'s `compute_background_galaxy_flag` already reads this
exact column (`np.isfinite(vals) & (vals != 0)`), so no downstream
consumer needed to change. Three regression tests added to
`tests/test_retriever.py` (previously a Phase 1 scaffold with zero real
tests -- this is the first real test coverage that module has had):
all-bool (the exact failure case), mixed bool/NaN, and all-NaN, each
asserting a real `to_netcdf` call succeeds. Re-ran the GD153 smoke test
after the fix: completed cleanly end-to-end (retriever through output),
2/479 stars (capped), zero errors. 136 tests pass project-wide.

**Status:** scope agreed and fix verified; the 15-field batch launched
in the background. Results (per-field timing/memory/disk, the aggregate
category-flag distribution, and any further bugs) to be reported and
logged once complete.

### 2026-07-22 -- 15-field trial batch: results, a real single-band-field bug found and fixed, memory discrepancy investigated and cleared

The batch above completed: 13/15 fields succeeded, 2 failed cleanly with
the same root cause. Reported here in full, plus the fix, the memory
investigation the researcher asked to be done explicitly rather than
assumed, and the final 15/15 re-run.

**Runtime, corrected with real measurements, not the pre-run estimate:**
the batch attempt (all 15 fields, including the 2 that errored partway
through) took **1248.46s (~20.8 min) wall-clock**, not the ~3-3.5 hours
estimated beforehand. The estimate was wrong because it extrapolated
from CONTROLFIELD's 33s/star as a typical cost, when it is closer to a
worst case: `fit_star`'s own early-exit logic (`pipeline/photosphere.py`,
`n_available_bands < 2` and the white-dwarf branch) skips the expensive
Kurucz/PHOENIX grid fit entirely for any star lacking at least 2 usable
photometric bands or classified as a white dwarf -- neither case needs
`qc_no_photosphere_grid`-style grid selection, just an instant NaN fill.
Checked directly against the real a1 outputs for all 13 successful
fields (233 stars): only **5/233 stars (2.1%)** ever triggered a real
per-star grid fit; 40/233 (17.2%) were white dwarfs (instant skip);
the remaining 188/233 (80.7%) lacked 2 usable bands (instant skip,
almost always no clean Gaia match). CONTROLFIELD -- the field the
per-star estimate was based on -- happens to be an atypically
fit-heavy field where all 20 stars had adequate photometry; most of the
archive-wide sample does not look like that. This matches the live
GD153 smoke-test observation already logged above (photosphere
finishing in under a second) -- confirmed here at full batch scale
rather than from one field's smoke test.

**Aggregate category-flag distribution (13 fields, 233 stars), from the
real `b2.nc` outputs, not estimated:**

| | count | rate |
|---|---|---|
| `qc_star_disqualified` | 231/233 | 99.1% |
| `qc_candidate_preliminary` (dual-band) | 0 | 0% |
| `qc_single_filter_detection` | 230/233 | 98.7% |
| `qc_contaminant_flagged_partial` | 39/233 | 16.7% |
| `qc_poor_photosphere_fit` | 190/233 | 81.5% |
| `qc_extinction_uncertain` | 188/233 | 80.7% |
| `qc_no_photosphere_grid` (white dwarf) | 40/233 | 17.2% |
| `qc_background_galaxy` | 38/233 | 16.3% |
| `qc_stopgap_young_cluster` | 20/233 | 8.6% |

**Zero survivors, same headline finding as the original 3-field check**
(2026-07-22, "Threshold set to 3.0" entry: 80/80 stars disqualified,
0/80 `qc_candidate_preliminary`), but not quite as absolute this time:
2/233 stars are NOT `qc_star_disqualified` (both in HD55677 --
Gaia 3167200388352639232 and 3167212139383161216), the first real
non-disqualified stars this project's real-data checks have ever
produced. Neither is a candidate: each is `qc_excess_clean` in only
ONE band (`qc_single_filter_detection`/band-level disqualification in
the other), so neither gets the dual-band cross-check
`qc_candidate_preliminary` requires -- checked directly (excess_sigma
-2.72 and -24.9 in their respective clean bands, both consistent with
non-excess, not even individually a marginal case). Consistent with,
not a contradiction of, the 3-field zero-survivor result: the archive
sample is large enough to finally surface single-band-clean stars that
the smaller curated 3-field sample never happened to contain, and this
pipeline's own design (per the researcher's 2026-07-22 decision, logged
above) deliberately withholds candidate status from single-band-only
detections rather than relaxing the criterion for them.

**A real bug, caught by the run itself, not a smoke test this time --
both failures had the identical cause:** `-BET-PIC` and
`NGC-1266-BACKGROUND` both crashed with
`KeyError: "No variable named 'miri_ra_F1000W'"` inside
`assemble_level_a0`. **Root cause:** both fields are genuinely
**F770W-only** -- confirmed directly (`load_miri_catalog_sources`'s own
`filter` column has exactly one value, `F770W`, for every source in
both fields; zero F1000W observations exist for either target in MAST,
not a download or cross-match failure). `pivot_to_one_row_per_star`'s
`unstack("filter")` correctly builds `miri_ra_{f}`/`miri_dec_{f}`
columns only for filters actually present in the input rows -- so a
single-band field never gets `miri_ra_F1000W`/`miri_dec_F1000W` columns
at all, not NaN-filled ones. `assemble_level_a0` (`pipeline/retriever.py`)
didn't know that: its per-filter units-attrs loop unconditionally
iterated over `config`'s full configured filter list
(`["F770W", "F1000W"]`) and indexed `ds[f"miri_ra_{f}"]` directly,
assuming every configured filter always has a column. This had never
been hit before because every field used in this project's real-data
checks so far (PN-TC-1, CONTROLFIELD, NGC-602, and by implication all
13 of this batch's other fields) happens to have at least some F1000W
coverage.

**The same bug pattern was found a second time by inspection before it
could cause a second crash:** `build_neighbor_index`
(`pipeline/miri_photometry.py`) has the identical assumption --
`a0_ds[f"miri_ra_{filt}"].values` indexed directly, one call per
configured filter, for every field. Unlike
`extract_flux_for_filter` (same module), which already degrades
gracefully via `row.get(f"miri_ra_{filt}", np.nan)` on a per-row dict
(returns `qc_no_mosaic_for_filter=1}` cleanly), `build_neighbor_index`
indexes the `xr.Dataset` directly and would have crashed with the same
`KeyError` on the very next stage once `assemble_level_a0` was fixed.
Caught and fixed proactively, not by running into it.

**Fix, in both functions, same pattern -- skip filters with no column
rather than assuming universal coverage:**
```python
# retriever.py, assemble_level_a0
for f in filters:
    if f"miri_ra_{f}" not in ds.data_vars:
        continue
    ds[f"miri_ra_{f}"].attrs["units"] = "deg"
    ds[f"miri_dec_{f}"].attrs["units"] = "deg"

# miri_photometry.py, build_neighbor_index
if f"miri_ra_{filt}" not in a0_ds.data_vars:
    return index  # empty -- every star gets qc_no_mosaic_for_filter=1
```
Not hardcoded to F1000W or to these two fields -- generic to any filter
genuinely absent from a field, matching the fix philosophy already
established for the GD153 bool-dtype bug earlier this stage.

**Verified against both fields specifically, with real MAST data (cached
from the original run, not re-downloaded):** re-ran retriever through
`miri_photometry` for both `-BET-PIC` (432 uncapped detections) and
`NGC-1266-BACKGROUND` (58 uncapped detections) in isolation first, ahead
of the full official re-run below. Both assembled `a0` cleanly with only
`miri_ra_F770W`/`miri_dec_F770W` present (no `F1000W` columns, confirmed
absent, not NaN-filled), and `miri_photometry` ran to completion with
`qc_no_mosaic_for_filter_F1000W == 1` for all stars in both fields, as
expected. **Regression check against the three original fields and the
13 already-succeeded trial-batch fields:** all 13 fields that succeeded
under the old buggy code necessarily have both filters' columns present
(the old code would have crashed identically on any single-band field,
with no exception) -- so the new guard is a structural no-op for every
one of them, and for PN-TC-1/CONTROLFIELD/NGC-602. Confirmed empirically
too: the existing regression tests (`test_assemble_level_a0_handles_*`,
which exercise both F770W and F1000W columns together) still pass
unchanged. Full suite: 137 tests pass (136 -> 137; one new test,
`test_assemble_level_a0_handles_field_with_only_one_band_present`,
added to `tests/test_retriever.py` -- the single-band-only case that
module didn't have a test for, per the researcher's request).

**Memory discrepancy investigated as its own question, per the
researcher's explicit ask -- not assumed benign:** the original batch
report showed peak RSS climbing from ~410 MB to **3901.3-3985.6 MB**
over the run, well above the ~2.3 GB seen in an earlier isolated single
`photosphere.run()` call. Two things needed to be distinguished:
legitimate reference-data residency (fine) vs. a real per-field leak
(a genuine problem at archive scale). **Method:** (1) inspected the
batch report's own RSS-vs-stage trace field by field -- `ru_maxrss` is
a monotonic high-water mark for the whole process, so it cannot fall,
but a true leak should still show it climbing indefinitely as more
fields are processed, while bounded caching should plateau. (2) read
the caching architecture directly: `photosphere.py`'s `_bayestar_query`
is a module-level singleton (loaded once, `global` keyword, never
cleared); `_get_bandpass` and `miri_photometry.py`'s
`_get_miri_psf_template` are both `@lru_cache(maxsize=None)`; Kurucz
grid reads go through `stsynphot`'s own internal grid-file caching;
PHOENIX reads go through `expecto`'s `cache=True`. All four are
"load once per distinct value ever requested, keep forever" by
design -- correct behavior for expensive reference data, not a leak,
*if* the set of distinct values requested is bounded. By contrast,
`miri_photometry.py`'s `mosaic_cache` (raw `_i2d` FITS arrays) is a
fresh local dict per field, explicitly closed via `close_mosaic_cache`
at the end of `assemble_miri_photometry` -- correctly field-scoped, not
part of the persistent set. (3) **a controlled, real, in-process test**
(not just reasoning from the architecture): ran `photosphere.run()` on
CONTROLFIELD, then a different field (NGC-602), then re-ran
CONTROLFIELD again, then NGC-602 again, all four calls in the same
process. Results: start 178.8 MB -> after CONTROLFIELD 624.1 MB -> after
NGC-602 2762.4 MB -> after CONTROLFIELD **re-run, same 2 stars, 2762.4 MB
(+0)** -> after NGC-602 **re-run, same 2 stars, 2762.4 MB (+0)**. Repeating
identical work added exactly zero additional memory; only a genuinely
*new* field (new Teff values, touching Kurucz/PHOENIX grid nodes not
yet cached) grew RSS at all. This is the direct evidence the
architecture read predicted: growth is bounded by the diversity of
distinct grid nodes/dust-map queries touched, not by the number of
fields or stars processed. It also explains the original batch's own
trace precisely: RSS was exactly flat for the 6 fields before any real
photosphere fit ran, jumped once at `2M0359+2009-B` (the first field
with a real fit, 130.7s), stayed flat for `VI-CYG-1`, jumped again
(smaller) at `HD55677` (the second and last field with real fits,
172.1s), then stayed flat for all 5 remaining fields including
`NGC-346` (2154 raw detections) and `M31-LRN-2015` (1458) -- exactly
the two step-jumps predicted by "only 5/233 stars ever ran a real fit,
both jumps line up with those two fields," not a smooth per-field
climb. **Conclusion, high confidence:** the ~3.9 GB figure is expected
steady-state reference-data residency (Bayestar dust map + touched
Kurucz/PHOENIX grid nodes + stpsf PSF templates), not a per-field leak.
The ~2.3 GB isolated-run figure undercounts simply because it only ever
touched one field's worth of distinct Teff values; a real archive-scale
run touching more distinct stellar types would plateau higher than
3.9 GB but still boundedly, capped by the finite size of the reference
grids themselves -- worth remembering as a real (bounded) memory
budget line item at full archive scale, not a bug to fix.

**Re-ran `-BET-PIC` and `NGC-1266-BACKGROUND` through the full official
chain** (retriever through `output.py`, same instrumentation as the
original batch script, same `trial_batch` directory/report so the batch
record is now a complete 15/15 rather than a separate throwaway run):
both completed with zero errors. `-BET-PIC`: 432 uncapped detections
(capped to 20), 46.84s total. `NGC-1266-BACKGROUND`: 58 uncapped
detections (capped to 20), 10.70s total -- both fast, benefiting from
the original run's cached MAST downloads and (consistent with the
runtime finding above) no real photosphere fits triggered in either
field.

**Full 15-field, 273-star aggregate**, folding these two in:

| | count | rate |
|---|---|---|
| `qc_star_disqualified` | 271/273 | 99.3% |
| `qc_candidate_preliminary` (dual-band) | 0 | 0% |
| `qc_single_filter_detection` | 270/273 | 98.9% |
| `qc_contaminant_flagged_partial` | 47/273 | 17.2% |

All 40 newly-added stars (20 capped from each of the two fields) are
`qc_star_disqualified` -- both fields are F770W-only, so every star
carries `qc_no_mosaic_for_filter_F1000W`/related single-band
disqualifications; the 2 non-disqualified HD55677 stars found above
remain the only exceptions across the full batch. **Zero candidates,
confirmed at the full 15-field/273-star scale** -- the same outcome as
the original 3-field (80-star) and 13-field (233-star) checks, not a
new result on its own, but now resting on real data from every field
this trial batch was scoped to cover.

**Status:** 15-field trial batch is now fully complete and logged
(15/15, zero unresolved errors), the single-band-field bug is fixed in
both places it existed and covered by a new regression test, and the
memory discrepancy is resolved as expected behavior, not a bug, with
real controlled evidence rather than an assumption. 137 tests pass
project-wide.

## Deferred to Future Work (consolidated as of 2026-07-22)

Everything below is scattered across individual Decision Log entries
above (each cited); this section exists so a single read gives a
complete, honest picture of what this pipeline does and does not yet
handle -- the intended source for a paper's methods/limitations
discussion, not a chronological journal. Items are grouped by what they
block, not by when they were found. "Open Methodological Questions"
earlier in this file remains the full chronological record if the
history behind a specific item matters; this section is the current-state
summary.

### Blocking the final `qc_anomalous_excess` composite

None of these are bugs -- each is a specific, named, still-open
prerequisite.

1. **`qc_photometric_artifact` is unimplemented.** Real DQ arrays exist
   (Level 2 `_cal.fits`, confirmed live), but require per-source
   position-to-multiple-exposure WCS remapping -- the same class of
   problem behind two of this project's three known index/ordering bugs
   (see "Recurring Methodological Pattern" above). Estimated 2-4 days,
   judged the worst cost/value ratio of the three Tier-3 items considered
   2026-07-22 (only refines `qc_saturated`'s existing NaN-pixel proxy and
   adds persistence/cosmic-ray-jump detection currently invisible to any
   check). Not started.
2. **Young-cluster/PMS, extragalactic half.** Confirmed: **9 real,
   statistically significant excess cases in NGC-602** depend solely on
   `excess.py`'s blanket, field-wide `qc_stopgap_young_cluster` -- no
   SMC/LMC-specific membership catalogue has been identified (Cantat-Gaudin
   et al. 2020, used for the Milky Way half, structurally cannot cover
   this population). May not have a bounded solution within this
   project's scope at all. Not started; the parallax/PM-based approach
   was explicitly checked and found unsafe (SMC-distance parallax is
   below Gaia's precision floor).
3. **`qc_rj_extrapolated` validation study, never done.** The original
   2026-07-20 blocking prerequisite: validating the Rayleigh-Jeans/
   blackbody-tail extrapolation (`photosphere.py`'s substitute for PHOENIX's
   ~5.5 micron mid-IR coverage gap) against real cool stars with known
   WISE/Spitzer mid-IR photometry, to produce an actual error-inflation
   factor. Currently handled by exclusion (`qc_rj_extrapolated` is
   disqualifying in `excess.py`, per the researcher's 2026-07-22 "option A"
   decision) rather than fixed -- these stars can never become candidates
   under the current design, not because they're known to be wrong, but
   because they're not yet known to be right. CONTROLFIELD star index 13
   (see the dedicated walkthrough entry above) is a live instance of
   exactly this gap.
4. **`single_band_significance_threshold_sigma` / `qc_single_band_candidate`
   still null/uncomputed.** Deliberately deferred 2026-07-22: must be a
   genuinely separate, stricter value from the primary threshold (3.0),
   not a scaled-down copy, since single-band-only stars
   (`qc_single_filter_detection`) don't get the dual-band cross-check that
   gives the primary criterion its own (already modest) statistical
   credibility. No candidate value proposed yet.
5. **`qc_anomalous_excess` itself** needs all of the above plus items 1-2
   resolved -- currently `qc_contaminant_flagged_partial` (partial) and
   `qc_candidate_preliminary`/`qc_candidate_preliminary_refined`
   (preliminary, pre-full-composite) are the closest working substitutes.

### Known, stated simplifications affecting result trustworthiness (not blocking, but not free either)

6. **Diffuse/neighbor background contamination in `miri_photometry.py`'s
   local-background annulus is a real, checked-but-unresolved systematic.**
   Directional check (2026-07-22) found this does NOT have a single safe
   direction the way `qc_extinction_uncertain` does -- it can bias
   `observed_flux_{band}` either low (safe) or high (could manufacture
   spurious excess) depending on local structure relative to the annulus.
   CONTROLFIELD star 13's real, resolved neighbor at 1.25" (this session's
   pixel-level walkthrough) is a concrete, quantitatively plausible
   instance of the high-bias direction -- not proven via PSF-subtraction,
   but a live example that this is not a hypothetical concern. No `qc_*`
   flag currently exists for this failure mode.
7. **Gaia DR2/DR3 source_id compatibility for Cantat-Gaudin (2020), NOT
   independently verified.** The cluster-membership catalogue is keyed by
   DR2 source_id; this project's own `gaia_source_id` is DR3. The two
   agree for the large majority of sources, but this has not been checked
   against this project's own sample -- revisit if a star that should
   plausibly be a member ever shows up as `qc_confirmed_field_star` instead.
8. **`qc_known_variable`, `qc_debris_disk_prime`/`_reserved`, and
   `qc_cluster_member_confirmed`'s live queries are all single bulk
   `IN (...)`-clause queries**, not scaled beyond a modest source list
   (dozens to low hundreds of stars). At full archive scale (~1000+
   stars), a bulk table-upload cross-match would be more appropriate than
   one very large IN clause -- stated as a known limitation in each
   module's own docstring, not silently assumed to scale.
9. **Bayestar-to-Av conversion coefficient (2.742) is an unverified,
   commonly-cited approximate value**, never independently checked against
   Green et al. (2019) Table 1 as the `photosphere.py` docstring itself
   states. Every `photosphere_av` value in this pipeline inherits this
   uncertainty.
10. **`photosphere.py` known simplifications, stated but not revisited**:
    `log_g` fixed at 4.5 (main-sequence assumption -- dwarfs/giants not
    distinguished by the fit itself, though `qc_evolved_star` now catches
    the luminosity mismatch downstream), Kurucz metallicity fixed to solar
    (`ckp00` subgrid only), and no white-dwarf-appropriate model grid
    exists at all (Koester models never sourced -- WD targets get
    `qc_no_photosphere_grid` and no prediction, not a wrong one).
11. **`qc_background_galaxy` is deliberately coarse** (`is_extended_{band}`
    only). `a0` already carries `sharpness_{band}`/`roundness_{band}`/
    `ellipticity_{band}`/`semimajor_sigma_{band}`/`semiminor_sigma_{band}`
    unused -- a refinement opportunity, not attempted since it wasn't part
    of what was asked for Tier 1.
12. **`qc_saturated` remains a non-finite-pixel proxy**, not real DQ-bit
    saturation detection (the `_i2d` mosaic carries no DQ extension) --
    the same underlying gap item 1 above would properly resolve.
13. **Debris-disk crossmatch (2.0") does not epoch-propagate** Cotten &
    Song (2016)'s Tycho-2-epoch (~1991) positions forward to this
    project's Gaia epoch (2016.0) -- a stated compromise (generous radius
    + an ambiguous-match diagnostic instead), not a validated treatment.
    Zero matches were found in this session's real test data, so the
    ambiguous-match rate at this radius has not actually been exercised
    against real crowding yet.
14. **`qc_low_snr` (stage: excess) was never implemented.** A pre-existing
    placeholder distinct from `qc_psf_disagreement_faint_{band}` (which is
    about PSF-vs-aperture disagreement explained by low SNR specifically,
    not a standalone SNR floor on `observed_flux` itself).

### Operational / not yet run at scale

15. **`photosphere.py`'s per-star fit runtime (~50-130s when both Kurucz
    and PHOENIX are needed) has never been optimized**, logged as a known
    gap since 2026-07-20. Fine for the dozens-of-stars samples used
    throughout this project's real-data checks; would take hours-to-days
    at the full archive's ~1000+ stellar-classified observations.
16. **The full pipeline has not been run at FULL archive scale.**
    Updated 2026-07-22: a moderate-scale trial (15 fields, 273 capped
    stars, stratified for code-path/category coverage -- see the
    dedicated Decision Log entry) has now been run end-to-end with zero
    unresolved errors, one order of magnitude beyond the earlier
    3-field/80-star checks. This is real progress on this item, not a
    resolution of it: 273 stars is still well short of the archive's
    ~1000+ stellar-classified observations, and the 15 fields were
    chosen for category diversity, not to be a representative random
    sample -- survivor counts and contaminant-flag rates from either the
    3-field or 15-field checks remain explicitly NOT archive-wide
    statistics. See the positive-control caveat (2026-07-22) for the
    clearest statement of this limitation.
17. **`pipeline/output.py` is still a complete stub** -- FITS catalogue,
    diagnostic figures, and LaTeX table export are all unwritten.
18. **retriever.py's "first detection kept, not best-SNR" simplification**
    for a star observed twice in the same filter (different proposals) --
    logged 2026-07-20, not verified to be rare, not revisited.

### A specific candidate flagged for individual manual review, not resolved

19. **CONTROLFIELD star index 13** (Gaia source_id 5258785479377301248) --
    real, ~30% achromatic excess in both MIRI bands at very high formal
    significance, but disqualified by three independent, concrete reasons
    (poor photosphere fit, unvalidated RJ-extrapolation, and a real,
    pixel-confirmed neighbor at 1.25" whose brightness is quantitatively
    consistent with explaining the excess via background contamination --
    see the dedicated walkthrough entry above). Not resolved one way or
    the other; the single most interesting individual case this pipeline
    has produced so far, and a natural first candidate for real PSF-
    subtraction/deblending analysis if that capability is ever built.
