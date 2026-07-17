# FMDL-2A Historical Source Benchmark — Retry-Aware Final

- Run ID: `FMDL2A_R2_20260717T111038+0800`
- Generated at: `2026-07-17T11:10:38+08:00`
- Current as-of date: `2026-07-16`
- AKShare version: `1.18.64`
- Scale sample: `120` symbols
- Production readiness: `READY_FOR_FMDL_2B`
- Primary provider: `sina_daily`

## Scale results

| Provider | Scope | Attempts | Success | Latest | Volume | Amount | Median sec | P95 sec |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| sina_daily | FULL_SCALE | 120 | 99.2% | 99.2% | 100.0% | 100.0% | 1.4446 | 15.9608 |
| tencent_hist | FALLBACK_SUBSAMPLE | 40 | 100.0% | 100.0% | 0.0% | 100.0% | 2.386 | 2.5444 |

## Routing decision

- `SH_MAIN`: primary=`sina_daily`, price fallback=`tencent_hist`
- `SZ_MAIN`: primary=`sina_daily`, price fallback=`tencent_hist`
- `STAR`: primary=`sina_daily`, price fallback=`None`
- `CHINEXT`: primary=`sina_daily`, price fallback=`None`
- `BSE`: primary=`sina_daily`, price fallback=`None`

## Decision boundary

The benchmark selects a technical data route only. It does not demonstrate alpha, rank stocks, change a portfolio or create trade permission.
