# COMMOS Recovery Drill

Targets: RPO <= 5 minutes; RTO <= 60 minutes.

Quarterly:
1. Restore PostgreSQL backup into isolated environment.
2. Run Alembic to expected revision.
3. Reconcile ledger totals and ownership-event chains.
4. Replay synthetic settlement idempotently.
5. Validate OPA critical-action denial and approval path.
6. Validate Temporal workflow resume/compensation.
7. Record actual RPO/RTO and corrective actions.
