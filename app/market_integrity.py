import hashlib, json, os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from app.db import db_session
from app.security import current_principal
from app.commos_models import CommodityLot, Order, LotReservation, TradeConfirmation, CounterpartyExposure, OwnershipEvent

router=APIRouter(prefix="/v1/commos/market-integrity",tags=["COMMOS Market Integrity"])

class ReserveRequest(BaseModel):
    lot_id:str
    order_id:str|None=None
    quantity:Decimal=Field(gt=0)
    ttl_seconds:int=Field(default=300,ge=30,le=3600)

class FillRequest(BaseModel):
    quantity:Decimal=Field(gt=0)
    unit_price:Decimal=Field(gt=0)
    buyer_id:str
    currency:str="USD"

class TitleTransferRequest(BaseModel):
    lot_id:str
    to_owner:str
    settlement_reference:str

@router.post("/reservations")
def reserve_lot(body:ReserveRequest):
    p=current_principal()
    now=datetime.now(timezone.utc)
    with db_session() as s:
        lot=s.execute(select(CommodityLot).where(CommodityLot.id==body.lot_id).with_for_update()).scalar_one_or_none()
        if not lot:raise HTTPException(404,"lot not found")
        if lot.status not in ("available","reserved"):raise HTTPException(409,"lot not reservable")
        reserved=s.scalar(select(func.coalesce(func.sum(LotReservation.quantity),0)).where(
            LotReservation.lot_id==body.lot_id,LotReservation.status=="active",LotReservation.expires_at>now
        )) or Decimal("0")
        available=lot.quantity-Decimal(str(reserved))
        if body.quantity>available:raise HTTPException(409,"insufficient unreserved quantity")
        rid=f"res_{uuid4().hex[:16]}"
        s.add(LotReservation(id=rid,lot_id=body.lot_id,order_id=body.order_id,reserved_for=p.subject,
            quantity=body.quantity,status="active",expires_at=now+timedelta(seconds=body.ttl_seconds)))
        lot.status="reserved";lot.version+=1
        return {"reservation_id":rid,"lot_id":body.lot_id,"quantity":str(body.quantity),"remaining_unreserved":str(available-body.quantity),"expires_at":(now+timedelta(seconds=body.ttl_seconds)).isoformat()}

@router.post("/orders/{order_id}/fill")
def fill_order(order_id:str,body:FillRequest):
    p=current_principal()
    with db_session() as s:
        order=s.execute(select(Order).where(Order.id==order_id).with_for_update()).scalar_one_or_none()
        if not order:raise HTTPException(404,"order not found")
        if order.status not in ("open","partially_filled"):raise HTTPException(409,"order not fillable")
        remaining=order.remaining_quantity if order.remaining_quantity is not None else order.quantity
        if body.quantity>remaining:raise HTTPException(409,"fill exceeds remaining quantity")
        gross=body.quantity*body.unit_price
        exposure=s.get(CounterpartyExposure,f"{body.buyer_id}:{body.currency}")
        require_limits=os.getenv("COMMOS_REQUIRE_COUNTERPARTY_LIMITS","true").lower()=="true"
        if require_limits and not exposure:raise HTTPException(403,"counterparty limit not configured")
        if exposure and exposure.current_exposure+gross>exposure.limit_amount:
            raise HTTPException(403,"counterparty exposure limit exceeded")
        new_remaining=remaining-body.quantity
        order.remaining_quantity=new_remaining
        order.status="filled" if new_remaining==0 else "partially_filled"
        order.version+=1
        if exposure:
            exposure.current_exposure+=gross
        payload={"order_id":order_id,"lot_id":order.lot_id,"buyer_id":body.buyer_id,"seller_id":order.actor_id,
                 "quantity":str(body.quantity),"unit_price":str(body.unit_price),"gross_value":str(gross),"currency":body.currency}
        confirmation_hash=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        cid=f"tc_{uuid4().hex[:16]}"
        s.add(TradeConfirmation(id=cid,order_id=order_id,lot_id=order.lot_id or "",buyer_id=body.buyer_id,
            seller_id=order.actor_id,quantity=body.quantity,unit_price=body.unit_price,gross_value=gross,
            currency=body.currency,status="confirmed",confirmation_hash=confirmation_hash))
        return {**payload,"confirmation_id":cid,"confirmation_hash":confirmation_hash,"remaining_quantity":str(new_remaining),"status":order.status,"confirmed_by":p.subject}

@router.post("/title-transfer")
def title_transfer(body:TitleTransferRequest):
    p=current_principal()
    with db_session() as s:
        lot=s.execute(select(CommodityLot).where(CommodityLot.id==body.lot_id).with_for_update()).scalar_one_or_none()
        if not lot:raise HTTPException(404,"lot not found")
        from_owner=lot.owner_id
        eid=f"own_{uuid4().hex[:16]}"
        s.add(OwnershipEvent(
            id=eid,lot_id=body.lot_id,from_owner=from_owner,to_owner=body.to_owner,
            event_type="settled-transfer",reference=body.settlement_reference,principal_sub=p.subject
        ))
        lot.owner_id=body.to_owner;lot.version+=1;lot.status="sold"
        return {"event_id":eid,"lot_id":body.lot_id,"from_owner":from_owner,"to_owner":body.to_owner,"event_type":"settled-transfer","version":lot.version}
