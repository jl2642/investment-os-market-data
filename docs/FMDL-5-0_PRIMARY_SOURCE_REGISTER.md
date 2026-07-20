# FMDL-5-0 Primary Source Register

## Hong Kong Stock Connect

- Authority: HKEX Stock Connect eligible-security lists
- Scope: Southbound securities eligible under Shanghai Connect and Shenzhen Connect
- Required controls: source URL, retrieval timestamp, effective date, list type, buy/sell eligibility, sell-only status, change notice lineage and file hash
- Official reference: `https://www.hkex.com.hk/mutual-market/stock-connect/eligible-stocks/view-all-eligible-securities`

## Hong Kong issuer disclosures

- Authority: HKEXnews issuer filings and reports
- Scope: results announcements, annual/interim reports, circulars, prospectuses and company-action disclosures
- Required controls: issuer code, document title, publication timestamp, reporting period, document hash and evidence registration
- Official reference: `https://www.hkexnews.hk/`

## U.S. filings and XBRL

- Authority: SEC EDGAR APIs and bulk archives
- Scope: submissions, Company Facts, XBRL Frames, 10-K, 10-Q, 8-K, 20-F, 40-F and 6-K
- Required controls: CIK, accession number, accepted timestamp, form, amendment status, taxonomy, fiscal period and raw filing URL
- Official reference: `https://www.sec.gov/search-filings/edgar-application-programming-interfaces`

## Source policy

Official sources govern eligibility, identity and filings. Free third-party price or convenience data may be used only with explicit fallback order, retrieval date, source identity, validation status and no silent authority substitution.
