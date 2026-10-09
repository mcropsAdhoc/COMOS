import asyncio, os
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import activity
from app.workflows import CommodityTradeWorkflow, CommodityFinanceWorkflow

@activity.defn
async def reserve_lot(payload:dict): return {"reserved":True,"lot_id":payload["lot_id"]}
@activity.defn
async def run_compliance(payload:dict): return {"passed":True}
@activity.defn
async def verify_approval(payload:dict): return {"verified":True,"approval_reference":payload.get("approval_reference")}
@activity.defn
async def execute_settlement(payload:dict): return {"status":"submitted","idempotency_key":payload.get("idempotency_key")}
@activity.defn
async def transfer_ownership(payload:dict): return {"transferred":True}
@activity.defn
async def close_trade(payload:dict): return {"closed":True}
@activity.defn
async def release_lot(payload:dict): return {"released":True}
@activity.defn
async def validate_collateral(payload:dict): return {"valid":True}
@activity.defn
async def assess_finance_risk(payload:dict): return {"risk":"acceptable"}
@activity.defn
async def originate_facility(payload:dict): return {"status":"originated"}

async def main():
    target=os.getenv("TEMPORAL_ADDRESS")
    namespace=os.getenv("TEMPORAL_NAMESPACE","default")
    if not target:raise RuntimeError("TEMPORAL_ADDRESS required")
    client=await Client.connect(target,namespace=namespace)
    worker=Worker(client,task_queue=os.getenv("TEMPORAL_TASK_QUEUE","commos-industrial"),
      workflows=[CommodityTradeWorkflow,CommodityFinanceWorkflow],
      activities=[reserve_lot,run_compliance,verify_approval,execute_settlement,transfer_ownership,close_trade,release_lot,validate_collateral,assess_finance_risk,originate_facility])
    await worker.run()

if __name__=="__main__":
    asyncio.run(main())
