from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int | None = None
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


class NodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int | None = None
    name: str
    hostname: str
    source_type: str
    os_name: str
    agent_version: str | None = None
    management_ip: str | None = None
    use_mock: bool = False
    is_archived: bool = False
    archived_at: datetime | None = None
    description: str | None = None
    status: str
    health_score: int
    first_seen: datetime
    last_seen: datetime


class AgentRegisterRequest(BaseModel):
    name: str
    hostname: str
    os_name: str
    agent_version: str
    token: str


class AgentRegisterResponse(BaseModel):
    node_id: int
    status: str


class TelemetryRequest(BaseModel):
    node_id: int | None = None
    timestamp: datetime
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    bytes_sent: int
    bytes_recv: int


class RedfishNodeCreateRequest(BaseModel):
    name: str
    source_type: str
    management_ip: str
    username: str
    password: str
    use_mock: bool = True


class RedfishNodeCreateResponse(BaseModel):
    node_id: int
    status: str
    source_type: str


class NodeUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class NodeClearHistoryResponse(BaseModel):
    deleted_metrics: int
    deleted_hardware_metrics: int
    deleted_process_snapshots: int
    deleted_process_snapshot_items: int


class HardwareMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    created_at: datetime
    power_state: str
    hardware_health: str
    temperature_c: float
    fans_health: str
    power_supplies_health: str
    summary: str
    raw_json: str | None = None


class ProcessSnapshotItemIn(BaseModel):
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float


class ProcessSnapshotIn(BaseModel):
    node_id: int | None = None
    reason: str
    items: list[ProcessSnapshotItemIn]


class ProcessSnapshotItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: int
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float


class ProcessSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    created_at: datetime
    reason: str
    items: list[ProcessSnapshotItemOut]


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOrganizationRead(BaseModel):
    id: int
    name: str
    role: str


class AuthUserRead(BaseModel):
    id: int
    username: str
    email: str
    organizations: list[UserOrganizationRead]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserRead


class OrganizationMemberRead(BaseModel):
    user_id: int
    username: str
    email: str
    role: str
    user_created_at: datetime
    member_created_at: datetime


class OrganizationMemberCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class OrganizationMemberUpdateRequest(BaseModel):
    role: str


class TransferOwnershipRequest(BaseModel):
    user_id: int


class EnrollmentKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    is_active: bool
    max_uses: int | None = None
    used_count: int
    expires_at: datetime | None = None
    created_at: datetime
    last_used_at: datetime | None = None


class EnrollmentKeyCreateRequest(BaseModel):
    name: str
    max_uses: int | None = 10
    expires_days: int | None = 30


class EnrollmentKeyCreateResponse(BaseModel):
    id: int
    name: str
    key: str
    message: str


class AgentDownloadRequest(BaseModel):
    platform_type: str | None = None
    enrollment_key_id: int
    enrollment_key: str


class AgentEnrollRequest(BaseModel):
    enrollment_key: str
    agent_name: str
    hostname: str
    os_name: str
    agent_version: str


class AgentEnrollResponse(BaseModel):
    node_id: int
    agent_token: str
    config: dict
