# FMDL-3E-A — Incremental Refresh Contract & Baseline Freeze

## 1. Purpose

FMDL-3E-A converts the accepted FMDL-3D unified layer into an immutable operating baseline and freezes the rules that later incremental refreshes must obey.

This stage does not fetch a new market session, a new financial disclosure or a new shareholder-return event. It defines how those future deltas will be detected, scoped, rebuilt, validated, promoted, replayed and rolled back.

## 2. Entry gate

The sole entry gate is the formally published FMDL-3D Final pointer:

`FMDL3D_VALUATION_CAPITALIZATION_AND_SHAREHOLDER_RETURN_LAYER_ACCEPTED`

The pointer, Current Release, decision, validation, unified Current, interface and all A–D component bindings must agree before the baseline can be frozen.

## 3. Baseline-0

`FMDL3D_CANONICAL_BASELINE_0` freezes:

- the accepted FMDL-3D Final Release;
- market as-of date;
- exact 5,528-symbol set;
- per-symbol unified row hashes;
- A–D component Release identities;
- source-file hashes and byte sizes;
- market, universe, financial, capitalization, valuation and shareholder-return watermarks;
- promotion, rollback and idempotence policy hashes.

The baseline is immutable after publication. Later runs create new Releases and deltas; they do not rewrite Baseline-0.

## 4. Delta event taxonomy

The contract defines 16 event types across six operating domains:

- market-session advance;
- universe membership and security-status changes;
- new financial disclosures, corrections and restatements;
- effective share-count changes;
- implemented dividends, completed buybacks, effective cancellations and completed issuance;
- source recovery, schema change, route change, baseline-integrity failure and operator-authorized full rebuild.

Every runtime delta must carry an event ID, source identity, effective time, explicit affected symbols and periods, recompute targets, PIT-replay requirement and incremental/full-rebuild decision.

## 5. Affected-scope rules

Incremental execution is permitted only when the affected scope is explicit and within the frozen limits:

- affected symbols no more than 20% of the accepted Universe;
- financial restatements no more than 10% of the Universe;
- no more than 12 dependent periods per affected symbol;
- unchanged symbol row hashes must remain identical;
- a full-Universe rewrite may not be silently labeled incremental.

Schema, contract, source-route or PIT-policy changes force a full rebuild regardless of affected-symbol count.

## 6. Promotion policy

The operating sequence is fail-closed:

`detect -> validate event -> derive scope -> build isolated candidate -> independently validate and replay -> publish immutable Release and Current -> update Last-success`

Promotion requires all required shards, exact expected Universe, source and output hashes, zero future-information errors, independent validation and no hard failures. Partial candidate promotion is prohibited.

## 7. Rollback policy

- Last-known-good remains active until the new candidate is fully published;
- failed candidates cannot modify Current or Last-success;
- Release and Archive are immutable;
- rollback can target only a previously accepted Release;
- rollback changes the active pointer, not the historical Release contents;
- failed candidate artifacts are retained for diagnosis.

## 8. Idempotence

The same source inputs, contract version and baseline must produce the same semantic outputs. Duplicate delta-event IDs and repeated event application are prohibited. Later FMDL-3E-D/E tests will verify idempotence, fault recovery and rollback with real runs and injected failures.

## 9. Outputs

- `FMDL3EA_BASELINE_MANIFEST.json`
- `FMDL3EA_BASELINE_SYMBOL_HASHES.parquet`
- `FMDL3EA_DELTA_EVENT_CATALOG.csv`
- `FMDL3EA_INCREMENTAL_INTERFACE.json`
- contract snapshot, decision, validation and manifest;
- immutable Release, Current, Archive and `FMDL3EA_LAST_SUCCESS.json`.

## 10. Authority boundary

FMDL-3E-A governs data operations only. It does not create a valuation conclusion, target price, candidate-pool mutation, simulation or real-account change, portfolio action or trade instruction.

Authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`

Trade authority: `NONE`

## 11. Exit and next gate

Exit:

`FMDL3EA_INCREMENTAL_REFRESH_CONTRACT_ACCEPTED`

Next:

`FMDL-3E-BC — Market and Financial Incremental Refresh`
