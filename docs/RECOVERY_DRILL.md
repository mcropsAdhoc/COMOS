# COMMOS Recovery Drill

Before enabling real-value supervised pilot transactions:

1. Take a database backup/snapshot.
2. Create a test lot, reservation, trade confirmation, ledger transaction and ownership event.
3. Record immutable identifiers.
4. Restore the backup into an isolated recovery database.
5. Run all migrations.
6. Reconcile row counts and financial invariants.
7. Verify ownership history and idempotency state.
8. Start COMMOS against the recovered database in an isolated environment.
9. Run synthetic read/write tests.
10. Record measured RPO/RTO and remediation items.

A drill is successful only if ledger debits equal credits, ownership history is intact, and duplicate settlement replay remains prevented.
