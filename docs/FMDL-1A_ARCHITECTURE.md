# FMDL-1A Market Data Repository Architecture

## Objective

Build the free A-share market data MVP layer for Investment OS.

## Design principles

1. Data source must be free or free-tier.
2. Every dataset must include source, timestamp, quality status and version.
3. Failed updates must not overwrite the last valid snapshot.
4. Data layer provides evidence and screening inputs; Investment OS retains investment decision authority.

## Initial data domains

- Stock universe
- Daily market snapshot
- Valuation snapshot
- Trading calendar
- Data quality report

## Planned structure

- config/: source and rule definitions
- ingestion/: data adapters
- pipeline/: normalization and validation
- datasets/: raw and processed data
- outputs/: Investment OS consumption files
- workflows/: GitHub Actions automation

## Acceptance gate

FMDL-1 MVP is accepted only after:

- Full A-share universe generated;
- Data quality checks passed;
- Snapshot versioning implemented;
- Automated workflow completed successfully;
- Output schema compatible with Investment OS.
