# HKCU P4-1R Portfolio Context Completion

## Purpose

P4-1R repairs the decision-critical evidence gaps exposed by the first real P4-1 run. It does not change the 70 formal HK Candidate members, either portfolio, target weights, cash, orders or trade authority.

## Repair surface

The original P4-1 global register identified four missing surfaces: sector/industry, factor/style look-through, marginal diversification/downside-risk, and expected-return/opportunity-cost context. Audit of the full 2,100-rule output also showed P4R07/P4R09 deferrals from unresolved exact A/H codes and pooled fund/ETF look-through. P4-1R therefore completes all six dimensions rather than mechanically closing only the four global rows.

### 1. Exact A/H identity

P4-1R uses the already accepted P2B-E1 A/H pair registry `evidence/hkcu_p2b/HKCU_P2B_AH_PAIR_REGISTRY_20260807.csv`. The 13 `TRUE_AH_PAIR` records are joined by exact H-share code and carry their accepted exact A-share code and exchange evidence. The production P4-1R build does not depend on a live A/H comparison endpoint. Fuzzy issuer-name matching remains prohibited.

### 2. Economic sector / industry

P4-1R uses the bounded exact-identity registry `evidence/hkcu_p4_1r/HKCU_P4_1R_ECONOMIC_SECTOR_REGISTRY_20260807.csv` for direct security economic-sector context. It contains exactly 86 rows: 70 formal HK Candidates and 16 direct A-share holdings. Each row preserves `security_id`, broad `economic_sector`, descriptive `industry_detail`, evidence lineage, assessment date and `trade_authority=NONE`.

These sector assignments are explicitly accepted secondary research classifications used for portfolio overlap and concentration context; they are not HKEX official issuer semantics and may not masquerade as a new security master. Listing taxonomy and P2A sleeve labels are not used as industry substitutes. The production build does not require a live company-profile or A-share individual-info endpoint.

Bond funds remain `FIXED_INCOME`; broad equity ETFs remain `MULTI_SECTOR_EQUITY`. A pooled vehicle is never assigned one fabricated single-stock industry.

### 3. Common style context

The five accepted P2A sleeves map deterministically to five descriptive portfolio styles: QUALITY, INCOME_VALUE, MOMENTUM_LIQUID, DEFENSIVE and RECOVERY_CYCLICAL. Existing portfolio assets retain explicit asset-class or portfolio-bucket evidence rather than receiving neutral-filled Candidate labels.

### 4. Marginal risk / diversification

Candidate price history comes from the accepted FMDL-5C vendor history. Current portfolio holdings use a Canonical-first history policy: held A-share stocks are read from the accepted FMDL-2B-4 Composite History; pooled ETFs and funds fall back to their existing governed public market/NAV history route only where the Canonical stock history does not apply. P4-1R computes market-value-weighted account return histories without zero-return filling, then records candidate/account correlation, downside correlation, volatility and a governed qualitative marginal-risk state. Minimum history and account market-value coverage are contract-controlled.

#### P4-1R-R1 Canonical Data Adapter acceptance

R1 repaired two data-interface defects without changing investment logic:

- accepted FMDL-5C history schema now recognizes `observation_date` and accepted `adj_close`/`close` fields;
- held A-share stocks now use accepted Composite History before any live-provider fallback.

The real Canonical-input run independently validated:

- `CTX_MARGINAL_RISK`: 142 -> 0;
- REAL account history market-value coverage: 82.11%, above the 65% contract minimum;
- SIMULATION account history market-value coverage: 92.73%, up from 0%;
- FMDL-5C history range recognized as 2023-01-03 through 2026-07-21, within the contract freshness tolerance for the 2026-08-07 assessment date;
- total residual decision-critical gaps: 242 -> 100, entirely outside R1 scope;
- Candidate, Simulation, Real Account, allocation and order mutations remain zero; `trade_authority=NONE`.

R1 therefore closed the Canonical history adapter repair.

#### P4-1R-R2 Industry + Exact A/H Evidence acceptance

R2 removed the remaining decision-critical dependency on live industry and A/H endpoints. Exact A/H identity is sourced from the accepted P2B-E1 registry, while direct-security economic sector is sourced from the bounded 86-row P4-1R registry described above.

The real P4-1R run independently validated:

- Candidate industry coverage: 70/70 = 100%;
- exact A/H mapping: 13/13 confirmed `TRUE_AH_PAIR` Candidates;
- Account×Security context ready: 140/140;
- REAL account history market-value coverage: 82.11%;
- SIMULATION account history market-value coverage: 92.73%;
- residual decision-critical gaps: 100 -> 0;
- operational status: `PASS_P4_1R_PORTFOLIO_CONTEXT_COMPLETION`;
- next gate: `P4_1_PORTFOLIO_FIT_REASSESSMENT`;
- Candidate, Simulation, Real Account, allocation and order mutations remain zero; `trade_authority=NONE`.

The independent validator returned `PASS` with zero errors and zero residual gaps. R2 therefore closes the Industry + Exact A/H evidence repair.

### 5. Opportunity cost

P4-1R does not fabricate point expected returns. It uses current accepted valuation anchor, trailing 120-day return and 120-day max drawdown in an unweighted Pareto comparison across the 70 formal Candidates. Quantile bands are distribution-derived; there is no weighted alpha score or fixed Top-N. Trailing return remains historical context, not a forecast.

### 6. Pooled exposure semantics

Existing ETFs/funds remain explicit pooled exposures. Their presence is a named constraint, not an automatic P4R09 defer once the account-level economic/style/risk context is otherwise complete. Same-issuer A/H exposure is also a named overlap constraint rather than automatic rejection, consistent with P4-0.

## Outputs

The real run writes Candidate Context, Account Holding Context, Account×Security Context, residual gaps, decision, quality, manifest, and the bounded A/H source snapshot used by the build. A PASS requires 70 Candidate rows, 24 current holding rows, 140 Account×Security rows and zero residual decision-critical gaps.

## Phase boundary

P4-1R may complete context and trigger a P4-1 reassessment. It may not size, allocate, admit, trade or mutate either portfolio. `trade_authority=NONE`.

R1 and R2 have now closed the substantive context-repair defects. The remaining P4-1R-R3 gate is final acceptance only: freeze the repaired evidence surface, run the clean final head, audit the complete diff/check set and unresolved review threads, then mark the PR ready and merge only if all gates remain green. Portfolio-fit reassessment begins only after that controlled merge.
