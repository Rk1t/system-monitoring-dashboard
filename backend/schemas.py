from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    bytes_sent: int
    bytes_recv: int
    network_sent_per_sec: float
    network_recv_per_sec: float


class MetricsSummary(BaseModel):
    records_count: int
    avg_cpu_percent: float
    max_cpu_percent: float
    avg_ram_percent: float
    max_ram_percent: float
    avg_disk_percent: float
    max_disk_percent: float
