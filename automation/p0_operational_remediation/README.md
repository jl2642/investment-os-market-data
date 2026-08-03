# P0 Operational Remediation

This module adds integration contracts and deterministic validation/build tools without replacing the existing Investment OS runtime.

Commands:

```bash
python automation/p0_operational_remediation/p0_operational.py validate --repo-root .
python automation/p0_operational_remediation/p0_operational.py build-run-manifest ...
python automation/p0_operational_remediation/p0_operational.py build-report-manifest ...
```

The validator distinguishes integrity errors from known production blockers. `PASS_WITH_BLOCKERS` is expected until R6 completes. It never changes positions, Candidate state, rules or orders.
