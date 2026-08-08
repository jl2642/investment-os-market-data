#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

# Keep this public path compatible with both package imports and direct script
# execution from GitHub Actions. Direct execution restarts the unchanged
# implementation as a module from the repository root so absolute
# `automation.cross_market` imports resolve deterministically.
if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    os.chdir(repo_root)
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "automation.cross_market.apply_round3_sec_observer_results_impl",
            *sys.argv[1:],
        ],
    )
else:
    from .apply_round3_sec_observer_results_impl import *  # noqa: F401,F403
