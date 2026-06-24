#!/usr/bin/env python3
"""Portable launcher for the substack-extraction skill."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from substack_extraction.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
