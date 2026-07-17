# FMDL-2B-4 Decision Log

- Preserve the accepted FMDL-2B-2 base as immutable.
- Use validated current-session snapshot rows for the normal one-session fast path.
- Route QFQ continuity breaks to full-series repair.
- Block multi-session gaps instead of fabricating missing sessions.
- Publish history and factors together or publish neither.
- Defer all screening and portfolio consequences to later phases.
