from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

def utcnow():
    return datetime.now(timezone.utc)

class CommodityLot(Base):
    __tablename__ = "commos_lots"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    commodity: Mapped[str] = mapped_column(String(80), index=True)
    origin_country: Mapped[str] = mapped_column(String(8), default="UG")
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(24), default="kg")
    grade: Mapped[str | None] = mapped_column(String(80), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(160), index=True)
    farm_ids: Mapped[list] = mapped_column(JSON, default=list)
    warehouse_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="available", index=True)
    buyer_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sale_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sale_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AgentRun(Base):
    __tablename__ = "commos_agent_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intent: Mapped[dict] = mapped_column(JSON)
    lot_snapshot: Mapped[dict] = mapped_column(JSON)
    plan: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), index=True)
    approval: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class TradeProposal(Base):
    __tablename__ = "commos_trade_proposals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    lot_id: Mapped[str] = mapped_column(String(128), index=True)
    buyer_id: Mapped[str] = mapped_column(String(160), index=True)
    unit_price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(24))
    gross_value: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="proposed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class MarketObservation(Base):
    __tablename__ = "commos_market_observations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    commodity: Mapped[str] = mapped_column(String(80), index=True)
    market: Mapped[str] = mapped_column(String(120), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    price_unit: Mapped[str] = mapped_column(String(24), default="kg")
    source: Mapped[str] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Order(Base):
    __tablename__ = "commos_orders"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_type: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8), index=True)
    commodity: Mapped[str] = mapped_column(String(80), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    actor_id: Mapped[str] = mapped_column(String(160), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(24))
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    terms: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class WarehouseReceipt(Base):
    __tablename__ = "commos_warehouse_receipts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lot_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(160), index=True)
    custodian_id: Mapped[str] = mapped_column(String(160))
    owner_id: Mapped[str] = mapped_column(String(160))
    lien_holder_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    collateral_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    status: Mapped[str] = mapped_column(String(24), default="issued", index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ForwardContract(Base):
    __tablename__ = "commos_forward_contracts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    commodity: Mapped[str] = mapped_column(String(80), index=True)
    seller_id: Mapped[str] = mapped_column(String(160))
    buyer_id: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(24))
    delivery_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fixed_price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    hedge_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class EudrEvidencePack(Base):
    __tablename__ = "commos_eudr_packs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lot_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    farm_evidence: Mapped[list] = mapped_column(JSON, default=list)
    traceability_evidence: Mapped[list] = mapped_column(JSON, default=list)
    risk_assessment: Mapped[dict] = mapped_column(JSON, default=dict)
    declaration: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class PolicyRule(Base):
    __tablename__ = "commos_policy_rules"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institution_id: Mapped[str] = mapped_column(String(160), index=True)
    actor_type: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    effect: Mapped[str] = mapped_column(String(16), default="allow")
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class AgentTrace(Base):
    __tablename__ = "commos_agent_traces"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    skill: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    monetary_exposure: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
