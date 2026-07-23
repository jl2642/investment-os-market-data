# FMDL-6X4-D Release Readiness

Required pre-merge evidence:

- contract and roadmap reconciliation pass;
- regression suite passes;
- producer and tests compile;
- real candidate build passes against accepted Release 44 and FMDL-6X3-D inputs;
- independent same-input replay is byte-identical;
- candidate artifact contains the control, attribution, recovery, queue, quality, decision, handoff and Manifest outputs;
- zero mutation and `trade_authority = NONE` remain explicit.

Required main publication:

- Release sequence 45;
- Current, immutable Release and normalized copies;
- Last-success and LKG pointers;
- next gate `FMDL-6X4-E_CROSS_MARKET_COMPARABILITY_AND_OPERATING_RUNBOOK`.
