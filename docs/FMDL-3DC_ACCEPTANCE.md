# FMDL-3D-C — Final Acceptance

## 1. Acceptance status

`FMDL3DC_VALUATION_ENGINE_CURRENT_ACCEPTED`

Accepted candidate:

- Head: `ed263748cf860b4125a9cab372f945286362a0b4`;
- workflow: `29686939875` — success;
- artifact: `8442396810`;
- artifact digest: `sha256:d36c2645da8361fb9240f2411f03c85b6ff303254bf3615b0aba1ceaa641e15f`;
- candidate release: `FMDL3DC_20260719T202626+0800`;
- independent validation: `PASS`;
- hard failures: `0`;
- authority: `DATA_AND_RESEARCH_EVIDENCE_ONLY`;
- trade authority: `NONE`.

## 2. Source bindings

- valuation contract: `FMDL3DA_20260719T190213+0800`;
- capitalization Current: `FMDL3DB_20260719T200447+0800`;
- financial denominator engine: `FMDL3CB_20260719T121912+0800`;
- market source release: `FMDL1BC_20260717T174015+0800`;
- market as-of date: `2026-07-17`.

## 3. Measured full-Universe result

- Universe / valuation Current rows: `5,528 / 5,528`;
- valuation metrics: `7`;
- metric detail rows: `38,696` (`5,528 × 7`);
- point-in-time financial input rows inspected: `46,693`;
- valid or warning / decision-grade metric rows: `24,436 / 24,436`;
- capitalization coverage: `99.909551%`;
- core denominator-resolved ratio: `93.691834%`;
- capitalization quarantine: `5` symbols;
- future-denominator controlled rows: `10`;
- future selected denominators: `0`;
- formula replay errors: `0`;
- denominator-sign errors: `0`;
- schema errors / manifest errors: `0 / 0`;
- automatic action authority: `0`;
- trade authority: `NONE`.

## 4. Valid valuation coverage

- PE TTM: `3,686`;
- earnings yield TTM: `3,686`;
- PB: `5,149`;
- PS TTM: `5,073`;
- FCF yield TTM: `5,076`;
- EV/Sales TTM: `1,016`;
- EV/operating income TTM: `750`.

The lower EV coverage is controlled and expected because EV metrics require all debt and cash components. Missing components remain null and are never inferred as zero.

## 5. Controlled states

The full metric matrix preserves explicit outcomes:

- `VALID`: `20,995`;
- `VALID_WITH_WARNING`: `3,441`;
- `NON_POSITIVE_EARNINGS`: `2,974`;
- `NON_POSITIVE_BOOK_EQUITY`: `33`;
- `NON_POSITIVE_REVENUE`: `2`;
- `NON_POSITIVE_OPERATING_INCOME`: `266`;
- `INVALID_ENTERPRISE_VALUE`: `2`;
- `NOT_APPLICABLE_SECTOR`: `388`;
- `SECTOR_PROFILE_UNRESOLVED`: `2,296`;
- `MISSING_REQUIRED_INPUT`: `7,743`;
- `QUARANTINED_INPUT`: `511`;
- `FUTURE_DENOMINATOR_BLOCKED`: `10`;
- `CONTROLLED_CAPITALIZATION_QUARANTINE`: `35`.

Invalid and controlled rows have null metric values. No neutral or zero fill is used.

## 6. Point-in-time and denominator acceptance

The accepted candidate proves:

- zero financial denominator selected after the market-close cutoff;
- later financial information cannot backfill the earlier valuation snapshot;
- non-positive parent earnings cannot create a valid PE or earnings yield;
- non-positive parent equity cannot create a valid PB;
- non-positive revenue cannot create a valid PS or EV/Sales;
- non-positive operating income cannot create valid EV/operating income;
- negative free cash flow remains valid negative evidence with a warning;
- incomplete debt or cash inputs cannot create a valid EV metric;
- every valid metric carries capitalization and financial fact lineage.

## 7. Sector acceptance

PE, earnings yield and PB may be calculated for accepted general and financial profiles when denominator rules pass. PS, FCF yield and EV metrics are limited to the general non-financial profile.

Independent validation found `0` ordinary-company valuation metrics published as valid for a non-general profile.

## 8. Publication boundary

This phase publishes valuation evidence only. It does not create:

- a composite valuation score;
- cheap/expensive investment conclusions;
- target prices;
- candidate-pool promotion or rejection;
- simulation or real-account actions;
- trade authority.

## 9. Controlled limitations

- valuation uses latest completed-session capitalization, not intraday prices;
- sector profiles remain the accepted FMDL-3C evidence-based profiles pending a hardened industry master;
- EV metrics have deliberately limited coverage because missing debt and cash components remain null;
- provider PE, PB and PS remain cross-check evidence only;
- dividend, buyback, issuance and shareholder-yield Current remain FMDL-3D-D work.

## 10. Next gate

`FMDL-3D-D_SHAREHOLDER_RETURN_EVENT_CURRENT`
