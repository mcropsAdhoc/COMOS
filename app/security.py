import os
from dataclasses import dataclass
from functools import lru_cache
import httpx
import jwt
from fastapi import Header, HTTPException, Request

@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    institution_id: str
    roles: tuple[str, ...]
    scopes: tuple[str, ...]
    token_id: str | None
    auth_method: str

    def has_role(self, *roles: str) -> bool:
        return bool(set(roles) & set(self.roles))

    def has_scope(self, *scopes: str) -> bool:
        return bool(set(scopes) & set(self.scopes))

@lru_cache(maxsize=1)
def _oidc_metadata():
    issuer=os.getenv("OIDC_ISSUER","").rstrip("/")
    if not issuer:
        return None
    r=httpx.get(f"{issuer}/.well-known/openid-configuration",timeout=5)
    r.raise_for_status()
    return r.json()

@lru_cache(maxsize=1)
def _jwks_client():
    md=_oidc_metadata()
    return jwt.PyJWKClient(md["jwks_uri"]) if md else None

def _decode(token:str)->dict:
    mode=os.getenv("COMMOS_AUTH_MODE","oidc").lower()
    audience=os.getenv("OIDC_AUDIENCE","commos-api")
    if mode=="dev":
        secret=os.getenv("COMMOS_DEV_JWT_SECRET","")
        if not secret: raise HTTPException(503,"development JWT mode not configured")
        return jwt.decode(token,secret,algorithms=["HS256"],audience=audience)
    issuer=os.getenv("OIDC_ISSUER","").rstrip("/")
    client=_jwks_client()
    if not issuer or client is None: raise HTTPException(503,"OIDC not configured")
    key=client.get_signing_key_from_jwt(token).key
    return jwt.decode(token,key,algorithms=["RS256","ES256"],audience=audience,issuer=issuer)

async def authenticate(request:Request,authorization:str|None=Header(default=None,alias="Authorization"))->Principal:
    if request.url.path in {"/health","/docs","/openapi.json"} or request.method=="OPTIONS":
        return Principal("anonymous","public","public",(),(),None,"anonymous")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Bearer token required")
    claims=_decode(authorization[7:])
    roles=claims.get("roles") or claims.get("realm_access",{}).get("roles") or []
    scopes=(claims.get("scope") or "").split()
    p=Principal(
        subject=claims.get("sub",""),
        tenant_id=claims.get("tenant_id") or claims.get("tenant") or "",
        institution_id=claims.get("institution_id") or claims.get("institution") or "",
        roles=tuple(roles),scopes=tuple(scopes),token_id=claims.get("jti"),auth_method=os.getenv("COMMOS_AUTH_MODE","oidc")
    )
    if not p.subject or not p.tenant_id or not p.institution_id:
        raise HTTPException(403,"subject, tenant_id and institution_id claims required")
    request.state.principal=p
    return p
