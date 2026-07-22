# FMDL-6X2 START HERE

Canonical entry status: `FMDL6X1_FINAL_ACCEPTED`  
Entry pointer: `outputs/status/FMDL6X1_LAST_SUCCESS.json`  
Authorized first phase: `FMDL-6X2-A_CURRENT_SECURITY_MASTER_PRODUCTION`  
Research Production Gate: `OPEN_FOR_FMDL6X2_DATA_PRODUCTION`  
Brokerage & Real-Account Gate: `CLOSED_NO_CHANNEL`  
Trade authority: `NONE`

## Fixed execution sequence

1. FMDL-6X2-A — Current Security Master Production
2. FMDL-6X2-B — Issuer Identity, Classification & Review Queues
3. FMDL-6X2-C — Historical Listing & Lifecycle Backfill
4. FMDL-6X2-D — Market History, Corporate Actions & FX Store
5. FMDL-6X2-E — SEC Filings & Financial Facts Store
6. FMDL-6X2-FINAL — Full Store Reconciliation & Operational Acceptance

Do not start a later phase without the prior phase Last-success. Do not infer brokerage eligibility from research eligibility. No automatic order execution is authorized.
