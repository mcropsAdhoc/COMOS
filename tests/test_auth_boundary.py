import os, jwt
from fastapi.testclient import TestClient
from app.main import app

SECRET="0123456789abcdef0123456789abcdef0123456789abcdef"
def token():
    return jwt.encode({"sub":"user-1","tenant_id":"tenant-1","institution_id":"dcf","roles":["dcf_admin"],"scope":"*","aud":"commos-api"},SECRET,algorithm="HS256")

def test_mutation_requires_bearer(monkeypatch):
    monkeypatch.setenv("COMMOS_AUTH_REQUIRED","true")
    monkeypatch.setenv("COMMOS_AUTH_MODE","dev")
    monkeypatch.setenv("COMMOS_DEV_JWT_SECRET",SECRET)
    r=TestClient(app).post("/v1/identities",json={"entity_type":"farmer","display_name":"x"})
    assert r.status_code==401

def test_authenticated_mutation(monkeypatch):
    monkeypatch.setenv("COMMOS_AUTH_REQUIRED","true")
    monkeypatch.setenv("COMMOS_AUTH_MODE","dev")
    monkeypatch.setenv("COMMOS_DEV_JWT_SECRET",SECRET)
    r=TestClient(app).post("/v1/identities",headers={"Authorization":f"Bearer {token()}"},json={"entity_type":"farmer","display_name":"x"})
    assert r.status_code==200
