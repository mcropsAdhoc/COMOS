import asyncio, os
from datetime import datetime, timezone
from decimal import Decimal
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import activity
from sqlalchemy import select, func
from app.db import db_session
from app.workflows import CommodityTradeWorkflow, CommodityFinanceWorkflow
from app.commos_models import CommodityLot, LotReservation, ApprovalRecord, WarehouseReceipt, TradeConfirmation
from app.security import Principal, set_current_principal, reset_current_principal
from app.commos_platform import SettlementRequest, agpay_live_settle
from app.market_integrity import TitleTransferRequest, title_transfer

def service_principal(payload:dict)->Principal:
    identity=payload.get("principal") or {}
    return Principal(
        subject=identity.get("subject","temporal-worker"),
        tenant_id=identity.get("tenant_id","pilot"),
        institution_id=identity.get("institution_id","dcf"),
        roles=tuple(identity.get("roles") or ["agent_service","pilot_approver"]),
        scopes=tuple(identity.get("scopes") or ["*"]),
        token_id=identity.get("token_id"),
        auth_method="temporal-service",
    )

@activity.defn
async def reserve_lot(payload:dict):
    quantity=Decimal(str(payload["quantity"]))
    now=datetime.now(timezone.utc)
    with db_session() as s:
        lot=s.execute(select(CommodityLot).where(CommodityLot.id==payload["lot_id"]).with_for_update()).scalar_one_or_none()
        if not lot: raise RuntimeError("lot not found")
        reserved=s.scalar(select(func.coalesce(func.sum(LotReservation.quantity),0)).where(
            LotReservation.lot_id==lot.id,LotReservation.status=="active",LotReservation.expires_at>now
        )) or Decimal("0")
        if quantity > lot.quantity-Decimal(str(reserved)): raise RuntimeError("insufficient unreserved quantity")
        rid="wfres_"+activity.info().activity_id.replace("-","")[:20]
        s.add(LotReservation(id=rid,lot_id=lot.id,order_id=payload.get("order_id"),reserved_for=payload["principal"]["subject"],
            quantity=quantity,status="active",expires_at=now.replace(microsecond=0)+__import__("datetime").timedelta(minutes=15)))
        lot.status="reserved"; lot.version+=1
        return {"reservation_id":rid,"lot_id":lot.id,"quantity":str(quantity)}

@activity.defn
async def run_compliance(payload:dict):
    with db_session() as s:
        lot=s.get(CommodityLot,payload["lot_id"])
        if not lot: raise RuntimeError("lot not found")
        passed=bool(lot.farm_ids) and (lot.attributes or {}).get("traceability") in ("verified","ready")
        if not passed: raise RuntimeError("lot compliance evidence incomplete")
        return {"passed":True,"farm_count":len(lot.farm_ids or []),"traceability":(lot.attributes or {}).get("traceability")}

@activity.defn
async def verify_approval(payload:dict):
    reference=payload.get("approval_reference")
    if not reference: raise RuntimeError("approval reference required")
    with db_session() as s:
        approval=s.scalar(select(ApprovalRecord).where(ApprovalRecord.id==reference))
        if not approval:
            approval=s.scalar(select(ApprovalRecord).where(ApprovalRecord.run_id==payload.get("run_id")).order_by(ApprovalRecord.created_at.desc()))
        if not approval: raise RuntimeError("authenticated approval record not found")
        return {"verified":True,"approval_id":approval.id,"principal_sub":approval.principal_sub,"institution_id":approval.institution_id}

@activity.defn
async def execute_settlement(payload:dict):
    p=service_principal(payload); ctx=set_current_principal(p)
    try:
        body=SettlementRequest(
            lot_id=payload["lot_id"],gross_value=Decimal(str(payload["gross_value"])),
            currency=payload.get("currency","USD"),
            allocations={k:Decimal(str(v)) for k,v in payload["allocations"].items()},
            approval_reference=payload["approval_reference"],
            idempotency_key=payload["idempotency_key"],
        )
        return agpay_live_settle(body)
    finally:
        reset_current_principal(ctx)

@activity.defn
async def transfer_ownership(payload:dict):
    p=service_principal(payload); ctx=set_current_principal(p)
    try:
        result=title_transfer(TitleTransferRequest(
            lot_id=payload["lot_id"],to_owner=payload["to_owner"],
            settlement_reference=payload["settlement"]["instruction"]["instruction_id"] if "instruction" in payload["settlement"] else payload["settlement"].get("instruction_id","")
        ))
        return result
    finally:
        reset_current_principal(ctx)

@activity.defn
async def close_trade(payload:dict):
    with db_session() as s:
        if payload.get("order_id"):
            conf=s.scalar(select(TradeConfirmation).where(TradeConfirmation.order_id==payload["order_id"]).order_by(TradeConfirmation.created_at.desc()))
            if conf: conf.status="settled"
    return {"closed":True}

@activity.defn
async def release_lot(payload:dict):
    with db_session() as s:
        rows=s.scalars(select(LotReservation).where(LotReservation.lot_id==payload["lot_id"],LotReservation.status=="active")).all()
        for row in rows: row.status="released"
        lot=s.get(CommodityLot,payload["lot_id"])
        if lot and lot.status=="reserved": lot.status="available";lot.version+=1
    return {"released":True}

@activity.defn
async def validate_collateral(payload:dict):
    with db_session() as s:
        receipt=s.scalar(select(WarehouseReceipt).where(WarehouseReceipt.lot_id==payload["lot_id"]))
        if not receipt or receipt.status!="issued": raise RuntimeError("active warehouse receipt required")
        return {"valid":True,"receipt_id":receipt.id,"collateral_value":str(receipt.collateral_value or 0),"currency":receipt.currency}

@activity.defn
async def assess_finance_risk(payload:dict):
    amount=Decimal(str(payload["requested_amount"]))
    collateral=Decimal(str(payload["collateral_value"]))
    advance=amount/collateral if collateral else Decimal("99")
    if advance>Decimal(os.getenv("COMMOS_PILOT_MAX_ADVANCE_RATE","0.60")): raise RuntimeError("pilot advance rate exceeded")
    return {"risk":"acceptable","advance_rate":str(advance)}

@activity.defn
async def originate_facility(payload:dict):
    return {"status":"ready_for_supervised_lender_submission","external_execution":False,"requested_amount":str(payload["requested_amount"])}

async def connect_temporal():
    target=os.getenv("TEMPORAL_ADDRESS")
    if not target: raise RuntimeError("TEMPORAL_ADDRESS required")
    kwargs={"namespace":os.getenv("TEMPORAL_NAMESPACE","default")}
    api_key=os.getenv("TEMPORAL_API_KEY")
    if api_key: kwargs["api_key"]=api_key; kwargs["tls"]=True
    return await Client.connect(target,**kwargs)

async def main():
    client=await connect_temporal()
    worker=Worker(client,task_queue=os.getenv("TEMPORAL_TASK_QUEUE","commos-pilot"),
      workflows=[CommodityTradeWorkflow,CommodityFinanceWorkflow],
      activities=[reserve_lot,run_compliance,verify_approval,execute_settlement,transfer_ownership,close_trade,release_lot,validate_collateral,assess_finance_risk,originate_facility])
    await worker.run()

if __name__=="__main__":
    asyncio.run(main())
