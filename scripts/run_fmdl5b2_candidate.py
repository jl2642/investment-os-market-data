#!/usr/bin/env python3
from __future__ import annotations

import re

import run_fmdl5b2_issuer_semantics as core

_original_normalized_issuer_name = core.normalized_issuer_name


def normalized_issuer_name(name: str) -> str:
    """Apply the additional explicit HKEX DI terminal share-class label `Others`.

    This is not fuzzy normalization. It removes only the official terminal
    `- Other` / `- Others` label after the core normalizer has removed explicit
    A/H/Domestic share-class labels and WVR/listing suffixes.
    """
    text = _original_normalized_issuer_name(name)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\s*-\s*OTHERS?\s*$", "", text, flags=re.IGNORECASE).strip()
        text = _original_normalized_issuer_name(text)
    return re.sub(r"\s+", " ", text)


core.normalized_issuer_name = normalized_issuer_name


if __name__ == "__main__":
    raise SystemExit(core.main())
