#!/usr/bin/env bash
set -Eeuo pipefail

as_of="${1:-$(date -u +%F)}"

python automation/wp3_r/repair_source.py
python automation/wp3_r/build_candidate_refresh_current.py --repo-root . --as-of "$as_of"
# Preserve the established financial/profile/industry diagnostics, then replace
# only the 73-name market screen with a dated live Candidate snapshot.
python automation/wp3_r/finalize_operating_products.py --repo-root . --as-of "$as_of"
python automation/wp3_r/refresh_candidate_market_screen.py --repo-root .
# Rebuild the aggregate Current after every governed input has advanced.
python automation/wp3_r/build_candidate_refresh_current.py --repo-root . --as-of "$as_of"
