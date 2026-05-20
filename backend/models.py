from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    hostname: Mapped[str] = mapped_column(String(255), index=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    os_name: Mapped[str] = mapped_column(String(255))
    agent_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="online", index=True)
    health_score: Mapped[int] = mapped_column(Integer, default=100)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    metrics: Mapped[list["Metric"]] = relationship(back_populates="node")


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_id: Mapped[int | None] = mapped_column(ForeignKey("nodes.id"), index=True, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    cpu_percent: Mapped[float] = mapped_column(Float)
    ram_percent: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float] = mapped_column(Float)
    bytes_sent: Mapped[int] = mapped_column(Integer)
    bytes_recv: Mapped[int] = mapped_column(Integer)
    network_sent_per_sec: Mapped[float] = mapped_column(Float)
    network_recv_per_sec: Mapped[float] = mapped_column(Float)

    node: Mapped[Node | None] = relationship(back_populates="metrics")
