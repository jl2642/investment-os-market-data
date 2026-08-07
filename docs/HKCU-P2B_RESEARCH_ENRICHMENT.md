# HKCU Phase 2B — Evidence-Controlled Research Enrichment

## Purpose

P2B begins only after P2A has been independently accepted. Its job is to turn the accepted 77-name Research Longlist into an evidence-controlled research queue. It does **not** graduate a formal Candidate Pool and does not create portfolio or trading authority.

## Upstream lock

P2B reads `outputs/hkcu_p2a/current/HKCU_P2A_ACCEPTANCE.json`, deterministically rebuilds P2A from the accepted HKCU Current, reruns the independent P2A validator, and checks the rebuilt output hashes against the accepted P2A hashes.

Any upstream drift fails closed. P2B may not silently research a different Longlist.

## Security-type first

The 77 securities are segmented before qualitative research because the same accounting and leverage heuristics are not transferable across all issuer types.

Current supported types:

- `GENERAL_NON_FINANCIAL`
- `BANK`
- `INSURANCE`
- `SECURITIES_AND_BROKERAGE`

An unknown type fails safe to `UNKNOWN_RESEARCH_REQUIRED`; it is not forced into an industrial-company template.

## Five research dimensions

P2B owns the dimensions intentionally excluded from P2A scoring:

1. `GOVERNANCE_VALUE_TRAP`
2. `EARNINGS_EXPECTATION_REVISION`
3. `CATALYST`
4. `TRANSACTION_COST_TAX`
5. `A_H_RELATIVE_VALUATION`

No qualitative score exists before evidence. Trailing P2A factors cannot be used as substitutes for consensus revision, catalyst or governance evidence.

## A/H applicability correction

P2A intentionally sent possible A/H work downstream as a conservative research gap. P2B applies a tighter rule:

- `h_share_flag` alone does **not** make A/H relative valuation applicable;
- `a_share_class_exists` is only an applicability lead;
- the evidence-collection stage must still prove that the A-share and H-share are share classes of the **same issuer**;
- parent/subsidiary or merely related A-share listings are `NOT_APPLICABLE`.

This applicability normalization changes the research queue only. It does not alter the accepted P2A rank or 77-name membership.

## Baseline outputs

The first P2B gate emits:

- `HKCU_P2B_SECURITY_TYPE_MATRIX.csv`
- `HKCU_P2B_DIMENSION_MATRIX.csv`
- `HKCU_P2B_RESEARCH_QUEUE.csv`
- `HKCU_P2B_QUALITY_REPORT.json`
- `HKCU_P2B_DECISION.json`
- `HKCU_P2B_MANIFEST.json`

The baseline is complete only when the exact 77-name P2A state is hash-locked, every security is typed, every security has five dimension records, inapplicable A/H work is explicitly removed, and all unevidenced dimensions remain unscored.

## What baseline PASS means

`PASS_P2B_BASELINE_EVIDENCE_COLLECTION_REQUIRED` means the research operating surface is valid and evidence collection may start. It explicitly does **not** mean P2B itself is finished.

The next gate is `P2B_EVIDENCE_COLLECTION`, where source-backed issuer/exchange/regulatory/market evidence is collected and normalized. Only after that evidence gate may P2B produce a research-enriched ranking for the later P2C / formal Candidate graduation process.

## Governance

P2B must not:

- change A-share Candidate Current;
- change HK formal Candidate state before its later graduation gate;
- change Simulation or Real Portfolio holdings;
- create orders;
- grant trade authority.

`trade_authority=NONE` remains mandatory.
