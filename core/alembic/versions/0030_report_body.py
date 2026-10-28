"""Store generated pentest report markdown."""
import sqlalchemy as sa
from alembic import op

revision = "0030_report_body"
down_revision = "0029_finding_retested"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reports", sa.Column("body", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("reports", "body")
