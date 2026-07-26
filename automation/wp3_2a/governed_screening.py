from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


VALID_EXCHANGES = {"SSE", "SZSE", "BSE"}


def number(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--max-proposals", type=int, default=100)
    parser.add_argument("--confirmation", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    if args.confirmation != "RUN_PROPOSAL_ONLY_SCREENING":
        raise SystemExit("confirmation mismatch")
    if args.max_proposals < 0 or args.max_proposals > 500:
        raise SystemExit("max-proposals must be between 0 and 500")

    repo = Path(args.repo_root)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    current = repo / config["current_root"]
    manifest = json.loads((current / "PROPOSAL_MANIFEST.json").read_text(encoding="utf-8"))
    lineage = json.loads((current / "LINEAGE_ACCEPTANCE.json").read_text(encoding="utf-8"))
    binding_path = repo / "investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))

    if lineage.get("status") != "PASS":
        raise SystemExit("accepted Current lineage not PASS")
    if binding.get("as_of_date") != manifest.get("session"):
        raise SystemExit("Current binding session mismatch")
    if binding.get("status") != "ACCEPTED_ON_MAIN":
        raise SystemExit("Current binding is not accepted on main")
    if binding.get("trade_authority") != "NONE":
        raise SystemExit("trade authority violation")

    universe_path = current / "A_SHARE_FULL_UNIVERSE.csv"
    with universe_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    expected_rows = int(binding["datasets"]["universe"]["rows"])
    if len(rows) != expected_rows:
        raise SystemExit(f"Current row count mismatch: {len(rows)} != {expected_rows}")

    codes = [str(row.get("security_code") or "") for row in rows]
    if len(set(codes)) != len(codes):
        raise SystemExit("duplicate security codes in accepted Current")

    triage: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    for row in rows:
        code = str(row.get("security_code") or "")
        name = str(row.get("security_name") or "")
        exchange = str(row.get("exchange") or "")
        price = number(row.get("last_price"))
        volume = number(row.get("volume"))
        turnover = number(row.get("turnover_amount"))
        market_cap = number(row.get("total_market_cap"))
        completeness = sum(value is not None for value in (price, volume, turnover, market_cap))

        reasons: list[str] = []
        if not code or not name or exchange not in VALID_EXCHANGES:
            reasons.append("IDENTITY_OR_EXCHANGE_INVALID")
        if price is None or price <= 0:
            reasons.append("PRICE_NOT_POSITIVE")
        if volume is None or volume <= 0:
            reasons.append("VOLUME_NOT_POSITIVE")
        if turnover is None or turnover <= 0:
            reasons.append("TURNOVER_NOT_POSITIVE")
        if completeness < 3:
            reasons.append("INSUFFICIENT_MARKET_FIELD_COMPLETENESS")

        status = "ELIGIBLE_FOR_RESEARCH_TRIAGE" if not reasons else "NOT_ELIGIBLE_DATA_OR_LIQUIDITY"
        record: dict[str, object] = {
            "security_code": code,
            "security_name": name,
            "exchange": exchange,
            "market_data_readiness": status,
            "eligibility_reason": "PASS" if not reasons else "|".join(reasons),
            "field_completeness_count": completeness,
            "last_price": price,
            "volume": volume,
            "turnover_amount": turnover,
            "total_market_cap": market_cap,
            "investment_quality_status": "NOT_EVALUATED",
            "valuation_status": "NOT_EVALUATED",
            "thesis_status": "NOT_CREATED",
            "entry_baseline_status": "MISSING",
            "candidate_admission_authority": False,
            "research_priority_basis": "DATA_READINESS_AND_LIQUIDITY_ONLY_NOT_INVESTMENT_RANK",
        }
        triage.append(record)
        if reasons:
            exclusions.append(record)

    eligible = [row for row in triage if row["market_data_readiness"] == "ELIGIBLE_FOR_RESEARCH_TRIAGE"]
    eligible.sort(
        key=lambda row: (
            float(row["turnover_amount"] or -1),
            float(row["total_market_cap"] or -1),
            str(row["security_code"]),
        ),
        reverse=True,
    )

    queue: list[dict[str, object]] = []
    for rank, row in enumerate(eligible[: args.max_proposals], start=1):
        queued = dict(row)
        queued["workload_priority_rank"] = rank
        queue.append(queued)

    proposal_id = f"WP3_2B_SCREENING_PROPOSAL_{manifest['session'].replace('-', '')}_{args.run_id}"
    output = repo / config["screening_root"] / proposal_id
    output.mkdir(parents=True, exist_ok=False)

    triage_fields = list(triage[0].keys()) if triage else []
    queue_fields = triage_fields + ["workload_priority_rank"]
    files = {
        "full_market_readiness": output / "FULL_MARKET_RESEARCH_READINESS.csv",
        "eligible_universe": output / "ELIGIBLE_UNIVERSE.csv",
        "research_workload_queue": output / "RESEARCH_WORKLOAD_QUEUE.csv",
        "screening_exclusions": output / "SCREENING_EXCLUSIONS.csv",
    }
    write_csv(files["full_market_readiness"], triage, triage_fields)
    write_csv(files["eligible_universe"], eligible, triage_fields)
    write_csv(files["research_workload_queue"], queue, queue_fields)
    write_csv(files["screening_exclusions"], exclusions, triage_fields)

    result = {
        "proposal_id": proposal_id,
        "work_package": "WP3-2B",
        "status": "PROPOSAL_ONLY_PENDING_HUMAN_REVIEW",
        "session": manifest["session"],
        "source_current_merge_sha": binding.get("accepted_merge_sha"),
        "universe_rows": len(rows),
        "eligible_universe_rows": len(eligible),
        "excluded_rows": len(exclusions),
        "workload_queue_rows": len(queue),
        "method": "DATA_READINESS_AND_LIQUIDITY_ONLY",
        "investment_ranking": False,
        "quality_score": False,
        "valuation_conclusion": False,
        "research_objects_created": 0,
        "candidate_membership_mutations": 0,
        "simulation_trade_mutations": 0,
        "real_account_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
        "files": {
            key: {
                "path": str(path.relative_to(repo)).replace("\\", "/"),
                "sha256": sha256(path),
            }
            for key, path in files.items()
        },
    }
    (output / "SCREENING_PROPOSAL_MANIFEST.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        f"# {proposal_id}\n\n"
        "本输出属于WP3-2B，仅用于形成数据与流动性合格Universe及研究工作量队列。"
        "它不是投资吸引力排名，不创建Research Object，不改变Candidate，不生成订单。\n\n"
        f"- Accepted Current session: {manifest['session']}\n"
        f"- Full universe: {len(rows)}\n"
        f"- Eligible universe: {len(eligible)}\n"
        f"- Excluded: {len(exclusions)}\n"
        f"- Research workload queue: {len(queue)}\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
