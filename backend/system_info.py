import platform
import socket
import time
from datetime import timedelta

import psutil


_last_network_by_interface = psutil.net_io_counters(pernic=True)
_last_network_time = time.monotonic()


def format_uptime(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def get_system_info() -> dict:
    boot_time = psutil.boot_time()
    return {
        "computer_name": socket.gethostname(),
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "uptime": format_uptime(time.time() - boot_time),
    }


def get_cpu_info() -> dict:
    per_core = psutil.cpu_percent(interval=0.2, percpu=True)
    frequency = psutil.cpu_freq()

    average_percent = 0
    if per_core:
        total = 0
        for value in per_core:
            total += value
        average_percent = round(total / len(per_core), 2)

    current_frequency = 0
    if frequency:
        current_frequency = round(frequency.current, 2)

    return {
        "physical_cores": psutil.cpu_count(logical=False) or 0,
        "logical_threads": psutil.cpu_count(logical=True) or 0,
        "current_frequency_mhz": current_frequency,
        "per_core_percent": per_core,
        "average_percent": average_percent,
    }


def get_memory_info() -> dict:
    memory = psutil.virtual_memory()
    return {
        "total": memory.total,
        "used": memory.used,
        "free": memory.free,
        "available": memory.available,
        "percent": memory.percent,
    }


def get_disks_info() -> list[dict]:
    disks = []
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, OSError):
            continue

        disks.append(
            {
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "file_system": partition.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            }
        )
    return disks


def get_network_info() -> list[dict]:
    global _last_network_by_interface, _last_network_time

    current = psutil.net_io_counters(pernic=True)
    current_time = time.monotonic()
    elapsed = current_time - _last_network_time
    if elapsed < 1:
        elapsed = 1

    interfaces = []

    for name, counters in current.items():
        previous = _last_network_by_interface.get(name)
        sent_speed = 0
        recv_speed = 0

        if previous:
            sent_speed = (counters.bytes_sent - previous.bytes_sent) / elapsed
            recv_speed = (counters.bytes_recv - previous.bytes_recv) / elapsed

            if sent_speed < 0:
                sent_speed = 0
            if recv_speed < 0:
                recv_speed = 0

        interfaces.append(
            {
                "name": name,
                "bytes_sent": counters.bytes_sent,
                "bytes_recv": counters.bytes_recv,
                "sent_per_sec": sent_speed,
                "recv_per_sec": recv_speed,
            }
        )

    _last_network_by_interface = current
    _last_network_time = current_time
    return interfaces


def get_processes(limit: int, sort: str) -> list[dict]:
    processes = []
    sort_field = "cpu_percent"
    if sort == "ram":
        sort_field = "memory_percent"

    logical_threads = psutil.cpu_count(logical=True)
    if not logical_threads:
        logical_threads = 1

    process_list = list(psutil.process_iter(["pid", "name"]))

    for process in process_list:
        try:
            process.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(0.1)

    for process in process_list:
        try:
            if process.pid == 0:
                continue

            cpu_percent = process.cpu_percent(interval=None)
            cpu_percent = cpu_percent / logical_threads
            if cpu_percent < 0:
                cpu_percent = 0
            if cpu_percent > 100:
                cpu_percent = 100

            processes.append(
                {
                    "pid": process.pid,
                    "name": process.name() or "unknown",
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_percent": round(process.memory_percent(), 2),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    def get_sort_value(item: dict) -> float:
        return item[sort_field]

    processes.sort(key=get_sort_value, reverse=True)
    return processes[:limit]
