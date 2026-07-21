from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "run_fmdl5b2_candidate.py"
spec = importlib.util.spec_from_file_location("fmdl5b2_candidate", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_explicit_others_suffix_normalization() -> None:
    assert module.normalized_issuer_name("Jiangsu Expressway Co. Ltd. - Others") == "Jiangsu Expressway Co. Ltd."
    assert module.normalized_issuer_name("China Communications Services Corporation Ltd. - Domestic Shares") == "China Communications Services Corporation Ltd."
    assert module.normalized_issuer_name("Biocytogen Pharmaceuticals (Beijing) Co., Ltd.- B - Others") == "Biocytogen Pharmaceuticals (Beijing) Co., Ltd."


def test_no_fuzzy_normalization() -> None:
    assert module.normalized_issuer_name("Others Technology Holdings Ltd.") == "Others Technology Holdings Ltd."
    assert module.normalized_issuer_name("Alpha Other Corporation") == "Alpha Other Corporation"
