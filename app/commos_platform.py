from __future__ import annotations
import os, time, csv, io, re, html, hashlib, json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from typing import Literal, Any
import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from app.db import db_session, init_db
from app.commos_models import Order, WarehouseReceipt, ForwardContract, EudrEvidencePack, PolicyRule, AgentTrace, CommodityLot, ApprovalRecord
from app.commos_repository import get_lot, create_market_observation, latest_market_observations
from app.live_connectors import infrastructure_health
from app.security import current_principal
from app.financials import reserve_idempotency, complete_idempotency, post_balanced_transaction
from app.agent_control import authorize_capability

router = APIRouter(prefix="/v1/commos", tags=["COMMOS Platform"])
CRITICAL_ACTIONS={"trade.execute","settlement.execute","warehouse.lien.create","forward.activate","ownership.transfer","loan.originate"}

SKILL_GRAPH = {
    "sell":["market.quote","risk.assess","compliance.check","orderbook.offer.create","trade.execute","settlement.execute"],
    "finance":["market.quote","risk.assess","warehouse.receipt.read","finance.assess"],
    "hedge":["market.quote","risk.assess","forward.hedge"],
    "settle":["policy.evaluate","settlement.execute"],
    "assess":["market.quote","risk.assess","compliance.check"],
}

TOOL_MANIFEST = [
    {"name":"planner.plan","description":"Create deterministic commodity skill plan from structured intent"},
    {"name":"orderbook.create","description":"Create bid, offer or RFQ"},
    {"name":"orderbook.list","description":"List open commodity orders"},
    {"name":"warehouse.receipt.issue","description":"Issue custody/collateral receipt for a lot"},
    {"name":"buyer.quote","description":"Request normalized quote from registered buyer connector"},
    {"name":"market.observe","description":"Write normalized market observation"},
    {"name":"market.latest","description":"Read latest normalized market observations"},
    {"name":"forward.create","description":"Create commodity forward contract"},
    {"name":"forward.hedge","description":"Calculate forward hedge coverage"},
    {"name":"eudr.generate","description":"Generate lot-linked EUDR evidence pack"},
    {"name":"policy.evaluate","description":"Evaluate institutional policy and approval requirement"},
    {"name":"agpay.settle","description":"Submit approved settlement instruction to AgrOS AgPay bridge"},
    {"name":"observability.summary","description":"Return agent execution metrics"},
]

BUYERS = {
    "exporter_demo":{"type":"exporter","commodities":["coffee","cocoa"],"regions":["UG","KE"],"status":"sandbox"},
    "processor_demo":{"type":"processor","commodities":["coffee","maize"],"regions":["UG"],"status":"sandbox"},
    "roaster_demo":{"type":"roaster","commodities":["coffee"],"regions":["UG","EU"],"status":"sandbox"},
}

class PlanRequest(BaseModel):
    intent: Literal["sell","finance","hedge","settle","assess"]
    lot_id: str
    requested_by: str
    institution_id: str | None = None

class OrderCreate(BaseModel):
    order_type: Literal["bid","offer","rfq"]
    side: Literal["buy","sell"]
    commodity: str
    actor_id: str
    quantity: Decimal = Field(gt=0)
    unit: str = "kg"
    lot_id: str | None = None
    limit_price: Decimal | None = None
    currency: str = "USD"
    terms: dict = {}
    expires_at: datetime | None = None

class ReceiptCreate(BaseModel):
    lot_id: str
    warehouse_id: str
    custodian_id: str
    owner_id: str
    lien_holder_id: str | None = None
    collateral_value: Decimal | None = None
    currency: str = "USD"

class BuyerQuoteRequest(BaseModel):
    buyer_connector: str
    lot_id: str
    reference_price: Decimal = Field(gt=0)
    currency: str = "USD"

class ObservationCreate(BaseModel):
    commodity: str
    market: str
    price: Decimal = Field(gt=0)
    currency: str = "USD"
    price_unit: str = "kg"
    source: str
    region: str | None = None
    metadata: dict = {}

