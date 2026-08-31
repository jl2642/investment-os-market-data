from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

VALID_STATES = {"VALID", "VALID_WITH_WARNING"}
TRADE_AUTHORITY = "NONE"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _clean_value(value: Any) -> Any:
    try:
        if value != value:
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    return value


def valuation_by_symbol(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get("symbol") or "")
        metric_id = str(row.get("metric_id") or "")
        if not sid or not metric_id:
            continue
        metric = {
            "metric_id": metric_id,
            "quality_state": str(row.get("quality_state") or ""),
            "metric_value": _clean_value(row.get("metric_value")),
            "decision_grade": bool(row.get("decision_grade")),
            "market_as_of_date": str(row.get("market_as_of_date") or ""),
            "denominator_available_from": _clean_value(row.get("denominator_available_from")),
        }
        out.setdefault(sid, {})[metric_id] = metric
    return out


def _resolved(metric: dict[str, Any] | None) -> bool:
    return bool(
        metric
        and metric.get("quality_state") in VALID_STATES
        and metric.get("decision_grade") is True
        and metric.get("metric_value") is not None
    )


def merge_live_context(
    phase2c: dict[str, Any],
    valuation_rows: list[dict[str, Any]],
    valuation_release: dict[str, Any],
    valuation_domain: dict[str, Any],
    target_ids: set[str],
    phase2c_source_id: str,
) -> dict[str, Any]:
    if valuation_domain.get("status") != "PASS":
        raise RuntimeError("P43_LIVE_VALUATION_DOMAIN_NOT_PASS")
    if valuation_domain.get("qc_status") != "PASS_EXACT_VALUATION_REBUILT":
        raise RuntimeError("P43_LIVE_VALUATION_QC_NOT_EXACT")
    if valuation_domain.get("trade_authority") != TRADE_AUTHORITY:
        raise RuntimeError("P43_LIVE_VALUATION_TRADE_AUTHORITY")
    if valuation_release.get("status") != "FMDL3DC_VALUATION_ENGINE_CURRENT_ACCEPTED":
        raise RuntimeError("P43_LIVE_VALUATION_RELEASE_NOT_ACCEPTED")
    market_as_of = str(valuation_release.get("source_releases", {}).get("market_as_of_date") or "")
    if market_as_of != str(valuation_domain.get("data_watermark") or ""):
        raise RuntimeError("P43_LIVE_VALUATION_WATERMARK_MISMATCH")

    values = valuation_by_symbol(valuation_rows)
    blocked: list[dict[str, Any]] = []
    for original in phase2c.get("blocked", []):
        row = json.loads(json.dumps(original))
        sid = str(row.get("security_id") or "")
        metrics = values.get(sid, {})
        resolved_ids = sorted(k for k, v in metrics.items() if _resolved(v))
        live_bound = bool(resolved_ids)
        pe_bound = _resolved(metrics.get("VAL_PE_TTM"))

        reasons = list(row.get("reason_codes", []))
        missing = list(row.get("missing_requirements", []))
        evidence_codes: list[str] = []

        if (
            sid in target_ids
            and "FRESH_VALUATION_BINDING_ABSENT" in reasons
            and live_bound
        ):
            reasons = [x for x in reasons if x != "FRESH_VALUATION_BINDING_ABSENT"]
            missing = [
                x for x in missing
                if "fresh completed-close price/multiple bound to research object" not in str(x)
            ]
            evidence_codes.append("LIVE_EXACT_VALUATION_BOUND")

        # A current PE_TTM is useful evidence, but it is not a normalized earnings
        # valuation. Do not silently cure FRESH_NORMALIZED_VALUATION_ABSENT.
        if (
            sid in target_ids
            and "FRESH_NORMALIZED_VALUATION_ABSENT" in reasons
            and pe_bound
        ):
            evidence_codes.append("LIVE_EXACT_PE_TTM_BOUND_NORMALIZED_PE_NOT_PROVEN")

        row["reason_codes"] = reasons
        row["missing_requirements"] = missing
        row["live_operating_authority"] = True
        row["valuation_context"] = {
            "live_exact_valuation_bound": live_bound,
            "resolved_decision_grade_metric_ids": resolved_ids,
            "metrics": {k: metrics[k] for k in sorted(metrics)},
            "market_as_of_date": market_as_of,
            "valuation_release_id": valuation_release.get("release_id"),
            "valuation_source_commit": valuation_domain.get("source_commit_sha"),
            "evidence_codes": evidence_codes,
            "normalized_valuation_proven": False,
            "automatic_action_authorized": False,
            "trade_authority": TRADE_AUTHORITY,
        }
        blocked.append(row)

    return {
        "schema_version": "1.0.0",
        "phase": "OCC_R3C_LIVE_RECOMMENDATION_CONTEXT",
        "mode": "LIVE_EXACT_VALUATION_BOUND_PHASE2C_BLOCKERS_RETAINED",
        "generated_at": valuation_domain.get("published_at_utc"),
        "latest_validated_governed_market_as_of": market_as_of,
        "eligible_non_reference_count": phase2c.get("eligible_non_reference_count", 0),
        "blocked_non_reference_count": phase2c.get("blocked_non_reference_count", len(blocked)),
        "blocked": blocked,
        "live_operating_authority": True,
        "source_bindings": {
            "phase2c_source_id": phase2c_source_id,
            "valuation_domain_id": valuation_domain.get("domain_id"),
            "valuation_source_branch": valuation_domain.get("source_branch"),
            "valuation_source_commit": valuation_domain.get("source_commit_sha"),
            "valuation_release_id": valuation_release.get("release_id"),
            "market_as_of_date": market_as_of,
        },
        "controls": {
            "new_scalar_recommendation_score": 0,
            "candidate_membership_mutations": 0,
            "portfolio_mutations": 0,
            "orders": 0,
            "trade_authority": TRADE_AUTHORITY,
        },
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--phase2c-pack", required=True)
    p.add_argument("--valuation-detail", required=True)
    p.add_argument("--valuation-release", required=True)
    p.add_argument("--valuation-domain", required=True)
    p.add_argument("--d2-current", required=True)
    p.add_argument("--phase2c-source-id", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    import pandas as pd

    phase2c = load_json(Path(args.phase2c_pack))
    release = load_json(Path(args.valuation_release))
    domain = load_json(Path(args.valuation_domain))
    d2 = load_json(Path(args.d2_current))
    target_ids = {
        str(row.get("security_id"))
        for row in d2.get("queue", [])
        if row.get("security_id")
    }
    detail = pd.read_parquet(args.valuation_detail)
    rows = detail[detail["symbol"].astype(str).isin(target_ids)].to_dict("records")
    payload = merge_live_context(
        phase2c, rows, release, domain, target_ids, args.phase2c_source_id
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PASS_LIVE_RECOMMENDATION_CONTEXT",
        "targets": sorted(target_ids),
        "market_as_of_date": payload["latest_validated_governed_market_as_of"],
        "orders": 0,
        "trade_authority": TRADE_AUTHORITY,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
