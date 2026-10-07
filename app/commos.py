from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.db import init_db
from app.commos_repository import create_lot as persist_lot, get_lot as persisted_lot, create_run as persist_run, get_run as persisted_run, update_run as persist_update_run, create_proposal as persist_proposal, get_proposal as persisted_proposal, update_proposal as persist_update_proposal

router = APIRouter(prefix="/v1/commos", tags=["COMMOS"])

commodity_lots = {}
agent_runs = {}
trade_proposals = {}
commodity_events = []

SKILLS = {
    "commodity.lot.create": {"risk":"low","approval":False,"category":"asset"},
    "market.quote": {"risk":"low","approval":False,"category":"intelligence"},
    "trade.propose": {"risk":"medium","approval":False,"category":"trade"},
    "finance.assess": {"risk":"medium","approval":False,"category":"finance"},
    "risk.assess": {"risk":"medium","approval":False,"category":"risk"},
    "compliance.check": {"risk":"medium","approval":False,"category":"compliance"},
    "trade.execute": {"risk":"critical","approval":True,"category":"trade"},
    "settlement.execute": {"risk":"critical","approval":True,"category":"settlement"},
}

def _emit(event_type: str, entity_id: str, payload=None):
    event = {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "entity_id": entity_id,
        "payload": payload or {},
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    commodity_events.append(event)
    return event

class CommodityLotCreate(BaseModel):
    commodity: str
    origin_country: str = "UG"
    quantity: float = Field(gt=0)
    unit: str = "kg"
    grade: str | None = None
    owner_id: str
    farm_ids: list[str] = []
    warehouse_id: str | None = None
    attributes: dict = {}

class MarketQuoteRequest(BaseModel):
    lot_id: str
    reference_price: float = Field(gt=0)
    currency: str = "USD"
    price_unit: str = "kg"

class HarnessIntent(BaseModel):
    intent: Literal["sell", "finance", "hedge", "settle", "assess"]
    lot_id: str
    requested_by: str
    institution: str | None = None
    target_price: float | None = None
    currency: str = "USD"
    notes: str | None = None


class FinanceAssessRequest(BaseModel):
    lot_id: str
    reference_unit_price: float = Field(gt=0)
    advance_rate: float = Field(default=0.6, gt=0, le=0.9)
    currency: str = "USD"

class RiskAssessRequest(BaseModel):
    lot_id: str
    reference_unit_price: float = Field(gt=0)
    downside_percent: float = Field(default=15, ge=0, le=100)
    currency: str = "USD"

class ComplianceCheckRequest(BaseModel):
    lot_id: str
    require_traceability: bool = True
    require_farm_links: bool = True
    require_warehouse: bool = False

class SettlementPreviewRequest(BaseModel):
    lot_id: str
    gross_value: float = Field(gt=0)
    currency: str = "USD"
    lender_percent: float = Field(default=0, ge=0, le=100)
    insurance_percent: float = Field(default=0, ge=0, le=100)
    cooperative_percent: float = Field(default=0, ge=0, le=100)
    platform_percent: float = Field(default=0, ge=0, le=100)

class TradeProposalCreate(BaseModel):
    run_id: str
    buyer_id: str
    unit_price: float = Field(gt=0)
    currency: str = "USD"

def _plan_for(intent: str):
    if intent == "sell":
        return ["market.quote", "risk.assess", "compliance.check", "trade.propose", "trade.execute", "settlement.execute"]
    if intent == "finance":
        return ["market.quote", "risk.assess", "finance.assess"]
    if intent == "hedge":
        return ["market.quote", "risk.assess", "trade.propose"]
    if intent == "settle":
        return ["compliance.check", "settlement.execute"]
    return ["market.quote", "risk.assess", "compliance.check"]

@router.get("/health")
def commos_health():
    return {
        "status":"ok",
        "service":"COMMOS",
        "version":"0.1.0",
        "skills":len(SKILLS),
        "lots":len(commodity_lots),
        "active_runs":sum(1 for r in agent_runs.values() if r["status"] not in ("completed","cancelled")),
    }

@router.get("/skills")
def list_skills():
    return [{"name":name, **meta} for name, meta in SKILLS.items()]

@router.post("/lots")
def create_lot(body: CommodityLotCreate):
    lot_id = f"agros:lot:{body.origin_country}:{uuid4().hex[:12]}"
    lot = {
        "lot_id":lot_id,
        **body.model_dump(),
        "status":"available",
        "created_at":datetime.now(timezone.utc).isoformat(),
    }
    init_db()
    stored = persist_lot(lot)
    commodity_lots[lot_id] = stored
    _emit("commodity.lot.created", lot_id, {"commodity":body.commodity,"quantity":body.quantity,"unit":body.unit})
    return stored

@router.get("/lots/{lot_id}")
def get_lot(lot_id: str):
    init_db()
    lot = persisted_lot(lot_id) or commodity_lots.get(lot_id)
    if not lot:
        raise HTTPException(404, "commodity lot not found")
    return lot

@router.post("/market/quote")
def market_quote(body: MarketQuoteRequest):
    init_db()
    lot = persisted_lot(body.lot_id) or commodity_lots.get(body.lot_id)
    if not lot:
        raise HTTPException(404, "commodity lot not found")
    gross_value = round(lot["quantity"] * body.reference_price, 2)
    result = {
        "lot_id":body.lot_id,
        "commodity":lot["commodity"],
        "reference_price":body.reference_price,
        "currency":body.currency,
        "price_unit":body.price_unit,
        "gross_reference_value":gross_value,
        "source":"user/reference-feed",
        "as_of":datetime.now(timezone.utc).isoformat(),
    }
    _emit("market.quote.generated", body.lot_id, result)
    return result


@router.post("/skills/finance.assess")
def finance_assess(body: FinanceAssessRequest):
    lot = commodity_lots.get(body.lot_id)
    if not lot:
        raise HTTPException(404, "commodity lot not found")
    reference_value = round(lot["quantity"] * body.reference_unit_price, 2)
    max_facility = round(reference_value * body.advance_rate, 2)
    result = {
        "lot_id": body.lot_id,
        "reference_value": reference_value,
        "currency": body.currency,
        "advance_rate": body.advance_rate,
        "max_facility": max_facility,
        "collateral_unit": lot["unit"],
        "status": "assessed",
    }
    _emit("finance.assessed", body.lot_id, result)
    return result

@router.post("/skills/risk.assess")
def risk_assess(body: RiskAssessRequest):
    lot = commodity_lots.get(body.lot_id)
    if not lot:
        raise HTTPException(404, "commodity lot not found")
    reference_value = round(lot["quantity"] * body.reference_unit_price, 2)
    stressed_value = round(reference_value * (1 - body.downside_percent / 100), 2)
    flags = []
    if not lot.get("warehouse_id"):
        flags.append("no_warehouse_custody")
    if not lot.get("farm_ids"):
        flags.append("no_farm_lineage")
    if lot.get("attributes", {}).get("traceability") not in ("verified", "ready"):
        flags.append("traceability_unverified")
    rating = "low" if not flags and body.downside_percent <= 15 else "medium" if len(flags) <= 1 else "high"
    result = {
        "lot_id": body.lot_id,
        "reference_value": reference_value,
        "stressed_value": stressed_value,
        "downside_percent": body.downside_percent,
        "currency": body.currency,
        "risk_rating": rating,
        "flags": flags,
    }
    _emit("risk.assessed", body.lot_id, result)
    return result

@router.post("/skills/compliance.check")
def compliance_check(body: ComplianceCheckRequest):
    lot = commodity_lots.get(body.lot_id)
    if not lot:
        raise HTTPException(404, "commodity lot not found")
    checks = {
        "traceability": (not body.require_traceability) or lot.get("attributes", {}).get("traceability") in ("verified", "ready"),
        "farm_links": (not body.require_farm_links) or bool(lot.get("farm_ids")),
        "warehouse": (not body.require_warehouse) or bool(lot.get("warehouse_id")),
    }
    passed = all(checks.values())
    result = {"lot_id": body.lot_id, "passed": passed, "checks": checks, "status": "clear" if passed else "review_required"}
    _emit("compliance.checked", body.lot_id, result)
    return result

@router.post("/settlements/preview")
def settlement_preview(body: SettlementPreviewRequest):
    lot = commodity_lots.get(body.lot_id)
    if not lot:
        raise HTTPException(404, "commodity lot not found")
    fixed = body.lender_percent + body.insurance_percent + body.cooperative_percent + body.platform_percent
    if fixed > 100:
        raise HTTPException(422, "settlement percentages exceed 100")
    farmer_percent = 100 - fixed
    allocations = {
        "lender": round(body.gross_value * body.lender_percent / 100, 2),
        "insurance": round(body.gross_value * body.insurance_percent / 100, 2),
        "cooperative": round(body.gross_value * body.cooperative_percent / 100, 2),
        "platform": round(body.gross_value * body.platform_percent / 100, 2),
        "owner_residual": round(body.gross_value * farmer_percent / 100, 2),
    }
    result = {
        "lot_id": body.lot_id,
        "gross_value": body.gross_value,
        "currency": body.currency,
        "allocations": allocations,
        "balanced": round(sum(allocations.values()), 2) == round(body.gross_value, 2),
        "status": "preview",
    }
    _emit("settlement.previewed", body.lot_id, result)
    return result


@router.post("/runs")
def create_run(body: HarnessIntent):
    lot = commodity_lots.get(body.lot_id)
    if not lot:
        raise HTTPException(404, "commodity lot not found")
    skills = _plan_for(body.intent)
    plan = []
    for index, skill in enumerate(skills, start=1):
        meta = SKILLS[skill]
        plan.append({
            "step":index,
            "skill":skill,
            "risk":meta["risk"],
            "requires_approval":meta["approval"],
            "status":"pending",
        })
    run_id = f"CM-{uuid4().hex[:10].upper()}"
    approval_required = any(step["requires_approval"] for step in plan)
    run = {
        "run_id":run_id,
        "intent":body.model_dump(),
        "lot_snapshot":lot.copy(),
        "plan":plan,
        "status":"approval_required" if approval_required else "ready",
        "approval":{"required":approval_required,"approved":False,"approved_by":None,"approved_at":None},
        "created_at":datetime.now(timezone.utc).isoformat(),
    }
    init_db()
    stored = persist_run(run)
    agent_runs[run_id] = stored
    _emit("commos.run.created", run_id, {"intent":body.intent,"lot_id":body.lot_id,"skills":skills})
    return stored

@router.post("/runs/{run_id}/approve")
def approve_run(run_id: str, approved_by: str):
    init_db()
    run = persisted_run(run_id) or agent_runs.get(run_id)
    if not run:
        raise HTTPException(404, "COMMOS run not found")
    run["approval"] = {
        "required":run["approval"]["required"],
        "approved":True,
        "approved_by":approved_by,
        "approved_at":datetime.now(timezone.utc).isoformat(),
    }
    run["status"] = "approved"
    run = persist_update_run(run_id, status="approved", approval=run["approval"]) or run
    agent_runs[run_id] = run
    _emit("commos.run.approved", run_id, {"approved_by":approved_by})
    return run

@router.post("/trade/proposals")
def create_trade_proposal(body: TradeProposalCreate):
    init_db()
    run = persisted_run(body.run_id) or agent_runs.get(body.run_id)
    if not run:
        raise HTTPException(404, "COMMOS run not found")
    lot = persisted_lot(run["intent"]["lot_id"]) or commodity_lots.get(run["intent"]["lot_id"])
    if not lot:
        raise HTTPException(404, "commodity lot not found")
    proposal_id = f"trade_{uuid4().hex[:12]}"
    gross = round(lot["quantity"] * body.unit_price, 2)
    proposal = {
        "proposal_id":proposal_id,
        "run_id":body.run_id,
        "lot_id":lot["lot_id"],
        "buyer_id":body.buyer_id,
        "unit_price":body.unit_price,
        "currency":body.currency,
        "quantity":lot["quantity"],
        "unit":lot["unit"],
        "gross_value":gross,
        "status":"proposed",
        "created_at":datetime.now(timezone.utc).isoformat(),
    }
    stored = persist_proposal(proposal)
    trade_proposals[proposal_id] = stored
    _emit("trade.proposed", proposal_id, stored)
    return stored

@router.post("/trade/proposals/{proposal_id}/execute")
def execute_trade(proposal_id: str):
    init_db()
    proposal = persisted_proposal(proposal_id) or trade_proposals.get(proposal_id)
    if not proposal:
        raise HTTPException(404, "trade proposal not found")
    run = persisted_run(proposal["run_id"]) or agent_runs.get(proposal["run_id"])
    if not run or not run["approval"]["approved"]:
        raise HTTPException(409, "approved COMMOS run required")
    lot = persisted_lot(proposal["lot_id"]) or commodity_lots.get(proposal["lot_id"])
    if not lot:
        raise HTTPException(404, "commodity lot not found")
    if lot["status"] != "available":
        raise HTTPException(409, "commodity lot is not available")
    executed_at = datetime.now(timezone.utc)
    proposal = persist_update_proposal(proposal_id,status="executed",executed_at=executed_at) or proposal
    proposal["status"] = "executed"
    proposal["executed_at"] = executed_at.isoformat()
    lot["status"] = "sold"
    lot["buyer_id"] = proposal["buyer_id"]
    lot["sale_value"] = proposal["gross_value"]
    lot["sale_currency"] = proposal["currency"]
    try:
        from app.commos_repository import update_lot_sale
        lot = update_lot_sale(proposal["lot_id"], proposal["buyer_id"], proposal["gross_value"], proposal["currency"]) or lot
    except Exception:
        pass
    run["status"] = "completed"
    for step in run["plan"]:
        step["status"] = "completed"
    run = persist_update_run(run["run_id"], status="completed", plan=run["plan"], completed_at=datetime.now(timezone.utc)) or run
    agent_runs[run["run_id"]] = run
    _emit("trade.executed", proposal_id, {"lot_id":lot["lot_id"],"gross_value":proposal["gross_value"],"currency":proposal["currency"]})
    _emit("settlement.instruction.ready", lot["lot_id"], {"gross_value":proposal["gross_value"],"currency":proposal["currency"]})
    return {"trade":proposal,"lot":lot,"run":run}

@router.get("/runs/{run_id}")
def get_run(run_id: str):
    init_db()
    run = persisted_run(run_id) or agent_runs.get(run_id)
    if not run:
        raise HTTPException(404, "COMMOS run not found")
    return run

@router.get("/events")
def list_events():
    return list(reversed(commodity_events[-100:]))

@router.get("/dashboard")
def dashboard():
    return {
        "lots":len(commodity_lots),
        "runs":len(agent_runs),
        "pending_approvals":sum(1 for r in agent_runs.values() if r["status"] == "approval_required"),
        "trades":len(trade_proposals),
        "skills":len(SKILLS),
        "skill_categories":sorted({v["category"] for v in SKILLS.values()}),
        "agents":[
            {"name":"Market Agent","purpose":"Price discovery and market context","status":"ready"},
            {"name":"Trade Agent","purpose":"Buyer matching, offers and execution plans","status":"guarded"},
            {"name":"Finance Agent","purpose":"Inventory and commodity finance assessment","status":"ready"},
            {"name":"Risk Agent","purpose":"Exposure, concentration and counterparty risk","status":"ready"},
            {"name":"Compliance Agent","purpose":"Traceability and policy checks","status":"ready"},
            {"name":"Settlement Agent","purpose":"Programmable settlement through AgPay","status":"guarded"},
        ],
    }
