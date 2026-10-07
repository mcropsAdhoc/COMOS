from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def make_lot():
    owner=client.post("/v1/identities",json={"entity_type":"coop","country":"UG","display_name":"COMMOS Coop"}).json()
    farm=client.post("/v1/identities",json={"entity_type":"farm","country":"UG","display_name":"Farm"}).json()
    return client.post("/v1/commos/lots",json={
        "commodity":"coffee","origin_country":"UG","quantity":5000,"unit":"kg","grade":"AA",
        "owner_id":owner["agros_id"],"farm_ids":[farm["agros_id"]],"warehouse_id":"WH-01",
        "attributes":{"traceability":"verified"}
    }).json()

def test_mcp_planner_and_market_gateway():
    lot=make_lot()
    init=client.post("/v1/commos/mcp",json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}).json()
    assert init["result"]["serverInfo"]["name"]=="COMMOS"
    tools=client.post("/v1/commos/mcp",json={"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}).json()
    assert len(tools["result"]["tools"])>=10
    plan=client.post("/v1/commos/planner/plan",json={"intent":"sell","lot_id":lot["lot_id"],"requested_by":"operator:1","institution_id":"dcf"}).json()
    assert plan["planner"]=="deterministic-v1"
    assert plan["transaction_authority"]=="none"
    assert any(s["requires_approval"] for s in plan["steps"])
    obs=client.post("/v1/commos/market/observations",json={"commodity":"coffee","market":"Kampala","price":4.1,"currency":"USD","price_unit":"kg","source":"test","region":"UG"}).json()
    assert obs["price"]==4.1
    latest=client.get("/v1/commos/market/observations/coffee").json()
    assert len(latest)>=1

def test_orderbook_receipt_buyer_forward_eudr_policy_settlement_observability():
    lot=make_lot()
    order=client.post("/v1/commos/orderbook/orders",json={
        "order_type":"offer","side":"sell","commodity":"coffee","lot_id":lot["lot_id"],
        "actor_id":lot["owner_id"],"quantity":5000,"unit":"kg","limit_price":4.2,"currency":"USD"
    }).json()
    accepted=client.post(f"/v1/commos/orderbook/orders/{order['order_id']}/accept?accepted_by=buyer:test").json()
    assert accepted["status"]=="accepted"

    receipt=client.post("/v1/commos/warehouse/receipts",json={
        "lot_id":lot["lot_id"],"warehouse_id":"WH-01","custodian_id":"custodian:1","owner_id":lot["owner_id"],
        "collateral_value":21000,"currency":"USD"
    }).json()
    assert receipt["status"]=="issued"

    quote=client.post("/v1/commos/buyers/quote",json={
        "buyer_connector":"exporter_demo","lot_id":lot["lot_id"],"reference_price":4.0,"currency":"USD"
    }).json()
    assert quote["status"]=="indicative"

    fwd=client.post("/v1/commos/forwards",json={
        "commodity":"coffee","seller_id":lot["owner_id"],"buyer_id":"buyer:test","quantity":3000,"unit":"kg",
        "delivery_date":(datetime.now(timezone.utc)+timedelta(days=90)).isoformat(),"fixed_price":4.3,"currency":"USD"
    }).json()
    assert fwd["status"]=="draft"

    hedge=client.post("/v1/commos/hedge/calculate",json={
        "exposure_quantity":5000,"forward_quantity":3000,"spot_reference":4.0,"forward_price":4.3
    }).json()
    assert hedge["interpretation"]=="partially_hedged"

    eudr=client.post("/v1/commos/eudr/evidence-packs",json={"lot_id":lot["lot_id"],"declaration":{"destination":"EU"}}).json()
    assert eudr["status"]=="ready"

    policy=client.post("/v1/commos/policy/evaluate",json={
        "institution_id":"dcf","actor_type":"operator","action":"settlement.execute","context":{"gross_value":20000}
    }).json()
    assert policy["requires_approval"] is True

    settlement=client.post("/v1/commos/agpay/settlements",json={
        "lot_id":lot["lot_id"],"gross_value":20000,"currency":"USD",
        "allocations":{"lender":4000,"insurance":600,"cooperative":400,"platform":200,"owner_residual":14800},
        "approved_by":"ops@dcf","approval_reference":"APR-001","idempotency_key":"SET-001"
    }).json()
    assert settlement["status"]=="submitted_to_agros"

    summary=client.get("/v1/commos/observability/summary").json()
    assert summary["traces"]>=1
    assert summary["monetary_exposure"]>=20000


def test_live_infrastructure_health_contract():
    health=client.get("/v1/commos/infrastructure/health")
    assert health.status_code == 200
    data=health.json()
    assert "services" in data
    assert "summary" in data
    assert any(x["kind"]=="database" for x in data["services"])

def test_live_connectors_fall_back_or_report_unconfigured():
    lot=make_lot()
    quote=client.post("/v1/commos/buyers/live-quote",json={
        "buyer_connector":"exporter_demo","lot_id":lot["lot_id"],"reference_price":4.0,"currency":"USD"
    })
    assert quote.status_code == 200
    assert quote.json()["connector_mode"] in ("sandbox","live")
