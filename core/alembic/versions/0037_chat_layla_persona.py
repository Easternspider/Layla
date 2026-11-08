"""Remember whether an agent chat should speak as Layla."""
import sqlalchemy as sa
from alembic import op

revision = "0037_chat_layla_persona"
down_revision = "0036_merge_crew_into_agent"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "chats", "layla_persona"):
        op.add_column("chats", sa.Column("layla_persona", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "chats", "layla_persona"):
        op.drop_column("chats", "layla_persona")
