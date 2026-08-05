#!/usr/bin/env bash
set -Eeuo pipefail

as_of="${1:-$(date -u +%F)}"

python automation/wp3_r/repair_source.py
# Rebuild the broad audit first, then preserve the established financial,
# profile and industry operating products from the specialized finalizer.
python automation/wp3_r/build_candidate_refresh_current.py --repo-root . --as-of "$as_of"
python automation/wp3_r/finalize_operating_products.py --repo-root . --as-of "$as_of"
# The broad audit input can remain older than the tracked Candidate market.
# Replace only the governed 73-name screen and reconcile its status into the
# aggregate Current as the final step; do not rerun the broad builder after it.
python automation/wp3_r/refresh_candidate_market_screen.py --repo-root .
