from sqlalchemy import desc
from sqlalchemy.orm import Session

from config import settings
from models import HardwareMetric, Metric, Node, ProcessSnapshot


SEVERITY_RANK = {"normal": 0, "warning": 1, "critical": 2}
WARNING_LIMITS = {"cpu": 70, "ram": 75, "disk": 85}
CRITICAL_LIMITS = {"cpu": 85, "ram": 90, "disk": 95}
METRIC_LABELS = {"cpu": "CPU", "ram": "RAM", "disk": "Disk", "network": "Network"}


def network_value(metric: Metric) -> float:
    return metric.network_recv_per_sec + metric.network_sent_per_sec


def average(values: list[float]) -> float:
    if not values:
        return 0

    total = 0
    for value in values:
        total += value

    return total / len(values)


def calculate_severity(metric_name: str, value: float, values: list[float] | None = None) -> str:
    if metric_name == "cpu" or metric_name == "ram" or metric_name == "disk":
        if value > CRITICAL_LIMITS[metric_name]:
            return "critical"
        if value > WARNING_LIMITS[metric_name]:
            return "warning"
        return "normal"

    if metric_name == "network":
        if values:
            if len(values) >= 5:
                base = average(values)
                if base > 0:
                    if value > base * 1.8:
                        if value - base > settings.network_anomaly_threshold_bytes_per_sec:
                            return "warning"
    return "normal"


def calculate_trend(values: list[float]) -> str:
    if len(values) < 5:
        return "stable"

    window_size = round(len(values) * 0.3)
    if window_size < 1:
        window_size = 1

    first_values = []
    last_values = []

    for index in range(window_size):
        first_values.append(values[index])

    start_index = len(values) - window_size
    for index in range(start_index, len(values)):
        last_values.append(values[index])

    first_average = average(first_values)
    last_average = average(last_values)
    difference = last_average - first_average

    if difference > 5:
        return "rising"
    if difference < -5:
        return "falling"
    return "stable"


def detect_anomaly(values: list[float], current_value: float, threshold: float = 20) -> bool:
    if len(values) < 5:
        return False

    avg_value = average(values)
    difference = current_value - avg_value
    if difference < 0:
        difference = difference * -1

    if difference > threshold:
        return True
    return False


def calculate_persistence(values: list[float], metric_name: str) -> str:
    if metric_name != "cpu" and metric_name != "ram" and metric_name != "disk":
        return "normal"
    if len(values) < 3:
        return "normal"

    warning_limit = WARNING_LIMITS[metric_name]
    last_values = []
    start_index = len(values) - 5
    if start_index < 0:
        start_index = 0
    for index in range(start_index, len(values)):
        last_values.append(values[index])

    warning_flags = []
    for value in last_values:
        warning_flags.append(value > warning_limit)

    last_five_are_warning = True
    for flag in warning_flags:
        if not flag:
            last_five_are_warning = False

    last_two_have_warning = False
    start_index = len(warning_flags) - 2
    if start_index < 0:
        start_index = 0
    for index in range(start_index, len(warning_flags)):
        flag = warning_flags[index]
        if flag:
            last_two_have_warning = True

    all_values_are_warning = True
    for flag in warning_flags:
        if not flag:
            all_values_are_warning = False

    if len(warning_flags) >= 5 and last_five_are_warning:
        return "persistent"
    if last_two_have_warning and not all_values_are_warning:
        return "short_spike"
    return "normal"


def calculate_health_score(current_metrics: dict, metrics_analysis: dict) -> int:
    network_score = current_metrics["network"] / settings.network_bottleneck_threshold_bytes_per_sec * 100
    if network_score > 100:
        network_score = 100

    cpu_part = current_metrics["cpu"] * 0.35
    ram_part = current_metrics["ram"] * 0.35
    disk_part = current_metrics["disk"] * 0.2
    network_part = network_score * 0.1
    weighted_load = cpu_part + ram_part + disk_part + network_part

    score = 100 - weighted_load

    for metric in metrics_analysis.values():
        if metric["anomaly"]:
            score -= 8
        if metric["persistence"] == "persistent":
            score -= 5
        if metric["persistence"] == "persistent" and metric["severity"] == "critical":
            score -= 15

    score = round(score)
    if score < 0:
        return 0
    if score > 100:
        return 100
    return score


