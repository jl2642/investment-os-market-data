# FMDL-6A — US Market Contract & Security Identity

## Decision

FMDL-6A freezes the US pilot market boundary and identity model before any live source benchmark or 24-security selection.

It does not build a live US Security Master and does not create an investable universe. Its authority is limited to contract, schema, lifecycle and identity semantics.

## Market boundary

The current pilot covers selected equity securities listed on:

- `XNYS`
- `XNAS`
- `XASE`

Included technical case types are common stock, ADR, foreign-private-issuer ordinary shares and equity-REIT common stock.

Funds, preferred stock, warrants, rights, units, options, futures, OTC securities, crypto assets, structured notes and SPAC units or warrants are excluded. Unknown instrument types are quarantined rather than included by default.

The future 24-security benchmark is a technical test set, not an investable universe, Longlist or candidate pool.

## Identity layers

FMDL-6A separates four layers:

1. **Issuer** — the legal/reporting entity, normally keyed by SEC CIK.
2. **Share class** — the economic and voting class within the issuer.
3. **Security** — the economic instrument associated with the issuer and share class.
4. **Listing** — the effective-dated exchange/ticker representation of a security.

This separation prevents ticker changes or exchange transfers from being misread as a new economic security.

## Controlled refinement of FMDL-6-0

FMDL-6-0 recorded the provisional pattern:

`US:<EXCHANGE_MIC>:<TICKER>:<SHARE_CLASS_OR_INSTRUMENT_CLASS>`

FMDL-6A formally interprets this as an effective-dated **listing locator**, not an immutable Security ID. The accepted FMDL-6-0 release remains unchanged.

Final identity patterns are:

- Issuer: `SEC:CIK:<CIK10>`
- Share class: `USCLASS:<ISSUER_KEY>:<CLASS_TOKEN>`
- Security: `USSEC:<ISSUER_KEY>:<INSTRUMENT_TYPE>:<CLASS_TOKEN>`
- Listing: `USLIST:<MIC>:<TICKER>:<EFFECTIVE_FROM_YYYYMMDD>`

## Lifecycle rules

The contract defines explicit handling for:

- ticker changes;
- exchange transfers;
- stock splits and reverse splits;
- dividends;
- new share classes;
- ADR ratio changes;
- mergers and acquisitions;
- spin-offs;
- delisting to OTC;
- bankruptcy or liquidation.

Ticker and exchange changes preserve issuer, share-class and security identity while closing the old listing and creating a new effective-dated listing. Mergers, spin-offs and legally distinct successors require explicit predecessor/successor links.

## Source conflict policy

Official SEC and exchange assertions retain their source, retrieval and effective timestamps. Conflicting assertions are preserved rather than silently overwritten. Unresolved conflicts are quarantined.

FMDL-6A does not declare any source route Decision-grade; that decision belongs to FMDL-6B.

## Acceptance boundary

FMDL-6A must prove:

- four identity layers;
- four included instrument types;
- at least ten excluded instrument types;
- ten lifecycle rules;
- twelve identity fixtures;
- deterministic output and same-input replay;
- zero candidate, simulation, real-account or order mutation;
- `trade_authority = NONE`.

## Exit

Expected status:

`FMDL6A_US_MARKET_CONTRACT_AND_SECURITY_IDENTITY_ACCEPTED`

Next gate:

`FMDL-6B_SOURCE_INTERFACE_AND_ACCESS_BENCHMARK`
