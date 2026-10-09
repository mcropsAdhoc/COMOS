from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Integer, Boolean, DateTime, Text, JSON, Numeric, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

MONEY=Numeric(24,8)
QTY=Numeric(24,8)

def utcnow():
    return datetime.now(timezone.utc)

class CommodityLot(Base):
    __tablename__="commos_lots"
    id: Mapped[str]=mapped_column(String(128),primary_key=True)
    commodity: Mapped[str]=mapped_column(String(80),index=True)
    origin_country: Mapped[str]=mapped_column(String(8),default="UG")
    quantity: Mapped[Decimal]=mapped_column(QTY)
    unit: Mapped[str]=mapped_column(String(24),default="kg")
    grade: Mapped[str|None]=mapped_column(String(80),nullable=True)
    owner_id: Mapped[str]=mapped_column(String(160),index=True)
    farm_ids: Mapped[list]=mapped_column(JSON,default=list)
    warehouse_id: Mapped[str|None]=mapped_column(String(160),nullable=True)
    attributes: Mapped[dict]=mapped_column(JSON,default=dict)
    status: Mapped[str]=mapped_column(String(32),default="available",index=True)
    buyer_id: Mapped[str|None]=mapped_column(String(160),nullable=True)
    sale_value: Mapped[Decimal|None]=mapped_column(MONEY,nullable=True)
    sale_currency: Mapped[str|None]=mapped_column(String(8),nullable=True)
    version: Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class AgentRun(Base):
    __tablename__="commos_agent_runs"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    intent: Mapped[dict]=mapped_column(JSON)
    lot_snapshot: Mapped[dict]=mapped_column(JSON)
    plan: Mapped[list]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String(32),index=True)
    approval: Mapped[dict]=mapped_column(JSON)
    tenant_id: Mapped[str|None]=mapped_column(String(160),nullable=True,index=True)
    institution_id: Mapped[str|None]=mapped_column(String(160),nullable=True,index=True)
    requested_by: Mapped[str|None]=mapped_column(String(160),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class TradeProposal(Base):
    __tablename__="commos_trade_proposals"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    run_id: Mapped[str]=mapped_column(String(64),index=True)
    lot_id: Mapped[str]=mapped_column(String(128),index=True)
    buyer_id: Mapped[str]=mapped_column(String(160),index=True)
    unit_price: Mapped[Decimal]=mapped_column(MONEY)
    currency: Mapped[str]=mapped_column(String(8))
    quantity: Mapped[Decimal]=mapped_column(QTY)
    unit: Mapped[str]=mapped_column(String(24))
    gross_value: Mapped[Decimal]=mapped_column(MONEY)
    status: Mapped[str]=mapped_column(String(32),default="proposed",index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    executed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketObservation(Base):
    __tablename__="commos_market_observations"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    commodity: Mapped[str]=mapped_column(String(80),index=True)
    market: Mapped[str]=mapped_column(String(120),index=True)
    price: Mapped[Decimal]=mapped_column(MONEY)
    currency: Mapped[str]=mapped_column(String(8),default="USD")
    price_unit: Mapped[str]=mapped_column(String(24),default="kg")
    source: Mapped[str]=mapped_column(String(120))
    region: Mapped[str|None]=mapped_column(String(120),nullable=True)
    metadata_json: Mapped[dict]=mapped_column(JSON,default=dict)
    observed_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class Order(Base):
    __tablename__="commos_orders"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    order_type: Mapped[str]=mapped_column(String(16),index=True)
    side: Mapped[str]=mapped_column(String(8),index=True)
    commodity: Mapped[str]=mapped_column(String(80),index=True)
    lot_id: Mapped[str|None]=mapped_column(String(128),nullable=True,index=True)
    actor_id: Mapped[str]=mapped_column(String(160),index=True)
    quantity: Mapped[Decimal]=mapped_column(QTY)
    remaining_quantity: Mapped[Decimal|None]=mapped_column(QTY,nullable=True)
    unit: Mapped[str]=mapped_column(String(24))
    limit_price: Mapped[Decimal|None]=mapped_column(MONEY,nullable=True)
    currency: Mapped[str]=mapped_column(String(8),default="USD")
    status: Mapped[str]=mapped_column(String(24),default="open",index=True)
    terms: Mapped[dict]=mapped_column(JSON,default=dict)
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    version: Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class WarehouseReceipt(Base):
    __tablename__="commos_warehouse_receipts"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    lot_id: Mapped[str]=mapped_column(String(128),unique=True,index=True)
    warehouse_id: Mapped[str]=mapped_column(String(160),index=True)
    custodian_id: Mapped[str]=mapped_column(String(160))
    owner_id: Mapped[str]=mapped_column(String(160))
    lien_holder_id: Mapped[str|None]=mapped_column(String(160),nullable=True)
    collateral_value: Mapped[Decimal|None]=mapped_column(MONEY,nullable=True)
    currency: Mapped[str]=mapped_column(String(8),default="USD")
    status: Mapped[str]=mapped_column(String(24),default="issued",index=True)
    issued_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class ForwardContract(Base):
    __tablename__="commos_forward_contracts"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    commodity: Mapped[str]=mapped_column(String(80),index=True)
    seller_id: Mapped[str]=mapped_column(String(160))
    buyer_id: Mapped[str]=mapped_column(String(160))
    quantity: Mapped[Decimal]=mapped_column(QTY)
    unit: Mapped[str]=mapped_column(String(24))
    delivery_date: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    fixed_price: Mapped[Decimal]=mapped_column(MONEY)
    currency: Mapped[str]=mapped_column(String(8),default="USD")
    status: Mapped[str]=mapped_column(String(24),default="draft",index=True)
    hedge_metadata: Mapped[dict]=mapped_column(JSON,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class EudrEvidencePack(Base):
    __tablename__="commos_eudr_packs"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    lot_id: Mapped[str]=mapped_column(String(128),index=True)
    status: Mapped[str]=mapped_column(String(32),default="draft",index=True)
    farm_evidence: Mapped[list]=mapped_column(JSON,default=list)
    traceability_evidence: Mapped[list]=mapped_column(JSON,default=list)
    risk_assessment: Mapped[dict]=mapped_column(JSON,default=dict)
    declaration: Mapped[dict]=mapped_column(JSON,default=dict)
    generated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class PolicyRule(Base):
    __tablename__="commos_policy_rules"
    id: Mapped[str]=mapped_column(String(80),primary_key=True)
    institution_id: Mapped[str]=mapped_column(String(160),index=True)
    actor_type: Mapped[str]=mapped_column(String(40),index=True)
    action: Mapped[str]=mapped_column(String(120),index=True)
    effect: Mapped[str]=mapped_column(String(16),default="deny")
    conditions: Mapped[dict]=mapped_column(JSON,default=dict)
    requires_approval: Mapped[bool]=mapped_column(Boolean,default=False)
    enabled: Mapped[bool]=mapped_column(Boolean,default=True)

class AgentTrace(Base):
    __tablename__="commos_agent_traces"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    run_id: Mapped[str]=mapped_column(String(64),index=True)
    skill: Mapped[str]=mapped_column(String(120),index=True)
    status: Mapped[str]=mapped_column(String(24),index=True)
    latency_ms: Mapped[int]=mapped_column(Integer,default=0)
    monetary_exposure: Mapped[Decimal]=mapped_column(MONEY,default=Decimal("0"))
    currency: Mapped[str]=mapped_column(String(8),default="USD")
    provenance: Mapped[dict]=mapped_column(JSON,default=dict)
    error: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class LedgerAccount(Base):
    __tablename__="commos_ledger_accounts"
    id: Mapped[str]=mapped_column(String(160),primary_key=True)
    account_type: Mapped[str]=mapped_column(String(40),index=True)
    currency: Mapped[str]=mapped_column(String(8),index=True)
    status: Mapped[str]=mapped_column(String(24),default="active")

class LedgerTransaction(Base):
    __tablename__="commos_ledger_transactions"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    reference: Mapped[str]=mapped_column(String(160),unique=True,index=True)
    currency: Mapped[str]=mapped_column(String(8),index=True)
    status: Mapped[str]=mapped_column(String(24),default="posted")
    metadata_json: Mapped[dict]=mapped_column(JSON,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class LedgerEntry(Base):
    __tablename__="commos_ledger_entries"
    __table_args__=(CheckConstraint("debit >= 0 AND credit >= 0","ck_ledger_nonnegative"),)
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    transaction_id: Mapped[str]=mapped_column(String(64),index=True)
    account_id: Mapped[str]=mapped_column(String(160),index=True)
    debit: Mapped[Decimal]=mapped_column(MONEY,default=Decimal("0"))
    credit: Mapped[Decimal]=mapped_column(MONEY,default=Decimal("0"))
    memo: Mapped[str|None]=mapped_column(String(255),nullable=True)

class OwnershipEvent(Base):
    __tablename__="commos_ownership_events"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    lot_id: Mapped[str]=mapped_column(String(128),index=True)
    from_owner: Mapped[str|None]=mapped_column(String(160),nullable=True)
    to_owner: Mapped[str]=mapped_column(String(160),index=True)
    event_type: Mapped[str]=mapped_column(String(40))
    reference: Mapped[str]=mapped_column(String(160),unique=True,index=True)
    principal_sub: Mapped[str]=mapped_column(String(160))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class IdempotencyKey(Base):
    __tablename__="commos_idempotency_keys"
    key: Mapped[str]=mapped_column(String(160),primary_key=True)
    operation: Mapped[str]=mapped_column(String(120),index=True)
    request_hash: Mapped[str]=mapped_column(String(128))
    status: Mapped[str]=mapped_column(String(24),default="reserved")
    resource_id: Mapped[str|None]=mapped_column(String(160),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class ApprovalRecord(Base):
    __tablename__="commos_approval_records"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    run_id: Mapped[str]=mapped_column(String(64),index=True)
    action: Mapped[str]=mapped_column(String(120),index=True)
    principal_sub: Mapped[str]=mapped_column(String(160),index=True)
    tenant_id: Mapped[str]=mapped_column(String(160),index=True)
    institution_id: Mapped[str]=mapped_column(String(160),index=True)
    policy_source: Mapped[str]=mapped_column(String(80))
    policy_decision: Mapped[dict]=mapped_column(JSON)
    token_jti: Mapped[str|None]=mapped_column(String(160),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
