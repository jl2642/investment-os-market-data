#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

PROGRAM_ID = "HKCU-P5C"
TRADE_AUTHORITY = "NONE"
TARGET_PRICE_MIN_HKD = 0.01
TARGET_PRICE_MAX_HKD = 5000.0


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(v: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(v).upper()).strip()


def code_match(v: Any, code5: str) -> bool:
    digits = re.sub(r"\D", "", str(v))
    if not digits:
        return False
    return digits.zfill(5) == code5


def parse_numeric(v: Any) -> float | None:
    s = str(v).replace(",", "").strip()
    if not s or s in {"-", "--", "N/A"}:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _table_close_candidates(html: str, targets: dict[str, str]) -> tuple[dict[str, float], dict[str, Any]]:
    prices: dict[str, float] = {}
    diag: dict[str, Any] = {"tables_seen": 0, "matching_rows": {}}
    try:
        tables = pd.read_html(StringIO(html))
    except Exception as exc:
        diag["read_html_error"] = repr(exc)
        return prices, diag
    diag["tables_seen"] = len(tables)
    for ti, table in enumerate(tables):
        cols = []
        for c in table.columns:
            if isinstance(c, tuple):
                cols.append(" ".join(str(x) for x in c if str(x) != "nan"))
            else:
                cols.append(str(c))
        ncols = [norm(x) for x in cols]
        close_idxs = [i for i, c in enumerate(ncols) if ("CLOS" in c and "PREV" not in c and "PRV" not in c)]
        code_idxs = [i for i, c in enumerate(ncols) if "CODE" in c]
        if not close_idxs:
            continue
        for _, row in table.iterrows():
            vals = [str(x).strip() for x in row.tolist()]
            for sid, code5 in targets.items():
                if sid in prices:
                    continue
                hit = any(code_match(vals[i], code5) for i in code_idxs if i < len(vals))
                if hit:
                    diag["matching_rows"][sid] = {"table": ti, "columns": cols, "values": vals}
                    for ci in close_idxs:
                        if ci < len(vals):
                            p = parse_numeric(vals[ci])
                            if p is not None and TARGET_PRICE_MIN_HKD <= p <= TARGET_PRICE_MAX_HKD:
                                prices[sid] = p
                                break
    return prices, diag


