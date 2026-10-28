"""Allow a finding to be marked retested."""
from alembic import op
from sqlalchemy import text

revision = "0029_finding_retested"
down_revision = "0028_code_workspaces"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    udt = conn.execute(text(
        "SELECT udt_name FROM information_schema.columns "
        "WHERE table_name = 'findings' AND column_name = 'status'"
    )).scalar()
    if udt == "findingstatus":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE findingstatus ADD VALUE IF NOT EXISTS 'retested'")


def downgrade():
    # Postgres cannot drop a single enum value without recreating the type.
    pass
