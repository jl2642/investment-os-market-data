# Research Queue D2 Auto Consumer

## Purpose

Close the operating gap between `RESEARCH_QUEUE_D1_CURRENT` routing and D2 deep research. D1 may route names to D2; the user must not need to manually start the research pipeline.

## Trigger contract

1. **Event trigger:** any accepted `main` change to D1 Current or D1 evidence wakes the D2 consumer.
2. **Recovery cadence:** weekdays at **08:35 Asia/Shanghai** (`00:35 UTC`) to recover from a missed event or transient failure.
3. **Manual `workflow_dispatch`:** retained only as a break-glass control. It is not part of normal operations.
4. **Bounded batch:** at most 3 D2-routed names are expected per operating batch.
5. **Idempotence:** a completed item with an unchanged D1 input watermark is not reset.

## Two-layer research model

GitHub Actions owns deterministic queue materialization, liveness, and primary-disclosure discovery. It uses the existing AkShare dependency to query CNINFO metadata and stores source lineage.

Semantic D2 research is intentionally **not faked by deterministic code**. It is owned by the ChatGPT-native D2 research consumer, which must answer the D1 `d2_questions` from primary/public evidence and may mark an item complete only after evidence gates pass.

If primary evidence is unavailable, the item remains `AUTO_RESEARCH_BLOCKED_PRIMARY_SOURCE_DISCOVERY`. A blocked item is still automatically operated; it does **not** mean the user must manually trigger it.

## Operating state

- `investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_CURRENT.json`
- `investment_os_runtime/30_STATE_CURRENT/30_RESEARCH/RESEARCH_QUEUE_D2_LIVENESS_CURRENT.json`
- `investment_os_runtime/40_EVIDENCE_AND_LINEAGE/RESEARCH_QUEUE_D2/`

Required liveness fields include pending, completed and blocked counts, oldest pending attempt, last consumer attempt, recovery cadence and `manual_trigger_required`.

## Hard boundaries

D2 automation cannot mutate:

- Candidate membership;
- Real account;
- Simulation account;
- Decision/implementation state;
- orders.

`trade_authority = NONE` at every layer.
