import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select, func
from fastapi import HTTPException
from app.db import db_session
from app.security import current_principal
from app.commos_models import CapabilityUsage

CAPABILITY_SCOPES={
  "planner.plan":"agent:plan",
  "market.observe":"market:write",
  "market.latest":"market:read",
  "buyer.quote":"buyer:quote",
  "orderbook.create":"order:write",
  "orderbook.list":"order:read",
  "warehouse.receipt.issue":"warehouse:write",
  "forward.create":"forward:write",
  "forward.hedge":"risk:read",
  "eudr.generate":"compliance:write",
  "policy.evaluate":"policy:read",
  "agpay.settle":"settlement:execute",
  "observability.summary":"audit:read",
}

def authorize_capability(capability:str,monetary_exposure:Decimal=Decimal("0"),currency:str="USD"):
    p=current_principal()
    required=CAPABILITY_SCOPES.get(capability)
    if required and required not in p.scopes and "*" not in p.scopes:
        raise HTTPException(403,f"scope {required} required")
    hourly_limit=int(os.getenv("COMMOS_AGENT_MAX_CALLS_PER_HOUR","500"))
    exposure_limit=Decimal(os.getenv("COMMOS_AGENT_MAX_EXPOSURE_PER_DAY","100000"))
    now=datetime.now(timezone.utc)
    with db_session() as s:
        calls=s.scalar(select(func.count()).select_from(CapabilityUsage).where(
          CapabilityUsage.principal_sub==p.subject,
          CapabilityUsage.created_at>=now-timedelta(hours=1)
        )) or 0
        if calls>=hourly_limit:raise HTTPException(429,"agent hourly capability limit exceeded")
        day_exposure=s.scalar(select(func.coalesce(func.sum(CapabilityUsage.monetary_exposure),0)).where(
          CapabilityUsage.principal_sub==p.subject,
          CapabilityUsage.created_at>=now-timedelta(days=1)
        )) or Decimal("0")
        if Decimal(str(day_exposure))+monetary_exposure>exposure_limit:
            raise HTTPException(403,"agent daily monetary exposure limit exceeded")
        s.add(CapabilityUsage(
          id=f"use_{uuid4().hex[:16]}",principal_sub=p.subject,tenant_id=p.tenant_id,
          capability=capability,monetary_exposure=monetary_exposure,currency=currency
        ))
    return p
