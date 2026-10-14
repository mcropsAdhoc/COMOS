import os
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache
import httpx
import jwt
from fastapi import HTTPException

@dataclass(frozen=True)
class Principal:
    subject:str
    tenant_id:str
    institution_id:str
    roles:tuple[str,...]
    scopes:tuple[str,...]
    token_id:str|None
    auth_method:str

    def has_role(self,*roles:str)->bool:
        return bool(set(roles)&set(self.roles))
    def has_scope(self,*scopes:str)->bool:
        return bool(set(scopes)&set(self.scopes))

_current:ContextVar[Principal|None]=ContextVar("commos_principal",default=None)

@lru_cache(maxsize=1)
def _oidc_metadata():
    issuer=os.getenv("OIDC_ISSUER","").rstrip("/")
    if not issuer:return None
    r=httpx.get(f"{issuer}/.well-known/openid-configuration",timeout=5)
    r.raise_for_status()
    return r.json()

@lru_cache(maxsize=1)
def _jwks_client():
    md=_oidc_metadata()
    return jwt.PyJWKClient(md["jwks_uri"]) if md else None

def principal_from_authorization(authorization:str|None)->Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Bearer token required")
    token=authorization[7:]
    mode=os.getenv("COMMOS_AUTH_MODE","oidc").lower()
    audience=os.getenv("OIDC_AUDIENCE","commos-api")
    if mode=="dev":
        secret=os.getenv("COMMOS_DEV_JWT_SECRET","")
        if not secret:raise HTTPException(503,"development JWT mode not configured")
        claims=jwt.decode(token,secret,algorithms=["HS256"],audience=audience)
    else:
        issuer=os.getenv("OIDC_ISSUER","").rstrip("/")
        client=_jwks_client()
        if not issuer or client is None:raise HTTPException(503,"OIDC not configured")
        key=client.get_signing_key_from_jwt(token).key
        claims=jwt.decode(token,key,algorithms=["RS256","ES256"],audience=audience,issuer=issuer)
    roles=claims.get("roles") or claims.get("realm_access",{}).get("roles") or []
    scopes=(claims.get("scope") or "").split()
    p=Principal(
        subject=claims.get("sub",""),
        tenant_id=claims.get("tenant_id") or claims.get("tenant") or "",
        institution_id=claims.get("institution_id") or claims.get("institution") or "",
        roles=tuple(roles),scopes=tuple(scopes),token_id=claims.get("jti"),auth_method=mode
    )
    if not p.subject or not p.tenant_id or not p.institution_id:
        raise HTTPException(403,"subject, tenant_id and institution_id claims required")
    return p

def set_current_principal(p:Principal):
    return _current.set(p)

def reset_current_principal(token):
    _current.reset(token)

def current_principal(required:bool=True)->Principal|None:
    p=_current.get()
    if required and p is None:raise HTTPException(401,"authenticated principal required")
    return p


ROLE_RULES=[
    ("POST","/v1/agent/sessions/","approval:write",{"dcf_admin","bank_approver","pilot_approver"}),
    ("POST","/v1/skills/payment.disburse","settlement:execute",{"dcf_admin","bank_approver","pilot_approver"}),
    ("POST","/v1/commos/policies","policy:admin",{"dcf_admin"}),
    ("POST","/v1/commos/market-integrity/title-transfer","ownership:transfer",{"dcf_admin","pilot_approver"}),
    ("POST","/v1/commos/workflows/","workflow:execute",{"dcf_admin","pilot_approver","bank_approver"}),
]
SCOPE_RULES=[
    ("POST","/v1/identities","identity:write"),
    ("POST","/v1/graph/","graph:write"),
    ("POST","/v1/skills/credit.prequalify","credit:assess"),
    ("POST","/v1/commos/lots","commodity:write"),
    ("POST","/v1/commos/orderbook/","order:write"),
    ("POST","/v1/commos/warehouse/","warehouse:write"),
    ("POST","/v1/commos/market/","market:write"),
    ("POST","/v1/commos/governance/","compliance:write"),
    ("POST","/v1/commos/market-integrity/","trade:execute"),
    ("POST","/v1/commos/workflows/","workflow:execute"),
]

def authorize_http_request(principal:Principal,method:str,path:str):
    if "*" in principal.scopes:
        scope_ok=lambda _: True
    else:
        scope_ok=lambda required: required in principal.scopes
    for rule_method,prefix,scope,roles in ROLE_RULES:
        if method==rule_method and path.startswith(prefix):
            if not scope_ok(scope):
                raise HTTPException(403,f"scope {scope} required")
            if not set(principal.roles)&roles:
                raise HTTPException(403,"role not authorized for operation")
            return
    for rule_method,prefix,scope in SCOPE_RULES:
        if method==rule_method and path.startswith(prefix):
            if not scope_ok(scope):
                raise HTTPException(403,f"scope {scope} required")
            return
