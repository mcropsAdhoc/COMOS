# COMMOS — Commodity Agentic Services Harness

## Mission

COMMOS is the commodity-services agent harness that sits above AgrOS.

AgrOS supplies the trusted primitives:

1. AgrOS ID
2. AgrOS Graph
3. Skills API
4. Agent Runtime and approval controls
5. AgPay + Event Ledger

COMMOS composes those primitives into commodity-specific agents and workflows for trade, finance, risk, compliance, logistics, market intelligence and settlement.

## Architectural boundary

```text
Users / Institutions / External Agents
                |
             COMMOS
   Commodity Agentic Services Harness
                |
  +-------------+-------------+
  | Market | Trade | Finance  |
  | Risk | Compliance | Settle|
  +-------------+-------------+
                |
         Governed Skills
                |
              AgrOS
 ID | Graph | Policy | AgPay | Ledger
                |
 Banks | Buyers | Warehouses | MoMo
 Exchanges | Insurers | CRBs | Climate
```

COMMOS never owns raw payment credentials and never bypasses AgrOS authorization.

## Initial domain agents

### Market Agent
Reads reference prices, lot attributes and market feeds. Produces quote context, spread estimates and market summaries.

### Trade Agent
Creates buyer-matching and sale proposals. Trade execution is critical-risk and requires explicit approval.

### Finance Agent
Assesses inventory-backed, warehouse-receipt and pre-export financing opportunities.

### Risk Agent
Evaluates commodity price exposure, concentration, collateral coverage and counterparty risk.

### Compliance Agent
Runs traceability, EUDR, certification and policy checks before trade or financing.

### Settlement Agent
Creates settlement instructions for AgPay. Settlement execution remains an AgrOS critical skill.

## Commodity object

The canonical object is a digital commodity lot:

```json
{
  "lot_id": "agros:lot:UG:...",
  "commodity": "coffee",
  "owner_id": "agros:coop:UG:...",
  "farm_ids": [],
  "quantity": 5000,
  "unit": "kg",
  "grade": "AA",
  "warehouse_id": null,
  "attributes": {
    "traceability": "verified",
    "eudr": "ready"
  },
  "status": "available"
}
```

## Harness lifecycle

```text
Commodity lot
   |
Intent: sell / finance / hedge / settle / assess
   |
COMMOS planner
   |
Skill graph
   |
Risk + policy checks
   |
Approval boundary where required
   |
Execution through AgrOS skills
   |
Event + audit + settlement trail
```

## Initial skill registry

- commodity.lot.create
- market.quote
- trade.propose
- finance.assess
- risk.assess
- compliance.check
- trade.execute
- settlement.execute

## Risk model

Low-risk skills are data/read operations. Medium-risk skills create recommendations or proposals. Critical skills move ownership or money and therefore always require approval.

## Next increments

1. Persist lots/runs/proposals in PostgreSQL.
2. Replace static registry with versioned skill manifests.
3. Add buyer and warehouse connectors.
4. Add structured price-feed providers.
5. Add AgPay settlement posting.
6. Add warehouse-receipt and collateral objects.
7. Add forward contract and hedge primitives.
8. Add commodity order book.
9. Add EUDR/MRV evidence packs.
10. Add model-provider-neutral LLM planner with deterministic tool execution.
11. Add institutional multi-tenancy and OPA policies.
12. Add MCP-compatible COMMOS gateway for external agents.
