import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "automation/wp3_2a/config.json"
ACCEPT_SCRIPT = ROOT / "automation/wp3_2a/accept_data_proposal.py"
BRIDGE = ROOT / ".github/workflows/wp3_2a_acceptance_connector_bridge.yml"
ACCEPT_WORKFLOW = ROOT / ".github/workflows/wp3_2a_accept_universe.yml"


def test_cdr_scope_exception_is_explicit_and_non_mutating():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    scope = config["ordinary_a_share_scope"]
    exceptions = {item["security_code"]: item for item in scope["scope_exceptions"]}

    assert "depositary receipts" in scope["excludes"]
    assert "689009" in exceptions
    item = exceptions["689009"]
    assert item["security_type"] == "CDR"
    assert item["not_a_delisting"] is True
    assert "NO_AUTOMATIC_CANDIDATE_ADMISSION" in item["handling"]
    assert config["trade_authority"] == "NONE"


def test_acceptance_writes_scope_record_and_rejects_special_security_leakage():
    text = ACCEPT_SCRIPT.read_text(encoding="utf-8")

    assert "WP3_2A_UNIVERSE_SCOPE_EXCEPTIONS_CURRENT.json" in text
    assert "special securities present in ordinary A-share universe" in text
    assert '"scope_exceptions_reviewed_by_merge": True' in text
    assert '"candidate_membership_mutations": 0' in text
    assert '"trade_authority": "NONE"' in text


def test_connector_bridge_only_dispatches_exact_protected_acceptance_request():
    text = BRIDGE.read_text(encoding="utf-8")

    assert "automation/wp3-2a-accept-*" in text
    assert ".wp3_2a_control/accept_request.json" in text
    assert "ACCEPT_UNIVERSE_PROPOSAL" in text
    assert "wp3_2a_accept_universe.yml" in text
    assert "forked acceptance requests are not permitted" in text
    assert "proposal_path is outside the governed WP3-2A proposal root" in text
    assert "Environment approval remains a human governance gate" in text
    assert "trade_authority: `NONE`" in text


def test_acceptance_pr_publication_uses_exact_governed_scope():
    text = ACCEPT_WORKFLOW.read_text(encoding="utf-8")

    assert 'BRANCH="automation/wp3-2a-accept-${SESSION}-${RUN_KEY}"' in text
    assert "create_or_update_pr.sh" not in text
    assert "git push --set-upstream origin" in text
    assert "--force" not in text
    assert "Acceptance publication scope violation" in text
    assert "investment_os_runtime/40_EVIDENCE_AND_LINEAGE/WP3_2A/CURRENT" in text
    assert "investment_os_runtime/50_MARKET_CAPABILITY_BINDINGS/A_SHARE_CURRENT.json" in text
    assert "investment_os_runtime/00_CONTROL/WP3_2A_UNIVERSE_SCOPE_EXCEPTIONS_CURRENT.json" in text
    assert "investment_os_runtime/00_CONTROL/WP3_2A_UNIVERSE_ACCEPTANCE_RECORD.json" in text
    assert "investment_os_runtime/00_CONTROL/EXECUTION_REGISTER_CURRENT.json" in text
    assert "Candidate / Research / account / simulation mutations:" in text
    assert "Orders:" in text
    assert "trade_authority:" in text
    assert "NONE" in text
