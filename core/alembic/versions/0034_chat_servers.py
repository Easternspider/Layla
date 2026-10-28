"""Remember which servers an Agent chat is allowed to use."""
import sqlalchemy as sa
from alembic import op

revision = "0034_chat_servers"
down_revision = "0033_agent_provider"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "chats", "server_ids"):
        op.add_column("chats", sa.Column("server_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "chats", "server_ids"):
        op.drop_column("chats", "server_ids")