class ForwardCreate(BaseModel):
    commodity: str
    seller_id: str
    buyer_id: str
    quantity: Decimal = Field(gt=0)
    unit: str = "kg"
    delivery_date: datetime
    fixed_price: Decimal = Field(gt=0)
    currency: str = "USD"
    hedge_metadata: dict = {}

class HedgeRequest(BaseModel):
    exposure_quantity: Decimal = Field(gt=0)
    forward_quantity: Decimal = Field(ge=0)
    spot_reference: Decimal = Field(gt=0)
    forward_price: Decimal = Field(gt=0)

class EudrRequest(BaseModel):
    lot_id: str
    declaration: dict = {}

class PolicyEvaluate(BaseModel):
    institution_id: str
    actor_type: str
    action: str
    context: dict = {}

class SettlementRequest(BaseModel):
    lot_id: str
    gross_value: Decimal = Field(gt=0)
    currency: str = "USD"
    allocations: dict[str,Decimal]
    approved_by: str | None = None
    approval_reference: str
    idempotency_key: str

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict = {}

def trace(run_id:str, skill:str, status:str="completed", latency_ms:int=0, exposure:float=0, currency:str="USD", provenance=None, error=None):
    with db_session() as s:
        s.add(AgentTrace(id=f"trace_{uuid4().hex[:12]}",run_id=run_id,skill=skill,status=status,latency_ms=latency_ms,
            monetary_exposure=exposure,currency=currency,provenance=provenance or {},error=error))

def deterministic_plan(req:PlanRequest):
    lot=get_lot(req.lot_id)
    if not lot: raise HTTPException(404,"commodity lot not found")
    steps=[]
    for i,skill in enumerate(SKILL_GRAPH[req.intent],1):
        critical=skill in {"trade.execute","settlement.execute"}
        steps.append({"step":i,"skill":skill,"risk":"critical" if critical else "medium" if skill in {"risk.assess","compliance.check","finance.assess","forward.hedge"} else "low","requires_approval":critical})
    return {"planner":"deterministic-v1","intent":req.intent,"lot_id":req.lot_id,"requested_by":req.requested_by,
        "institution_id":req.institution_id,"steps":steps,"transaction_authority":"none"}

@router.on_event("startup")
def startup():
    init_db()
    try:
        health = infrastructure_health()
        summary = health.get("summary", {})
        statuses = [
            {"name": s.get("name"), "status": s.get("status"), "reachable": s.get("reachable")}
            for s in health.get("services", [])
        ]
        print("COMMOS_INFRA_STATUS", {"summary": summary, "services": statuses})
    except Exception as exc:
        print("COMMOS_INFRA_STATUS", {"status": "probe_failed", "error_type": type(exc).__name__})

@router.post("/planner/plan")
def planner_plan(body:PlanRequest):
    t=time.perf_counter(); result=deterministic_plan(body)
    trace(f"plan_{uuid4().hex[:8]}","planner.plan",latency_ms=int((time.perf_counter()-t)*1000),provenance={"planner":"deterministic-v1"})
    return result

@router.post("/orderbook/orders")
def order_create(body:OrderCreate):
    oid=f"ord_{uuid4().hex[:12]}"
    with db_session() as s:
        s.add(Order(id=oid,order_type=body.order_type,side=body.side,commodity=body.commodity,lot_id=body.lot_id,
            actor_id=body.actor_id,quantity=body.quantity,unit=body.unit,limit_price=body.limit_price,
            currency=body.currency,status="open",terms=body.terms,expires_at=body.expires_at))
    return {"order_id":oid,**body.model_dump(),"status":"open"}

@router.get("/orderbook/orders")
def order_list(commodity:str|None=None,status:str="open"):
    with db_session() as s:
        q=select(Order).where(Order.status==status)
        if commodity:q=q.where(Order.commodity==commodity)
        rows=s.scalars(q.order_by(Order.created_at.desc())).all()
        return [{"order_id":x.id,"order_type":x.order_type,"side":x.side,"commodity":x.commodity,"lot_id":x.lot_id,
            "actor_id":x.actor_id,"quantity":x.quantity,"unit":x.unit,"limit_price":x.limit_price,
            "currency":x.currency,"status":x.status,"terms":x.terms} for x in rows]

