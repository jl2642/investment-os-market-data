# Accepted identity baseline transport

This directory contains the six-part `gzip+base64` transport for the verified identity-only derivative of the 2026-07-17 accepted A-share baseline. `automation/wp3_2a/materialize_identity_baseline.py` reconstructs and validates the exact JSONL consumed by Gate v3.

The transport has identity-diff authority only. It cannot mutate Candidate, Research, account, simulation or order state. `trade_authority=NONE`.
