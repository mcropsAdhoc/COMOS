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
