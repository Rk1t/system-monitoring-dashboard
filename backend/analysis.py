from sqlalchemy import desc
from sqlalchemy.orm import Session

from config import settings
from models import Metric


def _network_value(metric: Metric) -> float:
    return metric.network_recv_per_sec + metric.network_sent_per_sec


def _trend(first_value: float, last_value: float, threshold: float) -> str:
    difference = last_value - first_value
    if difference > threshold:
        return "growing"
    if difference < -threshold:
        return "falling"
    return "stable"


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0


def _build_anomaly(name: str, current: float, average: float, threshold: float, unit: str) -> dict | None:
    difference = current - average
    if abs(difference) <= threshold:
        return None

    direction = "выше" if difference > 0 else "ниже"
    return {
        "metric": name,
        "current": round(current, 2),
        "average": round(average, 2),
        "difference": round(difference, 2),
        "unit": unit,
        "message": f"{name} {direction} среднего значения на {abs(difference):.1f} {unit}.",
    }


def _health_status(score: int) -> str:
    if score >= 75:
        return "хорошее"
    if score >= 45:
        return "умеренная нагрузка"
    return "проблемное состояние"


def _bottleneck(current: Metric, trends: dict, anomalies: list[dict]) -> dict:
    network_current = _network_value(current)
    candidates = []

    if current.cpu_percent > 85:
        candidates.append(("CPU", current.cpu_percent, "CPU выше 85%, возможна высокая вычислительная нагрузка.", "Проверьте топ процессов по CPU."))
    if current.ram_percent > 90:
        candidates.append(("RAM", current.ram_percent, "RAM выше 90%, системе может не хватать оперативной памяти.", "Проверьте процессы по RAM и закройте лишние приложения."))
    if current.disk_percent > 95:
        candidates.append(("Disk", current.disk_percent, "Диск заполнен более чем на 95%.", "Освободите место и проверьте крупные файлы."))

    has_network_anomaly = any(item["metric"] == "Network" for item in anomalies)
    if network_current > settings.network_bottleneck_threshold_bytes_per_sec or trends["network"] == "growing" or has_network_anomaly:
        candidates.append(("Network", min(network_current / settings.network_bottleneck_threshold_bytes_per_sec * 100, 100), "Сетевая активность высокая или заметно растет.", "Проверьте загрузки, облачную синхронизацию и активные сетевые приложения."))

    if not candidates:
        return {
            "metric": "none",
            "title": "Узкое место не выявлено",
            "reason": "Критичных значений по CPU, RAM, Disk и Network сейчас нет.",
            "recommendation": "Продолжайте наблюдение за динамикой метрик.",
        }

    metric, _, reason, recommendation = max(candidates, key=lambda item: item[1])
    return {
        "metric": metric,
        "title": f"Предполагаемое узкое место: {metric}",
        "reason": reason,
        "recommendation": recommendation,
    }


def build_analysis_summary(db: Session, node_id: int, limit: int) -> dict:
    rows = (
        db.query(Metric)
        .filter(Metric.node_id == node_id)
        .order_by(desc(Metric.timestamp))
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))

    if not rows:
        return {
            "trends": {"cpu": "stable", "ram": "stable", "disk": "stable", "network": "stable"},
            "health_score": 100,
            "health_status": "хорошее",
            "anomalies": [],
            "bottleneck": {
                "metric": "none",
                "title": "Узкое место не выявлено",
                "reason": "Истории метрик пока недостаточно.",
                "recommendation": "Подождите несколько циклов сбора данных.",
            },
            "current_refresh_interval": settings.normal_refresh_interval_seconds,
            "explanations": ["Анализ начнется после накопления истории метрик."],
        }

    current = rows[-1]
    cpu_values = [row.cpu_percent for row in rows]
    ram_values = [row.ram_percent for row in rows]
    disk_values = [row.disk_percent for row in rows]
    network_values = [_network_value(row) for row in rows]

    trends = {
        "cpu": _trend(cpu_values[0], cpu_values[-1], settings.trend_threshold_percent),
        "ram": _trend(ram_values[0], ram_values[-1], settings.trend_threshold_percent),
        "disk": _trend(disk_values[0], disk_values[-1], settings.trend_threshold_percent),
        "network": _trend(network_values[0], network_values[-1], settings.network_anomaly_threshold_bytes_per_sec / 2),
    }

    anomalies = []
    for anomaly in [
        _build_anomaly("CPU", current.cpu_percent, _average(cpu_values), settings.cpu_anomaly_threshold_percent, "%"),
        _build_anomaly("RAM", current.ram_percent, _average(ram_values), settings.ram_anomaly_threshold_percent, "%"),
        _build_anomaly("Network", _network_value(current), _average(network_values), settings.network_anomaly_threshold_bytes_per_sec, "Б/с"),
    ]:
        if anomaly:
            anomalies.append(anomaly)

    warnings_count = sum([
        current.cpu_percent > 85,
        current.ram_percent > 90,
        current.disk_percent > 95,
    ])

    score = 100
    score -= current.cpu_percent * 0.25
    score -= current.ram_percent * 0.25
    score -= current.disk_percent * 0.15
    score -= warnings_count * 8
    score -= len(anomalies) * 6
    score = max(0, min(100, round(score)))

    has_alert = warnings_count > 0 or len(anomalies) > 0
    refresh_interval = settings.alert_refresh_interval_seconds if has_alert else settings.normal_refresh_interval_seconds

    return {
        "trends": trends,
        "health_score": score,
        "health_status": _health_status(score),
        "anomalies": anomalies,
        "bottleneck": _bottleneck(current, trends, anomalies),
        "current_refresh_interval": refresh_interval,
        "explanations": [
            "Тренд сравнивает первую и последнюю точку выбранного окна истории.",
            "Аномалии считаются по отклонению текущего значения от среднего.",
            "Health Score снижается при высокой нагрузке, предупреждениях и аномалиях.",
        ],
    }
