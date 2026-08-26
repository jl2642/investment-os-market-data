# Strategy Kernel v2 — Phase Execution Plan

## Global acceptance controls
Every phase must preserve: `orders=0`, `trade_authority=NONE`, mutation permissions false, Canonical source provenance, and no direct write to protected `main`.

### Phase 0B — COMPLETE
Input: Canonical Core Static on main. Output: semantic rule inventory and treatment map. Acceptance: no effective Core Static rewrite.

### Phase 1B — COMPLETE
Input: existing Canonical decisions/research/account states. Output: Decision Object v2 shadow adapter. Acceptance: canonical no-trade decisions preserved; missing valuation never fabricated.

### Phase 1C — UNDERWRITING EXTRACTION — VALIDATED SHADOW-ONLY
**Objective:** extract, not invent, the underwriting already contained in Canonical research.

**Coverage set:** 601138.SH, 605090.SH, HKEX:00669, 000719.SZ, 002039.SZ, 301215.SZ, 000333.SZ, 600900.SH.

**Required fields where evidenced:** business economics, normalized earnings/cash flow, durability, balance-sheet/capital-allocation observations, thesis, falsifiers, valuation evidence, portfolio context, research quality, explicit gaps and provenance.

**Acceptance:**
- all 8 objects generated deterministically from explicit extraction specifications;
- gaps are explicit and block promotion when material;
- D2 complete is not treated as BUY/Candidate permission;
- price-only trigger is not a user decision;
- concentration alone is not a trim/sell signal;
- accepted 601138 no-trade semantics are preserved;
- no valuation scenario is created unless explicitly supplied by Canonical evidence;
- shadow comparison readiness is separately encoded from decision readiness;
- all mutation permissions false; `orders=0`; `trade_authority=NONE`.

**Validation:** 11/11 regression tests pass; 8/8 generated objects pass `underwriting_object_v1.schema.json`; deterministic generated bundle matches the registry.

### Phase 2 — SHADOW CAPITAL COMPARATOR — NOT STARTED
**Precondition:** consume only objects whose `comparison_readiness` is `READY_NOW` or whose specified `refresh_requirements` have been satisfied by a fresh governed research input. Do not silently override stale or missing valuation/fundamental gates.

Comparator output is research-only relative ranking/diagnostics. It may compare existing positions, candidates, ETFs and cash, but cannot create a user decision or economic mutation.

### Phase 3 — POINT-IN-TIME REPLAY / CALIBRATION
Mandatory before any effective policy relaxation or migration. Replay using only contemporaneously available evidence; assess forecast calibration, false-negative reduction, false-positive cost, downside capture, turnover and opportunity-cost regret.

### Effective migration
Separate governed proposal only after Phase 3. Never inferred from shadow research performance alone.
