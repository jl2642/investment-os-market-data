# FMDL-6X2-E Acceptance Criteria

1. Bind accepted FMDL-6X2-D Release 33 and preserve `trade_authority = NONE`.
2. Preserve the GitHub-hosted SEC 403 route probe as controlled execution evidence.
3. Accept only `sec.gov/Archives/edgar` official evidence; no third-party proxy or silent substitution.
4. Hash-validate every normalized official extract before parsing.
5. Map every initial filing to Canonical Issuer, Security and Listing identities without fuzzy matching.
6. Preserve CIK10, accession, form, filing/acceptance dates, report period and official URLs.
7. Preserve taxonomy, tag, unit, period, accession and source lineage for every fact.
8. Keep amendments and restated accessions separate and forbid neutral fill.
9. Account for all 7,419 Issuers as accepted initial coverage or explicit backfill.
10. Produce exactly 2,368 deterministic logical shards and pass same-input byte replay.
11. Publish Current, immutable Release, normalized, raw evidence, Last-success and domain LKG atomically.
12. Candidate Pool, simulation, real account and order mutations remain zero.
