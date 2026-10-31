"""Subagents of an Orchestra chat. A slot is one of three concurrent runners."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import Timestamps, UUIDPk


class CrewMember(UUIDPk, Timestamps, Base):
    __tablename__ = "crew_members"
    __table_args__ = (UniqueConstraint("chat_id", "slot", name="uq_crew_member_slot"),)

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    slot: Mapped[int | None] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    report: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text)
    detached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
