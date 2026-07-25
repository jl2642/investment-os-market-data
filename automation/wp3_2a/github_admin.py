from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any


API_VERSION = "2026-03-10"
DEFAULT_REPO = "jl2642/investment-os-market-data"
ENVIRONMENTS = (
    "wp3-2a-data-acceptance",
    "wp3-2a-screening-approval",
)
REQUIRED_CHECK = "WP3-2A / Lineage Gate"


def run(
    command: list[str],
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        text=True,
        capture_output=capture,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def require_cli() -> None:
    if shutil.which("gh") is None:
        raise SystemExit("GitHub CLI 'gh' is required")
    run(["gh", "auth", "status"])


def gh_json(arguments: list[str]) -> Any:
    result = run(["gh", *arguments])
    text = result.stdout.strip()
    return json.loads(text) if text else None


def api(
    repo: str,
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None = None,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        "gh",
        "api",
        "--method",
        method,
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        f"X-GitHub-Api-Version: {API_VERSION}",
        f"repos/{repo}/{endpoint.lstrip('/')}",
    ]
    if payload is not None:
        command.extend(["--input", "-"])
        return subprocess.run(
            command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=check,
        )
    return run(command, check=check)


def repo_metadata(repo: str) -> dict[str, Any]:
    return gh_json(
        [
            "repo",
            "view",
            repo,
            "--json",
            "nameWithOwner,isPrivate,defaultBranchRef,url,viewerPermission",
        ]
    )


def get_status(repo: str) -> dict[str, Any]:
    metadata = repo_metadata(repo)
    output: dict[str, Any] = {
        "repository": metadata,
        "actions_permissions": None,
        "environments": None,
        "branch_protection": None,
        "workflows": None,
    }

    actions = api(repo, "GET", "actions/permissions/workflow", check=False)
    if actions.returncode == 0:
        output["actions_permissions"] = json.loads(actions.stdout)

    environments = api(repo, "GET", "environments", check=False)
    if environments.returncode == 0:
        output["environments"] = json.loads(environments.stdout)

    protection = api(
        repo, "GET", "branches/main/protection", check=False
    )
    if protection.returncode == 0:
        output["branch_protection"] = json.loads(protection.stdout)
    else:
        output["branch_protection"] = {
            "status": "UNAVAILABLE_OR_NOT_CONFIGURED",
            "stderr": protection.stderr.strip(),
        }

    workflows = run(
        [
            "gh",
            "workflow",
            "list",
            "--repo",
            repo,
            "--json",
            "id,name,path,state",
        ],
        check=False,
    )
    if workflows.returncode == 0 and workflows.stdout.strip():
        output["workflows"] = json.loads(workflows.stdout)

    return output


def configure_actions(repo: str) -> dict[str, Any]:
    payload = {
        "default_workflow_permissions": "read",
        "can_approve_pull_request_reviews": False,
    }
    result = api(
        repo,
        "PUT",
        "actions/permissions/workflow",
        payload,
        check=False,
    )
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stderr": result.stderr.strip(),
    }


def current_user() -> dict[str, Any]:
    return gh_json(["api", "user"])


def configure_environment(
    repo: str,
    name: str,
    reviewer_id: int,
    is_private: bool,
) -> dict[str, Any]:
    encoded = urllib.parse.quote(name, safe="")
    protected_payload = {
        "wait_timer": 0,
        "prevent_self_review": False,
        "reviewers": [{"type": "User", "id": reviewer_id}],
    }
    protected = api(
        repo,
        "PUT",
        f"environments/{encoded}",
        protected_payload,
        check=False,
    )
    if protected.returncode == 0:
        return {
            "environment": name,
            "status": "PASS_REQUIRED_REVIEWER_CONFIGURED",
        }

    fallback = api(
        repo,
        "PUT",
        f"environments/{encoded}",
        {},
        check=False,
    )
    return {
        "environment": name,
        "status": (
            "PASS_ENVIRONMENT_CREATED_WITHOUT_REQUIRED_REVIEWER"
            if fallback.returncode == 0
            else "FAIL"
        ),
        "repository_private": is_private,
        "required_reviewer_error": protected.stderr.strip(),
        "fallback_error": fallback.stderr.strip(),
        "control_fallback": (
            "EXACT_WORKFLOW_CONFIRMATION_AND_HUMAN_PR_MERGE"
        ),
    }