@router.post("/orderbook/orders/{order_id}/accept")
def order_accept(order_id:str,accepted_by:str):
    with db_session() as s:
        x=s.get(Order,order_id)
        if not x:raise HTTPException(404,"order not found")
        if x.status!="open":raise HTTPException(409,"order not open")
        x.status="accepted"; x.terms={**(x.terms or {}),"accepted_by":accepted_by,"accepted_at":datetime.now(timezone.utc).isoformat()}
        s.flush()
        return {"order_id":x.id,"status":x.status,"accepted_by":accepted_by}

@router.post("/warehouse/receipts")
def issue_receipt(body:ReceiptCreate):
    if not get_lot(body.lot_id):raise HTTPException(404,"commodity lot not found")
    rid=f"wr_{uuid4().hex[:12]}"
    with db_session() as s:
        existing=s.scalar(select(WarehouseReceipt).where(WarehouseReceipt.lot_id==body.lot_id))
        if existing:raise HTTPException(409,"receipt already exists for lot")
        s.add(WarehouseReceipt(id=rid,lot_id=body.lot_id,warehouse_id=body.warehouse_id,custodian_id=body.custodian_id,
            owner_id=body.owner_id,lien_holder_id=body.lien_holder_id,collateral_value=body.collateral_value,currency=body.currency))
    return {"receipt_id":rid,**body.model_dump(),"status":"issued"}

@router.get("/warehouse/receipts/{lot_id}")
def get_receipt(lot_id:str):
    with db_session() as s:
        x=s.scalar(select(WarehouseReceipt).where(WarehouseReceipt.lot_id==lot_id))
        if not x:raise HTTPException(404,"receipt not found")
        return {"receipt_id":x.id,"lot_id":x.lot_id,"warehouse_id":x.warehouse_id,"custodian_id":x.custodian_id,
            "owner_id":x.owner_id,"lien_holder_id":x.lien_holder_id,"collateral_value":x.collateral_value,
            "currency":x.currency,"status":x.status}

@router.get("/buyers/connectors")
def buyer_connectors():
    return [{"id":k,**v} for k,v in BUYERS.items()]

@router.post("/buyers/quote")
def buyer_quote(body:BuyerQuoteRequest):
    buyer=BUYERS.get(body.buyer_connector); lot=get_lot(body.lot_id)
    if not buyer:raise HTTPException(404,"buyer connector not found")
    if not lot:raise HTTPException(404,"commodity lot not found")
    compatible=lot["commodity"].lower() in buyer["commodities"]
    if not compatible:raise HTTPException(422,"buyer does not support commodity")
    spread={"exporter_demo":0.015,"processor_demo":-0.02,"roaster_demo":0.04}.get(body.buyer_connector,0)
    price=round(body.reference_price*(1+spread),4)
    return {"buyer_connector":body.buyer_connector,"lot_id":body.lot_id,"unit_price":price,"currency":body.currency,
        "quantity":lot["quantity"],"gross_value":round(price*lot["quantity"],2),"status":"indicative","connector_mode":"sandbox"}

@router.post("/market/observations")
def market_observe(body:ObservationCreate):
    return create_market_observation(body.model_dump())

@router.get("/market/observations/{commodity}")
def market_latest(commodity:str,limit:int=20):
    return latest_market_observations(commodity,limit)

@router.get("/market/adapters")
def market_adapters():
    return [
        {"id":"manual_reference","scope":"global","mode":"write-through","status":"ready"},
        {"id":"uganda_local","scope":"Uganda/East Africa","mode":"normalized-adapter","status":"ready"},
        {"id":"international_reference","scope":"international","mode":"connector-interface","status":"ready"},
    ]

@router.post("/forwards")
def forward_create(body:ForwardCreate):
    cid=f"fwd_{uuid4().hex[:12]}"
    with db_session() as s:
        s.add(ForwardContract(id=cid,commodity=body.commodity,seller_id=body.seller_id,buyer_id=body.buyer_id,
            quantity=body.quantity,unit=body.unit,delivery_date=body.delivery_date,fixed_price=body.fixed_price,
            currency=body.currency,status="draft",hedge_metadata=body.hedge_metadata))
    return {"contract_id":cid,**body.model_dump(),"status":"draft"}

