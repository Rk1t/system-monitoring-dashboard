import platform
import socket
from datetime import datetime

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from models import Node


def ensure_metrics_node_id_column(engine: Engine) -> None:
    """Добавляет metrics.node_id в старую SQLite-базу без удаления данных."""
    with engine.begin() as connection:
        table_info = connection.execute(text("PRAGMA table_info(metrics)")).mappings().all()
        column_names = {column["name"] for column in table_info}

        if table_info and "node_id" not in column_names:
            connection.execute(text("ALTER TABLE metrics ADD COLUMN node_id INTEGER"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_metrics_node_id ON metrics (node_id)"))


def get_or_create_local_node(db: Session) -> Node:
    now = datetime.utcnow()
    hostname = socket.gethostname()
    os_name = f"{platform.system()} {platform.platform()}"

    node = db.query(Node).filter(Node.source_type == "local").first()
    if node:
        node.hostname = hostname
        node.os_name = os_name
        node.status = "online"
        node.last_seen = now
        db.commit()
        db.refresh(node)
        return node

    node = Node(
        name="Local System",
        hostname=hostname,
        source_type="local",
        os_name=os_name,
        agent_version=None,
        status="online",
        health_score=100,
        first_seen=now,
        last_seen=now,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def assign_existing_metrics_to_node(db: Session, node_id: int) -> None:
    db.execute(text("UPDATE metrics SET node_id = :node_id WHERE node_id IS NULL"), {"node_id": node_id})
    db.commit()
