# FMDL-6X4-A｜Public Equity Investing Adapter & Contract Mapping

## Objective

Translate the accepted FMDL-6X3 research-production baseline into explicit Public Equity Investing workflow contracts without executing those workflows or mutating Investment OS state.

## Adapter boundary

The adapter maps seven members of `US_RESEARCH_BENCHMARK_POOL_V1` across fourteen Public Equity Investing workflows. Every mapping is assigned one of four states:

- `PARTIAL_ADAPTER_READY`: a source-backed payload can be handed to the workflow, but the workflow still requires its own runtime source checks and may remain screen-grade or partial.
- `HUMAN_CONFIRMATION_REQUIRED`: the stored evidence can seed the workflow, but the user must first define the investment question, meeting context, base case or thesis.
- `BLOCKED_REQUIRED_INPUTS_MISSING`: a load-bearing source or model input is absent; the workflow must not be executed from the stored payload alone.
- `NOT_APPLICABLE_REFERENCE_INSTRUMENT`: the issuer workflow does not apply to the benchmark reference instrument.

## Initial readiness

- `company-tearsheet`: partial adapter payload for all seven validation-pool members.
- `financials-normalizer`: partial quarterly payload for AAPL, MSFT and NVDA; blocked for JPM, BRK.B and XOM; not applicable to QQQ.
- scenario, thesis-tracker and meeting-prep routes require user confirmation before execution.
- earnings, valuation, model, catalyst, pitch, memo and initiating-coverage routes remain blocked until their workflow-owned inputs are available.

## Non-negotiable separation

- An adapter payload is not a completed Public Equity Investing artifact.
- A Research Card is not an investment recommendation.
- The benchmark pool is not the Investment OS candidate pool.
- Source-category mapping is not proof that a connector is installed, authorized or readable in a future run.
- No workflow execution, investment recommendation, candidate promotion, simulation action, real-account action or order is authorized in FMDL-6X4-A.

## Exit

Acceptance means the workflow registry, source-category requirements, security-workflow matrix, adapter payloads, blockers and human-confirmation queues are deterministic, recoverable and auditable. It opens only `FMDL-6X4-B_RESEARCH_WORKFLOW_INTEGRATION_AND_EVIDENCE_REGISTRATION`.
