import asyncio
import json
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc
from sqlalchemy.orm import Session

from analysis import build_analysis_summary
from auth import (
    create_access_token,
    generate_secret_token,
    get_user_org_role,
    get_current_user,
    primary_writable_organization_id,
    require_org_admin_or_owner,
    require_org_role,
    hash_password,
    token_prefix,
    user_organization_ids,
    verify_password,
)
from config import PROJECT_ROOT, RESOURCE_ROOT, settings
from database import Base, SessionLocal, engine, get_db
from diagnostics import build_diagnostics_summary
from metrics_collector import collect_metrics
from mock_redfish import get_mock_idrac_status, get_mock_ilo_status
from models import AgentToken, EnrollmentKey, HardwareMetric, Metric, Node, OrganizationMember, ProcessSnapshot, ProcessSnapshotItem, User
from node_manager import (
    assign_existing_metrics_to_node,
    ensure_default_admin_and_organization,
    ensure_metrics_node_id_column,
    ensure_node_management_columns,
    ensure_node_organization_column,
    ensure_node_redfish_columns,
    get_or_create_default_organization,
    get_or_create_local_node,
)
from redfish_client import RedfishClient
from schemas import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentDownloadRequest,
    AgentEnrollRequest,
    AgentEnrollResponse,
    AuthUserRead,
    EnrollmentKeyCreateRequest,
    EnrollmentKeyCreateResponse,
    EnrollmentKeyRead,
    HardwareMetricRead,
    LoginRequest,
    LoginResponse,
    MetricRead,
    MetricsSummary,
    NodeRead,
    NodeClearHistoryResponse,
    NodeUpdateRequest,
    OrganizationMemberCreateRequest,
    OrganizationMemberRead,
    OrganizationMemberUpdateRequest,
    ProcessSnapshotIn,
    ProcessSnapshotOut,
    RedfishNodeCreateRequest,
    RedfishNodeCreateResponse,
    TelemetryRequest,
    TransferOwnershipRequest,
    UserOrganizationRead,
)
from system_info import (
    get_cpu_info,
    get_disks_info,
    get_memory_info,
    get_network_info,
    get_processes,
    get_system_info,
)


STATIC_DIR = PROJECT_ROOT / "static"

if not STATIC_DIR.exists():
    STATIC_DIR = RESOURCE_ROOT / "static"

app = FastAPI(title="System Monitoring API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent_security = HTTPBearer(auto_error=False)


async def metrics_background_worker() -> None:
    """Фоновый сбор истории, чтобы графики наполнялись без ручных запросов."""
    while True:
        db = SessionLocal()
        try:
            collect_metrics(db)
        finally:
            db.close()
        await asyncio.sleep(settings.metrics_collect_interval_seconds)


@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_metrics_node_id_column(engine)
    ensure_node_redfish_columns(engine)
    ensure_node_organization_column(engine)
    ensure_node_management_columns(engine)
    db = SessionLocal()
    try:
        ensure_default_admin_and_organization(db)
        local_node = get_or_create_local_node(db)
        assign_existing_metrics_to_node(db, local_node.id)
    finally:
        db.close()
    asyncio.create_task(metrics_background_worker())


def get_node_or_404(db: Session, node_id: int) -> Node:
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Узел не найден")
    return node


def serialize_auth_user(db: Session, user: User) -> AuthUserRead:
    memberships = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user.id)
        .order_by(OrganizationMember.organization_id)
        .all()
    )

    organizations = []
    for membership in memberships:
        organization = UserOrganizationRead(
            id=membership.organization.id,
            name=membership.organization.name,
            role=membership.role,
        )
        organizations.append(organization)

    return AuthUserRead(id=user.id, username=user.username, email=user.email, organizations=organizations)


def get_accessible_node_or_404(db: Session, node_id: int, user: User) -> Node:
    node = get_node_or_404(db, node_id)
    if node.organization_id not in user_organization_ids(db, user):
        raise HTTPException(status_code=404, detail="Узел не найден")
    return node


def primary_user_organization_id(db: Session, user: User) -> int:
    membership = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user.id)
        .order_by(OrganizationMember.organization_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Пользователь не состоит в организации")
    return membership.organization_id


def get_membership_or_404(db: Session, organization_id: int, user_id: int) -> OrganizationMember:
    membership = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Участник не найден")
    return membership


def serialize_organization_member(membership: OrganizationMember) -> OrganizationMemberRead:
    return OrganizationMemberRead(
        user_id=membership.user.id,
        username=membership.user.username,
        email=membership.user.email,
        role=membership.role,
        user_created_at=membership.user.created_at,
        member_created_at=membership.created_at,
    )


def validate_member_role(role: str, allowed_roles: list[str] | None = None) -> str:
    normalized_role = role.strip().lower()
    if allowed_roles is None:
        allowed = ["owner", "admin", "viewer"]
    else:
        allowed = allowed_roles

    if normalized_role not in allowed:
        raise HTTPException(status_code=400, detail="Недопустимая роль")
    return normalized_role


def get_bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Требуется agent token")
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Требуется agent token")
    return credentials.credentials


def get_node_by_agent_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(agent_security),
    db: Session = Depends(get_db),
) -> Node:
    raw_token = get_bearer_token(credentials)
    prefix = token_prefix(raw_token)
    candidates = db.query(AgentToken).filter(AgentToken.prefix == prefix, AgentToken.is_active == True).all()
    for candidate in candidates:
        if verify_password(raw_token, candidate.token_hash):
            candidate.last_used_at = datetime.utcnow()
            db.commit()
            return get_node_or_404(db, candidate.node_id)
    raise HTTPException(status_code=401, detail="Недействительный agent token")


