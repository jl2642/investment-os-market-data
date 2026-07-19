from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fmdl3cb_engine.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    cfg = load_json(CONFIG)
    profiles = pd.read_csv(
        ROOT / cfg["publication"]["candidate_root"] / "FMDL3CB_SECTOR_PROFILES.csv",
        encoding="utf-8-sig",
        dtype=str,
    ).fillna("")
    overrides = pd.read_csv(
        ROOT / cfg["inputs"]["sector_overrides"],
        encoding="utf-8-sig",
        dtype=str,
    ).fillna("")
    counts = profiles["sector_profile"].value_counts().to_dict()
    errors: list[str] = []
    if profiles["symbol"].duplicated().any():
        errors.append("DUPLICATE_PROFILE_SYMBOL")
    if not set(profiles["sector_profile"]).issubset(
        set(cfg["engine"]["allowed_sector_profiles"])
    ):
        errors.append("UNCONTROLLED_PROFILE")
    profile_index = profiles.set_index("symbol")["sector_profile"].to_dict()
    for row in overrides.itertuples(index=False):
        if profile_index.get(str(row.symbol)) != str(row.sector_profile):
            errors.append(f"OVERRIDE_NOT_APPLIED:{row.symbol}")
    for profile, bounds in cfg["engine"]["profile_count_bounds"].items():
        count = int(counts.get(profile, 0))
        if count < int(bounds["minimum"]) or count > int(bounds["maximum"]):
            errors.append(
                f"PROFILE_COUNT_OUTSIDE_BOUND:{profile}:{count}:"
                f"{bounds['minimum']}-{bounds['maximum']}"
            )
    result = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "profile_counts": {key: int(value) for key, value in counts.items()},
        "override_count": len(overrides),
        "authority": cfg["authority"],
        "trade_authority": "NONE",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