@router.post("/hedge/calculate")
def hedge_calculate(body:HedgeRequest):
    ratio=min(body.forward_quantity/body.exposure_quantity,1)
    spot_value=body.exposure_quantity*body.spot_reference
    forward_value=body.forward_quantity*body.forward_price
    return {"hedge_ratio":round(ratio,4),"unhedged_quantity":max(body.exposure_quantity-body.forward_quantity,0),
      "spot_reference_value":round(spot_value,2),"forward_notional":round(forward_value,2),
      "interpretation":"fully_hedged" if ratio>=1 else "partially_hedged" if ratio>0 else "unhedged"}

@router.post("/eudr/evidence-packs")
def eudr_generate(body:EudrRequest):
    lot=get_lot(body.lot_id)
    if not lot:raise HTTPException(404,"commodity lot not found")
    farms=lot.get("farm_ids",[])
    traceability=lot.get("attributes",{}).get("traceability")
    risk={"farm_lineage":bool(farms),"traceability_verified":traceability in ("verified","ready"),
      "overall":"low" if farms and traceability in ("verified","ready") else "review_required"}
    pid=f"eudr_{uuid4().hex[:12]}"
    status="ready" if risk["overall"]=="low" else "review_required"
    with db_session() as s:
        s.add(EudrEvidencePack(id=pid,lot_id=body.lot_id,status=status,farm_evidence=farms,
          traceability_evidence=[{"type":"lot_attribute","value":traceability}],risk_assessment=risk,declaration=body.declaration))
    return {"pack_id":pid,"lot_id":body.lot_id,"status":status,"risk_assessment":risk,"declaration":body.declaration}

def local_policy(body:PolicyEvaluate):
    with db_session() as s:
        rows=s.scalars(select(PolicyRule).where(PolicyRule.enabled==True,PolicyRule.institution_id==body.institution_id,
          PolicyRule.actor_type==body.actor_type,PolicyRule.action==body.action)).all()
    if rows:
        r=rows[0];return {"allow":r.effect=="allow","requires_approval":r.requires_approval,"source":"local-policy","rule_id":r.id}
    return {"allow":False if body.action in CRITICAL_ACTIONS else True,
            "requires_approval":body.action in CRITICAL_ACTIONS,
            "source":"default-deny-critical","rule_id":None}

@router.post("/policy/evaluate")
def policy_evaluate(body:PolicyEvaluate):
    principal=current_principal()
    actor_type="agent_service" if "agent_service" in principal.roles else "buyer" if "buyer" in principal.roles else "operator"
    body=PolicyEvaluate(institution_id=principal.institution_id,actor_type=actor_type,action=body.action,context={**body.context,"tenant_id":principal.tenant_id,"principal_sub":principal.subject})
    opa=os.getenv("OPA_URL")
    if opa:
        try:
            res=httpx.post(opa.rstrip("/")+"/v1/data/commos/decision",json={"input":body.model_dump()},timeout=3)
            res.raise_for_status(); data=res.json().get("result")
            if isinstance(data,dict): return {**data,"source":"opa"}
        except Exception as exc:
            if body.action in CRITICAL_ACTIONS:
                return {"allow":False,"requires_approval":True,"source":"opa-fail-closed","reason":type(exc).__name__}
    if body.action in CRITICAL_ACTIONS and not opa:
        return {"allow":False,"requires_approval":True,"source":"opa-not-configured","reason":"critical actions require OPA"}
    return local_policy(body)

