from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Lead(Base):
    __tablename__ = "leads"

    lead_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(10), index=True, default="")
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    service_category: Mapped[str] = mapped_column(String(64), default="Other")
    summary: Mapped[str] = mapped_column(Text, default="")

    messages: Mapped[list["LeadMessage"]] = relationship(
        back_populates="lead", order_by="LeadMessage.position", cascade="all, delete-orphan"
    )
    sources: Mapped[list["LeadSource"]] = relationship(
        back_populates="lead", order_by="LeadSource.id", cascade="all, delete-orphan"
    )


class LeadMessage(Base):
    __tablename__ = "lead_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.lead_id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")

    lead: Mapped[Lead] = relationship(back_populates="messages")


class LeadSource(Base):
    __tablename__ = "lead_sources"
    __table_args__ = (UniqueConstraint("lead_id", "source", name="uq_lead_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.lead_id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32))

    lead: Mapped[Lead] = relationship(back_populates="sources")


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.lead_id", ondelete="CASCADE"), index=True)