def get_latest_metric(db: Session, node_id: int) -> Metric | None:
    """Возвращает последнюю запись метрик по узлу.

    Эта функция используется в разных endpoint'ах, чтобы не повторять один
    и тот же SQL-запрос несколько раз.
    """
    return (
        db.query(Metric)
        .filter(Metric.node_id == node_id)
        .order_by(desc(Metric.timestamp))
        .first()
    )


def get_latest_metric_or_404(db: Session, node_id: int) -> Metric:
    metric = get_latest_metric(db, node_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Для узла пока нет метрик")
    return metric


def build_metrics_summary(db: Session, node_id: int, limit: int) -> MetricsSummary:
    rows = (
        db.query(Metric)
        .filter(Metric.node_id == node_id)
        .order_by(desc(Metric.timestamp))
        .limit(limit)
        .all()
    )
    if not rows:
        return MetricsSummary(
            records_count=0,
            avg_cpu_percent=0,
            max_cpu_percent=0,
            avg_ram_percent=0,
            max_ram_percent=0,
            avg_disk_percent=0,
            max_disk_percent=0,
        )

    records_count = len(rows)
    cpu_sum = 0
    ram_sum = 0
    disk_sum = 0
    max_cpu = 0
    max_ram = 0
    max_disk = 0

    for row in rows:
        cpu_sum += row.cpu_percent
        ram_sum += row.ram_percent
        disk_sum += row.disk_percent

        if row.cpu_percent > max_cpu:
            max_cpu = row.cpu_percent
        if row.ram_percent > max_ram:
            max_ram = row.ram_percent
        if row.disk_percent > max_disk:
            max_disk = row.disk_percent

    return MetricsSummary(
        records_count=records_count,
        avg_cpu_percent=cpu_sum / records_count,
        max_cpu_percent=max_cpu,
        avg_ram_percent=ram_sum / records_count,
        max_ram_percent=max_ram,
        avg_disk_percent=disk_sum / records_count,
        max_disk_percent=max_disk,
    )


def build_node_analysis_summary(db: Session, node_id: int, limit: int) -> dict:
    analysis = build_analysis_summary(db, node_id, limit)
    analysis["diagnostics"] = build_diagnostics_summary(db, node_id, limit)
    node = get_node_or_404(db, node_id)
    node.health_score = analysis["diagnostics"]["health_score"]
    db.commit()
    return analysis


def calculate_network_speed(previous: Metric | None, telemetry: TelemetryRequest) -> tuple[float, float]:
    """Рассчитывает скорость сети для внешней телеметрии агента."""
    if previous is None:
        return 0.0, 0.0

    elapsed_seconds = (telemetry.timestamp - previous.timestamp).total_seconds()
    if elapsed_seconds <= 0:
        return 0.0, 0.0

    sent_per_sec = (telemetry.bytes_sent - previous.bytes_sent) / elapsed_seconds
    recv_per_sec = (telemetry.bytes_recv - previous.bytes_recv) / elapsed_seconds

    if sent_per_sec < 0:
        sent_per_sec = 0.0
    if recv_per_sec < 0:
        recv_per_sec = 0.0

    return sent_per_sec, recv_per_sec


def hardware_score(health: str) -> int:
    if health == "OK":
        return 95
    if health == "Warning":
        return 70
    if health == "Critical":
        return 35
    return 50


def save_hardware_metric(db: Session, node: Node, status: dict) -> HardwareMetric:
    power_state = "Unknown"
    hardware_health = "Unknown"
    temperature_c = 0.0
    fans_health = "Unknown"
    power_supplies_health = "Unknown"
    summary = "Аппаратное состояние получено"

    if status.get("power_state"):
        power_state = status.get("power_state")
    if status.get("hardware_health"):
        hardware_health = status.get("hardware_health")
    if status.get("temperature_c"):
        temperature_c = float(status.get("temperature_c"))
    if status.get("fans_health"):
        fans_health = status.get("fans_health")
    if status.get("power_supplies_health"):
        power_supplies_health = status.get("power_supplies_health")
    if status.get("summary"):
        summary = status.get("summary")

    metric = HardwareMetric(
        node_id=node.id,
        power_state=power_state,
        hardware_health=hardware_health,
        temperature_c=temperature_c,
        fans_health=fans_health,
        power_supplies_health=power_supplies_health,
        summary=summary,
        raw_json=json.dumps(status, ensure_ascii=False),
    )
    node.last_seen = datetime.utcnow()
    if metric.hardware_health == "OK":
        node.status = "online"
    elif metric.hardware_health == "Warning":
        node.status = "online"
    else:
        node.status = "alert"

    node.health_score = hardware_score(metric.hardware_health)
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


def collect_redfish_status(node: Node) -> dict:
    if node.use_mock:
        if node.source_type == "ilo":
            return get_mock_ilo_status()
        return get_mock_idrac_status()

    client = RedfishClient(
        base_url=f"https://{node.management_ip}",
        username=node.redfish_username if node.redfish_username else "",
        password=node.redfish_password if node.redfish_password else "",
        verify_ssl=False,
    )
    return client.collect_hardware_status()


# -------------------------
# Авторизация пользователей
# -------------------------

@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.username == payload.username, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    password_ok = verify_password(payload.password, user.password_hash)
    if not password_ok:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return LoginResponse(access_token=create_access_token(user), user=serialize_auth_user(db, user))


@app.get("/api/auth/me", response_model=AuthUserRead)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthUserRead:
    return serialize_auth_user(db, current_user)


# -------------------------
# Участники организации
# -------------------------

@app.get("/api/organization/members", response_model=list[OrganizationMemberRead])
def get_organization_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrganizationMemberRead]:
    organization_id = primary_user_organization_id(db, current_user)
    members = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.role, OrganizationMember.created_at)
        .all()
    )

    result = []
    for member in members:
        result.append(serialize_organization_member(member))
    return result