@router.post("/agpay/settlements")
def agpay_settle(body:SettlementRequest):
    principal=current_principal()
    total=sum(body.allocations.values(),Decimal("0"))
    if total.quantize(Decimal("0.00000001"))!=body.gross_value.quantize(Decimal("0.00000001")):
        raise HTTPException(422,"allocations must equal gross value")
    decision=policy_evaluate(PolicyEvaluate(
        institution_id=principal.institution_id,actor_type="operator",action="settlement.execute",
        context={"gross_value":str(body.gross_value),"currency":body.currency,"tenant_id":principal.tenant_id}
    ))
    if not decision.get("allow"):
        raise HTTPException(403,"policy denied settlement")
    if decision.get("requires_approval") and not body.approval_reference:
        raise HTTPException(409,"approval reference required")
    request_hash=hashlib.sha256(json.dumps({
        "lot_id":body.lot_id,"gross_value":str(body.gross_value),"currency":body.currency,
        "allocations":{k:str(v) for k,v in sorted(body.allocations.items())},
        "approval_reference":body.approval_reference
    },sort_keys=True).encode()).hexdigest()
    idem=reserve_idempotency(body.idempotency_key,"settlement.execute",request_hash)
    if idem["replay"] and idem["resource_id"]:
        return {"instruction_id":idem["resource_id"],"status":"idempotent_replay","rail":"AgPay"}
    instruction_id=f"set_{uuid4().hex[:12]}"
    entries=[{"account_id":f"settlement:clearing:{body.currency}","debit":body.gross_value,"account_type":"clearing"}]
    entries += [{"account_id":f"beneficiary:{name}:{body.currency}","credit":amount,"account_type":"payable"} for name,amount in body.allocations.items()]
    ledger_tx=post_balanced_transaction(instruction_id,body.currency,entries,metadata={
        "lot_id":body.lot_id,"approval_reference":body.approval_reference,"principal_sub":principal.subject
    })
    with db_session() as s:
        s.add(ApprovalRecord(
            id=f"apr_{uuid4().hex[:16]}",run_id=instruction_id,action="settlement.execute",
            principal_sub=principal.subject,tenant_id=principal.tenant_id,institution_id=principal.institution_id,
            policy_source=decision.get("source","unknown"),policy_decision=decision,token_jti=principal.token_id
        ))
    complete_idempotency(body.idempotency_key,instruction_id)
    result={"instruction_id":instruction_id,"lot_id":body.lot_id,"gross_value":str(body.gross_value),"currency":body.currency,
      "allocations":{k:str(v) for k,v in body.allocations.items()},"approved_by":principal.subject,
      "approval_reference":body.approval_reference,"idempotency_key":body.idempotency_key,
      "status":"submitted_to_agros","rail":"AgPay","ledger_transaction_id":ledger_tx["transaction_id"]}
    trace(instruction_id,"settlement.execute",exposure=body.gross_value,currency=body.currency,
      provenance={"approval_reference":body.approval_reference,"bridge":"agpay-v2","principal_sub":principal.subject})
    return result

@router.post("/policies")
def policy_create(body:PolicyEvaluate, effect:str="allow",requires_approval:bool=False):
    pid=f"pol_{uuid4().hex[:12]}"
    with db_session() as s:
        s.add(PolicyRule(id=pid,institution_id=body.institution_id,actor_type=body.actor_type,action=body.action,
          effect=effect,conditions=body.context,requires_approval=requires_approval,enabled=True))
    return {"policy_id":pid,"effect":effect,"requires_approval":requires_approval,**body.model_dump()}

@router.get("/observability/summary")
def observability_summary():
    with db_session() as s:
        count=s.scalar(select(func.count()).select_from(AgentTrace)) or 0
        failures=s.scalar(select(func.count()).select_from(AgentTrace).where(AgentTrace.status=="failed")) or 0
        exposure=s.scalar(select(func.coalesce(func.sum(AgentTrace.monetary_exposure),0))) or 0
        avg_latency=s.scalar(select(func.coalesce(func.avg(AgentTrace.latency_ms),0))) or 0
    return {"traces":count,"failures":failures,"monetary_exposure":float(exposure),"avg_skill_latency_ms":round(float(avg_latency),2)}

@router.get("/observability/traces")
def observability_traces(limit:int=100):
    with db_session() as s:
        rows=s.scalars(select(AgentTrace).order_by(AgentTrace.created_at.desc()).limit(limit)).all()
        return [{"trace_id":x.id,"run_id":x.run_id,"skill":x.skill,"status":x.status,"latency_ms":x.latency_ms,
          "monetary_exposure":x.monetary_exposure,"currency":x.currency,"provenance":x.provenance,"error":x.error,
          "created_at":x.created_at.isoformat()} for x in rows]

