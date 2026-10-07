from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_vertical_slice():
    farmer = client.post("/v1/identities", json={"entity_type":"farmer","country":"UG","display_name":"Demo Farmer"}).json()
    farm = client.post("/v1/identities", json={"entity_type":"farm","country":"UG","display_name":"Demo Farm"}).json()
    edge = client.post("/v1/graph/relationships", json={"source_id":farmer["agros_id"],"relationship":"OWNS","target_id":farm["agros_id"]})
    assert edge.status_code == 200

    credit = client.post("/v1/skills/credit.prequalify", json={"farmer_id":farmer["agros_id"],"requested_amount":2000000,"estimated_harvest_value":5000000}).json()
    assert credit["eligible"] is True

    session = client.post("/v1/agent/sessions", json={"intent":"finance farmer","farmer_id":farmer["agros_id"],"amount":2000000}).json()
    denied = client.post(f"/v1/skills/payment.disburse?session_id={session['session_id']}", headers={"Idempotency-Key":"demo-1"}, json={"payee_id":farmer["agros_id"],"amount":2000000,"currency":"UGX"})
    assert denied.status_code == 409

    approved = client.post(f"/v1/agent/sessions/{session['session_id']}/approve")
    assert approved.status_code == 200

    paid = client.post(f"/v1/skills/payment.disburse?session_id={session['session_id']}", headers={"Idempotency-Key":"demo-1"}, json={"payee_id":farmer["agros_id"],"amount":2000000,"currency":"UGX"}).json()
    assert paid["balanced"] is True
