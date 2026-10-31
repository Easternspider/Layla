"""Orchestra domain: subagent rows and the crew value on Postgres enums."""
import re

import sqlalchemy as sa
from alembic import op

revision = "0035_crew_domain"
down_revision = "0034_chat_servers"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        rows = bind.execute(sa.text(
            "SELECT DISTINCT t.typname FROM pg_attribute a "
            "JOIN pg_class c ON c.oid = a.attrelid "
            "JOIN pg_type t ON t.oid = a.atttypid "
            "WHERE c.relname IN ('chats', 'agent_runs') AND a.attname = 'domain' AND t.typtype = 'e'"
        )).fetchall()
        for (name,) in rows:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                continue
            exists = bind.execute(sa.text(
                "SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = :name AND e.enumlabel = 'crew'"
            ), {"name": name}).first()
            if exists:
                continue
            with op.get_context().autocommit_block():
                op.execute(f'ALTER TYPE "{name}" ADD VALUE \'crew\'')
    if "crew_members" in sa.inspect(bind).get_table_names():
        return
    metadata = sa.MetaData()
    for name in ("users", "chats", "projects", "jobs"):
        sa.Table(name, metadata, sa.Column("id", sa.String(36), primary_key=True))
    table = sa.Table(
        "crew_members", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chat_id", sa.String(36), sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("slot", sa.Integer()),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("report", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("detached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chat_id", "slot", name="uq_crew_member_slot"),
    )
    table.create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    if "crew_members" in sa.inspect(bind).get_table_names():
        op.drop_table("crew_members")