def configure_branch_protection(repo: str) -> dict[str, Any]:
    current = api(
        repo, "GET", "branches/main/protection", check=False
    )

    if current.returncode != 0:
        payload = {
            "required_status_checks": {
                "strict": True,
                "checks": [{"context": REQUIRED_CHECK, "app_id": -1}],
            },
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": True,
                "required_approving_review_count": 1,
                "require_last_push_approval": False,
            },
            "restrictions": None,
            "required_linear_history": False,
            "allow_force_pushes": False,
            "allow_deletions": False,
            "block_creations": False,
            "required_conversation_resolution": True,
            "lock_branch": False,
            "allow_fork_syncing": True,
        }
        created = api(
            repo,
            "PUT",
            "branches/main/protection",
            payload,
            check=False,
        )
        return {
            "status": "PASS_CREATED" if created.returncode == 0 else "FAIL",
            "stderr": created.stderr.strip(),
        }

    protection = json.loads(current.stdout)
    existing_contexts = {
        str(x)
        for x in (
            protection.get("required_status_checks", {}).get("contexts")
            or []
        )
    }
    existing_contexts.add(REQUIRED_CHECK)

    status_checks = api(
        repo,
        "PATCH",
        "branches/main/protection/required_status_checks",
        {
            "strict": True,
            "contexts": sorted(existing_contexts),
        },
        check=False,
    )
    reviews = api(
        repo,
        "PATCH",
        "branches/main/protection/required_pull_request_reviews",
        {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "required_approving_review_count": max(
                1,
                int(
                    protection.get(
                        "required_pull_request_reviews", {}
                    ).get("required_approving_review_count")
                    or 0
                ),
            ),
            "require_last_push_approval": False,
        },
        check=False,
    )
    enforce_admins = api(
        repo,
        "POST",
        "branches/main/protection/enforce_admins",
        {},
        check=False,
    )
    conversations = api(
        repo,
        "POST",
        "branches/main/protection/required_conversation_resolution",
        {},
        check=False,
    )
    no_force = api(
        repo,
        "DELETE",
        "branches/main/protection/allow_force_pushes",
        check=False,
    )
    no_delete = api(
        repo,
        "DELETE",
        "branches/main/protection/allow_deletions",
        check=False,
    )

    results = {
        "required_status_checks": status_checks.returncode,
        "required_pull_request_reviews": reviews.returncode,
        "enforce_admins": enforce_admins.returncode,
        "conversation_resolution": conversations.returncode,
        "disable_force_pushes": no_force.returncode,
        "disable_deletions": no_delete.returncode,
    }
    return {
        "status": (
            "PASS"
            if status_checks.returncode == 0
            and reviews.returncode == 0
            else "PARTIAL_OR_FAIL"
        ),
        "return_codes": results,
        "errors": {
            "status_checks": status_checks.stderr.strip(),
            "reviews": reviews.stderr.strip(),
            "enforce_admins": enforce_admins.stderr.strip(),
            "conversation_resolution": conversations.stderr.strip(),
            "disable_force_pushes": no_force.stderr.strip(),
            "disable_deletions": no_delete.stderr.strip(),
        },
    }


def configure(repo: str) -> dict[str, Any]:
    metadata = repo_metadata(repo)
    user = current_user()
    result = {
        "repository": metadata,
        "actions": configure_actions(repo),
        "environments": [
            configure_environment(
                repo,
                name,
                int(user["id"]),
                bool(metadata["isPrivate"]),
            )
            for name in ENVIRONMENTS
        ],
        "branch_protection": configure_branch_protection(repo),
    }
    return result


def trigger(
    repo: str,
    accepted_session: str,
    provider_policy: str,
    create_pr: bool,
    wait: bool,
) -> dict[str, Any]:
    command = [
        "gh",
        "workflow",
        "run",
        "wp3_2a_universe_refresh.yml",
        "--repo",
        repo,
        "-f",
        f"accepted_session={accepted_session}",
        "-f",
        f"provider_policy={provider_policy}",
        "-f",
        f"create_pr={'true' if create_pr else 'false'}",
    ]
    run(command)

    time.sleep(3)
    runs = gh_json(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            "wp3_2a_universe_refresh.yml",
            "--limit",
            "1",
            "--json",
            "databaseId,status,conclusion,url,headSha,createdAt",
        ]
    )
    if not runs:
        raise RuntimeError("workflow dispatch succeeded but no run was found")
    selected = runs[0]

    if wait:
        watched = run(
            [
                "gh",
                "run",
                "watch",
                str(selected["databaseId"]),
                "--repo",
                repo,
                "--exit-status",
            ],
            check=False,
            capture=False,
        )
        selected["watch_returncode"] = watched.returncode

    return selected


def review_latest(
    repo: str,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    runs = gh_json(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            "wp3_2a_universe_refresh.yml",
            "--limit",
            "1",
            "--json",
            "databaseId,status,conclusion,url,headSha,createdAt",
        ]
    )
    if not runs:
        raise RuntimeError("no Universe Refresh run found")
    latest_run = runs[0]

    download = run(
        [
            "gh",
            "run",
            "download",
            str(latest_run["databaseId"]),
            "--repo",
            repo,
            "--dir",
            str(output_dir / "artifacts"),
        ],
        check=False,
    )

    prs = gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--json",
            "number,title,url,headRefName,baseRefName,createdAt",
            "--limit",
            "100",
        ]
    )
    proposal_prs = [
        pr for pr in prs
        if str(pr["headRefName"]).startswith(
            "automation/wp3-2a-universe-"
        )
    ]

    review = {
        "run": latest_run,
        "artifact_download": {
            "status": "PASS" if download.returncode == 0 else "FAIL",
            "stderr": download.stderr.strip(),
        },
        "proposal_pull_requests": proposal_prs,
        "investment_decision": "NOT_PERFORMED",
        "candidate_membership_mutations": 0,
        "orders": 0,
        "trade_authority": "NONE",
    }
    (output_dir / "WP3_2A_GITHUB_RUN_REVIEW.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=DEFAULT_REPO)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")
    sub.add_parser("configure")

    trigger_parser = sub.add_parser("trigger")
    trigger_parser.add_argument("--accepted-session", default="")
    trigger_parser.add_argument(
        "--provider-policy",
        default="configured",
        choices=("configured", "eastmoney_public", "sina_public"),
    )
    trigger_parser.add_argument(
        "--no-create-pr", action="store_true"
    )
    trigger_parser.add_argument("--wait", action="store_true")

    review_parser = sub.add_parser("review")
    review_parser.add_argument(
        "--output-dir", default=".wp3_2a_admin/review"
    )

    args = parser.parse_args()
    require_cli()

    if args.command == "status":
        result = get_status(args.repo)
    elif args.command == "configure":
        result = configure(args.repo)
    elif args.command == "trigger":
        result = trigger(
            args.repo,
            args.accepted_session,
            args.provider_policy,
            not args.no_create_pr,
            args.wait,
        )
    elif args.command == "review":
        result = review_latest(
            args.repo, Path(args.output_dir)
        )
    else:
        raise AssertionError(args.command)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
