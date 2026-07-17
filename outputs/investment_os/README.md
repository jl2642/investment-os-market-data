# Investment OS Market-Data Interface

This directory is the stable machine-readable handoff from the free A-share market-data repository to 股票投资助手 / Investment OS.

## Canonical pointer

`INVESTMENT_OS_MARKET_DATA_INTERFACE.json`

The pointer does not duplicate the full market CSV files. It binds the consumer to the accepted `outputs/current/` release by path, hash, row count, run ID, as-of date, quality state and freshness policy.

## Consumer order

1. Read and validate the interface JSON against `schemas/investment_os_market_data_interface.schema.json`.
2. Read `outputs/current/CURRENT_RELEASE.json`.
3. Confirm zero hard failures, matching run ID/as-of date and allowed publication status.
4. Recompute hashes and row counts for the required datasets.
5. Apply the dataset freshness policy.
6. Surface soft warnings and `MARKET_EVENT_FLAGS.csv` before screening.
7. Pass validated FMDL-2 screen results to Public Equity Investing `idea-generation`.
8. Return research evidence to Investment OS at RESEARCH/SCORE. No data or research artifact creates trade permission.

## Authority boundary

This interface carries market evidence only. Investment OS remains the sole owner of candidate promotion, Gates, portfolio fit, capital migration, pre-trade review and execution permission. Real transactions always require explicit user confirmation.
