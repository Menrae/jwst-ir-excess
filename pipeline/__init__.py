"""
jwst-ir-excess pipeline package.

A tsdat-inspired pipeline for searching JWST/MIRI photometry for anomalous
mid-infrared excess relative to stellar photosphere predictions.

Stages (see RESEARCH_CONTEXT.md for full rationale):
    1. retriever.py    - MAST + Gaia DR3 + 2MASS ingestion (raw -> data level a0)
    2. photosphere.py  - Stellar photosphere model fitting and residual
                          extraction (data level a1)
    3. excess.py        - IR excess scoring (data level b1, pre contaminant QC)
    4. contaminants.py - Contaminant cross-matching and classification
                          (data level b1, qc_* flags appended)
    5. output.py        - Final catalogue export, figures, LaTeX tables

No modules are implemented yet -- this file marks the package and defines
shared version/config constants that later modules will import.
"""

__version__ = "0.0.1"
