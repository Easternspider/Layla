"""Fold existing Orchestra chats into the Agent domain."""
import sqlalchemy as sa
from alembic import op

revision = "0036_merge_crew_into_agent"
down_revision = "0035_crew_domain"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "chats" not in insp.get_table_names():
        return
    if "domain" not in {column["name"] for column in insp.get_columns("chats")}:
        return
    op.execute("UPDATE chats SET domain = 'agent' WHERE domain = 'crew'")


def downgrade():
    pass
