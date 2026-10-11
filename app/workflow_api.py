import os
from decimal import Decimal
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from temporalio.client import Client
from app.workflows import CommodityTradeWorkflow, CommodityFinanceWorkflow
from app.security import current_principal
from app.pilot_controls import enforce_supervised_action

router=APIRouter(prefix="/v1/commos/workflows",tags=["COMMOS Durable Workflows"])

class TradeWorkflowRequest(BaseModel):
    lot_id:str
    order_id:str|None=None
    quantity:Decimal=Field(gt=0)
    gross_value:Decimal=Field(gt=0)
    currency:str="USD"
    allocations:dict[str,Decimal]
    approval_reference:str
    idempotency_key:str
    to_owner:str

class FinanceWorkflowRequest(BaseModel):
    lot_id:str
    requested_amount:Decimal=Field(gt=0)
    collateral_value:Decimal=Field(gt=0)
    currency:str="USD"
    approval_reference:str

async def client():
    target=os.getenv("TEMPORAL_ADDRESS")
    if not target: raise HTTPException(503,"Temporal is not configured; durable execution is required for this workflow")
    kwargs={"namespace":os.getenv("TEMPORAL_NAMESPACE","default")}
    api_key=os.getenv("TEMPORAL_API_KEY")
    if api_key: kwargs["api_key"]=api_key;kwargs["tls"]=True
    return await Client.connect(target,**kwargs)

def principal_snapshot():
    p=current_principal()
    return {"subject":p.subject,"tenant_id":p.tenant_id,"institution_id":p.institution_id,"roles":list(p.roles),"scopes":list(p.scopes),"token_id":p.token_id}

@router.post("/trade")
async def start_trade(body:TradeWorkflowRequest):
    enforce_supervised_action("workflow.trade",body.gross_value,body.currency)
    c=await client()
    workflow_id=f"commos-trade-{body.lot_id.split(':')[-1]}-{uuid4().hex[:8]}"
    payload={**body.model_dump(mode="json"),"principal":principal_snapshot(),"run_id":workflow_id}
    handle=await c.start_workflow(CommodityTradeWorkflow.run,payload,id=workflow_id,task_queue=os.getenv("TEMPORAL_TASK_QUEUE","commos-pilot"))
    return {"workflow_id":handle.id,"run_id":handle.result_run_id,"status":"started","durability":"temporal"}

@router.post("/finance")
async def start_finance(body:FinanceWorkflowRequest):
    enforce_supervised_action("workflow.finance",body.requested_amount,body.currency)
    c=await client()
    workflow_id=f"commos-finance-{body.lot_id.split(':')[-1]}-{uuid4().hex[:8]}"
    payload={**body.model_dump(mode="json"),"principal":principal_snapshot(),"run_id":workflow_id}
    handle=await c.start_workflow(CommodityFinanceWorkflow.run,payload,id=workflow_id,task_queue=os.getenv("TEMPORAL_TASK_QUEUE","commos-pilot"))
    return {"workflow_id":handle.id,"run_id":handle.result_run_id,"status":"started","durability":"temporal"}

@router.get("/{workflow_id}")
async def workflow_status(workflow_id:str):
    c=await client()
    desc=await c.get_workflow_handle(workflow_id).describe()
    return {"workflow_id":workflow_id,"status":desc.status.name,"run_id":desc.run_id}