def detect_bottleneck(metrics_analysis: dict) -> dict:
    active = []

    for name, data in metrics_analysis.items():
        if data["severity"] == "warning" or data["severity"] == "critical":
            active.append((name, data))

    if len(active) >= 2:
        names = []
        worst_severity = "warning"

        for name, data in active:
            names.append(METRIC_LABELS[name])
            if SEVERITY_RANK[data["severity"]] > SEVERITY_RANK[worst_severity]:
                worst_severity = data["severity"]

        names_text = ""
        for index, name in enumerate(names):
            if index > 0:
                names_text += ", "
            names_text += name

        return {
            "component": "combined",
            "severity": worst_severity,
            "reason": f"Одновременно повышены несколько метрик: {names_text}.",
        }

    if len(active) == 1:
        name, data = active[0]
        label = METRIC_LABELS[name]
        reason = f"{label} превышает {data['severity']}-порог"
        if data["trend"] == "rising":
            reason += " и имеет растущий тренд"
        return {"component": name, "severity": data["severity"], "reason": reason}

    return {
        "component": "none",
        "severity": "normal",
        "reason": "Все основные метрики находятся в нормальном диапазоне.",
    }


def detect_scenario(metrics_analysis: dict) -> str:
    high = []
    for name in metrics_analysis:
        data = metrics_analysis[name]
        if data["severity"] == "warning":
            high.append(name)
        if data["severity"] == "critical":
            high.append(name)

    if len(high) >= 2:
        return "mixed_overload"

    if metrics_analysis["cpu"]["severity"] != "normal":
        if metrics_analysis["ram"]["severity"] == "normal":
            return "cpu_bound"

    if metrics_analysis["ram"]["severity"] != "normal":
        return "memory_pressure"
    if metrics_analysis["ram"]["trend"] == "rising":
        return "memory_pressure"

    if metrics_analysis["disk"]["severity"] != "normal":
        return "disk_pressure"

    if metrics_analysis["network"]["severity"] != "normal":
        return "network_activity"
    if metrics_analysis["network"]["trend"] == "rising":
        return "network_activity"

    return "idle"


def detect_system_state(metrics_analysis: dict) -> str:
    has_critical = False
    has_persistent_warning = False
    has_anomaly = False
    has_warning = False
    has_recovery = False

    for metric_name in metrics_analysis:
        item = metrics_analysis[metric_name]
        if item["severity"] == "critical":
            has_critical = True
        if item["severity"] == "warning":
            has_warning = True
        if item["severity"] == "warning" and item["persistence"] == "persistent":
            has_persistent_warning = True
        if item["anomaly"]:
            has_anomaly = True
        if item["trend"] == "falling":
            if item["severity"] == "warning":
                has_recovery = True
            if item["severity"] == "critical":
                has_recovery = True

    if has_critical:
        return "critical"
    if has_persistent_warning:
        return "degraded"
    if has_anomaly:
        return "unstable"
    if has_warning:
        return "warning"
    if has_recovery:
        return "recovery"
    return "normal"


def build_evidence(metrics_analysis: dict, bottleneck: dict) -> list[str]:
    evidence = []
    for name in metrics_analysis:
        data = metrics_analysis[name]
        label = METRIC_LABELS[name]
        if data["severity"] != "normal":
            evidence.append(f"{label} превышает {data['severity']}-порог")
        if data["trend"] == "rising":
            evidence.append(f"{label} имеет растущий тренд")
        if data["anomaly"]:
            evidence.append(f"{label} резко отклоняется от среднего уровня")
        if data["persistence"] == "persistent":
            evidence.append(f"{label}: высокая нагрузка сохраняется несколько измерений подряд")
        if data["persistence"] == "short_spike":
            evidence.append(f"{label}: обнаружен кратковременный всплеск нагрузки")

    if bottleneck["component"] == "combined":
        evidence.append("Одновременно повышены несколько основных метрик")

    if len(evidence) == 0:
        evidence.append("Основные метрики находятся в нормальном диапазоне")
    return evidence