@app.post("/api/organization/members", response_model=OrganizationMemberRead)
def create_organization_member(
    payload: OrganizationMemberCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationMemberRead:
    organization_id = primary_user_organization_id(db, current_user)
    actor_role = require_org_role(db, current_user, organization_id, ["owner", "admin"])
    new_role = validate_member_role(payload.role, ["admin", "viewer"])
    if actor_role == "admin":
        if new_role == "owner":
            raise HTTPException(status_code=403, detail="Admin не может создавать owner")

    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username не может быть пустым")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 6 символов")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            email=f"{username}@example.local",
            password_hash=hash_password(payload.password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    existing_membership = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id)
        .first()
    )
    if existing_membership:
        raise HTTPException(status_code=400, detail="Пользователь уже состоит в организации")

    membership = OrganizationMember(organization_id=organization_id, user_id=user.id, role=new_role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return serialize_organization_member(membership)


@app.patch("/api/organization/members/{user_id}", response_model=OrganizationMemberRead)
def update_organization_member(
    user_id: int,
    payload: OrganizationMemberUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationMemberRead:
    organization_id = primary_user_organization_id(db, current_user)
    actor_role = require_org_role(db, current_user, organization_id, ["owner", "admin"])
    target_membership = get_membership_or_404(db, organization_id, user_id)
    new_role = validate_member_role(payload.role, ["admin", "viewer"])

    if target_membership.role == "owner":
        raise HTTPException(status_code=403, detail="Роль owner изменяется только через передачу владения")
    if actor_role == "admin":
        if target_membership.role == "owner":
            raise HTTPException(status_code=403, detail="Admin не может изменять owner")

    target_membership.role = new_role
    db.commit()
    db.refresh(target_membership)
    return serialize_organization_member(target_membership)


@app.delete("/api/organization/members/{user_id}")
def delete_organization_member(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    organization_id = primary_user_organization_id(db, current_user)
    actor_role = require_org_role(db, current_user, organization_id, ["owner", "admin"])
    target_membership = get_membership_or_404(db, organization_id, user_id)

    if target_membership.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить собственное membership")
    if target_membership.role == "owner":
        raise HTTPException(status_code=403, detail="Owner нельзя удалить из организации")
    if actor_role == "admin":
        if target_membership.role == "owner":
            raise HTTPException(status_code=403, detail="Admin не может удалить owner")

    db.delete(target_membership)
    db.commit()
    return {"status": "removed"}


@app.post("/api/organization/transfer-ownership", response_model=list[OrganizationMemberRead])
def transfer_ownership(
    payload: TransferOwnershipRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrganizationMemberRead]:
    organization_id = primary_user_organization_id(db, current_user)
    current_membership = get_membership_or_404(db, organization_id, current_user.id)
    if current_membership.role != "owner":
        raise HTTPException(status_code=403, detail="Только owner может передать владение")
    if payload.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Новый owner уже является текущим owner")

    target_membership = get_membership_or_404(db, organization_id, payload.user_id)
    current_membership.role = "admin"
    target_membership.role = "owner"
    db.commit()

    members = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.role, OrganizationMember.created_at)
        .all()
    )

    result = []
    for member in members:
        result.append(serialize_organization_member(member))
    return result


# -------------------------
# Ключи подключения агентов
# -------------------------

@app.get("/api/enrollment-keys", response_model=list[EnrollmentKeyRead])
def get_enrollment_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EnrollmentKey]:
    organization_ids = user_organization_ids(db, current_user)
    if not organization_ids:
        return []
    return (
        db.query(EnrollmentKey)
        .filter(EnrollmentKey.organization_id.in_(organization_ids))
        .order_by(desc(EnrollmentKey.created_at))
        .all()
    )
