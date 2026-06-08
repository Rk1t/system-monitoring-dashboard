import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from metrics_collector import collect_metrics, get_top_processes


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "agent_state.json"

DEFAULT_CONFIG = {
    "server_url": "http://127.0.0.1:8000",
    "enrollment_key": "",
    "agent_token": "",
    "node_id": None,
    "agent_name": "Monitoring Agent",
    "send_interval_seconds": 5,
    "process_snapshot_cooldown_seconds": 30,
    "agent_version": "0.1.0",
}


def make_config(extra_values: dict | None = None) -> dict:
    config = DEFAULT_CONFIG.copy()
    if extra_values:
        for key, value in extra_values.items():
            config[key] = value
    return config


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8-sig") as file:
            file_config = json.load(file)
            return make_config(file_config)

    config = config_from_environment()
    if config:
        save_config(config)
        return config

    if sys.stdin.isatty():
        config = create_config_interactively()
        save_config(config)
        return config

    raise RuntimeError(
        "config.json не найден. Создайте config.json рядом с агентом или задайте "
        "SYSTEM_MONITOR_SERVER_URL и SYSTEM_MONITOR_ENROLLMENT_KEY."
    )


def save_config(config: dict) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2, ensure_ascii=False)


def config_from_environment() -> dict | None:
    server_url = os.getenv("SYSTEM_MONITOR_SERVER_URL", "").strip()
    enrollment_key = os.getenv("SYSTEM_MONITOR_ENROLLMENT_KEY", "").strip()
    if not server_url or not enrollment_key:
        return None

    config = make_config()
    config["server_url"] = server_url
    config["enrollment_key"] = enrollment_key
    config["agent_name"] = os.getenv("SYSTEM_MONITOR_AGENT_NAME", "Monitoring Agent").strip() or "Monitoring Agent"
    return config


def create_config_interactively() -> dict:
    print("config.json не найден. Выполняется первичная настройка агента.")
    server_url = input(f"Central backend URL [{DEFAULT_CONFIG['server_url']}]: ").strip() or DEFAULT_CONFIG["server_url"]
    enrollment_key = input("Enrollment key: ").strip()
    agent_name = input(f"Agent name [{DEFAULT_CONFIG['agent_name']}]: ").strip() or DEFAULT_CONFIG["agent_name"]

    config = make_config()
    config["server_url"] = server_url
    config["enrollment_key"] = enrollment_key
    config["agent_name"] = agent_name
    return config


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    with STATE_PATH.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def save_state(state: dict) -> None:
    with STATE_PATH.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, ensure_ascii=False)


def build_url(server_url: str, path: str) -> str:
    return server_url.rstrip("/") + path


def post_json(url: str, payload: dict, token: str | None = None, timeout: int = 5) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {}
    headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_data = response.read().decode("utf-8")
        return json.loads(response_data)


def register_agent(config: dict) -> int:
    metrics = collect_metrics()
    payload = {
        "name": config["agent_name"],
        "hostname": metrics["hostname"],
        "os_name": metrics["os_name"],
        "agent_version": config["agent_version"],
        "token": config["agent_token"],
    }
    url = build_url(config["server_url"], "/api/agents/register")
    response = post_json(url, payload)
    return response["node_id"]


def enroll_agent(config: dict) -> dict:
    metrics = collect_metrics()
    enrollment_key = config.get("enrollment_key")
    if not enrollment_key or enrollment_key == "smk_enroll_xxxxx":
        raise RuntimeError("Не указан enrollment_key. Создайте ключ подключения в web-интерфейсе.")

    payload = {
        "enrollment_key": enrollment_key,
        "agent_name": config["agent_name"],
        "hostname": metrics["hostname"],
        "os_name": metrics["os_name"],
        "agent_version": config["agent_version"],
    }
    url = build_url(config["server_url"], "/api/agents/enroll")
    response = post_json(url, payload)
    state = {
        "node_id": response["node_id"],
        "agent_token": response["agent_token"],
    }
    save_state(state)
    return state


def send_telemetry(config: dict, node_id: int, agent_token: str) -> None:
    metrics = collect_metrics()
    payload = {
        "node_id": node_id,
        "timestamp": metrics["timestamp"],
        "cpu_percent": metrics["cpu_percent"],
        "ram_percent": metrics["ram_percent"],
        "disk_percent": metrics["disk_percent"],
        "bytes_sent": metrics["bytes_sent"],
        "bytes_recv": metrics["bytes_recv"],
    }
    url = build_url(config["server_url"], "/api/telemetry")
    post_json(url, payload, token=agent_token)


