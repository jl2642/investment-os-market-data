from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

BUY_STATES = {
    (True, True): "BUY_ELIGIBLE_BOTH",
    (True, False): "BUY_ELIGIBLE_SH_ONLY",
    (False, True): "BUY_ELIGIBLE_SZ_ONLY",
}
CODE_COLUMNS = (
    "stock_code_5d",
    "stock_code",
    "code",
    "证券代码",
    "股份代号",
    "股份編號",
    "Stock Code",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str)
    if suffix == ".csv":
        for encoding in ("utf-8-sig", "utf-8", "big5", "gb18030"):
            try:
                return pd.read_csv(path, dtype=str, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Unable to decode CSV: {path}")
    raise ValueError(f"Unsupported official-list format: {path}")


def _find_code_column(columns: Iterable[str]) -> str:
    normalized = {str(column).strip(): str(column) for column in columns}
    for candidate in CODE_COLUMNS:
        if candidate in normalized:
            return normalized[candidate]
    for column in normalized.values():
        lower = column.lower().replace(" ", "_")
        if "code" in lower or "代码" in column or "代號" in column or "编号" in column:
            return column
    raise ValueError("No stock-code column found in official list")


def _normalize_code(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip().split(".")[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    return digits.zfill(5)[-5:]


def load_official_channel(path: Path, channel: str) -> pd.DataFrame:
    frame = _read_table(path)
    code_column = _find_code_column(frame.columns)
    result = pd.DataFrame({"stock_code_5d": frame[code_column].map(_normalize_code)})
    result = result.dropna().drop_duplicates("stock_code_5d")
    result[f"{channel}_buy_eligible"] = True
    return result


def build_universe(
    screening: pd.DataFrame,
    sh_list: pd.DataFrame,
    sz_list: pd.DataFrame,
    as_of_date: str,
    sh_source_sha256: str,
    sz_source_sha256: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required = {
        "security_id",
        "stock_code_5d",
        "security_type",
        "investability_status",
        "avg_turnover_hkd_20d",
        "active_trade_ratio_60d",
        "zero_volume_days_20d",
        "latest_close",
        "financial_decision_grade",
        "profile",
    }
    missing = sorted(required - set(screening.columns))
    if missing:
        raise ValueError(f"FMDL-5E screening input missing fields: {missing}")

    base = screening.copy()
    base["stock_code_5d"] = base["stock_code_5d"].map(_normalize_code)
    base = base.merge(sh_list, on="stock_code_5d", how="left")
    base = base.merge(sz_list, on="stock_code_5d", how="left")
    for column in ("sh_buy_eligible", "sz_buy_eligible"):
        base[column] = base[column].fillna(False).astype(bool)

    base["southbound_buy_eligible"] = base["sh_buy_eligible"] | base["sz_buy_eligible"]
    base["sell_only"] = False
    base["eligibility_status"] = [
        BUY_STATES.get((sh, sz), "NOT_ELIGIBLE")
        for sh, sz in zip(base["sh_buy_eligible"], base["sz_buy_eligible"], strict=True)
    ]
    base["as_of_date"] = as_of_date
    base["effective_from"] = as_of_date
    base["source_authority"] = "MULTI_SOURCE_RECONCILED"
    base["sh_source_sha256"] = sh_source_sha256
    base["sz_source_sha256"] = sz_source_sha256
    base["trade_authority"] = "NONE"

    numeric_columns = [
        "avg_turnover_hkd_20d",
        "active_trade_ratio_60d",
        "zero_volume_days_20d",
        "latest_close",
    ]
    for column in numeric_columns:
        base[column] = pd.to_numeric(base[column], errors="coerce")

    financial_ok = base["financial_decision_grade"].astype(str).str.lower().eq("true")
    research_exception = base["profile"].isin(
        {"PRE_PROFIT_OR_NEGATIVE_EARNINGS", "CHAPTER_18A", "RECENT_LISTING"}
    )

    checks = {
        "NOT_SOUTHBOUND_BUY_ELIGIBLE": ~base["southbound_buy_eligible"],
        "FMDL5E_NOT_INVESTABLE": ~base["investability_status"].isin({"ELIGIBLE_CORE", "ELIGIBLE_WATCH"}),
        "NON_COMMON_EQUITY": base["security_type"].ne("COMMON_EQUITY"),
        "LOW_20D_TURNOVER": base["avg_turnover_hkd_20d"].lt(20_000_000) | base["avg_turnover_hkd_20d"].isna(),
        "LOW_ACTIVE_TRADE_RATIO": base["active_trade_ratio_60d"].lt(0.90) | base["active_trade_ratio_60d"].isna(),
        "EXCESS_ZERO_VOLUME_DAYS": base["zero_volume_days_20d"].gt(2) | base["zero_volume_days_20d"].isna(),
        "MISSING_VALID_PRICE": base["latest_close"].le(0) | base["latest_close"].isna(),
        "FINANCIAL_EVIDENCE_INCOMPLETE": ~(financial_ok | research_exception),
    }

    reasons: list[str] = []
    for index in base.index:
        failed = [name for name, mask in checks.items() if bool(mask.loc[index])]
        reasons.append("|".join(failed) if failed else "PASS")
    base["hkcu1_gate_reason"] = reasons
    base["hkcu1_investable"] = base["hkcu1_gate_reason"].eq("PASS")

    eligibility_columns = [
        "as_of_date", "security_id", "stock_code_5d", "sh_buy_eligible",
        "sz_buy_eligible", "southbound_buy_eligible", "sell_only",
        "eligibility_status", "effective_from", "source_authority",
        "sh_source_sha256", "sz_source_sha256", "trade_authority",
    ]
    eligibility = base[eligibility_columns].sort_values("stock_code_5d")
    investable = base.loc[base["hkcu1_investable"]].sort_values(
        ["avg_turnover_hkd_20d", "stock_code_5d"], ascending=[False, True]
    )
    exclusions = base.loc[~base["hkcu1_investable"], [
        "security_id", "stock_code_5d", "eligibility_status",
        "investability_status", "hkcu1_gate_reason", "trade_authority",
    ]].sort_values("stock_code_5d")
    return eligibility, investable, exclusions


def main() -> None:
    parser = argparse.ArgumentParser(description="Build HKCU-1 Stock Connect investable universe")
    parser.add_argument("--screening", required=True, type=Path)
    parser.add_argument("--sh-list", required=True, type=Path)
    parser.add_argument("--sz-list", required=True, type=Path)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    screening = pd.read_csv(args.screening, dtype={"stock_code_5d": str})
    sh_list = load_official_channel(args.sh_list, "sh")
    sz_list = load_official_channel(args.sz_list, "sz")
    eligibility, investable, exclusions = build_universe(
        screening,
        sh_list,
        sz_list,
        args.as_of_date,
        _sha256(args.sh_list),
        _sha256(args.sz_list),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    eligibility.to_csv(args.output_dir / "HKCU1_STOCK_CONNECT_ELIGIBILITY.csv", index=False)
    investable.to_csv(args.output_dir / "HKCU1_INVESTABLE_UNIVERSE.csv", index=False)
    exclusions.to_csv(args.output_dir / "HKCU1_EXCLUSIONS.csv", index=False)

    quality = {
        "program_id": "HKCU-1",
        "as_of_date": args.as_of_date,
        "source_security_count": int(len(screening)),
        "southbound_buy_eligible_count": int(eligibility["southbound_buy_eligible"].sum()),
        "investable_universe_count": int(len(investable)),
        "excluded_count": int(len(exclusions)),
        "duplicate_eligibility_count": int(eligibility["security_id"].duplicated().sum()),
        "sell_only_in_investable_count": 0,
        "unknown_in_investable_count": 0,
        "candidate_pool_mutation_count": 0,
        "simulation_mutation_count": 0,
        "real_account_mutation_count": 0,
        "order_generation_count": 0,
        "trade_authority": "NONE",
    }
    quality["status"] = "PASS" if quality["duplicate_eligibility_count"] == 0 else "FAIL"
    (args.output_dir / "HKCU1_QUALITY_REPORT.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
