from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_commos_sell_harness_requires_approval():
    owner = client.post("/v1/identities", json={"entity_type":"farmer","country":"UG","display_name":"Commodity Owner"}).json()
    lot = client.post("/v1/commos/lots", json={
        "commodity":"coffee",
        "origin_country":"UG",
        "quantity":1000,
        "unit":"kg",
        "grade":"AA",
        "owner_id":owner["agros_id"],
        "attributes":{"traceability":"verified"}
    }).json()
    assert lot["status"] == "available"

    quote = client.post("/v1/commos/market/quote", json={
        "lot_id":lot["lot_id"],"reference_price":4.2,"currency":"USD","price_unit":"kg"
    }).json()
    assert quote["gross_reference_value"] == 4200

    run = client.post("/v1/commos/runs", json={
        "intent":"sell",
        "lot_id":lot["lot_id"],
        "requested_by":"trader:demo",
        "institution":"DCF"
    }).json()
    assert run["status"] == "approval_required"
    assert any(x["skill"] == "trade.execute" and x["requires_approval"] for x in run["plan"])

    proposal = client.post("/v1/commos/trade/proposals", json={
        "run_id":run["run_id"],"buyer_id":"buyer:exporter-1","unit_price":4.35,"currency":"USD"
    }).json()

    denied = client.post(f"/v1/commos/trade/proposals/{proposal['proposal_id']}/execute")
    assert denied.status_code == 409

    approval = client.post(f"/v1/commos/runs/{run['run_id']}/approve?approved_by=ops%40dcf")
    assert approval.status_code == 200

    executed = client.post(f"/v1/commos/trade/proposals/{proposal['proposal_id']}/execute")
    assert executed.status_code == 200
    payload = executed.json()
    assert payload["lot"]["status"] == "sold"
    assert payload["run"]["status"] == "completed"

def test_commos_finance_intent_is_read_only_ready():
    owner = client.post("/v1/identities", json={"entity_type":"coop","country":"UG","display_name":"Demo Coop"}).json()
    lot = client.post("/v1/commos/lots", json={
        "commodity":"coffee","origin_country":"UG","quantity":5000,"unit":"kg","owner_id":owner["agros_id"]
    }).json()
    run = client.post("/v1/commos/runs", json={
        "intent":"finance","lot_id":lot["lot_id"],"requested_by":"bank:demo"
    }).json()
    assert run["status"] == "ready"
    assert all(not s["requires_approval"] for s in run["plan"])


def test_commos_finance_risk_compliance_and_settlement_preview():
    owner = client.post("/v1/identities", json={"entity_type":"coop","country":"UG","display_name":"Traceable Coop"}).json()
    farm = client.post("/v1/identities", json={"entity_type":"farm","country":"UG","display_name":"Farm One"}).json()
    lot = client.post("/v1/commos/lots", json={
        "commodity":"coffee",
        "origin_country":"UG",
        "quantity":10000,
        "unit":"kg",
        "owner_id":owner["agros_id"],
        "farm_ids":[farm["agros_id"]],
        "warehouse_id":"warehouse:demo",
        "attributes":{"traceability":"verified"}
    }).json()

    finance = client.post("/v1/commos/skills/finance.assess", json={
        "lot_id":lot["lot_id"], "reference_unit_price":4.0, "advance_rate":0.6, "currency":"USD"
    }).json()
    assert finance["max_facility"] == 24000

    risk = client.post("/v1/commos/skills/risk.assess", json={
        "lot_id":lot["lot_id"], "reference_unit_price":4.0, "downside_percent":15, "currency":"USD"
    }).json()
    assert risk["risk_rating"] == "low"
    assert risk["flags"] == []

    compliance = client.post("/v1/commos/skills/compliance.check", json={
        "lot_id":lot["lot_id"], "require_traceability":True, "require_farm_links":True, "require_warehouse":True
    }).json()
    assert compliance["passed"] is True

    settlement = client.post("/v1/commos/settlements/preview", json={
        "lot_id":lot["lot_id"], "gross_value":40000, "currency":"USD",
        "lender_percent":20, "insurance_percent":3, "cooperative_percent":2, "platform_percent":1
    }).json()
    assert settlement["balanced"] is True
    assert settlement["allocations"]["owner_residual"] == 29600
