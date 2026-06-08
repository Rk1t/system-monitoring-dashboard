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
    if not values:
        return 0

    total = 0
    for value in values:
        total += value

    return total / len(values)


def _format_bytes_per_second(value: float) -> str:
    size = abs(value)
    units = ["Б/с", "КБ/с", "МБ/с", "ГБ/с"]
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size = size / 1024
        unit_index += 1

    if size >= 10:
        return f"{size:.0f} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def _build_anomaly(name: str, current: float, average: float, threshold: float, unit: str) -> dict | None:
    difference = current - average
    if abs(difference) <= threshold:
        return None

    # Для сети важен резкий рост трафика. Низкий трафик обычно не является проблемой.
    if name == "Network" and difference <= 0:
        return None

    direction = "ниже"
    if difference > 0:
        direction = "выше"
    difference_text = f"{abs(difference):.1f} {unit}"
    if unit == "Б/с":
        difference_text = _format_bytes_per_second(difference)

    return {
        "metric": name,
        "current": round(current, 2),
        "average": round(average, 2),
        "difference": round(difference, 2),
        "unit": unit,
        "message": f"{name} {direction} среднего значения на {difference_text}.",
    }


def _health_status(score: int) -> str:
    if score >= 75:
        return "хорошее"
    if score >= 45:
        return "умеренная нагрузка"
    return "проблемное состояние"


def _has_network_anomaly(anomalies: list[dict]) -> bool:
    for anomaly in anomalies:
        if anomaly["metric"] == "Network":
            return True
    return False


def _select_bottleneck_candidate(candidates: list[tuple]) -> tuple:
    selected = candidates[0]

    for candidate in candidates:
        if candidate[1] > selected[1]:
            selected = candidate

    return selected


def _bottleneck(current: Metric, trends: dict, anomalies: list[dict]) -> dict:
    network_current = _network_value(current)
    candidates = []

    if current.cpu_percent > 85:
        candidates.append((
            "CPU",
            current.cpu_percent,
            "CPU выше 85%, возможна высокая вычислительная нагрузка.",
            "Проверьте топ процессов по CPU.",
        ))

    if current.ram_percent > 90:
        candidates.append((
            "RAM",
            current.ram_percent,
            "RAM выше 90%, системе может не хватать оперативной памяти.",
            "Проверьте процессы по RAM и закройте лишние приложения.",
        ))

    if current.disk_percent > 95:
        candidates.append((
            "Disk",
            current.disk_percent,
            "Диск заполнен более чем на 95%.",
            "Освободите место и проверьте крупные файлы.",
        ))

    network_score = network_current / settings.network_bottleneck_threshold_bytes_per_sec * 100
    if network_score > 100:
        network_score = 100

    network_is_high = network_current > settings.network_bottleneck_threshold_bytes_per_sec
    network_is_growing = trends["network"] == "growing"

    if network_is_high or network_is_growing or _has_network_anomaly(anomalies):
        candidates.append((
            "Network",
            network_score,
            "Сетевая активность высокая или заметно растет.",
            "Проверьте загрузки, облачную синхронизацию и активные сетевые приложения.",
        ))

    if not candidates:
        return {
            "metric": "none",
            "title": "Узкое место не выявлено",
            "reason": "Критичных значений по CPU, RAM, Disk и Network сейчас нет.",
            "recommendation": "Продолжайте наблюдение за динамикой метрик.",
        }

    metric, _, reason, recommendation = _select_bottleneck_candidate(candidates)
    return {
        "metric": metric,
        "title": f"Предполагаемое узкое место: {metric}",
        "reason": reason,
        "recommendation": recommendation,
    }


def _count_warnings(current: Metric) -> int:
    count = 0
    if current.cpu_percent > 85:
        count += 1
    if current.ram_percent > 90:
        count += 1
    if current.disk_percent > 95:
        count += 1
    return count


def _calculate_health_score(current: Metric, warnings_count: int, anomalies_count: int) -> int:
    score = 100
    score -= current.cpu_percent * 0.25
    score -= current.ram_percent * 0.25
    score -= current.disk_percent * 0.15
    score -= warnings_count * 8
    score -= anomalies_count * 6

    if score < 0:
        return 0
    if score > 100:
        return 100
    return round(score)


def build_analysis_summary(db: Session, node_id: int, limit: int) -> dict:
    rows = (
        db.query(Metric)
        .filter(Metric.node_id == node_id)
        .order_by(desc(Metric.timestamp))
        .limit(limit)
        .all()
    )
    rows.reverse()

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
    cpu_values = []
    ram_values = []
    disk_values = []
    network_values = []

    for row in rows:
        cpu_values.append(row.cpu_percent)
        ram_values.append(row.ram_percent)
        disk_values.append(row.disk_percent)
        network_values.append(_network_value(row))

    trends = {
        "cpu": _trend(cpu_values[0], cpu_values[-1], settings.trend_threshold_percent),
        "ram": _trend(ram_values[0], ram_values[-1], settings.trend_threshold_percent),
        "disk": _trend(disk_values[0], disk_values[-1], settings.trend_threshold_percent),
        "network": _trend(network_values[0], network_values[-1], settings.network_anomaly_threshold_bytes_per_sec / 2),
    }

    cpu_anomaly = _build_anomaly(
        "CPU",
        current.cpu_percent,
        _average(cpu_values),
        settings.cpu_anomaly_threshold_percent,
        "%",
    )
    ram_anomaly = _build_anomaly(
        "RAM",
        current.ram_percent,
        _average(ram_values),
        settings.ram_anomaly_threshold_percent,
        "%",
    )
    network_anomaly = _build_anomaly(
        "Network",
        _network_value(current),
        _average(network_values),
        settings.network_anomaly_threshold_bytes_per_sec,
        "Б/с",
    )

    anomalies = []
    if cpu_anomaly:
        anomalies.append(cpu_anomaly)
    if ram_anomaly:
        anomalies.append(ram_anomaly)
    if network_anomaly:
        anomalies.append(network_anomaly)

    warnings_count = _count_warnings(current)
    score = _calculate_health_score(current, warnings_count, len(anomalies))

    has_alert = warnings_count > 0 or len(anomalies) > 0
    refresh_interval = settings.normal_refresh_interval_seconds
    if has_alert:
        refresh_interval = settings.alert_refresh_interval_seconds

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
