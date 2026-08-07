# HKCU-1 Failure / Recovery Runbook

## Purpose

HKCU-1 must operate as a low-touch eligibility service, not as a workflow that requires a human to debug every external-source failure. This runbook converts observed incidents into deterministic operating behavior.

## Failure classes

| Class | Meaning | Automated action | Canonical action |
|---|---|---|---|
| `TRANSIENT_INFRA` | GitHub Actions / network timeout / connection reset before a valid source response | bounded retry; a later scheduled run may retry again | keep previous Canonical |
| `SOURCE_BLOCKED` | official source reachable policy blocks the runner, e.g. SSE HTTP 403/429 | try bounded official acquisition paths; retain diagnostic evidence; use LKG only for continuity | keep previous Canonical; no publication |
| `DATA_CONTRACT_CHANGE` | official source responds but payload schema/signature/metadata changes | fail closed and require adapter review | keep previous Canonical |
| `CODE_DEFECT` | deterministic internal logic/test failure | fix code and add regression test | no publication until fixed |
| `UNKNOWN` | failure cannot yet be safely classified | fail closed | keep previous Canonical |

## Fresh vs stale evidence

`FRESH_PASS` means the current run obtained and validated fresh official evidence and may build a new release candidate.

`DEGRADED_CONTINUITY` means the current official acquisition failed but a recent last-known-good snapshot exists. The LKG may be used only to preserve continuity, compare holdings/candidates, and explain the last verified state. It must not be relabelled as current and must not advance Canonical.

`BLOCKED_NO_FRESH_SOURCE` means no usable fresh official source is available and the LKG is missing or too old. No release candidate may be published.

## SSE production policy

1. Use official `sse.com.cn` / `sseinfo.com` paths only.
2. Prefer a real Chromium page network/download path for the protected workbook.
3. Record landing and payload HTTP status, cookies, request/response headers, file size, signature and SHA-256.
4. Treat 403/429 as `SOURCE_BLOCKED`, not as a code defect.
5. A later scheduled run may obtain a different GitHub hosted-runner egress and recover without code changes.
6. Never substitute a broker, financial portal or search-engine list.
7. If fresh SSE acquisition fails, retain the previous Canonical and explicitly mark the run degraded.

## SZSE production policy

1. Use the official paginated JSON endpoint only.
2. Enforce metadata identity, page count and declared record count.
3. Retry transient connection resets with bounded backoff.
4. Re-run normalization independently and require identical hashes.

## Mutable-data rule

Live counts, dates, page counts and security membership are data, not constants. Validation must reconcile against official declared metadata or deterministic cross-run hashes. Never hard-code a live list size such as `651`.

## Sell-only rule

An official adjustment `OUT` event removes new-buy eligibility but does not automatically destroy disposal rights. If the security remains listed on HKEX, channel status becomes `SELL_ONLY`. `NOT_ELIGIBLE` is reserved for a separate explicit terminal condition. Sell-only securities must never enter the buyable Investable Universe.

## Scheduled-operation target

After Phase 1 promotion, a scheduled HKCU-1 run should:

1. fetch fresh official buy lists and adjustment notices;
2. retry transient failures within bounded limits;
3. classify unresolved failures;
4. normalize and reconstruct point-in-time channel status;
5. run deterministic replay, count/hash, future-leakage and sell-only contamination gates;
6. publish a new release candidate only if all freshness and quality gates pass;
7. otherwise keep previous Canonical unchanged and emit a compact failure/recovery artifact for the next run.

Human intervention should be required only for a new failure class, an official contract change, or a persistent source block beyond the configured continuity window.

`trade_authority=NONE` throughout HKCU-1.
