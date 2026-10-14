# COMMOS Industrialization Program

## P0 release gates
- OIDC principal enforcement on all mutation routes.
- OPA fail-closed on critical actions.
- Decimal/Numeric monetary state.
- Double-entry ledger and immutable ownership events.
- Idempotency registry.
- Temporal durable workflows for trade/finance/title transfer.
- Mandatory CI: tests, migrations, dependency audit, CodeQL, secret scan, container scan, SBOM and OPA tests.

## Promotion rule
No production deployment from this branch until all P0 CI jobs pass and the hardening PR is reviewed.

## P1
HA replicas; institutional RBAC/ABAC; scoped MCP; reservations/partial fills; EUDR evidence graph; warehouse-receipt governance.

## P2
SLOs, alerts, on-call, synthetic probes, chaos tests, recovery drills, capacity/load tests.