def invoke_tool(name:str,args:dict):
    exposure=Decimal(str(args.get("gross_value",0))) if name=="agpay.settle" else Decimal("0")
    authorize_capability(name,monetary_exposure=exposure,currency=args.get("currency","USD"))
    if name=="planner.plan":return deterministic_plan(PlanRequest(**args))
    if name=="orderbook.create":return order_create(OrderCreate(**args))
    if name=="orderbook.list":return order_list(**args)
    if name=="warehouse.receipt.issue":return issue_receipt(ReceiptCreate(**args))
    if name=="buyer.quote":return buyer_quote(BuyerQuoteRequest(**args))
    if name=="market.observe":return market_observe(ObservationCreate(**args))
    if name=="market.latest":return market_latest(**args)
    if name=="forward.create":return forward_create(ForwardCreate(**args))
    if name=="forward.hedge":return hedge_calculate(HedgeRequest(**args))
    if name=="eudr.generate":return eudr_generate(EudrRequest(**args))
    if name=="policy.evaluate":return policy_evaluate(PolicyEvaluate(**args))
    if name=="agpay.settle":return agpay_settle(SettlementRequest(**args))
    if name=="observability.summary":return observability_summary()
    raise HTTPException(404,f"unknown tool: {name}")

@router.get("/mcp")
def mcp_manifest():
    return {"name":"COMMOS","protocol":"MCP-compatible JSON-RPC gateway","version":"0.3.0","transport":"HTTP","authentication":"OIDC bearer","tools":[{**t,"required_scope":__import__("app.agent_control",fromlist=["CAPABILITY_SCOPES"]).CAPABILITY_SCOPES.get(t["name"])} for t in TOOL_MANIFEST]}

@router.post("/mcp")
def mcp_rpc(body:JsonRpcRequest, mcp_session_id:str|None=Header(default=None,alias="Mcp-Session-Id")):
    try:
        if body.method=="initialize":
            result={"protocolVersion":"2026-01-01","serverInfo":{"name":"COMMOS","version":"0.2.0"},
              "capabilities":{"tools":{}}}
        elif body.method=="tools/list":
            result={"tools":TOOL_MANIFEST}
        elif body.method=="tools/call":
            name=body.params.get("name"); args=body.params.get("arguments") or {}
            result={"content":[{"type":"text","text":str(invoke_tool(name,args))}],"isError":False}
        else:
            return {"jsonrpc":"2.0","id":body.id,"error":{"code":-32601,"message":"method not found"}}
        return {"jsonrpc":"2.0","id":body.id,"result":result}
    except Exception as e:
        return {"jsonrpc":"2.0","id":body.id,"error":{"code":-32000,"message":str(e)}}


@router.get("/infrastructure/health")
def live_infrastructure_health():
    return infrastructure_health()

@router.post("/market/sync/{scope}")
def market_sync(scope:str):
    if scope not in ("international","uganda"):
        raise HTTPException(422,"scope must be international or uganda")
    url_env="MARKET_INTL_API_URL" if scope=="international" else "MARKET_UG_API_URL"
    token_env="MARKET_INTL_API_TOKEN" if scope=="international" else "MARKET_UG_API_TOKEN"
    url=os.getenv(url_env)
    if not url:
        raise HTTPException(503,f"{url_env} not configured")
    headers={"Authorization":f"Bearer {os.getenv(token_env)}"} if os.getenv(token_env) else {}
    try:
        r=httpx.get(url.rstrip("/")+"/prices",headers=headers,timeout=8)
        r.raise_for_status()
        payload=r.json()
    except Exception as e:
        raise HTTPException(502,f"market feed unavailable: {type(e).__name__}")
    rows=payload if isinstance(payload,list) else payload.get("prices",[])
    saved=[]
    for row in rows:
        try:
            saved.append(create_market_observation({
                "commodity":row["commodity"],
                "market":row.get("market",scope),
                "price":float(row["price"]),
                "currency":row.get("currency","USD"),
                "price_unit":row.get("price_unit","kg"),
                "source":row.get("source",url),
                "region":row.get("region"),
                "metadata":row.get("metadata",{})
            }))
        except Exception:
            continue
    return {"scope":scope,"received":len(rows),"persisted":len(saved),"observations":saved[:20]}

