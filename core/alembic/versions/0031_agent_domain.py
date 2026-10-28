"""Allow the operator agent domain on Postgres enums."""
import re

import sqlalchemy as sa
from alembic import op

revision = "0031_agent_domain"
down_revision = "0030_report_body"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
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
            "WHERE t.typname = :name AND e.enumlabel = 'agent'"
        ), {"name": name}).first()
        if exists:
            continue
        with op.get_context().autocommit_block():
            op.execute(f'ALTER TYPE "{name}" ADD VALUE \'agent\'')


def downgrade():
    return
