from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import yaml


def tracked_repository_paths(repo: Path) -> list[Path]:
    """Return tracked paths when Git metadata is available.

    Runtime execution legitimately creates ignored ``__pycache__`` and
    ``.pytest_cache`` directories. Repository hygiene must reject cache files
    committed to source control, not transient ignored files produced by the
    current workflow run.
    """

    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0:
        return [repo / item.decode("utf-8", errors="surrogateescape") for item in proc.stdout.split(b"\0") if item]

    # Recovery packages may be tested outside a Git checkout. In that case,
    # scan package contents while excluding Git internals if present.
    return [
        path
        for path in repo.rglob("*")
        if ".git" not in path.relative_to(repo).parts
    ]


def is_generated_cache_path(path: Path) -> bool:
    return (
        path.name in {".pytest_cache", "__pycache__"}
        or path.suffix in {".pyc", ".pyo"}
    )


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
        path
        for path in tracked_repository_paths(repo)
        if is_generated_cache_path(path)
    ]
    if cache_paths:
        errors.append(
            "tracked generated cache paths present: "
            f"{[str(path.relative_to(repo)) for path in cache_paths[:10]]}"
        )

    result = {
        "status": "PASS" if not errors else "FAIL",
        "workflow_count": len(workflows),
        "errors": errors,
        "cache_scope": "TRACKED_REPOSITORY_PATHS",
        "trade_authority": "NONE",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not errors else 2)


if __name__ == "__main__":
    main()
