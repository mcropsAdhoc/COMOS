from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

@workflow.defn
class CommodityTradeWorkflow:
    @workflow.run
    async def run(self,payload:dict)->dict:
        retry=RetryPolicy(initial_interval=timedelta(seconds=1),maximum_interval=timedelta(seconds=30),maximum_attempts=5)
        reserve=await workflow.execute_activity("reserve_lot",payload,start_to_close_timeout=timedelta(seconds=20),retry_policy=retry)
        try:
            compliance=await workflow.execute_activity("run_compliance",payload,start_to_close_timeout=timedelta(minutes=2),retry_policy=retry)
            approval=await workflow.execute_activity("verify_approval",payload,start_to_close_timeout=timedelta(seconds=20),retry_policy=retry)
            settlement=await workflow.execute_activity("execute_settlement",payload,start_to_close_timeout=timedelta(minutes=5),retry_policy=retry)
            ownership=await workflow.execute_activity("transfer_ownership",{**payload,"settlement":settlement},start_to_close_timeout=timedelta(seconds=30),retry_policy=retry)
            await workflow.execute_activity("close_trade",payload,start_to_close_timeout=timedelta(seconds=20),retry_policy=retry)
            return {"status":"completed","reservation":reserve,"compliance":compliance,"approval":approval,"settlement":settlement,"ownership":ownership}
        except Exception:
            await workflow.execute_activity("release_lot",payload,start_to_close_timeout=timedelta(seconds=20))
            raise

@workflow.defn
class CommodityFinanceWorkflow:
    @workflow.run
    async def run(self,payload:dict)->dict:
        retry=RetryPolicy(maximum_attempts=4)
        collateral=await workflow.execute_activity("validate_collateral",payload,start_to_close_timeout=timedelta(minutes=2),retry_policy=retry)
        risk=await workflow.execute_activity("assess_finance_risk",payload,start_to_close_timeout=timedelta(minutes=2),retry_policy=retry)
        approval=await workflow.execute_activity("verify_approval",payload,start_to_close_timeout=timedelta(minutes=10),retry_policy=retry)
        facility=await workflow.execute_activity("originate_facility",payload,start_to_close_timeout=timedelta(minutes=5),retry_policy=retry)
        return {"status":"completed","collateral":collateral,"risk":risk,"approval":approval,"facility":facility}
