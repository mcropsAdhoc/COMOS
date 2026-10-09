package commos

test_critical_requires_approval if {
  result := decision with input as {"institution_id":"dcf","actor_type":"operator","action":"settlement.execute"}
  result.allow
  result.requires_approval
}
test_read_only_does_not_require_approval if {
  result := decision with input as {"institution_id":"dcf","actor_type":"operator","action":"market.quote"}
  result.allow
  not result.requires_approval
}
test_unknown_denied if {
  result := decision with input as {"institution_id":"unknown","actor_type":"unknown","action":"settlement.execute"}
  not result.allow
}
