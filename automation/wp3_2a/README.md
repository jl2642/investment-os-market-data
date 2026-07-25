# WP3-2A GitHub Automation

This package implements fail-closed A-share Universe acquisition and governance.

1. `WP3-2A Universe Refresh` runs on a Beijing-time schedule or manually, retries free providers, saves raw bytes, runs Gate v3 and opens a **proposal PR**.
2. `WP3-2A Lineage Gate` validates proposal hashes, forbidden-path invariants and Runtime Acceptance.
3. `WP3-2A Accept Universe Proposal` is manual and environment-protected. It creates a separate **acceptance PR**; merge is the human promotion event.
4. `WP3-2A Governed Screening Proposal` is manual and proposal-only. It ranks research workload by data readiness/liquidity, not investment attractiveness.

No workflow may alter Candidate membership, Research Objects, real-account positions, simulation trades or orders. `trade_authority=NONE`.
