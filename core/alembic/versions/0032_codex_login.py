"""Persist encrypted Codex device authorizations across workers and restarts."""
from alembic import op
from app.models.codex_login import CodexLogin

revision = "0032_codex_login"
down_revision = "0031_agent_domain"
branch_labels = None
depends_on = None


def upgrade():
    CodexLogin.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    CodexLogin.__table__.drop(op.get_bind(), checkfirst=True)
