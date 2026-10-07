package commos

default decision := {
  "allow": false,
  "requires_approval": true,
  "reason": "no matching rule"
}

critical_actions := {
  "trade.execute",
  "settlement.execute",
  "warehouse.lien.create",
  "forward.activate"
}

decision := {
  "allow": true,
  "requires_approval": input.action in critical_actions,
  "reason": "critical action requires human approval"
} if {
  input.institution_id == "dcf"
  input.actor_type in {"operator", "agent_service"}
}

decision := {
  "allow": true,
  "requires_approval": true,
  "reason": "buyer may propose trade but execution is approval-gated"
} if {
  input.actor_type == "buyer"
  input.action in {"trade.propose", "trade.execute"}
}

decision := {
  "allow": true,
  "requires_approval": false,
  "reason": "read-only analytical capability"
} if {
  input.action in {
    "market.quote",
    "market.observe",
    "risk.assess",
    "compliance.check",
    "finance.assess",
    "planner.plan"
  }
}
