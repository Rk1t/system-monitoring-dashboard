def get_mock_ilo_status() -> dict:
    return {
        "vendor": "HPE",
        "source_type": "ilo",
        "power_state": "On",
        "hardware_health": "OK",
        "temperature_c": 44,
        "fans_health": "OK",
        "power_supplies_health": "OK",
        "summary": "Аппаратное состояние сервера в норме",
    }


def get_mock_idrac_status() -> dict:
    return {
        "vendor": "Dell",
        "source_type": "idrac",
        "power_state": "On",
        "hardware_health": "Warning",
        "temperature_c": 58,
        "fans_health": "OK",
        "power_supplies_health": "OK",
        "summary": "Обнаружено предупреждение аппаратного уровня",
    }
