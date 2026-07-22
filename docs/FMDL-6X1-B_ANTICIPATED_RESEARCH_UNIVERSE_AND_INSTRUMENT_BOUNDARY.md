# FMDL-6X1-B — Anticipated Research Universe & Instrument Boundary

## Objective

Freeze the channel-agnostic US-equity research universe before any full Security Master or historical backfill is built. This phase defines what must be classified, what may enter issuer-level research, what requires a special analytical profile, what is reference-only, what is excluded, and what must be quarantined.

## Entry gate

- FMDL-6X1-A Release: `FMDL6X1A_20260722_795fcd84ed00`
- Required status: `FMDL6X1A_EXISTING_PILOT_AUDIT_AND_DUAL_ACTIVATION_CONTRACT_ACCEPTED`
- Research Production Gate: open for controlled build
- Brokerage & Real-Account Gate: `CLOSED_NO_CHANNEL`
- `trade_authority = NONE`

## Two-layer universe

### Security Master Universe

The future Security Master must classify every security row observed in the official current or historical directories of `XNYS`, `XNAS` and `XASE`. Membership is based on venue and official directory evidence only.

Price, market capitalization, liquidity, profitability, index membership and investment attractiveness must not determine Security Master membership. Excluded instruments remain classified records rather than disappearing from the evidence base. Delisted, acquired, renamed and transferred identities must be retained.

### Issuer Research Universe

The issuer research universe is derived from the Security Master. It contains only securities that can be routed to an explicit issuer, accounting and business-model research profile. Research eligibility does not create candidate, simulation or real-account authority.

A separate reference and hedge universe holds ETFs, ETNs, closed-end funds and index proxies. These instruments must never be mixed into issuer-level fundamental factor ranking.

## Orthogonal states

Every security has separate status dimensions:

1. **Research status** — core eligible, special-profile eligible, review required, reference only, excluded or quarantined.
2. **Channel status** — defaults to `CHANNEL_ELIGIBILITY_PENDING` while no brokerage channel exists.
3. **Portfolio status** — defaults to `PORTFOLIO_ADMISSION_NOT_AUTHORIZED`.
4. **Listing lifecycle status** — active, suspended, delisted, acquired, renamed, transferred, bankrupt, incomplete or quarantined.

No implementation may infer channel eligibility or portfolio admission from research eligibility.

## Core research-eligible instruments

- US domestic common stock;
- foreign-private-issuer ordinary shares listed on a target venue;
- sponsored exchange-listed ADRs with resolved underlying issuer and ADR ratio;
- equity REIT common stock routed to a REIT-specific profile.

## Special-profile research instruments

These are researchable but must not enter the standard industrial-company factor engine:

- BDC common stock — NAV, NII, credit-quality and leverage profile;
- publicly traded partnership or MLP common units — DCF, distribution coverage, leverage and tax profile;
- royalty trusts or comparable pass-through units — reserve decline, distribution and tax profile;
- pre-business-combination SPAC common shares — event-driven trust, deadline, redemption and sponsor profile.

The inclusion of a special profile is not a recommendation and does not authorize candidate admission.

## Reference only

- ETFs;
- exchange-traded notes;
- closed-end funds;
- index and market proxies.

These may later support benchmarking, hedging and market-context analysis but are outside issuer factor ranking.

## Explicit exclusions

- mutual funds;
- preferred and depositary preferred securities;
- corporate and convertible debt;
- warrants, rights, options and futures;
- structured notes;
- SPAC units and warrants;
- OTC securities and unsponsored OTC ADRs;
- crypto assets.

## Quarantine

Quarantine is mandatory for unknown or ambiguous instruments, unresolved ADR underlyings or ratios, conflicting official classifications, stapled/composite securities, missing issuer/listing identities and unresolved shell or reverse-merger status.

Unknown instruments are never default-included.

## Identity and duplicate-exposure rules

The accepted FMDL-6A model remains authoritative:

`Issuer → Share Class → Security → Effective-dated Listing`

Ticker and exchange are not immutable identities. ADRs remain distinct securities from their underlying shares but require an explicit cross-link. A/H/ADR and other same-issuer cross-market relationships must be represented so later research and portfolio layers can detect duplicate economic exposure.

## Point-in-time and survivorship controls

- effective-from and effective-to membership fields are required;
- retrieval timestamp and source lineage are required;
- delisted, acquired and renamed securities are retained;
- current-only backfill is forbidden;
- future information may not leak into historical membership;
- investability filters are deferred to FMDL-6X3.

## Authority and conflict policy

Classification priority:

1. official exchange or regulatory directory;
2. SEC submissions and filing security description;
3. issuer or depositary official disclosure;
4. explicitly approved fallback.

Fallbacks cannot silently create decision-grade classifications. Unresolved conflict results in quarantine.

## Phase boundary

FMDL-6X1-B creates no live Security Master rows, no historical data and no portfolio state. It freezes the contract needed by:

- FMDL-6X1-C for live source, cost and execution-route revalidation;
- FMDL-6X1-D for the full-build, storage, sharding and recovery contract.

## Required exit

`FMDL6X1B_ANTICIPATED_RESEARCH_UNIVERSE_AND_INSTRUMENT_BOUNDARY_ACCEPTED`

Next gate:

`FMDL-6X1-C_SOURCE_COST_AND_EXECUTION_ROUTE_REVALIDATION`
