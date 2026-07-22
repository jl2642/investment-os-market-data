#!/usr/bin/env python3
from __future__ import annotations

import sys

from fmdl6b_benchmark import main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("validate")
    raise SystemExit(main())
