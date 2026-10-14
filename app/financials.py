from decimal import Decimal
from uuid import uuid4
from app.db import db_session
from app.commos_models import LedgerAccount, LedgerTransaction, LedgerEntry, OwnershipEvent, IdempotencyKey

ZERO=Decimal("0")
def D(v)->Decimal: return Decimal(str(v))

def reserve_idempotency(key:str,operation:str,request_hash:str):
    with db_session() as s:
        row=s.get(IdempotencyKey,key)
        if row:
            if row.operation!=operation or row.request_hash!=request_hash:
                raise ValueError("idempotency key reused with different request")
            return {"replay":True,"resource_id":row.resource_id}
        s.add(IdempotencyKey(key=key,operation=operation,request_hash=request_hash,status="reserved"))
        return {"replay":False,"resource_id":None}

def complete_idempotency(key:str,resource_id:str):
    with db_session() as s:
        row=s.get(IdempotencyKey,key)
        if row: row.status="completed"; row.resource_id=resource_id

def post_balanced_transaction(reference:str,currency:str,entries:list[dict],metadata:dict|None=None):
    debit=sum((D(x.get("debit",0)) for x in entries),ZERO)
    credit=sum((D(x.get("credit",0)) for x in entries),ZERO)
    if debit!=credit or debit<=ZERO: raise ValueError("ledger transaction must be positive and balanced")
    txid=f"ltx_{uuid4().hex[:16]}"
    with db_session() as s:
        s.add(LedgerTransaction(id=txid,reference=reference,currency=currency,status="posted",metadata_json=metadata or {}))
        for e in entries:
            account=s.get(LedgerAccount,e["account_id"])
            if not account:
                s.add(LedgerAccount(id=e["account_id"],account_type=e.get("account_type","clearing"),currency=currency,status="active"))
            s.add(LedgerEntry(id=f"le_{uuid4().hex[:16]}",transaction_id=txid,account_id=e["account_id"],debit=D(e.get("debit",0)),credit=D(e.get("credit",0)),memo=e.get("memo")))
    return {"transaction_id":txid,"debits":str(debit),"credits":str(credit),"balanced":True}

def record_ownership_event(lot_id:str,from_owner:str|None,to_owner:str,event_type:str,reference:str,principal_sub:str):
    with db_session() as s:
        row=OwnershipEvent(id=f"own_{uuid4().hex[:16]}",lot_id=lot_id,from_owner=from_owner,to_owner=to_owner,event_type=event_type,reference=reference,principal_sub=principal_sub)
        s.add(row); s.flush()
        return {"event_id":row.id,"lot_id":lot_id,"from_owner":from_owner,"to_owner":to_owner,"event_type":event_type}
