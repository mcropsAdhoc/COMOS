# COMMOS Live Infrastructure

## Current live-ready topology

```text
COMMOS UI
   |
COMMOS API
   |
   +-- PostgreSQL / Supabase
   +-- OPA Policy Service
   +-- AgrOS AgPay API
   +-- Buyer APIs
   +-- International market feed
   +-- Uganda/East Africa market feed
   +-- FRED public coffee benchmark
```

## Health endpoint

`GET /v1/commos/infrastructure/health`

This reports only configuration/reachability status and never returns secrets.

## PostgreSQL

For serverless runtimes use a transaction pooler and set:

```
DATABASE_URL=postgresql+psycopg://...
DATABASE_POOLER_MODE=transaction
```

COMMOS disables psycopg automatic prepared statements in transaction-pooler mode.

## OPA

Deploy `policies/commos.rego` to an OPA service and set:

```
OPA_URL=https://<opa-host>
```

COMMOS calls:

`POST {OPA_URL}/v1/data/commos/decision`

If OPA is unavailable, persistent local policy rules remain the fallback.

## AgPay

Set:

```
AGPAY_API_URL=https://<agros-agpay-host>
AGPAY_API_TOKEN=<secret>
```

Approved settlements are sent to:

`POST {AGPAY_API_URL}/v1/settlements`

with an idempotency key.

## Buyers

Configure any of:

```
BUYER_EXPORTER_API_URL=
BUYER_EXPORTER_API_TOKEN=
BUYER_PROCESSOR_API_URL=
BUYER_PROCESSOR_API_TOKEN=
BUYER_ROASTER_API_URL=
BUYER_ROASTER_API_TOKEN=
```

Each connector is normalized by COMMOS.

## Market feeds

Partner feeds:

```
MARKET_INTL_API_URL=
MARKET_INTL_API_TOKEN=
MARKET_UG_API_URL=
MARKET_UG_API_TOKEN=
```

Credential-free global coffee benchmark:

`POST /v1/commos/market/public/fred/coffee/sync?variety=arabica`

or

`POST /v1/commos/market/public/fred/coffee/sync?variety=robusta`

The resulting observation is persisted into the COMMOS normalized market store.
