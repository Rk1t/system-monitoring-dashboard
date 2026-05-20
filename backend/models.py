from datetime import datetime

from sqlalchemy import DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    cpu_percent: Mapped[float] = mapped_column(Float)
    ram_percent: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float] = mapped_column(Float)
    bytes_sent: Mapped[int] = mapped_column(Integer)
    bytes_recv: Mapped[int] = mapped_column(Integer)
    network_sent_per_sec: Mapped[float] = mapped_column(Float)
    network_recv_per_sec: Mapped[float] = mapped_column(Float)
