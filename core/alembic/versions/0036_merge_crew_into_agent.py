"""Fold existing Orchestra chats into the Agent domain."""
from alembic import op

revision = "0036_merge_crew_into_agent"
down_revision = "0035_crew_domain"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE chats SET domain = 'agent' WHERE domain = 'crew'")


def downgrade():
    pass
