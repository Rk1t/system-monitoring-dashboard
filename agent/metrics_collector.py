from datetime import datetime
import platform
import socket

import psutil


def get_process_sort_value(process_info: dict, sort_field: str) -> float:
    return process_info[sort_field]


def collect_metrics() -> dict:
    """Собирает только базовую телеметрию, анализ выполняется на backend."""
    network = psutil.net_io_counters()

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "bytes_sent": network.bytes_sent,
        "bytes_recv": network.bytes_recv,
        "hostname": socket.gethostname(),
        "os_name": platform.platform(),
        "timestamp": datetime.utcnow().isoformat(),
    }


def get_top_processes(limit: int = 5, sort_by: str = "cpu") -> list[dict]:
    sort_field = "cpu_percent"
    if sort_by == "memory":
        sort_field = "memory_percent"

    logical_threads = psutil.cpu_count(logical=True)
    if not logical_threads:
        logical_threads = 1

    processes = []

    for process in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = process.info
            pid = 0
            name = "unknown"
            cpu_percent = 0.0
            memory_percent = 0.0

            if info.get("pid"):
                pid = int(info.get("pid"))
            if info.get("name"):
                name = info.get("name")
            if info.get("cpu_percent"):
                cpu_percent = float(info.get("cpu_percent"))
                cpu_percent = cpu_percent / logical_threads
                if cpu_percent < 0:
                    cpu_percent = 0.0
                if cpu_percent > 100:
                    cpu_percent = 100.0
            if info.get("memory_percent"):
                memory_percent = float(info.get("memory_percent"))

            processes.append({
                "pid": pid,
                "name": name,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
            })
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        except Exception:
            continue

    def sort_process(process_info: dict) -> float:
        return get_process_sort_value(process_info, sort_field)

    processes.sort(key=sort_process, reverse=True)
    return processes[:limit]
