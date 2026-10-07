from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from app.db import db_session
from app.commos_models import CommodityLot, MarketObservation

def lot_to_dict(x: CommodityLot):
    return {"lot_id":x.id,"commodity":x.commodity,"origin_country":x.origin_country,"quantity":x.quantity,
      "unit":x.unit,"grade":x.grade,"owner_id":x.owner_id,"farm_ids":x.farm_ids or [],
      "warehouse_id":x.warehouse_id,"attributes":x.attributes or {},"status":x.status,
      "buyer_id":x.buyer_id,"sale_value":x.sale_value,"sale_currency":x.sale_currency,
      "created_at":x.created_at.isoformat() if x.created_at else None}

def create_lot(data: dict):
    with db_session() as s:
        row=CommodityLot(id=data["lot_id"],commodity=data["commodity"],origin_country=data["origin_country"],
          quantity=data["quantity"],unit=data["unit"],grade=data.get("grade"),owner_id=data["owner_id"],
          farm_ids=data.get("farm_ids",[]),warehouse_id=data.get("warehouse_id"),attributes=data.get("attributes",{}),
          status=data.get("status","available"))
        s.add(row);s.flush();return lot_to_dict(row)

def get_lot(lot_id: str):
    with db_session() as s:
        row=s.get(CommodityLot,lot_id)
        return lot_to_dict(row) if row else None

def update_lot_sale(lot_id,buyer_id,value,currency):
    with db_session() as s:
        row=s.get(CommodityLot,lot_id)
        if not row:return None
        row.status="sold";row.buyer_id=buyer_id;row.sale_value=value;row.sale_currency=currency
        s.flush();return lot_to_dict(row)

def list_lots(limit=100):
    with db_session() as s:
        rows=s.scalars(select(CommodityLot).order_by(CommodityLot.created_at.desc()).limit(limit)).all()
        return [lot_to_dict(x) for x in rows]

def create_market_observation(data: dict):
    with db_session() as s:
        row=MarketObservation(id=data.get("id") or f"mkt_{uuid4().hex[:12]}",commodity=data["commodity"],
          market=data["market"],price=data["price"],currency=data.get("currency","USD"),
          price_unit=data.get("price_unit","kg"),source=data["source"],region=data.get("region"),
          metadata_json=data.get("metadata",{}),observed_at=data.get("observed_at") or datetime.now(timezone.utc))
        s.add(row);s.flush()
        return {"id":row.id,"commodity":row.commodity,"market":row.market,"price":row.price,"currency":row.currency,
          "price_unit":row.price_unit,"source":row.source,"region":row.region,"metadata":row.metadata_json,
          "observed_at":row.observed_at.isoformat()}

def latest_market_observations(commodity: str, limit=20):
    with db_session() as s:
        rows=s.scalars(select(MarketObservation).where(MarketObservation.commodity==commodity)
          .order_by(MarketObservation.observed_at.desc()).limit(limit)).all()
        return [{"id":x.id,"commodity":x.commodity,"market":x.market,"price":x.price,"currency":x.currency,
          "price_unit":x.price_unit,"source":x.source,"region":x.region,"metadata":x.metadata_json,
          "observed_at":x.observed_at.isoformat()} for x in rows]


from app.commos_models import AgentRun, TradeProposal

def run_to_dict(x: AgentRun):
    return {"run_id":x.id,"intent":x.intent,"lot_snapshot":x.lot_snapshot,"plan":x.plan,"status":x.status,
      "approval":x.approval,"created_at":x.created_at.isoformat() if x.created_at else None,
      "completed_at":x.completed_at.isoformat() if x.completed_at else None}

def create_run(data: dict):
    with db_session() as s:
        row=AgentRun(id=data["run_id"],intent=data["intent"],lot_snapshot=data["lot_snapshot"],plan=data["plan"],
          status=data["status"],approval=data["approval"])
        s.add(row);s.flush();return run_to_dict(row)

def get_run(run_id: str):
    with db_session() as s:
        row=s.get(AgentRun,run_id)
        return run_to_dict(row) if row else None

def update_run(run_id: str, **changes):
    with db_session() as s:
        row=s.get(AgentRun,run_id)
        if not row:return None
        for k,v in changes.items():
            if hasattr(row,k):setattr(row,k,v)
        s.flush();return run_to_dict(row)

def proposal_to_dict(x: TradeProposal):
    return {"proposal_id":x.id,"run_id":x.run_id,"lot_id":x.lot_id,"buyer_id":x.buyer_id,
      "unit_price":x.unit_price,"currency":x.currency,"quantity":x.quantity,"unit":x.unit,
      "gross_value":x.gross_value,"status":x.status,
      "created_at":x.created_at.isoformat() if x.created_at else None,
      "executed_at":x.executed_at.isoformat() if x.executed_at else None}

def create_proposal(data: dict):
    with db_session() as s:
        row=TradeProposal(id=data["proposal_id"],run_id=data["run_id"],lot_id=data["lot_id"],buyer_id=data["buyer_id"],
          unit_price=data["unit_price"],currency=data["currency"],quantity=data["quantity"],unit=data["unit"],
          gross_value=data["gross_value"],status=data.get("status","proposed"))
        s.add(row);s.flush();return proposal_to_dict(row)

def get_proposal(proposal_id: str):
    with db_session() as s:
        row=s.get(TradeProposal,proposal_id)
        return proposal_to_dict(row) if row else None

def update_proposal(proposal_id: str, **changes):
    with db_session() as s:
        row=s.get(TradeProposal,proposal_id)
        if not row:return None
        for k,v in changes.items():
            if hasattr(row,k):setattr(row,k,v)
        s.flush();return proposal_to_dict(row)
