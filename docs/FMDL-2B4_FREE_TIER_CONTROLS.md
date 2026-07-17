# FMDL-2B-4 Free-tier Controls

- Daily normal operation uses the accepted full-market snapshot and does not redownload 5,529 full histories.
- Full-history calls are limited to continuity breaks, new symbols and inherited quarantines.
- More than 50 automatic repairs in one run is escalated rather than silently consuming unbounded Actions minutes.
- Multi-session gaps use a manual full-rebase path instead of pretending one snapshot reconstructs missing sessions.
- Delta files compact after 20 files.
- One scheduled B4 run occurs after the FMDL-1 daily Current window.
- No paid market-data API, paid runner or broker API is used.
