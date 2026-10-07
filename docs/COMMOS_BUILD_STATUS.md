# COMMOS Build Status

## Implemented

1. PostgreSQL commodity state — SQLAlchemy models, PostgreSQL DATABASE_URL support, SQLite CI fallback, Alembic bootstrap.
2. MCP / Agent Gateway — MCP-compatible JSON-RPC initialize, tools/list and tools/call gateway.
3. LLM-independent planner — deterministic structured intent to skill graph with no transaction authority.
4. Commodity Order Book — bid, offer, RFQ, acceptance and expiry fields.
5. Warehouse Receipts — custody, ownership, lien holder and collateral value.
6. Buyer Connectors — normalized exporter, processor and roaster sandbox adapter contracts.
7. Market-price adapters — normalized market observation store and international/local adapter registry.
8. Forward contracts + hedge primitives — forward objects and deterministic hedge ratio calculations.
9. EUDR evidence engine — lot-linked farm lineage, traceability evidence and risk status.
10. AgPay settlement execution — approved, balanced settlement instruction submitted to the AgrOS AgPay boundary.
11. Institutional OPA policies — OPA decision endpoint when configured, persistent local institutional rules as fallback.
12. Full agent observability — persisted skill traces, latency, failures, monetary exposure and provenance.

## Deployment topology

- COMMOS UI: Vercel project root `apps/commos`
- COMMOS API: Vercel project root repository root using `api/index.py` + FastAPI
- PostgreSQL: external managed PostgreSQL exposed as `DATABASE_URL`
- OPA: external policy service exposed as `OPA_URL`

## Required Vercel environment variables

```
DATABASE_URL=postgresql+psycopg://...
OPA_URL=https://...
AGPAY_MODE=sandbox
COMMOS_BUYER_MODE=sandbox
```

## GitHub Actions deployment secrets

```
VERCEL_TOKEN
VERCEL_ORG_ID
VERCEL_COMMOS_PROJECT_ID
VERCEL_COMMOS_API_PROJECT_ID
```

## Current external blocker

The connected Vercel team returns HTTP 403 for project creation. The repository and deployment workflows are ready; a Vercel account/team role with project-create permission is required before the first hosted deployment can be created.
