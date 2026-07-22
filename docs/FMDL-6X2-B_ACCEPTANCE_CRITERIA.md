# FMDL-6X2-B Acceptance Criteria

Acceptance requires all of the following:

- bind the accepted FMDL-6X2-A Release 30 pointer and Current assets;
- account for every accepted input Security record through identity lineage;
- preserve every input Listing as one canonical Listing record;
- issue unique Issuer, Security and Listing IDs without fuzzy issuer merging;
- preserve inherited FMDL-6X2-A quarantine rows;
- infer no SEC CIK without official evidence;
- produce all six required review queues, even when a queue is empty;
- retain `CHANNEL_ELIGIBILITY_PENDING`, `PORTFOLIO_ADMISSION_NOT_AUTHORIZED` and `trade_authority = NONE`;
- create deterministic identity and review-queue ZIPs plus file and shard hashes;
- pass same-input byte replay and Current/immutable Release parity;
- preserve Current and LKG after a failed or colliding publication;
- publish `FMDL6X2B_IDENTITY_CLASSIFICATION_AND_REVIEW_QUEUES_ACCEPTED` and open only FMDL-6X2-C.
