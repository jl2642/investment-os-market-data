# Investment OS Control Runtime v1.0.1

This runtime is a deterministic control, validation and publication layer.

It validates:

- authority and schema boundaries;
- market capability bindings;
- freshness and semantic-change gates;
- cross-market permissions;
- event E0—E5 routing;
- operating-product promotion;
- attribution non-claims;
- rule-change governance;
- zero unauthorized mutation.

It does **not** perform fundamental research, choose stocks, connect to a broker,
place orders or mutate investment state automatically.

Current run: `WP1_5C_RUNTIME_BINDINGS_OPERATIONS_20260724_001`  
Automation activation: `DISABLED_UNTIL_WP6`  
Trade authority: `NONE`

## WP1-5E forward-compatibility repair

Fresh A-share data is accepted by the control gate. Stale data must still be
blocked for live action. The validation date is no longer hard-coded and may
be supplied with `--evaluation-date`; otherwise the current runtime date is used.
