# HKCU P2B-E1 — Common Transaction/Tax and A/H Pair Evidence

P2B-E1 is the first real evidence-collection gate after the 77-name P2B baseline.

It closes two evidence families that can be resolved without subjective company scoring:

1. **Common Southbound transaction and tax rules** for all 77 names.
2. **A/H same-issuer applicability** for all 15 P2B leads.

## What is evidenced

As of 2026-08-07, the common market evidence records the current HKEX mandatory transaction charges, the suspended Investor Compensation Levy, freely negotiable brokerage, the current PRC individual capital-gains IIT exemption through 2027-12-31, and the Southbound dividend withholding treatment.

Brokerage is deliberately left as a variable input. P2B-E1 must not invent a broker tariff or position size.

## A/H normalization

The 15 upstream leads resolve to:

- **13 true same-issuer A/H pairs**
- **2 not applicable**
  - `06990 SKB BIO`: the A-listed 002422 entity is its controlling parent, not the same issuer.
  - `02799 CITIC FAMC`: the issuer has Domestic Shares and H Shares; the Domestic Shares are not an exchange-listed A-share class.

This resolves applicability only. It does not yet compute an A/H premium/discount; synchronized prices and FX belong to the downstream valuation stage.

## Remaining P2B work

After P2B-E1, 231 company-specific evidence tasks remain:

- Governance / value-trap: 77
- Earnings-expectation revision: 77
- Catalyst: 77

P2B-E1 creates no Candidate graduation, portfolio mutation, order, or trade authority.

`trade_authority=NONE`.
