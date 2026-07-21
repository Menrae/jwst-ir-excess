"""
jwst-ir-excess pipeline package.

A tsdat-inspired pipeline for searching JWST/MIRI photometry for anomalous
mid-infrared excess relative to stellar photosphere predictions.

Stages (see RESEARCH_CONTEXT.md for full rationale):
    1. retriever.py        - MAST + Gaia DR3 + 2MASS ingestion, cross-match,
                              and pivot to one row per star (raw -> a0)
    2. miri_photometry.py  - MIRI photometry extraction from _i2d mosaics
                              (model-PSF fit, EE-corrected, primary; aperture
                              cross-check) -- own dataset, joined by `star`
    3. photosphere.py      - Stellar photosphere model fitting and residual
                              extraction (data level a1)
    4. excess.py            - IR excess scoring (data level b1, pre contaminant QC)
    5. contaminants.py     - Contaminant cross-matching and classification
                              (data level b1, qc_* flags appended)
    6. output.py            - Final catalogue export, figures, LaTeX tables

retriever.py, miri_photometry.py, and photosphere.py are implemented so
far -- this file marks the package and defines shared version/config
constants that later modules will import.
"""

__version__ = "0.0.1"
