# FMDL-6X2-B — Issuer Identity, Classification & Review Queues

## Objective

Transform the accepted FMDL-6X2-A current directory-observation layer into explicit Issuer, Share Class, Security and Listing identity objects, research classifications and controlled review queues.

## Identity boundary

Directory-derived IDs are internal canonical identifiers but remain `PROVISIONAL_DIRECTORY_DERIVED_MERGEABLE`. They may later receive aliases or supersession links when SEC, issuer, depositary or lifecycle evidence becomes available. Ticker and exchange are never immutable identity. Fuzzy issuer-name merging is forbidden.

This phase does not claim complete SEC legal-entity resolution. CIK values remain null unless supplied through an approved SEC official evidence bundle. GitHub-hosted SEC access limitations may not be bypassed with a third-party proxy.

## Classification hierarchy

1. Official Test Issue and ETF flags.
2. Explicit security-name evidence for warrants, rights, composite units, preferred equity, debt, ADR/ADS, funds and special profiles.
3. Conservative common-equity and unit classification.
4. Insufficient evidence remains `RESEARCH_REVIEW_REQUIRED` and enters a queue.

Core common equity remains pending SEC reporting and accounting-profile resolution. ADRs require underlying, depositary and ratio evidence. Special-profile securities are kept out of the standard industrial ranking engine.

## Required review queues

- ADR underlying, depositary and ratio;
- special instruments;
- classification ambiguity;
- SEC official identity pending;
- cross-market issuer groups;
- inherited source-scope quarantine.

## Publication

Publish Current, immutable Release, normalized identity dataset, Manifest, `FMDL6X2B_LAST_SUCCESS` and domain LKG only after deterministic replay and all identity gates pass.

No Candidate Pool, simulation, real-account or order mutation is authorized.