def build_recommendations(bottleneck: dict, metrics_analysis: dict) -> list[str]:
    recommendations = []
    component = bottleneck["component"]

    cpu_problem = False
    if component == "cpu":
        cpu_problem = True
    if component == "combined":
        cpu_problem = True
    if metrics_analysis["cpu"]["severity"] != "normal":
        cpu_problem = True

    ram_problem = False
    if component == "ram":
        ram_problem = True
    if component == "combined":
        ram_problem = True
    if metrics_analysis["ram"]["severity"] != "normal":
        ram_problem = True

    disk_problem = False
    if component == "disk":
        disk_problem = True
    if component == "combined":
        disk_problem = True
    if metrics_analysis["disk"]["severity"] != "normal":
        disk_problem = True

    network_problem = False
    if component == "network":
        network_problem = True
    if component == "combined":
        network_problem = True
    if metrics_analysis["network"]["severity"] != "normal":
        network_problem = True

    if cpu_problem:
        recommendations.append("Проверить процессы с высокой загрузкой CPU")
        recommendations.append("Убедиться, что не выполняются фоновые вычислительные задачи")
    if ram_problem:
        recommendations.append("Проверить процессы с высоким потреблением памяти")
        recommendations.append("Закрыть неиспользуемые приложения")
    if disk_problem:
        recommendations.append("Проверить свободное место на диске")
        recommendations.append("Проверить процессы с активной записью на диск")
    if network_problem:
        recommendations.append("Проверить фоновые загрузки и синхронизацию")
        recommendations.append("Проверить приложения с высокой сетевой активностью")
    if component == "combined":
        recommendations.append("Проверить несколько подсистем, так как нагрузка распределена между несколькими компонентами")

    result = []
    for recommendation in recommendations:
        if recommendation not in result:
            result.append(recommendation)

    if not result:
        result.append("Продолжать наблюдение за динамикой метрик")

    return result


def build_summary(system_state: str, scenario: str, bottleneck: dict) -> str:
    state_text = "Состояние системы не определено."
    if system_state == "normal":
        state_text = "Система работает в нормальном режиме."
    if system_state == "warning":
        state_text = "Система работает в режиме предупреждения."
    if system_state == "critical":
        state_text = "Система находится в критическом состоянии."
    if system_state == "unstable":
        state_text = "Система работает нестабильно из-за резкого отклонения метрик."
    if system_state == "degraded":
        state_text = "Система работает под устойчивой повышенной нагрузкой."
    if system_state == "recovery":
        state_text = "Система показывает признаки восстановления после нагрузки."

    scenario_text = "Сценарий нагрузки не определен."
    if scenario == "idle":
        scenario_text = "Сценарий нагрузки не выражен."
    if scenario == "cpu_bound":
        scenario_text = "Основная нагрузка связана с процессором."
    if scenario == "memory_pressure":
        scenario_text = "Основная нагрузка связана с оперативной памятью."
    if scenario == "disk_pressure":
        scenario_text = "Основная нагрузка связана с дисковой подсистемой."
    if scenario == "network_activity":
        scenario_text = "Основная активность связана с сетью."
    if scenario == "mixed_overload":
        scenario_text = "Нагрузка распределена между несколькими подсистемами."

    if bottleneck["component"] == "none":
        return f"{state_text} {scenario_text}"
    return f"{state_text} Предполагаемое узкое место: {bottleneck['component']}. {scenario_text}"


def build_metric_analysis(metric_name: str, values: list[float], current_value: float) -> dict:
    threshold = 20
    if metric_name == "network":
        threshold = settings.network_anomaly_threshold_bytes_per_sec

    return {
        "value": round(current_value, 2),
        "severity": calculate_severity(metric_name, current_value, values),
        "trend": calculate_trend(values),
        "anomaly": detect_anomaly(values, current_value, threshold),
        "persistence": calculate_persistence(values, metric_name),
    }


def _hardware_health_score(health: str) -> int:
    if health == "OK":
        return 95
    if health == "Warning":
        return 70
    if health == "Critical":
        return 35
    return 50


def _hardware_state(health: str) -> str:
    if health == "OK":
        return "normal"
    if health == "Warning":
        return "warning"
    if health == "Critical":
        return "critical"
    return "unstable"


