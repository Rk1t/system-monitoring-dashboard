import time
from datetime import datetime

import psutil
from sqlalchemy import desc
from sqlalchemy.orm import Session

from config import settings
from models import Metric
from node_manager import get_or_create_local_node


_last_network = psutil.net_io_counters()
_last_network_time = time.monotonic()


def collect_metrics(db: Session) -> Metric:
    """Считывает системные показатели и сохраняет одну точку истории."""
    global _last_network, _last_network_time

    local_node = get_or_create_local_node(db)
    collected_at = datetime.utcnow()

    current_network = psutil.net_io_counters()
    current_time = time.monotonic()
    elapsed = max(current_time - _last_network_time, 1)

    sent_per_sec = (current_network.bytes_sent - _last_network.bytes_sent) / elapsed
    recv_per_sec = (current_network.bytes_recv - _last_network.bytes_recv) / elapsed

    metric = Metric(
        node_id=local_node.id,
        timestamp=collected_at,
        cpu_percent=psutil.cpu_percent(interval=0.2),
        ram_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage("/").percent,
        bytes_sent=current_network.bytes_sent,
        bytes_recv=current_network.bytes_recv,
        network_sent_per_sec=max(sent_per_sec, 0),
        network_recv_per_sec=max(recv_per_sec, 0),
    )

    db.add(metric)
    local_node.last_seen = collected_at
    local_node.status = "online"
    db.commit()
    db.refresh(metric)
    cleanup_old_metrics(db, local_node.id, settings.history_limit_records)

    _last_network = current_network
    _last_network_time = current_time

    return metric


def cleanup_old_metrics(db: Session, node_id: int, limit: int) -> None:
    """Оставляет в базе только последние limit записей истории конкретного узла."""
    old_records = (
        db.query(Metric.id)
        .filter(Metric.node_id == node_id)
        .order_by(desc(Metric.timestamp))
        .offset(limit)
        .all()
    )

    if not old_records:
        return

    old_ids = [record.id for record in old_records]
    db.query(Metric).filter(Metric.id.in_(old_ids)).delete(synchronize_session=False)
    db.commit()
