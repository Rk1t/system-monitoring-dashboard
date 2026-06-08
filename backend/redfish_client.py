import base64
import json
import ssl
import urllib.error
import urllib.request


class RedfishClient:
    def __init__(self, base_url: str, username: str, password: str, verify_ssl: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl

    def _request_json(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        credentials = f"{self.username}:{self.password}".encode("utf-8")
        auth_header = base64.b64encode(credentials).decode("ascii")
        request = urllib.request.Request(url, headers={"Authorization": f"Basic {auth_header}"})
        context = None
        if not self.verify_ssl:
            context = ssl._create_unverified_context()

        with urllib.request.urlopen(request, timeout=8, context=context) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_service_root(self) -> dict:
        return self._request_json("/redfish/v1/")

    def get_system_info(self) -> dict:
        root = self.get_service_root()
        systems_link = root.get("Systems", {}).get("@odata.id", "/redfish/v1/Systems")
        systems = self._request_json(systems_link)
        members = systems.get("Members") or []
        if not members:
            return {}
        return self._request_json(members[0].get("@odata.id"))

    def get_chassis_health(self) -> dict:
        root = self.get_service_root()
        chassis_link = root.get("Chassis", {}).get("@odata.id", "/redfish/v1/Chassis")
        chassis = self._request_json(chassis_link)
        members = chassis.get("Members") or []
        if not members:
            return {}
        return self._request_json(members[0].get("@odata.id"))

    def get_power_state(self) -> str:
        system_info = self.get_system_info()
        return system_info.get("PowerState", "Unknown")

    def get_thermal_info(self) -> dict:
        chassis = self.get_chassis_health()
        thermal_link = chassis.get("Thermal", {}).get("@odata.id")
        if not thermal_link:
            return {}
        return self._request_json(thermal_link)

    def collect_hardware_status(self) -> dict:
        try:
            system_info = self.get_system_info()
            chassis = self.get_chassis_health()
            thermal = self.get_thermal_info()

            status = chassis.get("Status", {}) or system_info.get("Status", {})
            hardware_health = status.get("Health", "Unknown")
            temperatures = thermal.get("Temperatures", [])
            fans = thermal.get("Fans", [])

            temperature_c = 0
            for item in temperatures:
                reading = item.get("ReadingCelsius")
                if isinstance(reading, (int, float)) and reading > temperature_c:
                    temperature_c = reading

            fan_health_values = []
            for item in fans:
                health = item.get("Status", {}).get("Health")
                if health:
                    fan_health_values.append(health)

            fans_health = "OK"
            if "Critical" in fan_health_values:
                fans_health = "Critical"
            elif "Warning" in fan_health_values:
                fans_health = "Warning"

            return {
                "power_state": system_info.get("PowerState", "Unknown"),
                "hardware_health": hardware_health,
                "temperature_c": temperature_c,
                "fans_health": fans_health,
                "power_supplies_health": "Unknown",
                "summary": f"Redfish опрос выполнен. Hardware health: {hardware_health}.",
            }
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            return {
                "error": True,
                "message": f"Не удалось выполнить Redfish-опрос: {exc}",
                "power_state": "Unknown",
                "hardware_health": "Critical",
                "temperature_c": 0,
                "fans_health": "Unknown",
                "power_supplies_health": "Unknown",
                "summary": "Redfish-источник недоступен или вернул некорректный ответ",
            }
