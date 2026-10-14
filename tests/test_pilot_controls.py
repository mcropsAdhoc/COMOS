import os
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.security import Principal,set_current_principal,reset_current_principal
from app.pilot_controls import enforce_supervised_action

def principal(roles=("pilot_approver",)):
    return Principal("pilot-user","pilot-tenant","dcf",roles,("*",),"pilot-jti","test")

def test_pilot_cap_allows_supervised_amount(monkeypatch):
    monkeypatch.setenv("COMMOS_PILOT_MODE","true")
    monkeypatch.setenv("COMMOS_PILOT_MAX_TX_USD","10000")
    ctx=set_current_principal(principal())
    try:
        enforce_supervised_action("settlement.execute",Decimal("9999.99"),"USD")
    finally:
        reset_current_principal(ctx)

def test_pilot_cap_blocks_excess(monkeypatch):
    monkeypatch.setenv("COMMOS_PILOT_MODE","true")
    monkeypatch.setenv("COMMOS_PILOT_MAX_TX_USD","10000")
    ctx=set_current_principal(principal())
    try:
        with pytest.raises(HTTPException) as exc:
            enforce_supervised_action("settlement.execute",Decimal("10000.01"),"USD")
        assert exc.value.status_code==403
    finally:
        reset_current_principal(ctx)

def test_pilot_requires_supervised_role(monkeypatch):
    monkeypatch.setenv("COMMOS_PILOT_MODE","true")
    ctx=set_current_principal(principal(("viewer",)))
    try:
        with pytest.raises(HTTPException) as exc:
            enforce_supervised_action("ownership.transfer",Decimal("0"),"USD")
        assert exc.value.status_code==403
    finally:
        reset_current_principal(ctx)
