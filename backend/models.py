from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import mapped_column, relationship

from database import Base


class Node(Base):
    __tablename__ = "nodes"

    id = mapped_column(Integer, primary_key=True, index=True)
    organization_id = mapped_column(ForeignKey("organizations.id"), index=True, nullable=True)

    name = mapped_column(String(120), index=True)
    hostname = mapped_column(String(255), index=True)
    source_type = mapped_column(String(40), index=True)
    os_name = mapped_column(String(255))
    agent_version = mapped_column(String(80), nullable=True)

    management_ip = mapped_column(String(120), nullable=True)
    redfish_username = mapped_column(String(120), nullable=True)
    redfish_password = mapped_column(String(255), nullable=True)
    use_mock = mapped_column(Boolean, default=False)

    is_archived = mapped_column(Boolean, default=False, index=True)
    archived_at = mapped_column(DateTime, nullable=True)
    description = mapped_column(Text, nullable=True)

    status = mapped_column(String(40), default="online", index=True)
    health_score = mapped_column(Integer, default=100)
    first_seen = mapped_column(DateTime, default=datetime.utcnow)
    last_seen = mapped_column(DateTime, default=datetime.utcnow, index=True)

    organization = relationship("Organization", back_populates="nodes")
    metrics = relationship("Metric", back_populates="node")
    hardware_metrics = relationship("HardwareMetric", back_populates="node")
    process_snapshots = relationship("ProcessSnapshot", back_populates="node")


class User(Base):
    __tablename__ = "users"

    id = mapped_column(Integer, primary_key=True, index=True)
    username = mapped_column(String(80), unique=True, index=True)
    email = mapped_column(String(255), unique=True, index=True)
    password_hash = mapped_column(String(255))
    role_global = mapped_column(String(40), nullable=True)
    is_active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    last_login = mapped_column(DateTime, nullable=True)

    memberships = relationship("OrganizationMember", back_populates="user")


class Organization(Base):
    __tablename__ = "organizations"

    id = mapped_column(Integer, primary_key=True, index=True)
    name = mapped_column(String(160), unique=True, index=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    members = relationship("OrganizationMember", back_populates="organization")
    nodes = relationship("Node", back_populates="organization")
    enrollment_keys = relationship("EnrollmentKey", back_populates="organization")


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = mapped_column(Integer, primary_key=True, index=True)
    organization_id = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id = mapped_column(ForeignKey("users.id"), index=True)
    role = mapped_column(String(40), index=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")


class EnrollmentKey(Base):
    __tablename__ = "enrollment_keys"

    id = mapped_column(Integer, primary_key=True, index=True)
    organization_id = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by_user_id = mapped_column(ForeignKey("users.id"), index=True)

    name = mapped_column(String(160))
    key_hash = mapped_column(String(255))
    prefix = mapped_column(String(40), index=True)

    is_active = mapped_column(Boolean, default=True)
    max_uses = mapped_column(Integer, nullable=True)
    used_count = mapped_column(Integer, default=0)

    expires_at = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at = mapped_column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="enrollment_keys")
    created_by_user = relationship("User")


class AgentToken(Base):
    __tablename__ = "agent_tokens"

    id = mapped_column(Integer, primary_key=True, index=True)
    node_id = mapped_column(ForeignKey("nodes.id"), index=True)

    token_hash = mapped_column(String(255))
    prefix = mapped_column(String(40), index=True)
    is_active = mapped_column(Boolean, default=True)

    created_at = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at = mapped_column(DateTime, nullable=True)

    node = relationship("Node")


class Metric(Base):
    __tablename__ = "metrics"

    id = mapped_column(Integer, primary_key=True, index=True)
    node_id = mapped_column(ForeignKey("nodes.id"), index=True, nullable=True)
    timestamp = mapped_column(DateTime, default=datetime.utcnow, index=True)

    cpu_percent = mapped_column(Float)
    ram_percent = mapped_column(Float)
    disk_percent = mapped_column(Float)
    bytes_sent = mapped_column(Integer)
    bytes_recv = mapped_column(Integer)
    network_sent_per_sec = mapped_column(Float)
    network_recv_per_sec = mapped_column(Float)

    node = relationship("Node", back_populates="metrics")


class HardwareMetric(Base):
    __tablename__ = "hardware_metrics"

    id = mapped_column(Integer, primary_key=True, index=True)
    node_id = mapped_column(ForeignKey("nodes.id"), index=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow, index=True)

    power_state = mapped_column(String(80))
    hardware_health = mapped_column(String(80))
    temperature_c = mapped_column(Float)
    fans_health = mapped_column(String(80))
    power_supplies_health = mapped_column(String(80))
    summary = mapped_column(Text)
    raw_json = mapped_column(Text, nullable=True)

    node = relationship("Node", back_populates="hardware_metrics")


class ProcessSnapshot(Base):
    __tablename__ = "process_snapshots"

    id = mapped_column(Integer, primary_key=True, index=True)
    node_id = mapped_column(ForeignKey("nodes.id"), index=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow, index=True)
    reason = mapped_column(String(80))

    node = relationship("Node", back_populates="process_snapshots")
    items = relationship(
        "ProcessSnapshotItem",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class ProcessSnapshotItem(Base):
    __tablename__ = "process_snapshot_items"

    id = mapped_column(Integer, primary_key=True, index=True)
    snapshot_id = mapped_column(ForeignKey("process_snapshots.id"), index=True)
    pid = mapped_column(Integer)
    name = mapped_column(String(255))
    cpu_percent = mapped_column(Float)
    memory_percent = mapped_column(Float)

    snapshot = relationship("ProcessSnapshot", back_populates="items")
