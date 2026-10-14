# COMMOS Pilot SLOs and Operations

## Service objectives
| Signal | Pilot target |
|---|---:|
| API availability | 99.5% |
| GET p95 | < 750 ms |
| internal skill p95 | < 3 s |
| settlement instruction p95 | < 8 s |
| failed settlement rate | < 0.5% |
| ledger imbalance | 0 |
| duplicate settlement | 0 |
| unauthorized critical execution | 0 |
| lost audit/ownership events | 0 |

## Alert conditions
- 5xx rate > 2% over 5 minutes
- p95 API latency > 1.5 s over 10 minutes
- PostgreSQL unavailable
- OPA unavailable
- AgPay unavailable
- any ledger imbalance
- any duplicate idempotency conflict
- Temporal workflow stuck > 10 minutes
- pilot exposure cap violation
- counterparty exposure limit breach
- market feed stale beyond configured freshness

## Incident severity
- SEV-1: unauthorized execution, ledger imbalance, ownership corruption, duplicate settlement, database loss.
- SEV-2: settlement outage, OPA outage, Temporal outage, sustained 5xx.
- SEV-3: market-feed degradation, noncritical connector failure.

## Immediate SEV-1 actions
1. Disable value-moving skills through OPA.
2. Freeze new trade/settlement workflows.
3. Preserve logs/traces and database snapshots.
4. Reconcile ledger, ownership events and AgPay settlement records.
5. Notify pilot institution owners.
6. Resume only after signed incident review.

## Recovery objectives
Pilot target RPO: <= 15 minutes.
Pilot target RTO: <= 2 hours.
Industrial target should tighten these after measured pilot behavior.
