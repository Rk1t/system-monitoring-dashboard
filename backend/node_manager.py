import platform
import socket
from datetime import datetime

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from auth import hash_password
from models import Node, Organization, OrganizationMember, User


DEFAULT_ORGANIZATION_NAME = "Default Organization"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@example.local"
DEFAULT_ADMIN_PASSWORD = "admin123"


def ensure_metrics_node_id_column(engine: Engine) -> None:
    """Добавляет metrics.node_id в старую SQLite-базу без удаления данных."""
    with engine.begin() as connection:
        table_info = connection.execute(text("PRAGMA table_info(metrics)")).mappings().all()
        column_names = []
        for column in table_info:
            column_names.append(column["name"])

        if table_info and "node_id" not in column_names:
            connection.execute(text("ALTER TABLE metrics ADD COLUMN node_id INTEGER"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_metrics_node_id ON metrics (node_id)"))


def ensure_node_redfish_columns(engine: Engine) -> None:
    """Добавляет поля Redfish к старой таблице nodes без пересоздания базы."""
    with engine.begin() as connection:
        table_info = connection.execute(text("PRAGMA table_info(nodes)")).mappings().all()
        column_names = []
        for column in table_info:
            column_names.append(column["name"])

        if table_info and "management_ip" not in column_names:
            connection.execute(text("ALTER TABLE nodes ADD COLUMN management_ip VARCHAR(120)"))
        if table_info and "redfish_username" not in column_names:
            connection.execute(text("ALTER TABLE nodes ADD COLUMN redfish_username VARCHAR(120)"))
        if table_info and "redfish_password" not in column_names:
            connection.execute(text("ALTER TABLE nodes ADD COLUMN redfish_password VARCHAR(255)"))
        if table_info and "use_mock" not in column_names:
            connection.execute(text("ALTER TABLE nodes ADD COLUMN use_mock BOOLEAN DEFAULT 0"))


def ensure_node_organization_column(engine: Engine) -> None:
    """Добавляет nodes.organization_id в старую SQLite-базу без удаления узлов."""
    with engine.begin() as connection:
        table_info = connection.execute(text("PRAGMA table_info(nodes)")).mappings().all()
        column_names = []
        for column in table_info:
            column_names.append(column["name"])

        if table_info and "organization_id" not in column_names:
            connection.execute(text("ALTER TABLE nodes ADD COLUMN organization_id INTEGER"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_nodes_organization_id ON nodes (organization_id)"))


def ensure_node_management_columns(engine: Engine) -> None:
    """Добавляет поля управления узлами к старой SQLite-базе."""
    with engine.begin() as connection:
        table_info = connection.execute(text("PRAGMA table_info(nodes)")).mappings().all()
        column_names = []
        for column in table_info:
            column_names.append(column["name"])

        if table_info and "is_archived" not in column_names:
            connection.execute(text("ALTER TABLE nodes ADD COLUMN is_archived BOOLEAN DEFAULT 0"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_nodes_is_archived ON nodes (is_archived)"))
            connection.execute(text("UPDATE nodes SET is_archived = 0 WHERE is_archived IS NULL"))
        if table_info and "archived_at" not in column_names:
            connection.execute(text("ALTER TABLE nodes ADD COLUMN archived_at DATETIME"))
        if table_info and "description" not in column_names:
            connection.execute(text("ALTER TABLE nodes ADD COLUMN description TEXT"))


def get_or_create_default_organization(db: Session) -> Organization:
    organization = db.query(Organization).filter(Organization.name == DEFAULT_ORGANIZATION_NAME).first()
    if organization:
        return organization

    organization = Organization(name=DEFAULT_ORGANIZATION_NAME)
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization


def ensure_default_admin_and_organization(db: Session) -> tuple[User, Organization]:
    """Создает стартового admin и Default Organization для первого запуска продукта."""
    organization = get_or_create_default_organization(db)

    user = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
    if not user:
        user = User(
            username=DEFAULT_ADMIN_USERNAME,
            email=DEFAULT_ADMIN_EMAIL,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            role_global="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    membership = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization.id, OrganizationMember.user_id == user.id)
        .first()
    )
    if not membership:
        db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
        db.commit()

    nodes_without_organization = db.execute(
        text("SELECT COUNT(*) FROM nodes WHERE organization_id IS NULL")
    ).scalar()

    if nodes_without_organization:
        db.execute(
            text("UPDATE nodes SET organization_id = :organization_id WHERE organization_id IS NULL"),
            {"organization_id": organization.id},
        )
        db.commit()
    return user, organization


def get_or_create_local_node(db: Session) -> Node:
    now = datetime.utcnow()
    hostname = socket.gethostname()
    os_name = f"{platform.system()} {platform.platform()}"
    organization = get_or_create_default_organization(db)

    node = db.query(Node).filter(Node.source_type == "local").first()
    if node:
        changed = False
        if node.organization_id is None:
            node.organization_id = organization.id
            changed = True
        if node.hostname != hostname:
            node.hostname = hostname
            changed = True
        if node.os_name != os_name:
            node.os_name = os_name
            changed = True
        if changed:
            db.commit()
            db.refresh(node)
        return node

    node = Node(
        organization_id=organization.id,
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
    metrics_without_node = db.execute(
        text("SELECT COUNT(*) FROM metrics WHERE node_id IS NULL")
    ).scalar()

    if not metrics_without_node:
        return

    db.execute(text("UPDATE metrics SET node_id = :node_id WHERE node_id IS NULL"), {"node_id": node_id})
    db.commit()
