from datetime import datetime, timezone
from decimal import Decimal
import os
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.commos import router as commos_router
from app.commos_platform import router as commos_platform_router
from app.security import Principal, current_principal, principal_from_authorization, set_current_principal, reset_current_principal

app = FastAPI(title="DCF AgrOS Agent-Native Infrastructure", version="0.3.0")
cors_origins = [x.strip() for x in os.getenv("COMMOS_CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUBLIC_PATHS={"/health","/docs","/openapi.json","/v1/dashboard/public-summary","/v1/commos/dashboard"}

@app.middleware("http")
async def commos_auth_guard(request, call_next):
    required=os.getenv("COMMOS_AUTH_REQUIRED","true").lower()=="true"
    protected=request.url.path.startswith("/v1") and request.url.path not in PUBLIC_PATHS and request.method!="OPTIONS"
    ctx=None
    if protected:
        try:
            if required:
                principal=principal_from_authorization(request.headers.get("Authorization"))
            else:
                principal=Principal(
                    subject=os.getenv("COMMOS_DEV_SUBJECT","dev-user"),
                    tenant_id=os.getenv("COMMOS_DEV_TENANT","dev"),
                    institution_id=os.getenv("COMMOS_DEV_INSTITUTION","dcf"),
                    roles=("dcf_admin","bank_approver"),scopes=("*",),token_id="dev-token",auth_method="dev-bypass"
                )
            request.state.principal=principal
            ctx=set_current_principal(principal)
        except HTTPException as exc:
            return JSONResponse({"detail":exc.detail},status_code=exc.status_code)
    try:
        return await call_next(request)
    finally:
        if ctx is not None:
            reset_current_principal(ctx)
app.include_router(commos_router)
app.include_router(commos_platform_router)

identities = {}
edges = []
sessions = {}
ledger = []
events = []

class IdentityCreate(BaseModel):
    entity_type: str
    country: str = "UG"
    display_name: str
    metadata: dict = {}

class EdgeCreate(BaseModel):
    source_id: str
    relationship: str
    target_id: str
    metadata: dict = {}

class CreditRequest(BaseModel):
    farmer_id: str
    requested_amount: Decimal = Field(gt=0)
    estimated_harvest_value: Decimal = Field(gt=0)

class AgentPlan(BaseModel):
    intent: str
    farmer_id: str
    amount: Decimal = Field(gt=0)

class PaymentRequest(BaseModel):
    payee_id: str
    amount: float = Field(gt=0)
    currency: str = "UGX"

def emit(kind, entity, payload=None):
    event = {"event_id": str(uuid4()), "event_type": kind, "entity_id": entity, "payload": payload or {}, "occurred_at": datetime.now(timezone.utc).isoformat()}
    events.append(event)
    return event

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.3.0"}

@app.get("/v1/dashboard/public-summary")
def dashboard():
    pending = sum(1 for s in sessions.values() if s["status"] == "approval_required")
    return {
        "primitives": [
            {"id":"01","name":"AgrOS ID","status":"online","value":str(len(identities)),"detail":"Canonical identities"},
            {"id":"02","name":"AgrOS Graph","status":"online","value":str(len(edges)),"detail":"Economic relationships"},
            {"id":"03","name":"Skills API","status":"online","value":"2","detail":"Governed capabilities"},
            {"id":"04","name":"Agent Runtime","status":"guarded","value":str(pending),"detail":"Plans awaiting approval"},
            {"id":"05","name":"AgPay + Ledger","status":"online","value":str(len(ledger)),"detail":"Ledger entries"}
        ]
    }

@app.post("/v1/identities")
def create_identity(body: IdentityCreate):
    agros_id = f"agros:{body.entity_type}:{body.country}:{uuid4().hex[:12]}"
    item = {"agros_id": agros_id, **body.model_dump(), "created_at": datetime.now(timezone.utc).isoformat()}
    identities[agros_id] = item
    emit("identity.created", agros_id)
    return item

@app.post("/v1/graph/relationships")
def create_edge(body: EdgeCreate):
    if body.source_id not in identities or body.target_id not in identities:
        raise HTTPException(404, "source or target identity not found")
    item = {"edge_id": str(uuid4()), **body.model_dump(), "created_at": datetime.now(timezone.utc).isoformat()}
    edges.append(item)
    emit("graph.relationship.created", item["edge_id"], item)
    return item

@app.post("/v1/skills/credit.prequalify")
def credit_prequalify(body: CreditRequest):
    if body.farmer_id not in identities:
        raise HTTPException(404, "farmer not found")
    ltv = body.requested_amount / body.estimated_harvest_value
    score = max(300, min(850, round(760 - 220 * ltv)))
    eligible = ltv <= 0.6 and score >= 600
    result = {"farmer_id": body.farmer_id, "score": score, "eligible": eligible, "ltv": round(ltv, 4), "max_facility": round(body.estimated_harvest_value * 0.6, 2)}
    emit("credit.prequalified", body.farmer_id, result)
    return result

@app.post("/v1/agent/sessions")
def agent_plan(body: AgentPlan):
    if body.farmer_id not in identities:
        raise HTTPException(404, "farmer not found")
    sid = f"AG-{uuid4().hex[:8].upper()}"
    plan = [
        {"step":1,"skill":"credit.prequalify","requires_approval":False},
        {"step":2,"skill":"payment.disburse","requires_approval":True}
    ]
    sessions[sid] = {"session_id": sid, "intent": body.model_dump(), "plan": plan, "status": "approval_required"}
    emit("agent.plan.created", sid, {"intent": body.intent})
    return sessions[sid]

@app.post("/v1/agent/sessions/{session_id}/approve")
def approve(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "session not found")
    principal=current_principal()
    sessions[session_id]["status"]="approved"
    sessions[session_id]["approved_by"]=principal.subject
    sessions[session_id]["institution_id"]=principal.institution_id
    emit("agent.plan.approved",session_id,{"approved_by":principal.subject,"institution_id":principal.institution_id})
    return sessions[session_id]

@app.post("/v1/skills/payment.disburse")
def disburse(body: PaymentRequest, session_id: str, idempotency_key: str = Header(alias="Idempotency-Key")):
    session = sessions.get(session_id)
    if not session or session["status"] != "approved":
        raise HTTPException(409, "approved agent session required")
    existing = next((x for x in ledger if x["idempotency_key"] == idempotency_key), None)
    if existing:
        return existing
    txid = f"txn_{uuid4().hex[:12]}"
    entry = {"transaction_id": txid, "payee_id": body.payee_id, "amount": body.amount, "currency": body.currency, "debits": body.amount, "credits": body.amount, "balanced": True, "idempotency_key": idempotency_key, "status": "confirmed"}
    ledger.append(entry)
    emit("payment.confirmed", txid, {"amount": body.amount, "currency": body.currency})
    return entry

@app.get("/v1/audit/events")
def audit():
    return list(reversed(events[-100:]))
