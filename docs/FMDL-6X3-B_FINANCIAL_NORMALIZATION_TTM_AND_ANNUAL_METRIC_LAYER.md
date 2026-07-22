# FMDL-6X3-B — Financial Normalization, TTM & Annual Metric Layer

## Purpose

Convert the securities opened by FMDL-6X3-A into an auditable normalized financial layer. The first accepted baseline uses only SEC official facts, preserves source taxonomy, tag, label, unit, period and accession, and separates reported values from derived calculations.

## Production boundary

- Quarterly income-statement rows may become model-loadable after mapping and equation checks.
- TTM requires four distinct official quarters. One quarter must never be annualized or repeated.
- Annual metrics require fiscal-year or Form 10-K evidence.
- Balance-sheet and cash-flow readiness remain blocked until their official facts are captured.
- Missing values stay missing; no zero, median, peer or neutral fill is permitted.
- The output is a research-data layer only. It cannot change the Investment OS Candidate Pool, simulation, real account or orders.

## Initial accepted scope

The Release 36 readiness gate currently opens AAPL, MSFT and NVDA. Their captured SEC facts support a partial quarterly income statement and derived quarterly quality ratios. The system explicitly publishes TTM, annual and three-statement gaps as open issues.

## Downstream boundary

FMDL-6X3-C may consume the accepted quarterly ratios only in a quality sandbox. Valuation metrics that require TTM or annual denominators remain closed.