def _hardware_bottleneck(metric: HardwareMetric) -> dict:
    if metric.temperature_c >= 70:
        severity = "warning"
        if metric.temperature_c >= 80:
            severity = "critical"

        return {
            "component": "temperature",
            "severity": severity,
            "reason": "Температура сервера выше нормального диапазона.",
        }
    if metric.fans_health == "Warning" or metric.fans_health == "Critical":
        return {
            "component": "fans",
            "severity": metric.fans_health.lower(),
            "reason": "Контроллер сообщает о проблеме с вентиляторами.",
        }
    if metric.power_supplies_health == "Warning" or metric.power_supplies_health == "Critical":
        return {
            "component": "power",
            "severity": metric.power_supplies_health.lower(),
            "reason": "Контроллер сообщает о проблеме с блоками питания.",
        }
    if metric.hardware_health == "Warning" or metric.hardware_health == "Critical":
        return {
            "component": "hardware",
            "severity": metric.hardware_health.lower(),
            "reason": "Контроллер сообщает о предупреждении аппаратного уровня.",
        }
    return {
        "component": "none",
        "severity": "normal",
        "reason": "Аппаратных проблем не выявлено.",
    }


def _hardware_recommendations(metric: HardwareMetric, bottleneck: dict) -> list[str]:
    recommendations = []
    if metric.temperature_c >= 70:
        recommendations.append("Проверить температурный режим сервера")
    if metric.fans_health == "Warning" or metric.fans_health == "Critical":
        recommendations.append("Проверить состояние вентиляторов")
    if metric.power_supplies_health == "Warning" or metric.power_supplies_health == "Critical":
        recommendations.append("Проверить блоки питания")
    if metric.hardware_health == "Warning" or metric.hardware_health == "Critical":
        recommendations.append("Проверить журнал аппаратных событий iLO/iDRAC")
    if bottleneck["component"] == "none":
        recommendations.append("Продолжать мониторинг аппаратного состояния сервера")
    return recommendations


def build_hardware_diagnostics_summary(db: Session, node: Node) -> dict:
    metric = (
        db.query(HardwareMetric)
        .filter(HardwareMetric.node_id == node.id)
        .order_by(desc(HardwareMetric.created_at))
        .first()
    )
    if not metric:
        return {
            "node_id": node.id,
            "system_state": "normal",
            "scenario": "hardware_monitoring",
            "health_score": 100,
            "confidence": 0.2,
            "bottleneck": {
                "component": "none",
                "severity": "normal",
                "reason": "Аппаратные метрики пока не получены.",
            },
            "metrics": {},
            "evidence": ["Аппаратные метрики пока не получены"],
            "recommendations": ["Выполнить Redfish-опрос узла"],
            "summary": "Диагностика аппаратного источника начнется после первого Redfish-опроса.",
        }

    bottleneck = _hardware_bottleneck(metric)
    state = _hardware_state(metric.hardware_health)
    evidence = [
        f"Power state: {metric.power_state}",
        f"Hardware health: {metric.hardware_health}",
        f"Температура: {metric.temperature_c:.1f} C",
        f"Fans health: {metric.fans_health}",
        f"Power supplies health: {metric.power_supplies_health}",
    ]
    recommendations = _hardware_recommendations(metric, bottleneck)
    health_score = _hardware_health_score(metric.hardware_health)

    return {
        "node_id": node.id,
        "system_state": state,
        "scenario": "hardware_monitoring",
        "health_score": health_score,
        "confidence": 0.9,
        "bottleneck": bottleneck,
        "metrics": {
            "hardware": {
                "value": metric.hardware_health,
                "severity": bottleneck["severity"],
                "trend": "stable",
                "anomaly": metric.hardware_health == "Warning" or metric.hardware_health == "Critical",
                "persistence": "normal",
            }
        },
        "evidence": evidence,
        "recommendations": recommendations,
        "summary": metric.summary,
    }


