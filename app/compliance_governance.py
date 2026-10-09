import hashlib, json
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from app.db import db_session
from app.security import current_principal
from app.commos_models import EvidenceRecord, WarehouseReceipt, WarehouseReceiptEvent, ModelExecution, CommodityLot

router=APIRouter(prefix="/v1/commos/governance",tags=["COMMOS Governance"])

class EvidenceCreate(BaseModel):
    subject_type:str
    subject_id:str
    evidence_type:str
    source:str
    content:dict
    uri:str|None=None
    observed_at:datetime|None=None

class ReceiptEventCreate(BaseModel):
    receipt_id:str
    event_type:str
    payload:dict={}

class ModelExecutionCreate(BaseModel):
    run_id:str
    model_name:str
    model_version:str
    input_payload:dict
    output_payload:dict
    provenance:dict={}

@router.post("/evidence")
def add_evidence(body:EvidenceCreate):
    current_principal()
    canonical=json.dumps(body.content,sort_keys=True,separators=(",",":"))
    digest=hashlib.sha256(canonical.encode()).hexdigest()
    eid=f"ev_{uuid4().hex[:16]}"
    with db_session() as s:
        s.add(EvidenceRecord(id=eid,subject_type=body.subject_type,subject_id=body.subject_id,
          evidence_type=body.evidence_type,source=body.source,content_hash=digest,uri=body.uri,
          metadata_json=body.content,observed_at=body.observed_at or datetime.now(timezone.utc)))
    return {"evidence_id":eid,"content_hash":digest}

@router.get("/eudr/{lot_id}/evidence-graph")
def eudr_evidence_graph(lot_id:str):
    with db_session() as s:
        lot=s.get(CommodityLot,lot_id)
        if not lot:raise HTTPException(404,"lot not found")
        records=s.scalars(select(EvidenceRecord).where(
          EvidenceRecord.subject_id.in_([lot_id]+list(lot.farm_ids or []))
        ).order_by(EvidenceRecord.created_at.asc())).all()
        return {
          "lot_id":lot_id,
          "farm_ids":lot.farm_ids or [],
          "traceability_state":(lot.attributes or {}).get("traceability"),
          "evidence":[{"id":x.id,"subject_type":x.subject_type,"subject_id":x.subject_id,"type":x.evidence_type,
            "source":x.source,"hash":x.content_hash,"uri":x.uri,"observed_at":x.observed_at.isoformat()} for x in records],
          "ready":bool(lot.farm_ids) and (lot.attributes or {}).get("traceability") in ("verified","ready") and len(records)>0
        }

@router.post("/warehouse-receipts/events")
def warehouse_receipt_event(body:ReceiptEventCreate):
    p=current_principal()
    with db_session() as s:
        receipt=s.get(WarehouseReceipt,body.receipt_id)
        if not receipt:raise HTTPException(404,"warehouse receipt not found")
        eid=f"wre_{uuid4().hex[:16]}"
        s.add(WarehouseReceiptEvent(id=eid,receipt_id=body.receipt_id,event_type=body.event_type,principal_sub=p.subject,payload=body.payload))
        return {"event_id":eid,"receipt_id":body.receipt_id,"event_type":body.event_type,"principal_sub":p.subject}

@router.post("/model-executions")
def record_model_execution(body:ModelExecutionCreate):
    current_principal()
    ih=hashlib.sha256(json.dumps(body.input_payload,sort_keys=True,default=str).encode()).hexdigest()
    oh=hashlib.sha256(json.dumps(body.output_payload,sort_keys=True,default=str).encode()).hexdigest()
    mid=f"mx_{uuid4().hex[:16]}"
    with db_session() as s:
        s.add(ModelExecution(id=mid,run_id=body.run_id,model_name=body.model_name,model_version=body.model_version,
          input_hash=ih,output_hash=oh,provenance=body.provenance))
    return {"execution_id":mid,"input_hash":ih,"output_hash":oh}
