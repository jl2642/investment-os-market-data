from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    args = ap.parse_args()

    repo = Path(args.repo_root)
    workflows = sorted((repo / ".github/workflows").glob("wp3_2a_*.yml"))
    errors: list[str] = []

    if len(workflows) < 4:
        errors.append(f"expected at least 4 workflows, found {len(workflows)}")

    lineage = repo / ".github/workflows/wp3_2a_lineage_gate.yml"

    for workflow in workflows:
        try:
            text = workflow.read_text(encoding="utf-8")
            data = yaml.load(text, Loader=yaml.BaseLoader)
            if not isinstance(data, dict) or "jobs" not in data:
                errors.append(f"{workflow.name}: invalid workflow structure")
            if "push:" in text and "branches: [main]" in text:
                errors.append(f"{workflow.name}: direct-main push trigger prohibited")
        except Exception as exc:
            errors.append(f"{workflow.name}: {type(exc).__name__}: {exc}")

    if lineage.exists():
        text = lineage.read_text(encoding="utf-8")
        if "paths:" in text or "paths-ignore:" in text:
            errors.append(
                "required lineage workflow must not use path filters; skipped required "
                "checks can remain pending"
            )
        if "name: WP3-2A / Lineage Gate" not in text:
            errors.append("required lineage job name changed")
        if "automation/wp3-2a-*" not in text:
            errors.append("lineage workflow lacks WP3-2A branch-scoped mutation enforcement")
    else:
        errors.append("missing wp3_2a_lineage_gate.yml")

    config = json.loads(
        (repo / "automation/wp3_2a/config.json").read_text(encoding="utf-8")
    )
    if config.get("trade_authority") != "NONE":
        errors.append("trade authority violation")
    if any(config["permissions"].values()):
        errors.append("automatic investment permissions must all be false")

    cache_paths = [
        p for p in repo.rglob("*")
        if p.name in {".pytest_cache", "__pycache__"} or p.suffix == ".pyc"
    ]
    if cache_paths:
        errors.append(f"generated cache paths present: {[str(p) for p in cache_paths[:10]]}")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "workflow_count": len(workflows),
        "errors": errors,
        "trade_authority": "NONE",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not errors else 2)


if __name__ == "__main__":
    main()
