"""Store generated pentest report markdown."""
import sqlalchemy as sa
from alembic import op

revision = "0030_report_body"
down_revision = "0029_finding_retested"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "reports" not in set(inspector.get_table_names()):
        return
    if "body" in {column["name"] for column in inspector.get_columns("reports")}:
        return
    op.add_column("reports", sa.Column("body", sa.Text(), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "reports" not in set(inspector.get_table_names()):
        return
    if "body" not in {column["name"] for column in inspector.get_columns("reports")}:
        return
    op.drop_column("reports", "body")