@router.post("/buyers/live-quote")
def buyer_live_quote(body:BuyerQuoteRequest):
    mapping={
        "exporter_demo":("BUYER_EXPORTER_API_URL","BUYER_EXPORTER_API_TOKEN"),
        "processor_demo":("BUYER_PROCESSOR_API_URL","BUYER_PROCESSOR_API_TOKEN"),
        "roaster_demo":("BUYER_ROASTER_API_URL","BUYER_ROASTER_API_TOKEN"),
    }
    envs=mapping.get(body.buyer_connector)
    if not envs:
        raise HTTPException(404,"buyer connector not found")
    base=os.getenv(envs[0]); token=os.getenv(envs[1])
    if not base:
        return buyer_quote(body)
    lot=get_lot(body.lot_id)
    if not lot:raise HTTPException(404,"commodity lot not found")
    headers={"Authorization":f"Bearer {token}"} if token else {}
    try:
        r=httpx.post(base.rstrip("/")+"/quote",json={
            "lot":lot,"reference_price":body.reference_price,"currency":body.currency
        },headers=headers,timeout=8)
        r.raise_for_status()
        out=r.json()
        out["connector_mode"]="live"
        return out
    except Exception as e:
        raise HTTPException(502,f"buyer connector unavailable: {type(e).__name__}")

@router.post("/agpay/live-settlements")
def agpay_live_settle(body:SettlementRequest):
    preview=agpay_settle(body)
    base=os.getenv("AGPAY_API_URL")
    token=os.getenv("AGPAY_API_TOKEN")
    if not base:
        preview["connector_mode"]="sandbox"
        return preview
    headers={"Authorization":f"Bearer {token}","Idempotency-Key":body.idempotency_key}
    try:
        r=httpx.post(base.rstrip("/")+"/v1/settlements",json=preview,headers=headers,timeout=10)
        r.raise_for_status()
        result=r.json()
        trace(preview["instruction_id"],"settlement.execute",status="completed",exposure=body.gross_value,
            currency=body.currency,provenance={"bridge":"agpay-live","remote_status":r.status_code})
        return {"instruction":preview,"agpay_result":result,"connector_mode":"live"}
    except Exception as e:
        trace(preview["instruction_id"],"settlement.execute",status="failed",exposure=body.gross_value,
            currency=body.currency,provenance={"bridge":"agpay-live"},error=type(e).__name__)
        raise HTTPException(502,f"AgPay unavailable: {type(e).__name__}")


FRED_COFFEE_SERIES = {
    "arabica": "PCOFFOTMUSDM",
    "robusta": "PCOFFROBUSDM",
}

@router.post("/market/public/fred/coffee/sync")
def fred_coffee_sync(variety:str="arabica"):
    series=FRED_COFFEE_SERIES.get(variety.lower())
    if not series:
        raise HTTPException(422,"variety must be arabica or robusta")
    url=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    try:
        r=httpx.get(url,timeout=10,follow_redirects=True)
        r.raise_for_status()
        rows=list(csv.DictReader(io.StringIO(r.text)))
        usable=[x for x in rows if x.get(series) not in (None,"",".")]
        if not usable:
            raise ValueError("no observations")
        last=usable[-1]
        price=float(last[series])
    except Exception as e:
        raise HTTPException(502,f"FRED feed unavailable: {type(e).__name__}")
    observation=create_market_observation({
        "commodity":"coffee",
        "market":f"Global {variety.title()} Benchmark",
        "price":price,
        "currency":"USD",
        "price_unit":"US_cents_per_lb",
        "source":f"FRED:{series}",
        "region":"global",
        "metadata":{"series_id":series,"observation_date":last.get("DATE"),"frequency":"monthly"}
    })
    return {"variety":variety.lower(),"series_id":series,"observation":observation,"source_url":url}


@router.post("/infrastructure/probe")
def infrastructure_probe():
    health = infrastructure_health()
    required = [s for s in health["services"] if s["kind"] in ("database","policy","settlement")]
    required_online = all((not s["configured"]) or s["reachable"] for s in required)
    return {
        "status": "ok" if required_online else "degraded",
        "required_online": required_online,
        "summary": health["summary"],
        "services": health["services"],
    }


