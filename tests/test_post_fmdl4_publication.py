from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "publish_post_fmdl4.py"
spec = importlib.util.spec_from_file_location("publish_post_fmdl4", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_publication_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    publication = json.loads((root / "config/post_fmdl4_release8_publication.json").read_text(encoding="utf-8"))
    assert publication["release_sequence"] == 8
    assert publication["status"] == "INVESTMENT_OS_CANONICAL_REFRESH_AND_STATE_RECONCILIATION_ACCEPTED"
    assert publication["package_sha256"] == "479d375da1586419a98bb2821342cf691b0d1358882b66bc1601fd717ab2a9aa"
    assert publication["file_library_import_status"] == "USER_UPLOAD_PENDING"
    assert publication["trade_authority"] == "NONE"


def test_committed_evidence_hashes_match() -> None:
    root = Path(__file__).resolve().parents[1]
    publication = json.loads((root / "config/post_fmdl4_release8_publication.json").read_text(encoding="utf-8"))
    for key, filename in module.EVIDENCE_FILES.items():
        assert module.sha256(root / "evidence/post_fmdl4" / filename) == publication["evidence_hashes"][key]


def test_cleanup_is_gated() -> None:
    root = Path(__file__).resolve().parents[1]
    cleanup = json.loads((root / "evidence/post_fmdl4/POST_FMDL4_FILE_LIBRARY_RETAIN_DELETE_MANIFEST.json").read_text(encoding="utf-8"))
    assert cleanup["execute_only_after_new_files_uploaded_opened_and_sha_validated"] is True
    assert cleanup["project_sources_required"] is False
    assert cleanup["safety_rule"] == "DO_NOT_DELETE_RELEASE4_UNTIL_RELEASE8_IS_UPLOADED_OPENABLE_AND_SHA_VERIFIED"
