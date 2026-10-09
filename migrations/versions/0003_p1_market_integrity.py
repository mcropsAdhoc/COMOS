"""P1 market integrity and provenance"""
from alembic import op
import sqlalchemy as sa

revision="0003_p1_market_integrity"
down_revision="0002_industrial_p0"
branch_labels=None
depends_on=None
money=sa.Numeric(24,8)

def upgrade():
    insp=sa.inspect(op.get_bind())
    def create(name, *cols):
        if not insp.has_table(name):
            op.create_table(name,*cols)
    create("commos_lot_reservations",
      sa.Column("id",sa.String(64),primary_key=True),
      sa.Column("lot_id",sa.String(128),nullable=False),
      sa.Column("order_id",sa.String(64),nullable=True),
      sa.Column("reserved_for",sa.String(160),nullable=False),
      sa.Column("quantity",money,nullable=False),
      sa.Column("status",sa.String(24),nullable=False,server_default="active"),
      sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),
      sa.Column("version",sa.Integer(),nullable=False,server_default="1"),
      sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    create("commos_trade_confirmations",
      sa.Column("id",sa.String(64),primary_key=True),
      sa.Column("order_id",sa.String(64),nullable=False),
      sa.Column("lot_id",sa.String(128),nullable=False),
      sa.Column("buyer_id",sa.String(160),nullable=False),
      sa.Column("seller_id",sa.String(160),nullable=False),
      sa.Column("quantity",money,nullable=False),
      sa.Column("unit_price",money,nullable=False),
      sa.Column("gross_value",money,nullable=False),
      sa.Column("currency",sa.String(8),nullable=False),
      sa.Column("status",sa.String(24),nullable=False,server_default="confirmed"),
      sa.Column("confirmation_hash",sa.String(128),nullable=False,unique=True),
      sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    create("commos_counterparty_exposure",
      sa.Column("id",sa.String(160),primary_key=True),
      sa.Column("counterparty_id",sa.String(160),nullable=False),
      sa.Column("currency",sa.String(8),nullable=False),
      sa.Column("current_exposure",money,nullable=False,server_default="0"),
      sa.Column("limit_amount",money,nullable=False,server_default="0"),
      sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    create("commos_evidence_records",
      sa.Column("id",sa.String(64),primary_key=True),
      sa.Column("subject_type",sa.String(40),nullable=False),
      sa.Column("subject_id",sa.String(160),nullable=False),
      sa.Column("evidence_type",sa.String(80),nullable=False),
      sa.Column("source",sa.String(160),nullable=False),
      sa.Column("content_hash",sa.String(128),nullable=False),
      sa.Column("uri",sa.Text(),nullable=True),
      sa.Column("metadata_json",sa.JSON(),nullable=False),
      sa.Column("observed_at",sa.DateTime(timezone=True),nullable=False),
      sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    create("commos_warehouse_receipt_events",
      sa.Column("id",sa.String(64),primary_key=True),
      sa.Column("receipt_id",sa.String(64),nullable=False),
      sa.Column("event_type",sa.String(60),nullable=False),
      sa.Column("principal_sub",sa.String(160),nullable=False),
      sa.Column("payload",sa.JSON(),nullable=False),
      sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    create("commos_model_executions",
      sa.Column("id",sa.String(64),primary_key=True),
      sa.Column("run_id",sa.String(64),nullable=False),
      sa.Column("model_name",sa.String(120),nullable=False),
      sa.Column("model_version",sa.String(80),nullable=False),
      sa.Column("input_hash",sa.String(128),nullable=False),
      sa.Column("output_hash",sa.String(128),nullable=False),
      sa.Column("provenance",sa.JSON(),nullable=False),
      sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    create("commos_capability_usage",
      sa.Column("id",sa.String(64),primary_key=True),
      sa.Column("principal_sub",sa.String(160),nullable=False),
      sa.Column("tenant_id",sa.String(160),nullable=False),
      sa.Column("capability",sa.String(120),nullable=False),
      sa.Column("monetary_exposure",money,nullable=False,server_default="0"),
      sa.Column("currency",sa.String(8),nullable=False,server_default="USD"),
      sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))

def downgrade():
    for t in ["commos_capability_usage","commos_model_executions","commos_warehouse_receipt_events","commos_evidence_records","commos_counterparty_exposure","commos_trade_confirmations","commos_lot_reservations"]:
        op.drop_table(t)
