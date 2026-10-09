"""industrial P0 financial and identity state"""
from alembic import op
import sqlalchemy as sa

revision="0002_industrial_p0"
down_revision="0001_commos_state"
branch_labels=None
depends_on=None
money=sa.Numeric(24,8)

def upgrade():
    bind=op.get_bind()
    insp=sa.inspect(bind)
    def cols(table): return {c["name"] for c in insp.get_columns(table)}
    def has_table(table): return insp.has_table(table)

    for table,col in [
        ("commos_lots","quantity"),("commos_lots","sale_value"),
        ("commos_trade_proposals","unit_price"),("commos_trade_proposals","quantity"),("commos_trade_proposals","gross_value"),
        ("commos_market_observations","price"),("commos_orders","quantity"),("commos_orders","limit_price"),
        ("commos_warehouse_receipts","collateral_value"),("commos_forward_contracts","quantity"),
        ("commos_forward_contracts","fixed_price"),("commos_agent_traces","monetary_exposure")
    ]:
        if col in cols(table):
            with op.batch_alter_table(table) as b:
                b.alter_column(col,type_=money,existing_nullable=True)

    if "version" not in cols("commos_lots"):
        with op.batch_alter_table("commos_lots") as b:
            b.add_column(sa.Column("version",sa.Integer(),nullable=False,server_default="1"))
    oc=cols("commos_orders")
    with op.batch_alter_table("commos_orders") as b:
        if "remaining_quantity" not in oc:b.add_column(sa.Column("remaining_quantity",money,nullable=True))
        if "version" not in oc:b.add_column(sa.Column("version",sa.Integer(),nullable=False,server_default="1"))
    rc=cols("commos_agent_runs")
    with op.batch_alter_table("commos_agent_runs") as b:
        if "tenant_id" not in rc:b.add_column(sa.Column("tenant_id",sa.String(160),nullable=True))
        if "institution_id" not in rc:b.add_column(sa.Column("institution_id",sa.String(160),nullable=True))
        if "requested_by" not in rc:b.add_column(sa.Column("requested_by",sa.String(160),nullable=True))

    if not has_table("commos_ledger_accounts"):
        op.create_table("commos_ledger_accounts",sa.Column("id",sa.String(160),primary_key=True),sa.Column("account_type",sa.String(40),nullable=False),sa.Column("currency",sa.String(8),nullable=False),sa.Column("status",sa.String(24),nullable=False,server_default="active"))
    if not has_table("commos_ledger_transactions"):
        op.create_table("commos_ledger_transactions",sa.Column("id",sa.String(64),primary_key=True),sa.Column("reference",sa.String(160),nullable=False,unique=True),sa.Column("currency",sa.String(8),nullable=False),sa.Column("status",sa.String(24),nullable=False,server_default="posted"),sa.Column("metadata_json",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    if not has_table("commos_ledger_entries"):
        op.create_table("commos_ledger_entries",sa.Column("id",sa.String(64),primary_key=True),sa.Column("transaction_id",sa.String(64),nullable=False),sa.Column("account_id",sa.String(160),nullable=False),sa.Column("debit",money,nullable=False,server_default="0"),sa.Column("credit",money,nullable=False,server_default="0"),sa.Column("memo",sa.String(255),nullable=True),sa.CheckConstraint("debit >= 0 AND credit >= 0",name="ck_ledger_nonnegative"))
    if not has_table("commos_ownership_events"):
        op.create_table("commos_ownership_events",sa.Column("id",sa.String(64),primary_key=True),sa.Column("lot_id",sa.String(128),nullable=False),sa.Column("from_owner",sa.String(160),nullable=True),sa.Column("to_owner",sa.String(160),nullable=False),sa.Column("event_type",sa.String(40),nullable=False),sa.Column("reference",sa.String(160),nullable=False,unique=True),sa.Column("principal_sub",sa.String(160),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    if not has_table("commos_idempotency_keys"):
        op.create_table("commos_idempotency_keys",sa.Column("key",sa.String(160),primary_key=True),sa.Column("operation",sa.String(120),nullable=False),sa.Column("request_hash",sa.String(128),nullable=False),sa.Column("status",sa.String(24),nullable=False,server_default="reserved"),sa.Column("resource_id",sa.String(160),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    if not has_table("commos_approval_records"):
        op.create_table("commos_approval_records",sa.Column("id",sa.String(64),primary_key=True),sa.Column("run_id",sa.String(64),nullable=False),sa.Column("action",sa.String(120),nullable=False),sa.Column("principal_sub",sa.String(160),nullable=False),sa.Column("tenant_id",sa.String(160),nullable=False),sa.Column("institution_id",sa.String(160),nullable=False),sa.Column("policy_source",sa.String(80),nullable=False),sa.Column("policy_decision",sa.JSON(),nullable=False),sa.Column("token_jti",sa.String(160),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))

def downgrade():
    for t in ["commos_approval_records","commos_idempotency_keys","commos_ownership_events","commos_ledger_entries","commos_ledger_transactions","commos_ledger_accounts"]:
        op.drop_table(t)
