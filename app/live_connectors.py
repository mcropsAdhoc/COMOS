import os, time
from dataclasses import dataclass
from typing import Any
import httpx
from sqlalchemy import text
from app.db import engine

@dataclass
class Connector:
    name: str
    kind: str
    base_url_env: str
    health_path: str = "/health"
    auth_header_env: str | None = None
    auth_prefix: str = "Bearer"

    def configured(self) -> bool:
        return bool(os.getenv(self.base_url_env))

    def _headers(self) -> dict[str,str]:
        if not self.auth_header_env:
            return {}
        token=os.getenv(self.auth_header_env)
        return {"Authorization":f"{self.auth_prefix} {token}"} if token else {}

    def health(self) -> dict[str,Any]:
        url=os.getenv(self.base_url_env)
        if not url:
            return {"name":self.name,"kind":self.kind,"configured":False,"reachable":False,"status":"not_configured"}
        started=time.perf_counter()
        try:
            r=httpx.get(url.rstrip("/")+self.health_path,headers=self._headers(),timeout=4)
            latency=int((time.perf_counter()-started)*1000)
            return {"name":self.name,"kind":self.kind,"configured":True,"reachable":r.status_code<500,
                "http_status":r.status_code,"latency_ms":latency,"status":"online" if r.status_code<400 else "degraded"}
        except Exception as e:
            return {"name":self.name,"kind":self.kind,"configured":True,"reachable":False,
                "status":"offline","error_type":type(e).__name__}

CONNECTORS=[
    Connector("OPA","policy","OPA_URL","/health"),
    Connector("AgrOS AgPay","settlement","AGPAY_API_URL","/health","AGPAY_API_TOKEN"),
    Connector("Exporter Buyer","buyer","BUYER_EXPORTER_API_URL","/health","BUYER_EXPORTER_API_TOKEN"),
    Connector("Processor Buyer","buyer","BUYER_PROCESSOR_API_URL","/health","BUYER_PROCESSOR_API_TOKEN"),
    Connector("Roaster Buyer","buyer","BUYER_ROASTER_API_URL","/health","BUYER_ROASTER_API_TOKEN"),
    Connector("International Market Feed","market","MARKET_INTL_API_URL","/health","MARKET_INTL_API_TOKEN"),
    Connector("Uganda Market Feed","market","MARKET_UG_API_URL","/health","MARKET_UG_API_TOKEN"),
]

def database_health():
    started=time.perf_counter()
    try:
        with engine.connect() as c:
            value=c.execute(text("select 1")).scalar_one()
        return {"name":"PostgreSQL","kind":"database","configured":True,"reachable":value==1,
            "latency_ms":int((time.perf_counter()-started)*1000),"status":"online" if value==1 else "degraded"}
    except Exception as e:
        return {"name":"PostgreSQL","kind":"database","configured":bool(os.getenv("DATABASE_URL")),
            "reachable":False,"status":"offline","error_type":type(e).__name__}

def infrastructure_health():
    services=[database_health()]+[c.health() for c in CONNECTORS]
    online=sum(1 for x in services if x["reachable"])
    configured=sum(1 for x in services if x["configured"])
    return {"services":services,"summary":{"online":online,"configured":configured,"total":len(services),
        "ready":configured>0 and online==configured}}
