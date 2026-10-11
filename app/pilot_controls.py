import os
from decimal import Decimal
from fastapi import HTTPException
from app.security import current_principal

DEFAULT_LIMITS={"USD":Decimal("10000"),"UGX":Decimal("40000000")}

def pilot_mode()->bool:
    return os.getenv("COMMOS_PILOT_MODE","true").lower()=="true"

def pilot_limit(currency:str)->Decimal:
    key=f"COMMOS_PILOT_MAX_TX_{currency.upper()}"
    if os.getenv(key):
        return Decimal(os.environ[key])
    return DEFAULT_LIMITS.get(currency.upper(),Decimal(os.getenv("COMMOS_PILOT_MAX_TX_DEFAULT","10000")))

def enforce_supervised_action(action:str, amount:Decimal=Decimal("0"), currency:str="USD"):
    if not pilot_mode():
        return
    p=current_principal()
    allowed_roles=set(x.strip() for x in os.getenv("COMMOS_PILOT_APPROVER_ROLES","dcf_admin,pilot_approver,bank_approver").split(",") if x.strip())
    if not (set(p.roles)&allowed_roles):
        raise HTTPException(403,f"{action} requires supervised pilot approver role")
    limit=pilot_limit(currency)
    if amount>limit:
        raise HTTPException(403,f"pilot transaction cap exceeded for {currency}; maximum {limit}")
