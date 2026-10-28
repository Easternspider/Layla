"""Remember which provider a pentest chat selected.

The same model name can exist on Codex and on another account. Routing by name
alone used the first active provider.
"""
import sqlalchemy as sa
from alembic import op

revision = "0033_agent_provider"
down_revision = "0032_codex_login"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if "agent_runs" not in sa.inspect(bind).get_table_names():
        return
    if not _has_column(bind, "agent_runs", "provider_id"):
        op.add_column("agent_runs", sa.Column("provider_id", sa.String(36), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "agent_runs", "provider_id"):
        op.drop_column("agent_runs", "provider_id")
