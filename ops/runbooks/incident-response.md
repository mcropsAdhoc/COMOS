# COMMOS Incident Response

Severity 1: unauthorized execution, ledger imbalance, duplicate settlement, ownership divergence, database loss.
- Freeze critical capabilities at OPA.
- Disable settlement and ownership-transfer skills.
- Preserve logs/traces and database snapshot.
- Reconcile ledger, ownership events, AgPay settlement records and partner acknowledgements.
- Require two-person approval before reopening.

Severity 2: connector outage, degraded market feed, elevated 5xx/latency.
- Circuit-break affected connector.
- Mark data stale/degraded.
- Prevent executable pricing from degraded sources.
- Restore or switch approved adapter.

Post-incident: timeline, root cause, financial exposure, affected entities, remediation owner, control change, recovery test.
