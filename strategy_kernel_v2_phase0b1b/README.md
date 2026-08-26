# Strategy Kernel v2 — Phase 0B + 1B

Status: **SHADOW / RESEARCH-ONLY / NOT EFFECTIVE POLICY**

This package binds the Strategy Kernel v2 experiment to Canonical `main` SHA `5c5df9082688f65332c79fef3b9cbfa893a06908`.

Scope:
- semantic audit of all 11 `investment_os_runtime/10_CORE_STATIC/` modules;
- repo-bound shadow Decision Object v2 adapter for 601138, 605090, HKEX:00669 and D2 research states;
- explicit missing-valuation semantics so the system never fabricates expected returns merely to make an idea comparable;
- regression tests that preserve existing no-trade decisions and authority boundaries.

Non-scope / invariants:
- no effective Core Static or Policy change;
- no Real/Simulation economic-state mutation;
- no Candidate membership/tier mutation;
- no target-portfolio writeback;
- no order authorization or execution;
- `orders=0`, `trade_authority=NONE`.

Phase 0B is an architectural audit, not a conclusion that legacy gates are too strict. Phase 3 point-in-time replay will test false positives, false negatives, regret, turnover, downside and decision calibration before any migration proposal.