UCDA_STATS_URL = "https://new.ugandacoffee.go.ug/resource-center/statistics"

@router.post("/market/public/ucda/coffee/sync")
def ucda_coffee_sync():
    try:
        r=httpx.get(UCDA_STATS_URL,timeout=12,follow_redirects=True,headers={"User-Agent":"COMMOS/0.2 market adapter"})
        r.raise_for_status()
        text_body=html.unescape(re.sub(r"<[^>]+>", " ", r.text))
        text_body=re.sub(r"\s+", " ", text_body)
    except Exception as e:
        raise HTTPException(502,f"UCDA feed unavailable: {type(e).__name__}")

    grade_patterns = {
        "Robusta Screen 18": r"Screen 18\s+([0-9]+(?:\.[0-9]+)?)",
        "Robusta Screen 15": r"Robusta\s*[–-]\s*Screen 15\s+([0-9]+(?:\.[0-9]+)?)",
        "Robusta Screen 12": r"Robusta\s*[–-]\s*Screen 12\s+([0-9]+(?:\.[0-9]+)?)",
        "Arabica Bugisu AA": r"Arabicas\s*[–-]\s*Bugisu AA\s+([0-9]+(?:\.[0-9]+)?)",
        "Arabica Bugisu A": r"Arabicas\s*[–-]\s*Bugisu A\s+([0-9]+(?:\.[0-9]+)?)",
        "Arabica Bugisu PB": r"Arabicas\s*[–-]\s*Bugisu PB\s+([0-9]+(?:\.[0-9]+)?)",
        "Arabica Bugisu B": r"Arabicas\s*[–-]\s*Bugisu B\s+([0-9]+(?:\.[0-9]+)?)",
        "Arabica Wugar": r"Arabicas\s*[–-]\s*Wugar\s+([0-9]+(?:\.[0-9]+)?)",
        "Arabica Drugar": r"Arabicas\s*[–-]\s*Drugar\s+([0-9]+(?:\.[0-9]+)?)",
    }
    farmgate_patterns = {
        "Kiboko": r"Kiboko\s+([0-9,]+)\s*(?:/=)?\s*[-–]\s*([0-9,]+)",
        "FAQ": r"FAQ\s+([0-9,]+)\s*(?:/=)?\s*[-–]\s*([0-9,]+)",
        "Arabica Parchment": r"ARABICA PARCHMENT\s+([0-9,]+)\s*(?:/=)?\s*[-–]\s*([0-9,]+)",
        "Drugar Clean": r"DRUGAR COFFEE \(CLEAN\)\s+([0-9,]+)\s*(?:/=)?\s*[-–]\s*([0-9,]+)",
    }

    saved=[]
    for label, pattern in grade_patterns.items():
        m=re.search(pattern,text_body,re.IGNORECASE)
        if not m:
            continue
        value=float(m.group(1))
        saved.append(create_market_observation({
            "commodity":"coffee",
            "market":f"Uganda UCDA · {label}",
            "price":value,
            "currency":"N/A",
            "price_unit":"UCDA_published_unit",
            "source":"UCDA",
            "region":"Uganda",
            "metadata":{"official_url":UCDA_STATS_URL,"grade":label,"source_type":"daily_market_price"}
        }))

    for label, pattern in farmgate_patterns.items():
        m=re.search(pattern,text_body,re.IGNORECASE)
        if not m:
            continue
        low=float(m.group(1).replace(",",""))
        high=float(m.group(2).replace(",",""))
        midpoint=round((low+high)/2,2)
        saved.append(create_market_observation({
            "commodity":"coffee",
            "market":f"Uganda Farmgate · {label}",
            "price":midpoint,
            "currency":"UGX",
            "price_unit":"kg",
            "source":"UCDA",
            "region":"Uganda",
            "metadata":{"official_url":UCDA_STATS_URL,"product":label,"min_price":low,"max_price":high,"source_type":"farmgate_range"}
        }))

    if not saved:
        raise HTTPException(502,"UCDA page was reachable but no known price fields could be parsed")
    return {"source":"UCDA","official_url":UCDA_STATS_URL,"persisted":len(saved),"observations":saved}
