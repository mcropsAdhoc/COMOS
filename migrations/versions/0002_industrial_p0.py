"""industrial P0 financial and identity state"""
from alembic import op
import sqlalchemy as sa

revision="0002_industrial_p0"
down_revision="0001_commos_state"
branch_labels=None
depends_on=None

money=sa.Numeric(24,8)

def upgrade():
    for table,col in [
        ("commos_lots","quantity"),("commos_lots","sale_value"),
        ("commos_trade_proposals","unit_price"),("commos_trade_proposals","quantity"),("commos_trade_proposals","gross_value"),
        ("commos_market_observations","price"),
        ("commos_orders","quantity"),("commos_orders","limit_price"),
        ("commos_warehouse_receipts","collateral_value"),
        ("commos_forward_contracts","quantity"),("commos_forward_contracts","fixed_price"),
        ("commos_agent_traces","monetary_exposure"),
    ]:
        with op.batch_alter_table(table) as b:
            b.alter_column(col,type_=money,existing_nullable=True)
    with op.batch_alter_table("commos_lots") as b:
        b.add_column(sa.Column("version",sa.Integer(),nullable=False,server_default="1"))
    with op.batch_alter_table("commos_orders") as b:
        b.add_column(sa.Column("remaining_quantity",money,nullable=True))
        b.add_column(sa.Column("version",sa.Integer(),nullable=False,server_default="1"))
    with op.batch_alter_table("commos_agent_runs") as b:
        b.add_column(sa.Column("tenant_id",sa.String(160),nullable=True))
        b.add_column(sa.Column("institution_id",sa.String(160),nullable=True))
        b.add_column(sa.Column("requested_by",sa.String(160),nullable=True))

    op.create_table("commos_ledger_accounts",
        sa.Column("id",sa.String(160),primary_key=True),
        sa.Column("account_type",sa.String(40),nullable=False),
        sa.Column("currency",sa.String(8),nullable=False),
        sa.Column("status",sa.String(24),nullable=False,server_default="active"))
    op.create_table("commos_ledger_transactions",
        sa.Column("id",sa.String(64),primary_key=True),
        sa.Column("reference",sa.String(160),nullable=False,unique=True),
        sa.Column("currency",sa.String(8),nullable=False),
        sa.Column("status",sa.String(24),nullable=False,server_default="posted"),
        sa.Column("metadata_json",sa.JSON(),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("commos_ledger_entries",
        sa.Column("id",sa.String(64),primary_key=True),
        sa.Column("transaction_id",sa.String(64),nullable=False),
        sa.Column("account_id",sa.String(160),nullable=False),
        sa.Column("debit",money,nullable=False,server_default="0"),
        sa.Column("credit",money,nullable=False,server_default="0"),
        sa.Column("memo",sa.String(255),nullable=True),
        sa.CheckConstraint("debit >= 0 AND credit >= 0",name="ck_ledger_nonnegative"))
    op.create_table("commos_ownership_events",
        sa.Column("id",sa.String(64),primary_key=True),
        sa.Column("lot_id",sa.String(128),nullable=False),
        sa.Column("from_owner",sa.String(160),nullable=True),
        sa.Column("to_owner",sa.String(160),nullable=False),
        sa.Column("event_type",sa.String(40),nullable=False),
        sa.Column("reference",sa.String(160),nullable=False,unique=True),
        sa.Column("principal_sub",sa.String(160),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("commos_idempotency_keys",
        sa.Column("key",sa.String(160),primary_key=True),
        sa.Column("operation",sa.String(120),nullable=False),
        sa.Column("request_hash",sa.String(128),nullable=False),
        sa.Column("status",sa.String(24),nullable=False,server_default="reserved"),
        sa.Column("resource_id",sa.String(160),nullable=True),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("commos_approval_records",
        sa.Column("id",sa.String(64),primary_key=True),
        sa.Column("run_id",sa.String(64),nullable=False),
        sa.Column("action",sa.String(120),nullable=False),
        sa.Column("principal_sub",sa.String(160),nullable=False),
        sa.Column("tenant_id",sa.String(160),nullable=False),
        sa.Column("institution_id",sa.String(160),nullable=False),
        sa.Column("policy_source",sa.String(80),nullable=False),
        sa.Column("policy_decision",sa.JSON(),nullable=False),
        sa.Column("token_jti",sa.String(160),nullable=True),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))

def downgrade():
    for t in ["commos_approval_records","commos_idempotency_keys","commos_ownership_events","commos_ledger_entries","commos_ledger_transactions","commos_ledger_accounts"]:
        op.drop_table(t)
    with op.batch_alter_table("commos_agent_runs") as b:
        b.drop_column("requested_by");b.drop_column("institution_id");b.drop_column("tenant_id")
    with op.batch_alter_table("commos_orders") as b:
        b.drop_column("version");b.drop_column("remaining_quantity")
    with op.batch_alter_table("commos_lots") as b:
        b.drop_column("version")
