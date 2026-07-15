# jwst-ir-excess

Searching for anomalous mid-infrared excess in stars observed by JWST/MIRI —
a validated anomaly-detection pipeline, built as a candidate-flagging tool
for Dyson sphere / partial Dyson swarm technosignatures.

**Status:** Phase 1 (repository scaffold). No pipeline stages are
implemented yet.

## What this project does (and doesn't do)

A Dyson sphere or partial Dyson swarm would absorb starlight and re-radiate
it as waste heat in the mid-infrared, producing an IR excess relative to what
the star's photosphere alone predicts. This has been searched for before
using IRAS and WISE data (Carrigan 2009; Griffith et al. 2015 / G-HAT); this
project applies the same basic idea to JWST/MIRI photometry, which has
substantially better sensitivity and resolution than those earlier
instruments.

**This pipeline does not claim to detect Dyson spheres.** It flags stars
with statistically significant, unexplained mid-IR excess *after* exhaustive
removal of known astrophysical and instrumental contaminants (debris disks,
background galaxies, evolved stars, artifacts, variables, binary
companions), and characterizes that flagged population statistically. A
clean null result — no unexplained excess above the noise floor — is
treated as a legitimate, publishable outcome in its own right.

See [`RESEARCH_CONTEXT.md`](./RESEARCH_CONTEXT.md) for the full scientific
rationale, prior literature, and the running log of open methodological
questions and decisions.

## Pipeline stages

The pipeline follows a tsdat-inspired architecture: each stage has a single
responsibility, data moves between stages as `xarray.Dataset` objects saved
to NetCDF, and every quality-control decision is recorded as an explicit
`qc_*` variable rather than by silently dropping data.

| Stage | Module | Data level | Responsibility |
|---|---|---|---|
| Retriever | `pipeline/retriever.py` | raw → a0 | Ingest JWST/MIRI photometry (MAST), Gaia DR3, and 2MASS |
| Standardise | `pipeline/photosphere.py` | a0 → a1 | Fit stellar photosphere model; extract mid-IR residuals |
| Quality / anomaly | `pipeline/excess.py`, `pipeline/contaminants.py` | a1 → b1 | Score excess significance; cross-match and flag contaminants |
| Output | `pipeline/output.py` | b1 → results | Export FITS catalogue, diagnostic figures, LaTeX tables |

None of these modules are implemented yet — each will be built out with an
explicit scientific/methodological discussion first, per project convention.

## Repository structure

```
jwst-ir-excess/
  data/
    raw/          # downloaded catalogues (gitignored)
    processed/    # model-fit outputs and residuals (gitignored)
    flagged/      # anomaly-scored final catalogue (gitignored)
  pipeline/        # the four pipeline stages (see table above)
  notebooks/        # exploratory + write-up notebooks, one per phase
  tests/             # pytest unit tests, one file per pipeline module
  config/
    pipeline_config.yaml   # data sources, filters, model choices
    quality_config.yaml    # qc_* flag definitions and thresholds
  results/
    figures/       # diagnostic + publication figures
    tables/         # output tables (e.g. candidate catalogue)
    paper/          # manuscript source
  RESEARCH_CONTEXT.md   # scientific rationale, literature, decision log
  requirements.txt
  .gitignore
```

## Quickstart

This project runs inside a VS Code dev container on Python 3.12
(Debian Bullseye). No proprietary data access is required — everything
comes from public archives (MAST, Gaia, 2MASS).

```bash
# From the repository root, inside the dev container:
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests (currently placeholders — will grow with each pipeline module)
pytest tests/
```

Configuration lives in `config/pipeline_config.yaml` (data sources, filters,
model choices) and `config/quality_config.yaml` (contaminant/QC flag
definitions and thresholds). Many values in both files are still marked
`TODO` — see `RESEARCH_CONTEXT.md` for the list of open methodological
questions that need to be resolved before those TODOs are filled in.

## Project conventions

- Every pipeline module is discussed scientifically — what it does, why,
  and what could go wrong — before it's implemented.
- Uncertainty about data availability, catalogue contents, or prior work is
  flagged explicitly rather than assumed.
- No `git commit`, `git push`, or other history-modifying git command is run
  without explicit instruction.
- Positive findings require an exhaustive null-hypothesis / contaminant
  check before being treated as scientifically interesting.

## Status

Currently in Phase 1: repository scaffold only. Phase 2 (data retrieval from
MAST) is next.