def get_snapshot_reason(metrics: dict) -> str | None:
    cpu_high = metrics["cpu_percent"] > 70
    ram_high = metrics["ram_percent"] > 75

    if cpu_high and ram_high:
        return "combined_high"
    if cpu_high:
        return "cpu_high"
    if ram_high:
        return "ram_high"
    return None


def send_process_snapshot(config: dict, node_id: int, agent_token: str, metrics: dict) -> None:
    reason = get_snapshot_reason(metrics)
    if not reason:
        return

    sort_by = "cpu"
    if reason == "ram_high":
        sort_by = "memory"

    payload = {
        "node_id": node_id,
        "reason": reason,
        "items": get_top_processes(limit=5, sort_by=sort_by),
    }
    url = build_url(config["server_url"], "/api/process-snapshots")
    post_json(url, payload, token=agent_token)


def get_saved_agent_connection(config: dict) -> tuple[int | None, str | None]:
    """Берем node_id и token из agent_state.json.

    Если agent_state.json еще нет, пробуем взять значения из config.json.
    Это сделано для простого первого запуска агента.
    """
    state = load_state()
    node_id = state.get("node_id") or config.get("node_id")
    agent_token = state.get("agent_token") or config.get("agent_token")
    return node_id, agent_token


def connect_agent_if_needed(config: dict, node_id: int | None, agent_token: str | None) -> tuple[int, str]:
    """Если агент еще не привязан к серверу, выполняем enroll."""
    if node_id and agent_token:
        return node_id, agent_token

    state = enroll_agent(config)
    print(f"Привязка агента успешна. node_id={state['node_id']}")
    return state["node_id"], state["agent_token"]


def build_telemetry_payload(node_id: int, metrics: dict) -> dict:
    """Готовим простой JSON, который отправляется на backend."""
    return {
        "node_id": node_id,
        "timestamp": metrics["timestamp"],
        "cpu_percent": metrics["cpu_percent"],
        "ram_percent": metrics["ram_percent"],
        "disk_percent": metrics["disk_percent"],
        "bytes_sent": metrics["bytes_sent"],
        "bytes_recv": metrics["bytes_recv"],
    }


def send_one_metrics_packet(config: dict, node_id: int, agent_token: str) -> dict:
    """Собираем метрики и отправляем одну порцию данных на сервер."""
    metrics = collect_metrics()
    payload = build_telemetry_payload(node_id, metrics)
    post_json(build_url(config["server_url"], "/api/telemetry"), payload, token=agent_token)
    return metrics


def should_send_process_snapshot(metrics: dict, last_snapshot_sent_at: float, cooldown_seconds: int) -> bool:
    """Проверяем, пора ли отправлять top процессов.

    Снимок процессов отправляется не постоянно, а только при высокой нагрузке
    и не чаще одного раза за cooldown_seconds.
    """
    if not get_snapshot_reason(metrics):
        return False

    seconds_after_last_snapshot = time.time() - last_snapshot_sent_at
    if seconds_after_last_snapshot >= cooldown_seconds:
        return True
    return False


def main() -> None:
    config = load_config()
    config["server_url"] = config["server_url"].rstrip("/")
    interval = 5
    snapshot_cooldown = 30
    if config.get("send_interval_seconds"):
        interval = int(config.get("send_interval_seconds"))
    if config.get("process_snapshot_cooldown_seconds"):
        snapshot_cooldown = int(config.get("process_snapshot_cooldown_seconds"))
    last_snapshot_sent_at = 0.0
    node_id, agent_token = get_saved_agent_connection(config)

    print("Monitoring Agent запущен")
    print(f"Центральный backend: {config['server_url']}")

    while True:
        try:
            node_id, agent_token = connect_agent_if_needed(config, node_id, agent_token)
            metrics = send_one_metrics_packet(config, node_id, agent_token)
            print(f"Отправка успешна. node_id={node_id}")

            if should_send_process_snapshot(metrics, last_snapshot_sent_at, snapshot_cooldown):
                send_process_snapshot(config, node_id, agent_token, metrics)
                last_snapshot_sent_at = time.time()
                print(f"Снимок процессов отправлен. cooldown={snapshot_cooldown} сек.")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"Ошибка подключения к серверу: {exc}")
            print("Повторная попытка...")
        except Exception as exc:
            print(f"Ошибка работы агента: {exc}")
            print("Повторная попытка...")

        time.sleep(interval)


if __name__ == "__main__":
    main()