def build_diagnostics_summary(db: Session, node_id: int, limit: int) -> dict:
    # Аппаратные источники iLO/iDRAC анализируются отдельно.
    # У них нет обычных CPU/RAM/Disk метрик от агента, поэтому берем hardware_metrics.
    node = db.query(Node).filter(Node.id == node_id).first()
    if node:
        if node.source_type == "ilo":
            return build_hardware_diagnostics_summary(db, node)
        if node.source_type == "idrac":
            return build_hardware_diagnostics_summary(db, node)

    # Берем последние записи истории по конкретному узлу.
    # Сначала SQLAlchemy возвращает их от новых к старым, поэтому ниже разворачиваем список.
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
            "node_id": node_id,
            "system_state": "normal",
            "scenario": "idle",
            "health_score": 100,
            "confidence": 0.1,
            "bottleneck": {
                "component": "none",
                "severity": "normal",
                "reason": "Истории метрик пока недостаточно.",
            },
            "metrics": {},
            "evidence": ["Истории метрик пока недостаточно для диагностики"],
            "recommendations": ["Подождать несколько циклов сбора данных"],
            "summary": "Диагностика начнется после накопления истории метрик.",
        }

    current = rows[-1]

    # Для защиты ВКР эта часть самая важная:
    # здесь из временного ряда получаются списки значений по каждой метрике.
    cpu_values = []
    ram_values = []
    disk_values = []
    network_values = []

    for row in rows:
        cpu_values.append(row.cpu_percent)
        ram_values.append(row.ram_percent)
        disk_values.append(row.disk_percent)
        network_values.append(network_value(row))

    current_values = {}
    current_values["cpu"] = current.cpu_percent
    current_values["ram"] = current.ram_percent
    current_values["disk"] = current.disk_percent
    current_values["network"] = network_value(current)

    # Каждая метрика анализируется одинаково:
    # severity, trend, anomaly и persistence.
    metrics_analysis = {}
    metrics_analysis["cpu"] = build_metric_analysis("cpu", cpu_values, current_values["cpu"])
    metrics_analysis["ram"] = build_metric_analysis("ram", ram_values, current_values["ram"])
    metrics_analysis["disk"] = build_metric_analysis("disk", disk_values, current_values["disk"])
    metrics_analysis["network"] = build_metric_analysis("network", network_values, current_values["network"])

    # После анализа отдельных метрик собираем общий вывод по узлу.
    bottleneck = detect_bottleneck(metrics_analysis)
    scenario = detect_scenario(metrics_analysis)
    system_state = detect_system_state(metrics_analysis)
    health_score = calculate_health_score(current_values, metrics_analysis)
    evidence = build_evidence(metrics_analysis, bottleneck)
    recommendations = build_recommendations(bottleneck, metrics_analysis)
    latest_snapshot = (
        db.query(ProcessSnapshot)
        .filter(ProcessSnapshot.node_id == node_id)
        .order_by(desc(ProcessSnapshot.created_at))
        .first()
    )
    if latest_snapshot:
        if bottleneck["component"] == "cpu":
            evidence.append("Зафиксированы процессы с повышенной загрузкой CPU")
            recommendations.append("Проверить процессы, указанные в диагностической карточке")
            recommendations.append("При необходимости завершить или перезапустить ресурсоёмкие приложения")
        if bottleneck["component"] == "ram":
            evidence.append("Зафиксированы процессы с повышенным потреблением памяти")
            recommendations.append("Проверить процессы, указанные в диагностической карточке")
            recommendations.append("При необходимости завершить или перезапустить ресурсоёмкие приложения")

    unique_recommendations = []
    for recommendation in recommendations:
        if recommendation not in unique_recommendations:
            unique_recommendations.append(recommendation)
    recommendations = unique_recommendations

    rows_count_for_confidence = len(rows)
    if rows_count_for_confidence > 30:
        rows_count_for_confidence = 30

    confidence = round(0.35 + rows_count_for_confidence / 50 + len(evidence) * 0.03, 2)
    if confidence > 0.95:
        confidence = 0.95

    return {
        "node_id": node_id,
        "system_state": system_state,
        "scenario": scenario,
        "health_score": health_score,
        "confidence": confidence,
        "bottleneck": bottleneck,
        "metrics": metrics_analysis,
        "evidence": evidence,
        "recommendations": recommendations,
        "summary": build_summary(system_state, scenario, bottleneck),
    }
