# HKCU P4-1R Portfolio Context Completion

## Purpose

P4-1R repairs the decision-critical evidence gaps exposed by the first real P4-1 run. It does not change the 70 formal HK Candidate members, either portfolio, target weights, cash, orders or trade authority.

## Repair surface

The original P4-1 global register identified four missing surfaces: sector/industry, factor/style look-through, marginal diversification/downside-risk, and expected-return/opportunity-cost context. Audit of the full 2,100-rule output also showed P4R07/P4R09 deferrals from unresolved exact A/H codes and pooled fund/ETF look-through. P4-1R therefore completes all six dimensions rather than mechanically closing only the four global rows.

### 1. Exact A/H identity

A/H mapping uses the Eastmoney A/H comparison surface through AKShare and joins by exact H-share code. Fuzzy issuer-name matching is prohibited. A Candidate already flagged TRUE_AH_PAIR must obtain exactly one A-share code or remain a residual context gap.

### 2. Economic sector / industry

HK Candidate industry uses the Eastmoney Hong Kong company profile field `所属行业` through AKShare. Direct A-share portfolio holdings use the Eastmoney A-share individual-info industry field. These are explicitly secondary research classifications, not HKEX official issuer semantics. Listing taxonomy and P2A sleeve labels may not masquerade as industry.

Bond funds are classified as `FIXED_INCOME`; broad equity ETFs are `MULTI_SECTOR_EQUITY`. A pooled vehicle is never assigned one fabricated single-stock industry.

### 3. Common style context

The five accepted P2A sleeves map deterministically to five descriptive portfolio styles: QUALITY, INCOME_VALUE, MOMENTUM_LIQUID, DEFENSIVE and RECOVERY_CYCLICAL. Existing portfolio assets retain explicit asset-class or portfolio-bucket evidence rather than receiving neutral-filled Candidate labels.

### 4. Marginal risk / diversification

Candidate price history comes from the accepted FMDL-5C vendor history. Current portfolio holdings use public market/NAV histories through AKShare. P4-1R computes market-value-weighted account return histories without zero-return filling, then records candidate/account correlation, downside correlation, volatility and a governed qualitative marginal-risk state. Minimum history and account market-value coverage are contract-controlled.

### 5. Opportunity cost

P4-1R does not fabricate point expected returns. It uses current accepted valuation anchor, trailing 120-day return and 120-day max drawdown in an unweighted Pareto comparison across the 70 formal Candidates. Quantile bands are distribution-derived; there is no weighted alpha score or fixed Top-N. Trailing return remains historical context, not a forecast.

### 6. Pooled exposure semantics

Existing ETFs/funds remain explicit pooled exposures. Their presence is a named constraint, not an automatic P4R09 defer once the account-level economic/style/risk context is otherwise complete. Same-issuer A/H exposure is also a named overlap constraint rather than automatic rejection, consistent with P4-0.

## Outputs

The real run writes Candidate Context, Account Holding Context, Account×Security Context, residual gaps, decision, quality, manifest, and a source snapshot of the A/H comparison surface. A PASS requires 70 Candidate rows, 24 current holding rows, 140 Account×Security rows and zero residual decision-critical gaps.

## Phase boundary

P4-1R may complete context and trigger a P4-1 reassessment. It may not size, allocate, admit, trade or mutate either portfolio. `trade_authority=NONE`.
