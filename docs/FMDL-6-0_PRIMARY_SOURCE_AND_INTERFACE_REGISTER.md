# FMDL-6-0 — Primary Source & Interface Register

## Purpose

This register defines the source interfaces that FMDL-6B must benchmark. It does not pre-approve any interface as Decision-grade.

## Interface 1 — SEC identity and submissions

**Source family:** `SEC_DATA_SEC_GOV`

**Required capabilities:**

- issuer / CIK reference;
- ticker and exchange reference where available;
- submissions history;
- accession number;
- filing type;
- filing date;
- acceptance timestamp;
- primary document metadata;
- amendment and successor filing visibility.

**Key risks to benchmark:**

- ticker and exchange fields are not permanent issuer identity;
- one CIK may relate to multiple securities or historical tickers;
- foreign private issuer forms differ from domestic forms;
- accession and acceptance-time fields must be preserved.

## Interface 2 — SEC Company Facts and XBRL facts

**Source family:** `SEC_DATA_SEC_GOV`

**Required capabilities:**

- company facts;
- taxonomy and tag identity;
- unit;
- fiscal period and fiscal year;
- filing and accession lineage;
- filed date and acceptance time;
- amended fact visibility;
- US GAAP and IFRS foreign private issuer distinction.

**Key risks to benchmark:**

- issuer-specific extension tags;
- duplicate facts across forms or amendments;
- quarter / year-to-date ambiguity;
- restatement and amendment handling;
- inconsistent units and dimensions;
- facts that are available in filings but absent from Company Facts.

## Interface 3 — Official listed-security reference

**Source family:** `OFFICIAL_US_EXCHANGE_OR_REGULATORY_REFERENCE`

**Required capabilities:**

- listed symbol;
- exchange / MIC;
- instrument type;
- effective or retrieval date;
- test-issue and non-common-security flags where available;
- symbol changes, exchange transfers and removals where available.

**Key risks to benchmark:**

- different exchanges publish different fields and formats;
- directories may include ETFs, preferreds, warrants, rights or units;
- current symbol directories do not by themselves provide historical identity;
- exchange symbol is not the same as issuer identity.

## Interface 4 — Free daily market, corporate action and FX data

**Source family:** `FREE_OR_FREE_TIER_MARKET_DATA_WITH_EXPLICIT_FALLBACKS`

**Required capabilities:**

- daily OHLCV;
- adjusted and unadjusted price fields or enough event data to reconstruct them;
- split events;
- cash dividends;
- latest completed-session snapshot;
- USD/CNY and USD/HKD FX interface;
- retrieval timestamp and provider identity.

**Key risks to benchmark:**

- rate limits and anti-bot behavior;
- GitHub Actions runner access;
- inconsistent adjusted-close methodology;
- missing delisted history;
- split and dividend revisions;
- incomplete or stale volume;
- symbol collision and ticker reuse;
- free-source terms or endpoint behavior changing without notice.

## FMDL-6B benchmark fields

Every tested route must record:

- `interface_id`
- `provider_id`
- `endpoint_or_artifact`
- `official_or_fallback`
- `access_status`
- `http_or_adapter_status`
- `retrieval_timestamp`
- `sample_security_count`
- `field_coverage`
- `history_depth`
- `latency`
- `rate_limit_observation`
- `github_actions_compatibility`
- `point_in_time_support`
- `revision_support`
- `failure_mode`
- `fallback_route`
- `decision_grade_status`
- `trade_authority`

## Source decision policy

1. Official primary sources are preferred for identity, filing and financial evidence.
2. Free market-data sources may support the pilot only after explicit benchmarking.
3. No fallback may silently replace an official identity or filing source.
4. Missing data must remain missing or quarantined; neutral filling is forbidden.
5. A failed or degraded route may not replace Last Known Good.
6. All source decisions remain research-data authority only.
7. `trade_authority = NONE`.
