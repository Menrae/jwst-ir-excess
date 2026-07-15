"""
Shared pytest fixtures for jwst-ir-excess tests.

STATUS: not yet implemented (Phase 1 scaffold only).

Anticipated fixtures once pipeline modules exist:
    - small synthetic Gaia/2MASS/MIRI catalogue (a few rows, known truth
      values) for fast unit tests that don't hit MAST or Gaia archive
      network calls
    - a mocked astroquery.mast / astroquery.gaia response fixture, so tests
      never depend on live network access
"""

import pytest
