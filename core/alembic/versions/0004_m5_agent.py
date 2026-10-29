"""M5: таблицы agent_steps, agent_configs и новые колонки agent_runs.

Идемпотентно: на свежей БД baseline (0001) уже создаёт всё из метаданных,
поэтому add_column пропускается, если колонка есть; новые таблицы создаются
с checkfirst. На БД, развёрнутой до M5, добавляется недостающее.

DDL заморожен на форму M5. Нельзя брать живые модели: у agent_steps позже
появляется worker_id со ссылкой на agent_workers, а эта таблица создаётся
только в 0018. Свежий upgrade это скрывает, потому что 0001 уже создал
текущую форму и checkfirst ничего не делает.

Revision ID: 0004_m5
Revises: 0003_m3
Create Date: 2026-09-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_m5"
down_revision = "0003_m3"
branch_labels = None
depends_on = None

_AGENT_RUN_COLS = {
    "task": sa.Text(),
    "mode": sa.String(20),
    "model": sa.String(200),
    "persona_id": sa.String(36),
}


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def _m5_tables() -> tuple[sa.Table, sa.Table]:
    """Форма таблиц на момент M5: без worker_id и без ссылки на agent_workers."""
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.String(36), primary_key=True))
    sa.Table("agent_runs", metadata, sa.Column("id", sa.String(36), primary_key=True))
    steps = sa.Table(
        "agent_steps",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("requires_hitl", sa.Boolean(), nullable=False),
        sa.Column("target", sa.String(500)),
        sa.Column("command", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("output", sa.Text()),
    )
    configs = sa.Table(
        "agent_configs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "owner_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            index=True,
            nullable=False,
        ),
        sa.Column("preset", sa.String(20), nullable=False),
        sa.Column("role_models", sa.JSON(), nullable=False),
        sa.Column("budgets", sa.JSON(), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
    )
    return steps, configs


def upgrade() -> None:
    bind = op.get_bind()
    for name, coltype in _AGENT_RUN_COLS.items():
        if not _has_column(bind, "agent_runs", name):
            op.add_column("agent_runs", sa.Column(name, coltype, nullable=True))
    for table in _m5_tables():
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    present = set(sa.inspect(bind).get_table_names())
    for name in ("agent_steps", "agent_configs"):
        if name in present:
            op.drop_table(name)
    for name in _AGENT_RUN_COLS:
        if _has_column(bind, "agent_runs", name):
            op.drop_column("agent_runs", name)
