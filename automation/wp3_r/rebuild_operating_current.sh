#!/usr/bin/env bash
set -Eeuo pipefail

as_of="${1:-$(date -u +%F)}"

python automation/wp3_r/repair_source.py
python automation/wp3_r/build_candidate_refresh_current.py --repo-root . --as-of "$as_of"
python automation/wp3_r/finalize_operating_products.py --repo-root . --as-of "$as_of"
# Rebuild the aggregate Current after weekly/industry/financial products have
# advanced, so it does not retain the pre-finalization status or old watermark.
python automation/wp3_r/build_candidate_refresh_current.py --repo-root . --as-of "$as_of"
