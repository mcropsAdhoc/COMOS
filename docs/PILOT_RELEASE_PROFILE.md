# COMMOS Pilot Release Profile

## Intended use
This release is limited to named pilot institutions, controlled demonstrations, sandbox trading, market intelligence, commodity registration, workflow prototyping, API integration testing and limited supervised transactions.

## Explicitly out of scope
- autonomous or unsupervised settlement
- high-value settlement above configured pilot caps
- legally final exchange/clearing functions
- production bank credit origination without an external lender approval
- unrestricted external-agent execution
- anonymous mutation APIs

## Default safety envelope
- COMMOS_PILOT_MODE=true
- supervised roles: dcf_admin, pilot_approver, bank_approver
- USD transaction cap: 10,000
- UGX transaction cap: 40,000,000
- counterparty limits required for order fills
- OPA fail-closed for critical actions
- Temporal required for durable trade/finance workflows
- ownership transfer only after settlement reference
- all financial amounts use fixed precision

## Pilot acceptance gates
1. All CI jobs green.
2. Alembic migrations pass from a clean Postgres instance.
3. OIDC issuer configured and auth-required enabled.
4. OPA reachable and critical actions fail closed on outage.
5. PostgreSQL, OPA and AgPay health green.
6. Synthetic /health and authenticated workflow checks green.
7. Backup/restore drill completed before real-value transactions.
8. Named incident owner and pilot institution contacts recorded.