def _dom_close_candidates(html: str, targets: dict[str, str]) -> tuple[dict[str, float], dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    prices: dict[str, float] = {}
    diag: dict[str, Any] = {"matching_rows": {}}
    for table_i, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        header_cells: list[str] | None = None
        close_idx: int | None = None
        for tr in rows:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if not cells:
                continue
            normalized = [norm(x) for x in cells]
            if close_idx is None:
                for i, h in enumerate(normalized):
                    if "CLOS" in h and "PREV" not in h and "PRV" not in h:
                        close_idx = i
                        header_cells = cells
                        break
            for sid, code5 in targets.items():
                if sid in prices:
                    continue
                if any(code_match(x, code5) for x in cells[:4]):
                    diag["matching_rows"][sid] = {"table": table_i, "header": header_cells, "values": cells}
                    if close_idx is not None and close_idx < len(cells):
                        p = parse_numeric(cells[close_idx])
                        if p is not None and TARGET_PRICE_MIN_HKD <= p <= TARGET_PRICE_MAX_HKD:
                            prices[sid] = p
    return prices, diag


def _quotation_two_line_close_candidates(html: str, targets: dict[str, str]) -> tuple[dict[str, float], dict[str, Any]]:
    """Parse HKEX legacy Main Board Daily Quotations two-line quote rows.

    The official report encodes each stock in two physical lines under the QUOTATIONS
    header. First line: code/name/currency, previous close, ask, high, shares traded.
    Second line: closing price, bid, low, turnover. We therefore take the first numeric
    price token from the immediately following non-empty line, and never scan later
    short-selling / turnover sections for a code match.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = "\n".join(p.get_text("\n") for p in soup.find_all("pre")) or soup.get_text("\n")
    lines = text.splitlines()
    prices: dict[str, float] = {}
    diag: dict[str, Any] = {"quote_header_indices": [], "matching_quote_pairs": {}, "all_code_occurrences": {}}

    # Capture all occurrences for fail-closed diagnostics, even outside the quotation section.
    for idx, line in enumerate(lines):
        for sid, code5 in targets.items():
            code_int = str(int(code5))
            if re.match(rf"^\s*[*#]?\s*{re.escape(code_int)}\s+", line):
                diag["all_code_occurrences"].setdefault(sid, []).append({
                    "index": idx,
                    "line": line,
                    "next": lines[idx + 1] if idx + 1 < len(lines) else "",
                })

    header_indices = []
    for idx, line in enumerate(lines):
        u = line.upper()
        if "CODE" in u and "NAME OF STOCK" in u and "PRV.CLO" in u and "SHARES TRADED" in u:
            header_indices.append(idx)
    diag["quote_header_indices"] = header_indices

    row_re = re.compile(r"^\s*[*#]?\s*(\d{1,5})\s+(.+?)\s+(HKD|USD|CNY)\s+", re.I)
    for header_idx in header_indices:
        # The actual quotation table is large. Stop at the next report section.
        for idx in range(header_idx + 1, len(lines)):
            upper = lines[idx].strip().upper()
            if idx > header_idx + 2 and (upper.startswith("SALES RECORDS FOR ALL STOCKS") or upper.startswith("SALES RECORDS OVER")):
                break
            m = row_re.match(lines[idx])
            if not m:
                continue
            code5 = m.group(1).zfill(5)
            matching_sid = next((sid for sid, target_code in targets.items() if target_code == code5), None)
            if matching_sid is None or matching_sid in prices:
                continue
            next_idx = idx + 1
            while next_idx < len(lines) and not lines[next_idx].strip():
                next_idx += 1
            second = lines[next_idx] if next_idx < len(lines) else ""
            # Closing is the first field on the second quote line. It is a price-like token,
            # not a comma-separated volume/turnover integer.
            second_clean = second.strip()
            first_token = second_clean.split()[0] if second_clean else ""
            p = parse_numeric(first_token)
            diag["matching_quote_pairs"][matching_sid] = {
                "first_line_index": idx,
                "first_line": lines[idx],
                "second_line_index": next_idx,
                "second_line": second,
                "closing_token": first_token,
                "parsed_close": p,
            }
            if p is not None and math.isfinite(p) and TARGET_PRICE_MIN_HKD <= p <= TARGET_PRICE_MAX_HKD:
                prices[matching_sid] = p
    return prices, diag


def extract_hkex_close_prices(html: str, targets: dict[str, str]) -> tuple[dict[str, float], dict[str, Any]]:
    methods = []
    merged: dict[str, float] = {}
    # Legacy HKEX daily-quotation pages are fixed-width text, so use the exact two-line
    # quotation parser first. HTML-table parsers are only secondary fallbacks.
    for fn in (_quotation_two_line_close_candidates, _table_close_candidates, _dom_close_candidates):
        unresolved = {sid: code for sid, code in targets.items() if sid not in merged}
        if not unresolved:
            break
        p, d = fn(html, unresolved)
        methods.append({"method": fn.__name__, "prices": p, "diagnostics": d})
        for sid, val in p.items():
            merged[sid] = val
    return merged, {"methods": methods}


def fetch_hkex_html(url: str) -> tuple[str, bytes]:
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 HKCU-P5C governance fetch"}, timeout=45)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text, r.content


def valuation_multiple(row: pd.Series, close_price: float) -> float:
    basis = float(row["basis_value"])
    if str(row["basis_currency"]).upper() == "USD":
        denominator = basis * float(row["fx_anchor"])
    else:
        denominator = basis
    if denominator <= 0:
        raise ValueError(f"INVALID_VALUATION_DENOMINATOR:{row['security_id']}")
    return close_price / denominator


def build(root: Path, p5b_dir: Path, out: Path, quote_html: Path | None = None) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    contract = read_json(root / "config/hkcu_p5c_user_decision_gate_contract.json")
    p5b_contract = read_json(root / contract["authoritative_inputs"]["p5b_contract"])
    p5b_prefix = p5b_contract["output_prefix"]
    prefix = contract["output_prefix"]
    entry = contract["entry_contract"]
    policy = contract["decision_policy"]
    acceptance = contract["acceptance"]

    p5b_decision = read_json(p5b_dir / f"{p5b_prefix}_DECISION.json")
    p5b_memos = pd.read_csv(p5b_dir / f"{p5b_prefix}_SECURITY_MEMOS.csv", dtype={"stock_code_5d": str}, keep_default_na=False)
    context = pd.read_csv(root / contract["authoritative_inputs"]["valuation_context_registry"], dtype={"stock_code_5d": str}, keep_default_na=False)
    errors: list[str] = []

    if p5b_decision.get("status") != entry["required_p5b_status"]:
        errors.append("P5B_STATUS")
    if p5b_decision.get("next_gate") != entry["required_p5b_next_gate"]:
        errors.append("P5B_NEXT_GATE")
    if p5b_decision.get("aggregate_memo_state") != entry["required_aggregate_memo_state"]:
        errors.append("P5B_AGGREGATE_STATE")
    if int(p5b_decision.get("advanced_with_price_gate_count", -1)) != entry["required_advanced_count"]:
        errors.append("P5B_ADVANCED_COUNT")
    if int(p5b_decision.get("deferred_security_count", -1)) != entry["required_deferred_count"]:
        errors.append("P5B_DEFERRED_COUNT")
    if p5b_decision.get("trade_authority") != TRADE_AUTHORITY:
        errors.append("P5B_AUTHORITY")

    advanced = p5b_memos[p5b_memos["memo_state"].astype(str).eq("ADVANCE_WITH_PRICE_GATE")].copy()
    target_sids = contract["price_surface"]["required_advanced_securities"]
    if set(advanced["security_id"].astype(str)) != set(target_sids):
        errors.append("ADVANCED_SECURITY_SET")
    if len(context) != len(target_sids) or set(context["security_id"].astype(str)) != set(target_sids):
        errors.append("VALUATION_CONTEXT_SET")

    quote_url = contract["price_surface"]["url"]
    if quote_html:
        raw = quote_html.read_bytes()
        html = raw.decode("utf-8", errors="replace")
        quote_source_mode = "TEST_FIXTURE"
    else:
        html, raw = fetch_hkex_html(quote_url)
        quote_source_mode = "HKEX_NETWORK"
    quote_sha = sha256_bytes(raw)
    prices, diagnostics = extract_hkex_close_prices(html, {sid: sid.split(":")[1] for sid in target_sids})
    write_json(out / f"{prefix}_PRICE_PARSE_DIAGNOSTICS.json", diagnostics)

    missing_prices = sorted(set(target_sids) - set(prices))
    if missing_prices:
        errors.append("HKEX_PRICE_PARSE_MISSING:" + ",".join(missing_prices))
    outlier_prices = sorted(sid for sid, p in prices.items() if not (TARGET_PRICE_MIN_HKD <= float(p) <= TARGET_PRICE_MAX_HKD))
    if outlier_prices:
        errors.append("HKEX_PRICE_OUTLIER:" + ",".join(outlier_prices))

    quote_rows = []
    for sid in target_sids:
        quote_rows.append({"security_id": sid, "stock_code_5d": sid.split(":")[1], "price_date": contract["price_surface"]["price_date"], "close_hkd": prices.get(sid, ""), "price_source": "HKEX_OFFICIAL_DAILY_QUOTATIONS_MAIN_BOARD", "source_url": quote_url, "source_sha256": quote_sha, "source_mode": quote_source_mode})
    pd.DataFrame(quote_rows).to_csv(out / f"{prefix}_OFFICIAL_PRICE_SURFACE.csv", index=False)

    packet = p5b_memos.copy().merge(context, on=["security_id", "stock_code_5d", "security_name"], how="left", validate="one_to_one")
    packet["price_date"] = contract["price_surface"]["price_date"]
    packet["official_close_hkd"] = packet["security_id"].map(prices)
    packet["valuation_multiple"] = ""
    packet["valuation_vs_own_history_median_pct"] = ""
    packet["valuation_vs_reference_pct"] = ""
    packet["decision_eligibility"] = policy["deferred_state"]
    packet["available_user_choices"] = ""
    packet["user_decision"] = ""
    packet["user_modified_weight"] = ""
    packet["user_trade_confirmation_recorded"] = False
    packet["manual_execution_checklist_produced"] = False
    packet["target_writeback"] = False
    packet["portfolio_mutation"] = False
    packet["orders_created"] = 0
    packet["trade_authority"] = TRADE_AUTHORITY

    for i, row in packet.iterrows():
        if str(row["memo_state"]) == "ADVANCE_WITH_PRICE_GATE":
            sid = str(row["security_id"])
            if sid not in prices:
                continue
            mult = valuation_multiple(row, prices[sid])
            hist = float(row["history_median"])
            ref = float(row["peer_or_current_reference"])
            packet.at[i, "valuation_multiple"] = round(mult, 6)
            packet.at[i, "valuation_vs_own_history_median_pct"] = round((mult / hist - 1.0) * 100.0, 2)
            packet.at[i, "valuation_vs_reference_pct"] = round((mult / ref - 1.0) * 100.0, 2)
            packet.at[i, "decision_eligibility"] = policy["eligible_state"]
            packet.at[i, "available_user_choices"] = "|".join(policy["allowed_user_choices"])

    eligible = int(packet["decision_eligibility"].eq(policy["eligible_state"]).sum())
    deferred_count = int(packet["decision_eligibility"].eq(policy["deferred_state"]).sum())
    if eligible != acceptance["user_decision_eligible_count"]:
        errors.append("ELIGIBLE_COUNT")
    if deferred_count != acceptance["deferred_not_eligible_count"]:
        errors.append("DEFERRED_NOT_ELIGIBLE_COUNT")
    if packet["user_decision"].astype(str).str.strip().ne("").any():
        errors.append("USER_DECISION_PREPOPULATED")
    if contract["price_surface"]["third_party_price_fallback_allowed"] is not False:
        errors.append("THIRD_PARTY_PRICE_POLICY")
    if policy["technical_pass_may_substitute_user_approval"] is not False:
        errors.append("TECHNICAL_PASS_POLICY")

    packet.to_csv(out / f"{prefix}_DECISION_PACKET.csv", index=False)
    status = acceptance["pass_status"] if not errors else acceptance["fail_status"]
    gate_state = policy["current_gate_state_on_pass"] if not errors else "P5C_INTEGRITY_FAIL"
    summary = {"program_id": PROGRAM_ID, "phase": contract["phase"], "as_of_date": contract["as_of_date"], "status": status, "gate_state": gate_state, "price_date": contract["price_surface"]["price_date"], "price_source": contract["price_surface"]["required_source"], "price_source_url": quote_url, "price_source_sha256": quote_sha, "decision_packet_security_count": len(packet), "user_decision_eligible_count": eligible, "deferred_not_eligible_count": deferred_count, "user_decision_recorded_count": 0, "current_next_action": policy["current_next_action"] if not errors else acceptance["repair_gate"], "conditional_next_gate_after_explicit_user_decisions": policy["next_gate_only_after_explicit_eligible_decisions"], "user_trade_confirmation_recorded": False, "manual_execution_checklist_produced": False, "target_portfolio_writeback": False, "candidate_pool_mutations": 0, "simulation_mutations": 0, "real_account_mutations": 0, "orders_created": 0, "integrity_failures": errors, "trade_authority": TRADE_AUTHORITY}
    write_json(out / f"{prefix}_DECISION.json", summary)

    md = ["# HKCU P5C User Decision Gate", "", f"As of: {contract['as_of_date']}", f"Gate state: **{gate_state}**", f"Official price surface: **HKEX Daily Quotations {contract['price_surface']['price_date']}**", "", "This packet does **not** record user approval. A technical PASS only means the three P5B-advanced securities have a reproducible official-price and valuation context ready for explicit user choice.", ""]
    for row in packet.sort_values("security_id").itertuples(index=False):
        md += [f"## {row.security_id} {row.security_name}", f"- P5B memo state / weight: {row.memo_state} / {float(row.memo_proposed_weight):.4%}", f"- P5C eligibility: **{row.decision_eligibility}**"]
        if row.decision_eligibility == policy["eligible_state"]:
            md += [f"- Official HKEX close ({row.price_date}): **HK${float(row.official_close_hkd):.4f}**", f"- Valuation metric: {row.valuation_metric} = **{float(row.valuation_multiple):.2f}x**", f"- Own-history context: {row.history_context}; current vs median {float(row.valuation_vs_own_history_median_pct):+.1f}%", f"- Reference/peer context: {row.peer_context}; current vs reference {float(row.valuation_vs_reference_pct):+.1f}%", f"- User choices: {row.available_user_choices}"]
        else:
            md += ["- Current action: remains deferred; not eligible for approval until P5B evidence trigger is satisfied.", f"- Review triggers: {getattr(row, 'review_triggers_y', '')}"]
        md += [f"- Funding: {row.funding_source_class}", f"- Principal falsifier: {getattr(row, 'principal_falsifier_y', '')}", ""]
    md += ["## Governance", "", "- `user_decision_recorded_count=0`", "- `user_trade_confirmation_recorded=false`", "- no manual execution checklist", "- no target writeback", "- no Candidate/REAL/SIMULATION mutation", "- zero orders", "- `trade_authority=NONE`", "", f"Conditional next gate after explicit eligible-security decisions: **{policy['next_gate_only_after_explicit_eligible_decisions']}**."]
    (out / f"{prefix}.md").write_text("\n".join(md), encoding="utf-8")

    quality = {"program_id": PROGRAM_ID, "status": "PASS" if not errors else "FAIL", "official_hkex_price_surface_required": True, "third_party_price_fallback_used": False, "ambiguous_date_price_used": False, "valuation_context_documented": True, "fixed_valuation_ceiling_used": False, "technical_pass_substitutes_user_approval": False, "user_decision_prepopulated": False, "user_trade_confirmation_recorded": False, "manual_execution_checklist_produced": False, "target_writeback": False, "portfolio_mutations": 0, "orders_created": 0, "hard_failures": errors, "trade_authority": TRADE_AUTHORITY}
    write_json(out / f"{prefix}_QUALITY.json", quality)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--p5b-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--quote-html")
    args = ap.parse_args()
    summary = build(Path(args.repo_root).resolve(), Path(args.p5b_dir).resolve(), Path(args.output).resolve(), Path(args.quote_html).resolve() if args.quote_html else None)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not summary["integrity_failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
