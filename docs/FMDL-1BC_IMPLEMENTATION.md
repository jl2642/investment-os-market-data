# FMDL-1B/C Implementation — A-share Universe + Daily Market Snapshot

## Scope

This batch implements real, free-source ingestion for:

- `a_share_universe`
- `daily_market_snapshot`
- trading-calendar support used to select the latest completed session
- candidate manifests and quality reports

It does not promote data into `outputs/current/`; stable publication, scheduling hardening and Investment OS consumption remain FMDL-1D/E/F responsibilities.

## Selected AKShare functions

| Purpose | Function | Requirement |
|---|---|---|
| Market-wide identity and market snapshot | `stock_zh_a_spot_em` | Required |
| Shanghai main-board master | `stock_info_sh_name_code("主板A股")` | Optional enrichment |
| STAR Market master | `stock_info_sh_name_code("科创板")` | Optional enrichment |
| Shenzhen A-share master | `stock_info_sz_name_code("A股列表")` | Optional enrichment |
| Beijing Stock Exchange master | `stock_info_bj_name_code()` | Optional enrichment |
| Trading calendar | `tool_trade_date_hist_sina()` | Optional with conservative weekday fallback |

The required market-wide source is retried four times. Optional exchange-master failures do not fabricate fields; they create warnings and reduce the relevant fill ratios.

## Data semantics

- Canonical symbol: `000001.SZ`, `600000.SH`, `832000.BJ`.
- Universe includes ST, suspended and recent IPO securities; FMDL-2 owns screening exclusions.
- Eastmoney/AKShare `成交量` is treated as lots and converted to shares with a multiplier of 100.
- `pe_ttm` temporarily receives the free-source dynamic PE field and carries an explicit limitation until FMDL-3.
- A candidate is retained on soft-gate warnings but hard-gate failure exits non-zero and prevents acceptance.

## Candidate outputs

```text
outputs/candidate/
├── A_SHARE_UNIVERSE.csv
├── DAILY_MARKET_SNAPSHOT.csv
├── A_SHARE_UNIVERSE_MANIFEST.json
├── DAILY_MARKET_SNAPSHOT_MANIFEST.json
├── A_SHARE_UNIVERSE_QUALITY.json
├── DAILY_MARKET_SNAPSHOT_QUALITY.json
├── FMDL_1BC_RUN_REPORT.json
└── FMDL_1BC_RUN_REPORT.md
```

Raw market-wide evidence is retained under `datasets/raw/<date>/<run_id>/` for the first acceptance run.

## Acceptance

FMDL-1B/C can be accepted only after GitHub-hosted execution produces real files and both datasets have no hard quality failures. Soft warnings, especially industry or listing-date coverage from optional free endpoints, must remain visible.
