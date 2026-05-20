import asyncio

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc
from sqlalchemy.orm import Session

from analysis import build_analysis_summary
from config import PROJECT_ROOT, RESOURCE_ROOT, settings
from database import Base, SessionLocal, engine, get_db
from metrics_collector import collect_metrics
from models import Metric
from schemas import MetricRead, MetricsSummary
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
    asyncio.create_task(metrics_background_worker())


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
        rows = db.query(Metric).order_by(desc(Metric.timestamp)).limit(limit).all()
        return list(reversed(rows))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Не удалось загрузить историю метрик") from exc


@app.get("/api/metrics/summary", response_model=MetricsSummary)
def get_metrics_summary(
    limit: int = Query(default=60, ge=1, le=500),
    db: Session = Depends(get_db),
) -> MetricsSummary:
    try:
        rows = db.query(Metric).order_by(desc(Metric.timestamp)).limit(limit).all()
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
        return MetricsSummary(
            records_count=records_count,
            avg_cpu_percent=sum(row.cpu_percent for row in rows) / records_count,
            max_cpu_percent=max(row.cpu_percent for row in rows),
            avg_ram_percent=sum(row.ram_percent for row in rows) / records_count,
            max_ram_percent=max(row.ram_percent for row in rows),
            avg_disk_percent=sum(row.disk_percent for row in rows) / records_count,
            max_disk_percent=max(row.disk_percent for row in rows),
        )
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
        return build_analysis_summary(db, limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Не удалось выполнить анализ метрик") from exc


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


if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str) -> FileResponse:
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Frontend не собран. Запустите Vue dev server или соберите static.")