@app.post("/api/enrollment-keys", response_model=EnrollmentKeyCreateResponse)
def create_enrollment_key(
    payload: EnrollmentKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EnrollmentKeyCreateResponse:
    organization_id = primary_writable_organization_id(db, current_user)
    require_org_role(db, current_user, organization_id, ["owner", "admin"])

    raw_key = generate_secret_token("smk_enroll")
    now = datetime.utcnow()
    expires_at = None
    if payload.expires_days:
        expires_at = now + timedelta(days=payload.expires_days)

    key = EnrollmentKey(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        name=payload.name,
        key_hash=hash_password(raw_key),
        prefix=token_prefix(raw_key),
        is_active=True,
        max_uses=payload.max_uses,
        used_count=0,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return EnrollmentKeyCreateResponse(
        id=key.id,
        name=key.name,
        key=raw_key,
        message="Сохраните ключ, повторно он показан не будет",
    )


@app.post("/api/enrollment-keys/{key_id}/revoke")
def revoke_enrollment_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    key = db.query(EnrollmentKey).filter(EnrollmentKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Ключ не найден")

    organization_ids = user_organization_ids(db, current_user)
    if key.organization_id not in organization_ids:
        raise HTTPException(status_code=404, detail="Ключ не найден")

    require_org_role(db, current_user, key.organization_id, ["owner", "admin"])
    key.is_active = False
    db.commit()
    return {"status": "revoked"}


@app.delete("/api/enrollment-keys/{key_id}")
def delete_enrollment_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    key = db.query(EnrollmentKey).filter(EnrollmentKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Ключ не найден")

    organization_ids = user_organization_ids(db, current_user)
    if key.organization_id not in organization_ids:
        raise HTTPException(status_code=404, detail="Ключ не найден")

    require_org_role(db, current_user, key.organization_id, ["owner", "admin"])
    db.delete(key)
    db.commit()
    return {"status": "deleted"}


def validate_download_enrollment_key(
    db: Session,
    current_user: User,
    payload: AgentDownloadRequest,
) -> EnrollmentKey:
    key = db.query(EnrollmentKey).filter(EnrollmentKey.id == payload.enrollment_key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Ключ подключения не найден")

    user_org_ids = user_organization_ids(db, current_user)
    if key.organization_id not in user_org_ids:
        raise HTTPException(status_code=404, detail="Ключ подключения не найден")

    require_org_role(db, current_user, key.organization_id, ["owner", "admin"])

    if not key.is_active:
        raise HTTPException(status_code=400, detail="Ключ подключения отозван")
    if key.expires_at:
        if key.expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Ключ подключения истек")
    if not verify_password(payload.enrollment_key, key.key_hash):
        raise HTTPException(status_code=400, detail="Открытый enrollment key не соответствует выбранной записи")
    return key


DOWNLOAD_PLATFORM_LABELS = {
    "windows_desktop": "Windows Desktop",
    "windows_server": "Windows Server",
    "linux_gui": "Linux GUI",
    "linux_server": "Linux Server",
}

AGENT_DOWNLOAD_DIR = PROJECT_ROOT / "backend" / "downloads" / "agents"

AGENT_BINARY_FILES = {
    "windows_desktop": ("agent-windows.exe", "application/vnd.microsoft.portable-executable"),
    "windows_server": ("agent-windows-server.exe", "application/vnd.microsoft.portable-executable"),
    "linux_gui": ("agent-linux-gui", "application/octet-stream"),
    "linux_server": ("agent-linux-server", "application/octet-stream"),
}


def normalize_download_platform(platform_type: str | None) -> str:
    platform = "windows_desktop"
    if platform_type:
        platform = platform_type
    if platform not in DOWNLOAD_PLATFORM_LABELS:
        raise HTTPException(status_code=400, detail="Неизвестный тип пакета агента")
    return platform


def agent_binary_response(platform_type: str) -> FileResponse:
    platform = normalize_download_platform(platform_type)
    file_name, media_type = AGENT_BINARY_FILES[platform]
    file_path = AGENT_DOWNLOAD_DIR / file_name
    if not file_path.exists():
        build_command = "agent/build_linux.sh"
        if platform.startswith("windows"):
            build_command = "agent/build_windows.ps1"
        raise HTTPException(
            status_code=404,
            detail=(
                f"Файл агента {file_name} ещё не собран. "
                f"Запустите {build_command}."
            ),
        )
    return FileResponse(path=file_path, filename=file_name, media_type=media_type)


@app.post("/api/downloads/agent")
def download_agent_package(
    payload: AgentDownloadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    validate_download_enrollment_key(db, current_user, payload)
    platform_type = "windows_desktop"
    if payload.platform_type:
        platform_type = payload.platform_type
    return agent_binary_response(platform_type)


@app.post("/api/downloads/agent/windows")
def download_windows_agent(
    payload: AgentDownloadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    validate_download_enrollment_key(db, current_user, payload)
    return agent_binary_response("windows_desktop")


@app.post("/api/downloads/agent/linux")
def download_linux_agent(
    payload: AgentDownloadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    validate_download_enrollment_key(db, current_user, payload)
    return agent_binary_response("linux_gui")


# -------------------------
# Старые endpoint'ы локального режима
# Они оставлены для обратной совместимости.
# -------------------------

@app.get("/api/metrics/current", response_model=MetricRead)
def get_current_metrics(db: Session = Depends(get_db)) -> Metric:
    try:
        return collect_metrics(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Не удалось получить системные метрики") from exc


@app.get("/api/metrics/history", response_model=list[MetricRead])
def get_metrics_history(
    limit: int = Query(default=60, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[Metric]:
    try:
        local_node = get_or_create_local_node(db)
        rows = (
            db.query(Metric)
            .filter(Metric.node_id == local_node.id)
            .order_by(desc(Metric.timestamp))
            .limit(limit)
            .all()
        )
        rows.reverse()
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Не удалось загрузить историю метрик") from exc


@app.get("/api/metrics/summary", response_model=MetricsSummary)
def get_metrics_summary(
    limit: int = Query(default=60, ge=1, le=500),
    db: Session = Depends(get_db),
) -> MetricsSummary:
    try:
        local_node = get_or_create_local_node(db)
        return build_metrics_summary(db, local_node.id, limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Не удалось рассчитать сводку метрик") from exc


@app.get("/api/app/config")
def get_app_config() -> dict:
    return {
        "metrics_collect_interval_seconds": settings.metrics_collect_interval_seconds,
        "frontend_refresh_interval_seconds": settings.frontend_refresh_interval_seconds,
        "normal_refresh_interval_seconds": settings.normal_refresh_interval_seconds,
        "alert_refresh_interval_seconds": settings.alert_refresh_interval_seconds,
        "history_limit_records": settings.history_limit_records,
    }


@app.get("/api/analysis/summary")
def get_analysis_summary(
    limit: int = Query(default=60, ge=2, le=500),
    db: Session = Depends(get_db),
) -> dict:
    try:
        local_node = get_or_create_local_node(db)
        return build_node_analysis_summary(db, local_node.id, limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Не удалось выполнить анализ метрик") from exc


# -------------------------
# Подключение агентов
# Агент сначала получает token, потом отправляет telemetry.
# -------------------------

def find_enrollment_key_by_open_key(db: Session, open_key: str) -> EnrollmentKey | None:
    """Ищем enrollment key по открытому ключу.

    В базе хранится только hash, поэтому сначала отбираем записи по prefix,
    а потом проверяем полный ключ через verify_password().
    """
    prefix = token_prefix(open_key)
    candidates = db.query(EnrollmentKey).filter(EnrollmentKey.prefix == prefix, EnrollmentKey.is_active == True).all()
    for candidate in candidates:
        if verify_password(open_key, candidate.key_hash):
            return candidate
    return None


def check_enrollment_key_can_be_used(enrollment_key: EnrollmentKey | None, now: datetime) -> EnrollmentKey:
    if not enrollment_key:
        raise HTTPException(status_code=401, detail="Недействительный enrollment key")
    if enrollment_key.expires_at and enrollment_key.expires_at < now:
        raise HTTPException(status_code=401, detail="Enrollment key истек")
    if enrollment_key.max_uses is not None and enrollment_key.used_count >= enrollment_key.max_uses:
        raise HTTPException(status_code=401, detail="Enrollment key больше нельзя использовать")
    return enrollment_key


def get_or_create_agent_node(db: Session, payload: AgentEnrollRequest, organization_id: int, now: datetime) -> Node:
    """Создаем новый узел агента или обновляем уже существующий."""
    node = (
        db.query(Node)
        .filter(
            Node.organization_id == organization_id,
            Node.hostname == payload.hostname,
            Node.source_type == "agent",
        )
        .first()
    )

    if node:
        node.name = payload.agent_name
        node.os_name = payload.os_name
        node.agent_version = payload.agent_version
        node.status = "online"
        node.last_seen = now
        return node

    node = Node(
        organization_id=organization_id,
        name=payload.agent_name,
        hostname=payload.hostname,
        source_type="agent",
        os_name=payload.os_name,
        agent_version=payload.agent_version,
        status="online",
        health_score=100,
        first_seen=now,
        last_seen=now,
    )
    db.add(node)
    db.flush()
    return node


def create_agent_token_for_node(db: Session, node: Node, now: datetime) -> str:
    """Создаем token для дальнейшей отправки telemetry агентом."""
    raw_agent_token = generate_secret_token("smk_agent")

    agent_token = AgentToken(
        node_id=node.id,
        token_hash=hash_password(raw_agent_token),
        prefix=token_prefix(raw_agent_token),
        is_active=True,
        created_at=now,
    )
    db.add(agent_token)
    return raw_agent_token


def save_agent_telemetry(db: Session, node: Node, payload: TelemetryRequest) -> None:
    """Сохраняем одну запись метрик, которую прислал агент."""
    if node.is_archived:
        raise HTTPException(status_code=409, detail="Узел архивирован, telemetry не сохраняется")

    previous_metric = get_latest_metric(db, node.id)
    sent_per_sec, recv_per_sec = calculate_network_speed(previous_metric, payload)

    metric = Metric(
        node_id=node.id,
        timestamp=payload.timestamp,
        cpu_percent=payload.cpu_percent,
        ram_percent=payload.ram_percent,
        disk_percent=payload.disk_percent,
        bytes_sent=payload.bytes_sent,
        bytes_recv=payload.bytes_recv,
        network_sent_per_sec=sent_per_sec,
        network_recv_per_sec=recv_per_sec,
    )

    node.status = "online"
    node.last_seen = payload.timestamp
    db.add(metric)
    db.commit()


def save_process_snapshot(db: Session, node: Node, payload: ProcessSnapshotIn) -> None:
    """Сохраняем снимок top процессов, если агент прислал его при высокой нагрузке."""
    if node.is_archived:
        raise HTTPException(status_code=409, detail="Узел архивирован, snapshot не сохраняется")

    snapshot = ProcessSnapshot(node_id=node.id, reason=payload.reason)
    db.add(snapshot)
    db.flush()

    for item in payload.items[:20]:
        snapshot_item = ProcessSnapshotItem(
            snapshot_id=snapshot.id,
            pid=item.pid,
            name=item.name,
            cpu_percent=item.cpu_percent,
            memory_percent=item.memory_percent,
        )
        db.add(snapshot_item)

    node.last_seen = datetime.utcnow()
    node.status = "online"
    db.commit()


def get_metrics_history_for_node(db: Session, node_id: int, limit: int) -> list[Metric]:
    """Берем историю метрик узла и возвращаем ее от старых записей к новым."""
    rows = (
        db.query(Metric)
        .filter(Metric.node_id == node_id)
        .order_by(desc(Metric.timestamp))
        .limit(limit)
        .all()
    )
    rows.reverse()
    return rows


def clear_history_for_node(db: Session, node: Node) -> NodeClearHistoryResponse:
    """Удаляем историю выбранного узла, но сам узел оставляем."""
    snapshot_ids = []
    snapshot_rows = db.query(ProcessSnapshot.id).filter(ProcessSnapshot.node_id == node.id).all()
    for row in snapshot_rows:
        snapshot_ids.append(row[0])

    deleted_items = 0
    if snapshot_ids:
        deleted_items = (
            db.query(ProcessSnapshotItem)
            .filter(ProcessSnapshotItem.snapshot_id.in_(snapshot_ids))
            .delete(synchronize_session=False)
        )

    deleted_snapshots = db.query(ProcessSnapshot).filter(ProcessSnapshot.node_id == node.id).delete(synchronize_session=False)
    deleted_metrics = db.query(Metric).filter(Metric.node_id == node.id).delete(synchronize_session=False)
    deleted_hardware = db.query(HardwareMetric).filter(HardwareMetric.node_id == node.id).delete(synchronize_session=False)
    db.commit()

    return NodeClearHistoryResponse(
        deleted_metrics=deleted_metrics,
        deleted_hardware_metrics=deleted_hardware,
        deleted_process_snapshots=deleted_snapshots,
        deleted_process_snapshot_items=deleted_items,
    )


def refresh_redfish_node(db: Session, node: Node) -> dict:
    """Для iLO/iDRAC обновление означает новый Redfish-опрос."""
    if node.is_archived:
        raise HTTPException(status_code=409, detail="Архивный Redfish-узел нельзя опросить")

    status = collect_redfish_status(node)
    metric = save_hardware_metric(db, node, status)
    return {
        "status": "ok",
        "mode": "redfish_poll",
        "node": NodeRead.model_validate(node).model_dump(),
        "hardware": HardwareMetricRead.model_validate(metric).model_dump(),
    }


def refresh_push_node(db: Session, node: Node) -> dict:
    """Для Local System и Agent используется push-модель.

    Это значит, что refresh не заставляет агент работать прямо сейчас,
    а просто возвращает последние известные данные.
    """
    latest_metric = get_latest_metric(db, node.id)
    diagnostics = None
    try:
        diagnostics = build_diagnostics_summary(db, node.id, 60)
    except Exception:
        diagnostics = None

    metric_data = None
    if latest_metric:
        metric_data = MetricRead.model_validate(latest_metric).model_dump()

    return {
        "status": "ok",
        "mode": "push_model",
        "node": NodeRead.model_validate(node).model_dump(),
        "metric": metric_data,
        "diagnostics": diagnostics,
    }


@app.post("/api/agents/register", response_model=AgentRegisterResponse)
def register_agent(
    payload: AgentRegisterRequest,
    db: Session = Depends(get_db),
) -> AgentRegisterResponse:
    if not payload.token:
        raise HTTPException(status_code=400, detail="Не указан token агента")

    now = datetime.utcnow()
    node = (
        db.query(Node)
        .filter(Node.hostname == payload.hostname, Node.source_type == "agent")
        .first()
    )

    if node:
        node.name = payload.name
        node.os_name = payload.os_name
        node.agent_version = payload.agent_version
        if node.organization_id is None:
            node.organization_id = get_or_create_default_organization(db).id
        node.status = "online"
        node.last_seen = now
    else:
        organization = get_or_create_default_organization(db)
        node = Node(
            organization_id=organization.id,
            name=payload.name,
            hostname=payload.hostname,
            source_type="agent",
            os_name=payload.os_name,
            agent_version=payload.agent_version,
            status="online",
            health_score=100,
            first_seen=now,
            last_seen=now,
        )
        db.add(node)

    db.commit()
    db.refresh(node)
    return AgentRegisterResponse(node_id=node.id, status="registered")


@app.post("/api/agents/enroll", response_model=AgentEnrollResponse)
def enroll_agent(
    payload: AgentEnrollRequest,
    db: Session = Depends(get_db),
) -> AgentEnrollResponse:
    now = datetime.utcnow()
    enrollment_key = find_enrollment_key_by_open_key(db, payload.enrollment_key)
    enrollment_key = check_enrollment_key_can_be_used(enrollment_key, now)
    node = get_or_create_agent_node(db, payload, enrollment_key.organization_id, now)
    raw_agent_token = create_agent_token_for_node(db, node, now)

    enrollment_key.used_count += 1
    enrollment_key.last_used_at = now
    db.commit()
    db.refresh(node)
    return AgentEnrollResponse(
        node_id=node.id,
        agent_token=raw_agent_token,
        config={
            "send_interval_seconds": settings.metrics_collect_interval_seconds,
            "process_snapshot_enabled": True,
            "process_snapshot_cooldown_seconds": 30,
        },
    )


@app.post("/api/telemetry")
def receive_telemetry(
    payload: TelemetryRequest,
    agent_node: Node = Depends(get_node_by_agent_token),
    db: Session = Depends(get_db),
) -> dict:
    node = get_node_or_404(db, agent_node.id)
    save_agent_telemetry(db, node, payload)
    return {"status": "ok"}


@app.post("/api/process-snapshots")
def create_process_snapshot(
    payload: ProcessSnapshotIn,
    agent_node: Node = Depends(get_node_by_agent_token),
    db: Session = Depends(get_db),
) -> dict:
    node = get_node_or_404(db, agent_node.id)
    save_process_snapshot(db, node, payload)
    return {"status": "ok"}


# -------------------------
# Redfish / iLO / iDRAC
# Сейчас поддерживается мониторинг состояния оборудования.
# -------------------------

@app.post("/api/nodes/redfish", response_model=RedfishNodeCreateResponse)
def create_redfish_node(
    payload: RedfishNodeCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedfishNodeCreateResponse:
    valid_source_type = False
    if payload.source_type == "ilo":
        valid_source_type = True
    if payload.source_type == "idrac":
        valid_source_type = True

    if not valid_source_type:
        raise HTTPException(status_code=400, detail="source_type должен быть ilo или idrac")

    now = datetime.utcnow()
    organization_id = primary_writable_organization_id(db, current_user)
    node = (
        db.query(Node)
        .filter(
            Node.organization_id == organization_id,
            Node.source_type == payload.source_type,
            Node.management_ip == payload.management_ip,
        )
        .first()
    )
    status_text = "updated"
    if node:
        node.name = payload.name
        node.hostname = payload.management_ip
        node.redfish_username = payload.username
        node.redfish_password = payload.password
        node.use_mock = payload.use_mock
        node.status = "online"
        node.last_seen = now
    else:
        status_text = "created"
        node = Node(
            organization_id=organization_id,
            name=payload.name,
            hostname=payload.management_ip,
            source_type=payload.source_type,
            os_name="Redfish hardware controller",
            agent_version=None,
            management_ip=payload.management_ip,
            redfish_username=payload.username,
            redfish_password=payload.password,
            use_mock=payload.use_mock,
            status="online",
            health_score=100,
            first_seen=now,
            last_seen=now,
        )
        db.add(node)
    db.commit()
    db.refresh(node)

    status = collect_redfish_status(node)
    save_hardware_metric(db, node, status)
    return RedfishNodeCreateResponse(node_id=node.id, status=status_text, source_type=node.source_type)


@app.post("/api/nodes/{node_id}/poll-redfish")
def poll_redfish_node(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    node = get_accessible_node_or_404(db, node_id, current_user)
    require_org_role(db, current_user, node.organization_id, ["owner", "admin"])

    redfish_node = False
    if node.source_type == "ilo":
        redfish_node = True
    if node.source_type == "idrac":
        redfish_node = True

    if not redfish_node:
        raise HTTPException(status_code=400, detail="Узел не является Redfish-источником")

    status = collect_redfish_status(node)
    metric = save_hardware_metric(db, node, status)
    return {
        "node_id": node.id,
        "status": "ok",
        "hardware": HardwareMetricRead.model_validate(metric).model_dump(),
    }


# -------------------------
# Узлы мониторинга
# Здесь список систем, редактирование, архив и очистка истории.
# -------------------------

@app.get("/api/nodes", response_model=list[NodeRead])
def get_nodes(
    include_archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Node]:
    local_node = get_or_create_local_node(db)
    build_node_analysis_summary(db, local_node.id, 60)
    organization_ids = user_organization_ids(db, current_user)
    if not organization_ids:
        return []
    query = db.query(Node).filter(Node.organization_id.in_(organization_ids))
    if include_archived:
        writable_ids = []
        for organization_id in organization_ids:
            role = get_user_org_role(db, current_user, organization_id)
            if role == "owner":
                writable_ids.append(organization_id)
            elif role == "admin":
                writable_ids.append(organization_id)

        if not writable_ids:
            query = query.filter(Node.is_archived == False)
        else:
            query = query.filter(Node.organization_id.in_(writable_ids))
    else:
        query = query.filter(Node.is_archived == False)
    return query.order_by(Node.id).all()


@app.get("/api/nodes/{node_id}", response_model=NodeRead)
def get_node(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Node:
    return get_accessible_node_or_404(db, node_id, current_user)


@app.patch("/api/nodes/{node_id}", response_model=NodeRead)
def update_node(
    node_id: int,
    payload: NodeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Node:
    node = get_accessible_node_or_404(db, node_id, current_user)
    require_org_admin_or_owner(db, current_user, node.organization_id)
    if payload.name is not None:
        new_name = payload.name.strip()
        if new_name:
            node.name = new_name
    if payload.description is not None:
        new_description = payload.description.strip()
        if new_description:
            node.description = new_description
        else:
            node.description = None
    db.commit()
    db.refresh(node)
    return node


@app.post("/api/nodes/{node_id}/archive", response_model=NodeRead)
def archive_node(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Node:
    node = get_accessible_node_or_404(db, node_id, current_user)
    require_org_admin_or_owner(db, current_user, node.organization_id)
    node.is_archived = True
    node.archived_at = datetime.utcnow()
    node.status = "archived"
    db.commit()
    db.refresh(node)
    return node


@app.post("/api/nodes/{node_id}/restore", response_model=NodeRead)
def restore_node(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Node:
    node = get_accessible_node_or_404(db, node_id, current_user)
    require_org_admin_or_owner(db, current_user, node.organization_id)
    node.is_archived = False
    node.archived_at = None

    seconds_after_last_seen = (datetime.utcnow() - node.last_seen).total_seconds()
    if seconds_after_last_seen < 120:
        node.status = "online"
    else:
        node.status = "offline"

    db.commit()
    db.refresh(node)
    return node


@app.delete("/api/nodes/{node_id}", response_model=NodeRead)
def delete_node_alias(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Node:
    return archive_node(node_id=node_id, current_user=current_user, db=db)


@app.post("/api/nodes/{node_id}/clear-history", response_model=NodeClearHistoryResponse)
def clear_node_history(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NodeClearHistoryResponse:
    node = get_accessible_node_or_404(db, node_id, current_user)
    require_org_admin_or_owner(db, current_user, node.organization_id)
    return clear_history_for_node(db, node)


@app.post("/api/nodes/{node_id}/refresh")
def refresh_node(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    node = get_accessible_node_or_404(db, node_id, current_user)
    require_org_admin_or_owner(db, current_user, node.organization_id)
    if node.source_type == "ilo":
        return refresh_redfish_node(db, node)
    if node.source_type == "idrac":
        return refresh_redfish_node(db, node)
    return refresh_push_node(db, node)


@app.get("/api/nodes/{node_id}/metrics/current", response_model=MetricRead)
def get_node_current_metrics(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Metric:
    node = get_accessible_node_or_404(db, node_id, current_user)
    if node.source_type == "local":
        latest_metric = get_latest_metric(db, node.id)
        if latest_metric:
            return latest_metric
        return collect_metrics(db)
    return get_latest_metric_or_404(db, node_id)


@app.get("/api/nodes/{node_id}/metrics/history", response_model=list[MetricRead])
def get_node_metrics_history(
    node_id: int,
    limit: int = Query(default=60, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Metric]:
    get_accessible_node_or_404(db, node_id, current_user)
    return get_metrics_history_for_node(db, node_id, limit)


@app.get("/api/nodes/{node_id}/metrics/summary", response_model=MetricsSummary)
def get_node_metrics_summary(
    node_id: int,
    limit: int = Query(default=60, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MetricsSummary:
    get_accessible_node_or_404(db, node_id, current_user)
    return build_metrics_summary(db, node_id, limit)


@app.get("/api/nodes/{node_id}/analysis/summary")
def get_node_analysis_summary(
    node_id: int,
    limit: int = Query(default=60, ge=2, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_accessible_node_or_404(db, node_id, current_user)
    return build_node_analysis_summary(db, node_id, limit)


@app.get("/api/nodes/{node_id}/diagnostics")
def get_node_diagnostics(
    node_id: int,
    limit: int = Query(default=60, ge=5, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_accessible_node_or_404(db, node_id, current_user)
    diagnostics = build_diagnostics_summary(db, node_id, limit)
    node = get_accessible_node_or_404(db, node_id, current_user)
    node.health_score = diagnostics["health_score"]
    db.commit()
    return diagnostics


@app.get("/api/nodes/{node_id}/hardware/latest", response_model=HardwareMetricRead)
def get_latest_hardware_metric(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HardwareMetric:
    get_accessible_node_or_404(db, node_id, current_user)
    metric = (
        db.query(HardwareMetric)
        .filter(HardwareMetric.node_id == node_id)
        .order_by(desc(HardwareMetric.created_at))
        .first()
    )
    if not metric:
        raise HTTPException(status_code=404, detail="Для узла пока нет аппаратных метрик")
    return metric


@app.get("/api/nodes/{node_id}/hardware/history", response_model=list[HardwareMetricRead])
def get_hardware_history(
    node_id: int,
    limit: int = Query(default=20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HardwareMetric]:
    get_accessible_node_or_404(db, node_id, current_user)
    rows = (
        db.query(HardwareMetric)
        .filter(HardwareMetric.node_id == node_id)
        .order_by(desc(HardwareMetric.created_at))
        .limit(limit)
        .all()
    )
    rows.reverse()
    return rows


@app.get("/api/nodes/{node_id}/process-snapshots/latest", response_model=ProcessSnapshotOut)
def get_latest_process_snapshot(
    node_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProcessSnapshot:
    get_accessible_node_or_404(db, node_id, current_user)
    snapshot = (
        db.query(ProcessSnapshot)
        .filter(ProcessSnapshot.node_id == node_id)
        .order_by(desc(ProcessSnapshot.created_at))
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Для узла пока нет снимков процессов")
    return snapshot


@app.get("/api/nodes/{node_id}/process-snapshots", response_model=list[ProcessSnapshotOut])
def get_process_snapshots(
    node_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProcessSnapshot]:
    get_accessible_node_or_404(db, node_id, current_user)
    rows = (
        db.query(ProcessSnapshot)
        .filter(ProcessSnapshot.node_id == node_id)
        .order_by(desc(ProcessSnapshot.created_at))
        .limit(limit)
        .all()
    )
    rows.reverse()
    return rows


# -------------------------
# Подробные live-метрики локального компьютера
# Эти endpoint'ы нужны для страницы "Подробные метрики".
# -------------------------

@app.get("/api/system/info")
def system_info() -> dict:
    return get_system_info()


@app.get("/api/system/cpu")
def system_cpu() -> dict:
    return get_cpu_info()


@app.get("/api/system/memory")
def system_memory() -> dict:
    return get_memory_info()


@app.get("/api/system/disks")
def system_disks() -> list[dict]:
    return get_disks_info()


@app.get("/api/system/network")
def system_network() -> list[dict]:
    return get_network_info()


@app.get("/api/system/processes")
def system_processes(
    limit: int = Query(default=10, ge=1, le=50),
    sort: str = Query(default="cpu", pattern="^(cpu|ram)$"),
) -> list[dict]:
    return get_processes(limit=limit, sort=sort)


# -------------------------
# Frontend
# FastAPI отдает собранный Vue-интерфейс из папки static.
# -------------------------

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str) -> FileResponse:
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Frontend не собран. Запустите Vue dev server или соберите static.")
