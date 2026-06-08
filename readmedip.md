# Техническое описание проекта для ВКР

Тема ВКР: **«Разработка модуля визуализации мониторинга данных компьютерных систем»**.

Данный документ описывает текущее состояние проекта по фактическому коду. Его можно использовать как техническую основу для написания пояснительной записки ВКР: описания архитектуры, серверной части, клиентского интерфейса, хранения данных, визуализации, анализа телеметрии и ограничений текущей версии.

Главный акцент проекта: это не простой аналог диспетчера задач, а центральная система визуализации и анализа телеметрии компьютерных систем. Система хранит историю измерений, строит графики, уменьшает количество отображаемых точек для снижения нагрузки на браузер, анализирует состояние узлов, выявляет тренды, аномалии, предполагаемые узкие места и формирует диагностические рекомендации.

---

## 1. Общая архитектура проекта

### 1.1 Основные реализованные части

В проекте реализованы следующие компоненты:

- **Central Backend на FastAPI**  
  Основной сервер приложения. Принимает телеметрию, хранит данные в SQLite, предоставляет REST API, выполняет диагностику, анализ, авторизацию и управление узлами.
  Основные файлы:
  - `backend/main.py`
  - `backend/models.py`
  - `backend/database.py`
  - `backend/config.py`
  - `backend/analysis.py`
  - `backend/diagnostics.py`
  - `backend/auth.py`
  - `backend/node_manager.py`

- **Frontend на Vue 3 + Vite**  
  Web-интерфейс администратора. Показывает список систем, карточки метрик, графики, диагностику, ключи подключения, пользователей организации, Download Center и аппаратные источники.
  Основные файлы:
  - `frontend/src/App.vue`
  - `frontend/src/main.js`
  - `frontend/src/styles.css`
  - `frontend/package.json`
  - `frontend/vite.config.js`

- **SQLite + SQLAlchemy**  
  Локальная база данных для хранения узлов, пользователей, организаций, временных рядов метрик, аппаратных метрик, ключей подключения, токенов агентов и снимков процессов.
  Основные файлы:
  - `backend/database.py`
  - `backend/models.py`

- **Local System collector**  
  Встроенный сборщик метрик на стороне backend. Собирает метрики того компьютера, на котором запущен backend.
  Основной файл:
  - `backend/metrics_collector.py`

- **Monitoring Agent**  
  Отдельный лёгкий агент, который запускается на контролируемой системе, собирает базовую телеметрию через `psutil` и отправляет её на центральный backend. Агент не выполняет анализ, не хранит историю и не строит графики.
  Основные файлы:
  - `agent/agent.py`
  - `agent/metrics_collector.py`
  - `agent/config.json`
  - `agent/build_windows.ps1`
  - `agent/build_linux.sh`
  - `agent/README.md`

- **Подготовка HPE iLO / Dell iDRAC через Redfish API**  
  Добавлена архитектурная поддержка аппаратных источников через Redfish. В коде есть реальный базовый Redfish-клиент и mock-источники для демонстрации без физического сервера.
  Основные файлы:
  - `backend/redfish_client.py`
  - `backend/mock_redfish.py`

- **Подготовка к сборке локального exe**  
  Добавлены файлы для PyInstaller-сборки backend + static frontend в исполняемое приложение.
  Основные файлы:
  - `build/SystemMonitor.spec`
  - `build/build_exe.ps1`
  - `backend/run.py`

### 1.2 Клиент-серверная архитектура

Проект построен по клиент-серверной архитектуре:

1. **Web UI** работает в браузере и обращается к backend через REST API.
2. **Central Backend** обрабатывает запросы, проверяет JWT/agent token, читает и записывает данные в SQLite.
3. **SQLite** хранит историю, пользователей, организации, узлы и служебные данные.
4. **Local collector** внутри backend собирает метрики локальной машины.
5. **Monitoring Agent** на удалённых машинах отправляет telemetry через HTTP.
6. **Redfish source** для iLO/iDRAC создаётся как отдельный тип узла. В текущей версии web-интерфейс добавляет такие узлы, backend сохраняет аппаратные метрики, а фактический опрос может выполняться через mock или через базовый `RedfishClient`.

### 1.3 Поток данных

#### Local System

1. Backend запускается через `backend/run.py`.
2. При startup выполняется `Base.metadata.create_all(bind=engine)`.
3. Выполняются безопасные SQLite-инициализации в `backend/node_manager.py`.
4. Создаётся или обновляется локальный узел `Local System`.
5. Фоновая задача `metrics_background_worker()` каждые `metrics_collect_interval_seconds` секунд вызывает `collect_metrics(db)`.
6. `backend/metrics_collector.py` собирает CPU, RAM, Disk, Network через `psutil`.
7. Метрика сохраняется в таблицу `metrics` с `node_id` локального узла.
8. Frontend открывает страницу узла и запрашивает:
   - текущие метрики;
   - историю;
   - сводку;
   - analysis summary;
   - diagnostics.
9. Vue строит карточки, графики и диагностические блоки.

#### Agent node

1. Пользователь создаёт enrollment key в web-интерфейсе.
2. Агент запускается на контролируемой системе.
3. Если у агента нет `agent_state.json`, он выполняет enrollment через `/api/agents/enroll`.
4. Backend проверяет enrollment key, создаёт или обновляет Node типа `agent`, выдаёт `agent_token`.
5. Агент сохраняет `node_id` и `agent_token` в `agent_state.json`.
6. Далее агент отправляет telemetry на `/api/telemetry` с `Authorization: Bearer <agent_token>`.
7. Backend определяет `node_id` по токену и сохраняет метрику.
8. При высокой CPU/RAM нагрузке агент отправляет top-5 процессов на `/api/process-snapshots`.
9. Анализ и диагностика выполняются только на backend.

#### iLO / iDRAC

1. Пользователь добавляет аппаратный источник через web-интерфейс.
2. Frontend отправляет `POST /api/nodes/redfish`.
3. Backend создаёт Node с `source_type = ilo` или `idrac`.
4. Backend сохраняет аппаратную запись в `hardware_metrics`.
5. На странице узла отображаются power state, hardware health, temperature, fans, power supplies и diagnostics.
6. В текущем коде UI по умолчанию передаёт `use_mock: true`, хотя на экране это уже скрыто. Поэтому демонстрационный сценарий работает без физического сервера.

### 1.4 Файлы запуска

- `backend/run.py`  
  Запускает FastAPI через `uvicorn`, автоматически открывает браузер.

- `frontend/package.json`  
  Содержит команды Vite:
  - `npm run dev`
  - `npm run build`

- `agent/agent.py`  
  Запуск Monitoring Agent.

- `build/build_exe.ps1`  
  Сборка frontend, копирование в `static/`, запуск PyInstaller.

- `agent/build_windows.ps1`  
  Сборка Windows-агента через PyInstaller.

- `agent/build_linux.sh`  
  Сборка Linux-агента через PyInstaller в Linux-среде.

---

## 2. Backend

### 2.1 Технологии backend

Backend реализован на:

- Python;
- FastAPI;
- SQLAlchemy;
- SQLite;
- psutil;
- uvicorn;
- Pydantic-схемы.

Зависимости указаны в `backend/requirements.txt`.

### 2.2 Основные backend-файлы

#### `backend/main.py`

Главный файл API. В нём находятся:

- создание `FastAPI`;
- CORS;
- startup-инициализация;
- фоновый сбор локальных метрик;
- endpoint’ы авторизации;
- endpoint’ы пользователей и организаций;
- endpoint’ы enrollment keys;
- endpoint’ы скачивания агентов;
- старые compatibility endpoint’ы метрик;
- node-aware endpoint’ы;
- agent enrollment и telemetry;
- Redfish endpoint’ы;
- endpoint’ы hardware metrics;
- endpoint’ы process snapshots;
- endpoint’ы подробных live-метрик Local System;
- раздача собранного frontend из `static/`.

#### `backend/models.py`

SQLAlchemy-модели:

- `Node`
- `User`
- `Organization`
- `OrganizationMember`
- `EnrollmentKey`
- `AgentToken`
- `Metric`
- `HardwareMetric`
- `ProcessSnapshot`
- `ProcessSnapshotItem`

#### `backend/schemas.py`

Pydantic-схемы входных и выходных данных:

- `MetricRead`
- `MetricsSummary`
- `NodeRead`
- `LoginRequest`
- `LoginResponse`
- `EnrollmentKeyRead`
- `AgentEnrollRequest`
- `AgentEnrollResponse`
- `ProcessSnapshotIn`
- `ProcessSnapshotOut`
- `HardwareMetricRead`
- и другие.

#### `backend/database.py`

Создаёт SQLite engine и session:

- путь к БД берётся из `config.json`;
- используется `sqlite:///...`;
- создаётся директория БД;
- предоставляется dependency `get_db()`.

#### `backend/config.py`

Загружает `config.json` и учитывает режим PyInstaller:

- `PROJECT_ROOT`;
- `RESOURCE_ROOT`;
- `CONFIG_PATH`;
- `AppConfig`;
- `resolve_project_path()`.

#### `backend/metrics_collector.py`

Собирает локальные метрики:

- CPU;
- RAM;
- Disk;
- bytes sent/recv;
- скорость сети;
- сохраняет запись в `metrics`;
- обновляет `Node.last_seen`;
- очищает старые локальные записи через `cleanup_old_metrics()`.

Важно: очистка старых записей по `history_limit_records` сейчас явно вызывается для локального сборщика. Для agent telemetry в `receive_telemetry()` такой очистки нет, поэтому история agent-узлов может расти до ручной очистки через `clear-history`.

#### `backend/analysis.py`

Выполняет лёгкий анализ истории:

- тренды CPU/RAM/Disk/Network;
- простые аномалии;
- health score;
- health status;
- bottleneck;
- адаптивный refresh interval.

#### `backend/diagnostics.py`

Выполняет расширенную rule-based диагностику:

- severity;
- trend;
- anomaly;
- persistence;
- bottleneck;
- scenario;
- system_state;
- health_score;
- evidence;
- recommendations;
- summary.

Для iLO/iDRAC использует `hardware_metrics`.

#### `backend/auth.py`

Реализует:

- хеширование паролей через `hashlib.pbkdf2_hmac`;
- генерацию JWT вручную через HMAC SHA-256;
- проверку JWT;
- helper’ы ролей и организаций;
- генерацию секретных токенов;
- вычисление prefix токена.

Важное замечание для диплома: JWT реализован без внешней библиотеки. Это упрощает зависимости, но для промышленной эксплуатации лучше использовать проверенную библиотеку, например `python-jose` или `PyJWT`, и вынести секрет в защищённое окружение.

#### `backend/node_manager.py`

Содержит безопасную инициализацию старых SQLite-баз:

- добавление `metrics.node_id`;
- добавление Redfish-полей в `nodes`;
- добавление `organization_id`;
- добавление management-полей `is_archived`, `archived_at`, `description`;
- создание default admin;
- создание `Default Organization`;
- создание `Local System`.

#### `backend/system_info.py`

Подробные live-метрики Local System:

- system info;
- CPU info;
- memory info;
- disks;
- network interfaces;
- processes.

Эти endpoint’ы относятся именно к машине backend и не являются универсальными для agent-узлов.

#### `backend/redfish_client.py`

Базовый Redfish-клиент:

- service root;
- system info;
- chassis health;
- power state;
- thermal info;
- normalized hardware status.

Если реальный запрос не удался, возвращает структурированный словарь с ошибкой и `hardware_health = Critical`, а не роняет backend.

#### `backend/mock_redfish.py`

Содержит демонстрационные ответы:

- `get_mock_ilo_status()`;
- `get_mock_idrac_status()`.

Используется для проверки интерфейса без физического сервера HPE/Dell.

### 2.3 Где выполняется обработка и анализ

Анализ выполняется на backend:

- базовый analysis: `backend/analysis.py`;
- диагностика: `backend/diagnostics.py`;
- summary: `build_metrics_summary()` в `backend/main.py`;
- hardware diagnostics: `build_hardware_diagnostics_summary()` в `backend/diagnostics.py`.

Агент анализ не выполняет. Агент только:

- собирает базовые метрики;
- проверяет простые пороги CPU/RAM, чтобы решить, отправлять ли process snapshot;
- отправляет telemetry и snapshots на backend.

---

## 3. Сбор и анализ метрик

### 3.1 Какие метрики собираются

#### Основные метрики временного ряда

Сохраняются в таблицу `metrics`:

- `cpu_percent`;
- `ram_percent`;
- `disk_percent`;
- `bytes_sent`;
- `bytes_recv`;
- `network_sent_per_sec`;
- `network_recv_per_sec`;
- `timestamp`;
- `node_id`.

Эти данные используются для:

- текущих карточек;
- графиков CPU/RAM;
- summary;
- trend analysis;
- anomaly detection;
- health score;
- bottleneck detection;
- diagnostics.

#### Подробные live-метрики Local System

Endpoint’ы `/api/system/*` возвращают:

- имя компьютера;
- ОС;
- версия ОС;
- архитектура;
- uptime;
- физические ядра;
- логические потоки;
- частота CPU;
- загрузка по ядрам;
- память;
- диски;
- сетевые интерфейсы;
- процессы.

Файлы:

- `backend/system_info.py`
- `frontend/src/App.vue`

#### Process snapshots

При повышенной нагрузке агент отправляет top-5 процессов:

- `pid`;
- `name`;
- `cpu_percent`;
- `memory_percent`.

Файлы:

- `agent/metrics_collector.py`, функция `get_top_processes()`;
- `agent/agent.py`, функции `get_snapshot_reason()` и `send_process_snapshot()`;
- `backend/models.py`, модели `ProcessSnapshot`, `ProcessSnapshotItem`;
- `backend/main.py`, endpoint’ы `/api/process-snapshots` и `/api/nodes/{node_id}/process-snapshots/*`.

Порог отправки:

- CPU > 70;
- RAM > 75;
- если оба условия, reason = `combined_high`;
- cooldown между отправками: `process_snapshot_cooldown_seconds`, по умолчанию 30 секунд.

### 3.2 Как часто обновляются данные

Настройки находятся в `config.json`:

```json
{
  "metrics_collect_interval_seconds": 5,
  "frontend_refresh_interval_seconds": 3,
  "normal_refresh_interval_seconds": 5,
  "alert_refresh_interval_seconds": 2,
  "history_limit_records": 200
}
```

Фактическая логика:

- Local System собирается backend-фоном каждые `metrics_collect_interval_seconds`.
- Agent отправляет telemetry каждые `send_interval_seconds` из `agent/config.json`.
- Frontend обновляет список систем раз в 7 секунд.
- Frontend обновляет страницу узла с интервалом, который берётся из:
  - `analysis.current_refresh_interval`;
  - или `frontend_refresh_interval_seconds`;
  - или fallback 3 секунды.
- Backend может вернуть более частый интервал при предупреждениях/аномалиях.

### 3.3 Анализ нагрузки

Реализованы два уровня анализа:

#### `backend/analysis.py`

Более лёгкий summary-анализ:

- `trends`;
- `health_score`;
- `health_status`;
- `anomalies`;
- `bottleneck`;
- `current_refresh_interval`;
- `explanations`.

Пример результата:

```json
{
  "trends": {
    "cpu": "stable",
    "ram": "growing",
    "disk": "stable",
    "network": "stable"
  },
  "health_score": 74,
  "health_status": "умеренная нагрузка",
  "anomalies": [],
  "bottleneck": {
    "metric": "RAM",
    "title": "Предполагаемое узкое место: RAM",
    "reason": "RAM выше 90%, системе может не хватать оперативной памяти.",
    "recommendation": "Проверьте процессы по RAM и закройте лишние приложения."
  },
  "current_refresh_interval": 2
}
```

#### `backend/diagnostics.py`

Более подробная диагностическая карточка:

- `system_state`;
- `scenario`;
- `health_score`;
- `confidence`;
- `bottleneck`;
- `metrics`;
- `evidence`;
- `recommendations`;
- `summary`.

Пример результата:

```json
{
  "node_id": 1,
  "system_state": "warning",
  "scenario": "memory_pressure",
  "health_score": 72,
  "confidence": 0.81,
  "bottleneck": {
    "component": "ram",
    "severity": "warning",
    "reason": "RAM превышает warning-порог и имеет растущий тренд"
  },
  "metrics": {
    "cpu": {
      "value": 42,
      "severity": "normal",
      "trend": "stable",
      "anomaly": false,
      "persistence": "normal"
    }
  },
  "evidence": [
    "RAM превышает warning-порог",
    "RAM имеет растущий тренд"
  ],
  "recommendations": [
    "Проверить процессы с высоким потреблением памяти"
  ],
  "summary": "Система работает в режиме предупреждения."
}
```

### 3.4 Тренды, аномалии и узкие места

Реализовано:

- тренды:
  - `growing/falling/stable` в `analysis.py`;
  - `rising/falling/stable` в `diagnostics.py`;
- аномалии:
  - сравнение текущего значения со средним за окно истории;
  - для CPU/RAM/Disk порог около 20;
  - для Network используется порог из config;
- persistence:
  - `normal`;
  - `short_spike`;
  - `persistent`;
- bottleneck:
  - `cpu`;
  - `ram`;
  - `disk`;
  - `network`;
  - `combined`;
  - `none`;
- scenario:
  - `idle`;
  - `cpu_bound`;
  - `memory_pressure`;
  - `disk_pressure`;
  - `network_activity`;
  - `mixed_overload`;
  - `hardware_monitoring`.

---

## 4. Хранение данных

### 4.1 База данных

Используется **SQLite**.

Путь к базе указывается в `config.json`:

```json
{
  "database_path": "database/metrics.db"
}
```

Подключение формируется в `backend/database.py`.

SQLite подходит для дипломного прототипа и локального развёртывания. Для промышленной многопользовательской эксплуатации желательно перейти на PostgreSQL.

### 4.2 Таблицы и назначение

#### `users`

Хранит пользователей:

- `id`;
- `username`;
- `email`;
- `password_hash`;
- `role_global`;
- `is_active`;
- `created_at`;
- `last_login`.

Пароли хранятся только в виде PBKDF2-хэша.

#### `organizations`

Хранит рабочие пространства:

- `id`;
- `name`;
- `created_at`.

#### `organization_members`

Связывает пользователей и организации:

- `id`;
- `organization_id`;
- `user_id`;
- `role`;
- `created_at`.

Роли:

- `owner`;
- `admin`;
- `viewer`.

#### `nodes`

Хранит контролируемые системы:

- `id`;
- `organization_id`;
- `name`;
- `hostname`;
- `source_type`;
- `os_name`;
- `agent_version`;
- `management_ip`;
- `redfish_username`;
- `redfish_password`;
- `use_mock`;
- `is_archived`;
- `archived_at`;
- `description`;
- `status`;
- `health_score`;
- `first_seen`;
- `last_seen`.

`source_type` может быть:

- `local`;
- `agent`;
- `ilo`;
- `idrac`.

#### `metrics`

Основная таблица временных рядов:

- `id`;
- `node_id`;
- `timestamp`;
- `cpu_percent`;
- `ram_percent`;
- `disk_percent`;
- `bytes_sent`;
- `bytes_recv`;
- `network_sent_per_sec`;
- `network_recv_per_sec`.

#### `hardware_metrics`

История аппаратного состояния iLO/iDRAC:

- `id`;
- `node_id`;
- `created_at`;
- `power_state`;
- `hardware_health`;
- `temperature_c`;
- `fans_health`;
- `power_supplies_health`;
- `summary`;
- `raw_json`.

#### `enrollment_keys`

Ключи первичного подключения агентов:

- `id`;
- `organization_id`;
- `created_by_user_id`;
- `name`;
- `key_hash`;
- `prefix`;
- `is_active`;
- `max_uses`;
- `used_count`;
- `expires_at`;
- `created_at`;
- `last_used_at`.

Открытый ключ в базе не хранится. Хранится только hash и prefix.

#### `agent_tokens`

Токены агентов для дальнейшей telemetry:

- `id`;
- `node_id`;
- `token_hash`;
- `prefix`;
- `is_active`;
- `created_at`;
- `last_used_at`.

Открытый agent token в базе не хранится.

#### `process_snapshots`

Снимок процессов при высокой нагрузке:

- `id`;
- `node_id`;
- `created_at`;
- `reason`.

#### `process_snapshot_items`

Процессы внутри снимка:

- `id`;
- `snapshot_id`;
- `pid`;
- `name`;
- `cpu_percent`;
- `memory_percent`.

### 4.3 Безопасные миграции SQLite

Проект не использует Alembic. Вместо этого в `backend/node_manager.py` есть простые функции, которые через `PRAGMA table_info` проверяют наличие колонок и добавляют их через `ALTER TABLE`.

Это удобно для дипломного прототипа, но для промышленного проекта лучше использовать Alembic.

---

## 5. API

Ниже перечислены endpoint’ы, найденные в `backend/main.py`.

### 5.1 Авторизация

#### `POST /api/auth/login`

Назначение: вход пользователя.

Request:

```json
{
  "username": "admin",
  "password": "admin123"
}
```

Response:

```json
{
  "access_token": "jwt...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.local",
    "organizations": [
      {
        "id": 1,
        "name": "Default Organization",
        "role": "owner"
      }
    ]
  }
}
```

Используется frontend для login screen.

#### `GET /api/auth/me`

Назначение: получить текущего пользователя по JWT.

Используется frontend при загрузке страницы, если в `localStorage` есть access token.

### 5.2 Пользователи и организация

#### `GET /api/organization/members`

Назначение: список участников текущей организации.

Response:

```json
[
  {
    "user_id": 1,
    "username": "admin",
    "email": "admin@example.local",
    "role": "owner",
    "user_created_at": "2026-05-20T12:00:00",
    "member_created_at": "2026-05-20T12:00:00"
  }
]
```

#### `POST /api/organization/members`

Назначение: создать пользователя или добавить существующего пользователя в организацию.

Request:

```json
{
  "username": "ivan",
  "password": "TempPassword123",
  "role": "viewer"
}
```

#### `PATCH /api/organization/members/{user_id}`

Назначение: изменить роль участника.

Request:

```json
{
  "role": "admin"
}
```

#### `DELETE /api/organization/members/{user_id}`

Назначение: удалить membership. Сам пользователь физически не удаляется.

Response:

```json
{
  "status": "removed"
}
```

#### `POST /api/organization/transfer-ownership`

Назначение: передача роли owner другому участнику.

Request:

```json
{
  "user_id": 12
}
```

### 5.3 Enrollment keys

#### `GET /api/enrollment-keys`

Назначение: получить ключи подключения организаций пользователя.

Response:

```json
[
  {
    "id": 1,
    "name": "Windows servers",
    "prefix": "smk_enroll_xxxxx",
    "is_active": true,
    "max_uses": 10,
    "used_count": 0,
    "expires_at": "2026-06-20T12:00:00",
    "created_at": "2026-05-20T12:00:00",
    "last_used_at": null
  }
]
```

#### `POST /api/enrollment-keys`

Назначение: создать enrollment key.

Request:

```json
{
  "name": "Windows servers",
  "max_uses": 10,
  "expires_days": 30
}
```

Response:

```json
{
  "id": 1,
  "name": "Windows servers",
  "key": "smk_enroll_...",
  "message": "Сохраните ключ, повторно он показан не будет"
}
```

Открытый ключ возвращается только один раз.

#### `POST /api/enrollment-keys/{key_id}/revoke`

Назначение: отозвать ключ.

Response:

```json
{
  "status": "revoked"
}
```

### 5.4 Download Center

#### `POST /api/downloads/agent`

Назначение: скачать готовый файл агента.

Request:

```json
{
  "platform_type": "windows_desktop",
  "enrollment_key_id": 1,
  "enrollment_key": "smk_enroll_..."
}
```

Поддерживаемые `platform_type`:

- `windows_desktop`;
- `windows_server`;
- `linux_gui`;
- `linux_server`.

Backend проверяет:

- JWT;
- роль owner/admin;
- принадлежность ключа организации;
- активность ключа;
- срок действия;
- соответствие открытого key хэшу в БД.

Затем отдаёт файл из `backend/downloads/agents/`:

- `agent-windows.exe`;
- `agent-windows-server.exe`;
- `agent-linux-gui`;
- `agent-linux-server`.

Если файл не собран, возвращается понятная ошибка `404`.

#### `POST /api/downloads/agent/windows`

Compatibility endpoint для Windows desktop.

#### `POST /api/downloads/agent/linux`

Compatibility endpoint для Linux GUI.

### 5.5 Compatibility endpoint’ы локальных метрик

Эти endpoint’ы оставлены для обратной совместимости и работают через Local System.

#### `GET /api/metrics/current`

Возвращает текущие локальные метрики и сохраняет новую точку.

Пример:

```json
{
  "id": 100,
  "node_id": 1,
  "timestamp": "2026-05-20T12:00:00",
  "cpu_percent": 12.5,
  "ram_percent": 54.1,
  "disk_percent": 70.2,
  "bytes_sent": 123456,
  "bytes_recv": 654321,
  "network_sent_per_sec": 1024,
  "network_recv_per_sec": 2048
}
```

#### `GET /api/metrics/history?limit=N`

Возвращает историю Local System.

#### `GET /api/metrics/summary?limit=N`

Возвращает средние и максимальные значения CPU/RAM/Disk.

#### `GET /api/analysis/summary?limit=N`

Возвращает analysis summary для Local System.

### 5.6 App config

#### `GET /api/app/config`

Назначение: отдать frontend интервалы и лимиты.

Response:

```json
{
  "metrics_collect_interval_seconds": 5,
  "frontend_refresh_interval_seconds": 3,
  "normal_refresh_interval_seconds": 5,
  "alert_refresh_interval_seconds": 2,
  "history_limit_records": 200
}
```

### 5.7 Agent API

#### `POST /api/agents/register`

Старый dev/local endpoint регистрации агента. Сохранён для обратной совместимости.

#### `POST /api/agents/enroll`

Продуктовый endpoint первичного подключения агента.

Request:

```json
{
  "enrollment_key": "smk_enroll_...",
  "agent_name": "SERVER-01",
  "hostname": "SERVER-01",
  "os_name": "Windows Server 2022",
  "agent_version": "0.1.0"
}
```

Response:

```json
{
  "node_id": 12,
  "agent_token": "smk_agent_...",
  "config": {
    "send_interval_seconds": 5,
    "process_snapshot_enabled": true,
    "process_snapshot_cooldown_seconds": 30
  }
}
```

#### `POST /api/telemetry`

Назначение: приём telemetry от агента.

Требует `Authorization: Bearer <agent_token>`.

Request:

```json
{
  "node_id": 12,
  "timestamp": "2026-05-20T12:00:00",
  "cpu_percent": 10.5,
  "ram_percent": 50.2,
  "disk_percent": 70.1,
  "bytes_sent": 123456,
  "bytes_recv": 654321
}
```

Важно: backend не доверяет `node_id` из тела, а определяет узел по agent token.

#### `POST /api/process-snapshots`

Назначение: приём top-N процессов от агента при высокой CPU/RAM нагрузке.

Требует `Authorization: Bearer <agent_token>`.

Request:

```json
{
  "node_id": 12,
  "reason": "cpu_high",
  "items": [
    {
      "pid": 1234,
      "name": "chrome.exe",
      "cpu_percent": 25.5,
      "memory_percent": 12.3
    }
  ]
}
```

### 5.8 Nodes API

#### `GET /api/nodes?include_archived=false`

Назначение: список узлов, доступных пользователю по организации.

Response:

```json
[
  {
    "id": 1,
    "organization_id": 1,
    "name": "Local System",
    "hostname": "DESKTOP",
    "source_type": "local",
    "os_name": "Windows Windows-10...",
    "agent_version": null,
    "management_ip": null,
    "use_mock": false,
    "is_archived": false,
    "archived_at": null,
    "description": null,
    "status": "online",
    "health_score": 90,
    "first_seen": "2026-05-20T12:00:00",
    "last_seen": "2026-05-20T12:00:00"
  }
]
```

#### `GET /api/nodes/{node_id}`

Назначение: получить информацию об узле.

#### `PATCH /api/nodes/{node_id}`

Назначение: переименовать узел и изменить описание.

Request:

```json
{
  "name": "New name",
  "description": "Описание узла"
}
```

#### `POST /api/nodes/{node_id}/archive`

Назначение: архивировать узел. Физического удаления нет.

#### `POST /api/nodes/{node_id}/restore`

Назначение: восстановить архивный узел.

#### `DELETE /api/nodes/{node_id}`

Alias для archive.

#### `POST /api/nodes/{node_id}/clear-history`

Назначение: очистить историю узла:

- `metrics`;
- `hardware_metrics`;
- `process_snapshots`;
- `process_snapshot_items`.

Response:

```json
{
  "deleted_metrics": 100,
  "deleted_hardware_metrics": 5,
  "deleted_process_snapshots": 2,
  "deleted_process_snapshot_items": 10
}
```

#### `POST /api/nodes/{node_id}/refresh`

Назначение:

- для `local/agent` возвращает последние данные push-модели;
- для `ilo/idrac` выполняет Redfish poll.

### 5.9 Node-aware metrics API

#### `GET /api/nodes/{node_id}/metrics/current`

Назначение: текущая метрика конкретного узла.

Для Local System вызывает локальный сборщик. Для agent возвращает последнюю полученную метрику.

#### `GET /api/nodes/{node_id}/metrics/history?limit=N`

Назначение: история конкретного узла.

#### `GET /api/nodes/{node_id}/metrics/summary?limit=N`

Назначение: сводка по последним N точкам:

- records count;
- average CPU;
- max CPU;
- average RAM;
- max RAM;
- average Disk;
- max Disk.

#### `GET /api/nodes/{node_id}/analysis/summary?limit=N`

Назначение: лёгкий analysis summary + вложенный diagnostics.

#### `GET /api/nodes/{node_id}/diagnostics?limit=N`

Назначение: полноценная диагностическая карточка.

### 5.10 Hardware / iLO / iDRAC API

#### `POST /api/nodes/redfish`

Назначение: добавить аппаратный источник.

Request:

```json
{
  "name": "DELL-SERVER-01",
  "source_type": "idrac",
  "management_ip": "192.168.1.100",
  "username": "root",
  "password": "password",
  "use_mock": true
}
```

Response:

```json
{
  "node_id": 4,
  "status": "created",
  "source_type": "idrac"
}
```

#### `POST /api/nodes/{node_id}/poll-redfish`

Назначение: выполнить опрос Redfish-источника и сохранить hardware metric.

#### `GET /api/nodes/{node_id}/hardware/latest`

Назначение: последняя аппаратная запись.

#### `GET /api/nodes/{node_id}/hardware/history?limit=N`

Назначение: история аппаратных записей.

### 5.11 Process snapshots API

#### `GET /api/nodes/{node_id}/process-snapshots/latest`

Назначение: последний снимок процессов.

#### `GET /api/nodes/{node_id}/process-snapshots?limit=N`

Назначение: история снимков процессов.

### 5.12 Подробные live-метрики backend-машины

Эти endpoint’ы используются на странице «Подробные метрики» только для Local System:

- `GET /api/system/info`;
- `GET /api/system/cpu`;
- `GET /api/system/memory`;
- `GET /api/system/disks`;
- `GET /api/system/network`;
- `GET /api/system/processes?limit=10&sort=cpu`.

---

## 6. Frontend

### 6.1 Технологии frontend

Frontend написан на:

- Vue 3;
- Composition API;
- Vite;
- обычный CSS;
- `fetch` для API-запросов.

Файлы:

- `frontend/src/App.vue`;
- `frontend/src/main.js`;
- `frontend/src/styles.css`.

Проект не использует Vue Router. Навигация реализована внутренним состоянием `activePage`, `selectedNodeId` и History API.

### 6.2 Реализованные экраны

#### Login screen

Показывается, если нет JWT access token.

Функции:

- ввод username/password;
- запрос `/api/auth/login`;
- сохранение token в `localStorage`;
- загрузка `/api/auth/me`.

#### Список систем

Главный экран после входа.

Показывает:

- Local System;
- Agent nodes;
- HPE iLO;
- Dell iDRAC;
- status badge;
- source type;
- health score;
- hostname;
- description;
- last seen;
- quick actions.

Действия:

- открыть узел;
- переименовать;
- обновить;
- очистить историю;
- архивировать;
- восстановить;
- добавить Redfish-источник.

#### Страница выбранного узла

Старый dashboard стал страницей конкретного узла.

Для `local/agent` отображает:

- карточки CPU/RAM/Disk/Network;
- предупреждения;
- Health Score;
- bottleneck;
- diagnostics;
- process snapshot;
- summary;
- графики CPU/RAM;
- выбор лимита истории;
- режим «все точки / оптимизированное отображение»;
- режим сравнения.

Для `ilo/idrac` отображает:

- аппаратное состояние;
- diagnostics по hardware metrics;
- кнопку Redfish poll.

#### Подробные метрики

Доступны только для Local System:

- system info;
- CPU cores;
- memory;
- disks;
- network interfaces;
- processes.

Для agent-узлов отображается сообщение, что live-метрики доступны только для Local System, а agent-узлы используют telemetry history.

#### Ключи подключения

Показывает:

- список enrollment keys;
- masked/reveal/copy;
- создание ключа;
- отзыв ключа;
- used/max uses;
- expiration.

Открытый ключ сохраняется только локально в браузере после создания.

#### Users

Показывает:

- участников организации;
- роли;
- создание пользователя;
- изменение роли;
- удаление membership;
- передачу ownership.

#### Download Center

Позволяет выбрать:

- Windows;
- Windows Server;
- Linux GUI;
- Linux Server.

Проверяет enrollment key и скачивает готовый файл агента из backend.

### 6.3 Обновление данных

В `frontend/src/App.vue` реализованы:

- `isInitialLoading`;
- `isBackgroundRefreshing`;
- `refreshError`;
- `lastUpdated`;
- `loadOverview()`;
- `restartOverviewTimer()`;
- `applyAdaptiveRefreshInterval()`.

При фоновом обновлении интерфейс не очищает старые данные. Это важно для UX и диплома: система не мигает при обновлении telemetry, а обновляет данные после успешного ответа.

### 6.4 Авторизация и роли во frontend

Frontend хранит JWT в `localStorage`:

- ключ: `system-monitor-access-token`.

Все защищённые запросы идут через `apiFetch()`, который добавляет:

```http
Authorization: Bearer <token>
```

Если backend возвращает `401`, frontend вызывает `logout()`.

Роль берётся из первой организации пользователя:

- `selectedOrganization`;
- `canManageNodes`;
- `canManageUsers`;
- `isOwner`.

Ограничения frontend:

- owner/admin видят кнопки управления;
- viewer не должен видеть management-действия;
- фактическая защита всё равно выполняется на backend.

---

## 7. Оптимизация визуализации

Это один из центральных пунктов ВКР.

### 7.1 Где реализован downsampling

Downsampling реализован во frontend:

Файл:

- `frontend/src/App.vue`

Функция:

```js
function downsampleMetrics(data, targetCount) {
  if (!Array.isArray(data) || data.length <= targetCount) {
    return data
  }

  const result = [data[0]]
  const middleCount = targetCount - 2
  const step = (data.length - 2) / middleCount

  for (let index = 1; index <= middleCount; index += 1) {
    const sourceIndex = Math.round(index * step)
    result.push(data[sourceIndex])
  }

  result.push(data[data.length - 1])
  return result
}
```

Особенности алгоритма:

- если точек меньше лимита, массив не изменяется;
- первая точка сохраняется;
- последняя точка сохраняется;
- промежуточные точки выбираются равномерно;
- алгоритм простой и объяснимый;
- не требует дополнительных библиотек;
- снижает количество SVG-точек на графике.

### 7.2 Ограничение количества точек

Во frontend:

- `historyLimitOptions = [20, 50, 100, 200]`;
- `selectedHistoryLimit = 50`;
- `targetChartPoints = 60`.

Пользователь выбирает, сколько точек запросить с backend:

```http
GET /api/nodes/{node_id}/metrics/history?limit=N
```

Если получено больше `targetChartPoints`, применяется downsampling.

### 7.3 Режимы отображения

Реализованы:

- **Все точки**;
- **Оптимизированное отображение**;
- **Сравнение режимов**.

Во frontend:

- `isOptimizedView`;
- `isComparisonMode`;
- `optimizedHistory`;
- `displayedHistory`;
- `pointsReductionPercent`.

Интерфейс показывает:

- сколько точек получено;
- сколько точек отображено;
- процент сокращения;
- график со всеми точками;
- график после downsampling.

### 7.4 Как снижается нагрузка на браузер

Снижение нагрузки происходит за счёт:

1. Ограничения `limit` при запросе истории.
2. Downsampling перед построением SVG polyline.
3. Отрисовки только CPU/RAM, а не всех возможных метрик одновременно.
4. Разделения initial loading и background refresh.
5. Адаптивного интервала обновления.
6. Отсутствия постоянного потока WebSocket-сообщений.
7. Process snapshot отправляется только при высокой нагрузке, а не постоянно.

### 7.5 Адаптивная частота обновления

Backend в `analysis.py` возвращает:

```json
{
  "current_refresh_interval": 2
}
```

Логика:

- если есть предупреждения или аномалии, используется `alert_refresh_interval_seconds`;
- если система стабильна, используется `normal_refresh_interval_seconds`.

Frontend использует:

```js
const refreshIntervalMs = computed(() => (
  (analysis.value?.current_refresh_interval
    || appConfig.value?.frontend_refresh_interval_seconds
    || 3) * 1000
))
```

Если интервал изменился, вызывается `restartOverviewTimer()`.

### 7.6 Что можно написать в дипломе

В дипломе можно описать «адаптивную визуализацию временных рядов»:

- входной поток telemetry может расти;
- отображение всех точек ухудшает производительность интерфейса;
- поэтому вводится клиентский downsampling;
- алгоритм сохраняет первую и последнюю точки;
- промежуточные точки выбираются равномерно;
- пользователь может сравнить полный и оптимизированный график;
- система показывает процент сокращения точек;
- подход не меняет данные в БД, а оптимизирует только визуальное представление.

Ограничение: это не LTTB и не статистическая агрегация. Алгоритм простой, но хорошо подходит для дипломного проекта, потому что легко объясняется и демонстрируется.

---

## 8. Анализ состояния системы

### 8.1 Что реализовано

Реализован автоматический backend-анализ:

- summary по метрикам;
- trend analysis;
- anomaly detection;
- bottleneck detection;
- system health score;
- diagnostics card;
- recommendations;
- evidence;
- hardware diagnostics для iLO/iDRAC;
- process snapshot evidence для CPU/RAM.

### 8.2 Где реализовано

Файлы:

- `backend/analysis.py`;
- `backend/diagnostics.py`;
- `backend/main.py`;
- `frontend/src/App.vue`.

### 8.3 Severity

В `backend/diagnostics.py` используются пороги:

CPU:

- normal: <= 70;
- warning: > 70 и <= 85;
- critical: > 85.

RAM:

- normal: <= 75;
- warning: > 75 и <= 90;
- critical: > 90.

Disk:

- normal: <= 85;
- warning: > 85 и <= 95;
- critical: > 95.

Network:

- мягкая оценка через отклонение от среднего.

### 8.4 Тренды

В `calculate_trend(values)`:

- берётся первое 30% окна;
- берётся последнее 30% окна;
- сравниваются средние значения;
- если разница > 5, trend = `rising`;
- если < -5, trend = `falling`;
- иначе `stable`.

### 8.5 Anomaly Detection

В `detect_anomaly(values, current_value, threshold)`:

- если меньше 5 записей, anomaly = false;
- иначе текущее значение сравнивается со средним;
- если отклонение больше порога, anomaly = true.

### 8.6 Persistence

В `calculate_persistence()`:

- если последние 4-5 значений подряд выше warning-порога, состояние `persistent`;
- если последние 1-2 значения выше warning, но раньше было нормально, `short_spike`;
- иначе `normal`.

### 8.7 Bottleneck

В `detect_bottleneck()`:

- если повышены две и более метрики, bottleneck = `combined`;
- если повышена одна, bottleneck = эта метрика;
- если всё normal, bottleneck = `none`.

### 8.8 System state

В `detect_system_state()`:

- critical, если есть critical;
- degraded, если есть persistent warning;
- unstable, если есть anomaly;
- warning, если есть warning;
- recovery, если есть falling после warning/critical;
- normal иначе.

### 8.9 Health Score

В `calculate_health_score()`:

```text
weighted_load = cpu * 0.35 + ram * 0.35 + disk * 0.2 + network_score * 0.1
health_score = 100 - weighted_load
```

Дополнительно score уменьшается при:

- anomaly;
- persistent critical;
- persistent warning.

### 8.10 Что можно усилить для диплома

Желательные доработки:

- добавить хранение диагностических событий в отдельную таблицу;
- добавить backend-side downsampling endpoint;
- добавить более строгую сетевую нормализацию;
- добавить графические маркеры аномалий на графике;
- добавить экспорт отчёта диагностики;
- добавить тестовые сценарии нагрузки.

---

## 9. Пользователи и устройства

### 9.1 Пользователи

Реализована модель:

```text
User -> OrganizationMember -> Organization -> Node
```

Файлы:

- `backend/models.py`;
- `backend/auth.py`;
- `backend/main.py`;
- `frontend/src/App.vue`.

### 9.2 Роли

Роли организации:

- `owner`;
- `admin`;
- `viewer`.

Права:

- owner: полный доступ, управление участниками, transfer ownership;
- admin: управление узлами, ключами, пользователями viewer/admin, Download Center;
- viewer: просмотр систем, метрик и диагностики.

В коде роли проверяются backend helper’ами:

- `require_org_role()`;
- `require_org_admin_or_owner()`;
- `primary_writable_organization_id()`;
- `user_organization_ids()`.

### 9.3 API tokens

Есть два вида токенов:

#### JWT пользователя

Используется web-интерфейсом:

- `/api/auth/login`;
- `/api/auth/me`;
- защищённые node/user/key/download endpoint’ы.

#### Agent token

Используется агентом:

- `/api/telemetry`;
- `/api/process-snapshots`.

Хранится в БД только как hash.

### 9.4 Enrollment key

Enrollment key используется только для первичной привязки агента:

1. owner/admin создаёт key.
2. Открытый key показывается один раз.
3. Агент вызывает `/api/agents/enroll`.
4. Backend выдаёт `agent_token`.
5. Агент дальше работает по `agent_token`.

### 9.5 Добавление устройств

Реализованные способы:

- Local System создаётся автоматически;
- Agent node создаётся через enrollment;
- iLO/iDRAC node создаётся через `/api/nodes/redfish`;
- узлы можно архивировать, восстанавливать, переименовывать, очищать историю.

### 9.6 Что пока частично

- Нет полноценной регистрации пользователей через публичную форму.
- Нет приглашений по email.
- Нет выбора нескольких организаций во frontend, используется первая организация пользователя.
- Нет refresh token.
- Нет полноценного audit log.

---

## 10. Агент и развёртывание

### 10.1 Как работает агент

Файл:

- `agent/agent.py`.

Логика:

1. Загружает `config.json`.
2. Если файла нет, пытается взять:
   - `SYSTEM_MONITOR_SERVER_URL`;
   - `SYSTEM_MONITOR_ENROLLMENT_KEY`;
   - `SYSTEM_MONITOR_AGENT_NAME`.
3. Если запуск интерактивный, спрашивает server URL, enrollment key и имя агента.
4. Загружает `agent_state.json`.
5. Если нет `node_id` или `agent_token`, выполняет enroll.
6. Сохраняет `agent_state.json`.
7. В цикле собирает telemetry.
8. Отправляет telemetry на backend.
9. При высокой CPU/RAM нагрузке отправляет process snapshot с cooldown.

### 10.2 Метрики агента

Файл:

- `agent/metrics_collector.py`.

Собирает:

- CPU percent;
- RAM percent;
- Disk percent;
- bytes sent;
- bytes recv;
- hostname;
- os_name;
- timestamp;
- top processes при необходимости.

### 10.3 EXE-сборка агента

Добавлены build-скрипты:

- `agent/build_windows.ps1`;
- `agent/build_linux.sh`.

Windows build:

- собирает `agent-windows.exe`;
- копирует его в `backend/downloads/agents/agent-windows.exe`;
- копирует тот же exe как `agent-windows-server.exe`.

Linux build:

- собирает `agent-linux-gui`;
- копирует как `agent-linux-gui`;
- копирует как `agent-linux-server`.

Ограничение:

- PyInstaller не является полноценным cross-compiler. Linux-бинарники нужно собирать в Linux-среде.
- Windows Server сейчас получает отдельное имя файла, но полноценный Windows Service installer не реализован в текущем коде.
- Linux Server сейчас получает отдельное имя файла, но systemd install.sh больше не генерируется backend’ом после перехода на скачивание одиночных файлов.

### 10.4 Сборка backend + frontend в exe

Файлы:

- `build/SystemMonitor.spec`;
- `build/build_exe.ps1`;
- `backend/run.py`.

`build/build_exe.ps1`:

1. Собирает frontend через `npm run build`.
2. Копирует результат в `static/`.
3. Проверяет PyInstaller.
4. Запускает PyInstaller по spec-файлу.
5. Копирует `config.json`, `static` и `database` рядом с exe.

`backend/run.py`:

- запускает uvicorn;
- автоматически открывает браузер.

### 10.5 Download Center

Frontend:

- `openDownloadModal()`;
- `downloadAgentPackage()`;
- `downloadPlatformOptions`.

Backend:

- `POST /api/downloads/agent`;
- `AGENT_DOWNLOAD_DIR`;
- `AGENT_BINARY_FILES`;
- `agent_binary_response()`.

Download Center отдаёт не zip, а готовые одиночные файлы, если они собраны.

---

## 11. Поддержка iDRAC и HPE iLO

### 11.1 Что реализовано

Реализованы:

- модель `Node` с `source_type = ilo/idrac`;
- поля `management_ip`, `redfish_username`, `redfish_password`, `use_mock`;
- модель `HardwareMetric`;
- endpoint добавления Redfish-узла;
- endpoint Redfish poll;
- endpoint latest/history hardware;
- диагностика hardware metrics;
- frontend-страница аппаратного состояния;
- mock-ответы для iLO/iDRAC.

### 11.2 Что реально работает

Без физического сервера работает демонстрационный сценарий:

- добавить iDRAC;
- добавить HPE iLO;
- увидеть аппаратные метрики;
- увидеть diagnostics;
- выполнить poll.

Фактически UI сейчас по умолчанию отправляет `use_mock: true`, хотя пользователю это не показывается.

### 11.3 Что частично реализовано

`backend/redfish_client.py` содержит базовый Redfish-клиент, но интеграция с реальным оборудованием требует проверки на физическом сервере:

- корректные credentials;
- доступность Redfish endpoint;
- SSL;
- структура Redfish-ответов конкретного производителя;
- дополнительные endpoint’ы Power/Thermal/Chassis.

Поле `power_supplies_health` в реальном клиенте сейчас возвращается как `Unknown`, то есть блок питания полноценно не парсится из Redfish Power endpoint.

### 11.4 Что не реализовано

Не реализованы:

- управление питанием;
- BIOS;
- RAID;
- firmware;
- remote console;
- Redfish event subscription;
- хранение credentials в зашифрованном виде.

Для ВКР это можно честно описать как архитектурную подготовку и мониторинг состояния, а не управление серверным оборудованием.

---

## 12. Соответствие структуре диплома

### 2.1 Архитектура системы

Что реализовано:

- клиент-серверная архитектура;
- центральный backend;
- Vue web UI;
- SQLite хранилище;
- Local System;
- Monitoring Agent;
- Redfish sources.

Файлы:

- `backend/main.py`;
- `frontend/src/App.vue`;
- `agent/agent.py`;
- `backend/models.py`;
- `backend/database.py`;
- `backend/redfish_client.py`.

Что использовать в дипломе:

- схему `Monitoring Agent / Redfish source -> Central Backend -> Database -> Web UI`;
- описание node-aware архитектуры;
- описание разделения сбора и анализа.

Чего не хватает:

- C4 diagram;
- sequence diagram enrollment;
- deployment diagram.

Желательно доработать:

- добавить диаграммы;
- явно описать границы Local/Agent/Redfish.

### 2.2 Проектирование структуры хранения данных

Что реализовано:

- SQLAlchemy-модели;
- таблицы users/organizations/nodes/metrics/hardware/process snapshots/keys/tokens;
- связи `Organization -> Node`, `Node -> Metric`, `Node -> HardwareMetric`.

Файлы:

- `backend/models.py`;
- `backend/database.py`;
- `backend/node_manager.py`.

Что использовать:

- ER-диаграмму;
- описание временных рядов;
- описание ключей и токенов.

Чего не хватает:

- Alembic migrations;
- индексы описаны частично;
- нет retention policy для agent metrics.

Желательно доработать:

- добавить retention для agent telemetry;
- добавить ER-схему.

### 2.3 Проектирование серверной части системы

Что реализовано:

- FastAPI-приложение;
- REST API;
- background worker;
- auth;
- diagnostics;
- Redfish;
- downloads.

Файлы:

- `backend/main.py`;
- `backend/auth.py`;
- `backend/analysis.py`;
- `backend/diagnostics.py`;
- `backend/metrics_collector.py`.

Что использовать:

- описание слоёв backend;
- описание dependency `get_db`;
- описание JWT и agent token.

Чего не хватает:

- сервисного слоя отдельно от `main.py`;
- unit tests.

Желательно доработать:

- вынести часть endpoint-логики в сервисы;
- добавить тесты API.

### 2.4 Проектирование API

Что реализовано:

- endpoints авторизации;
- endpoints пользователей;
- endpoints узлов;
- endpoints telemetry;
- endpoints analysis/diagnostics;
- endpoints hardware;
- endpoints downloads.

Файлы:

- `backend/main.py`;
- `backend/schemas.py`.

Что использовать:

- таблицу endpoint’ов из раздела 5;
- примеры JSON.

Чего не хватает:

- OpenAPI-скриншот;
- Postman/HTTPie коллекция.

Желательно доработать:

- добавить раздел API testing;
- сделать скриншот `/docs`.

### 2.5 Проектирование пользовательского интерфейса

Что реализовано:

- login screen;
- systems page;
- node details;
- diagnostics panel;
- keys page;
- users page;
- Download Center;
- responsive CSS.

Файлы:

- `frontend/src/App.vue`;
- `frontend/src/styles.css`.

Что использовать:

- макеты экранов;
- описание dashboard;
- описание ролей и visibility.

Чего не хватает:

- отдельные Vue-компоненты;
- дизайн-система;
- UI-тесты.

Желательно доработать:

- разбить `App.vue` на компоненты;
- добавить скриншоты для ВКР.

### 2.6 Особенности визуализации и обработки данных

Что реализовано:

- графики CPU/RAM;
- downsampling;
- режим сравнения;
- adaptive refresh;
- diagnostics;
- tooltips;
- warnings.

Файлы:

- `frontend/src/App.vue`;
- `backend/analysis.py`;
- `backend/diagnostics.py`.

Что использовать:

- описание downsampling;
- формулы health score;
- правила anomaly/trend/bottleneck.

Чего не хватает:

- backend-side aggregation/downsampling;
- маркеры аномалий на графике.

Желательно доработать:

- добавить визуальные маркеры anomalies;
- добавить экспорт графиков/отчёта.

### 2.7 Производительность, масштабируемость и надёжность

Что реализовано:

- ограничение history limit;
- downsampling;
- adaptive refresh;
- process snapshot по событию;
- SQLite safe init;
- archive вместо физического удаления.

Файлы:

- `frontend/src/App.vue`;
- `backend/metrics_collector.py`;
- `backend/node_manager.py`;
- `backend/main.py`.

Что использовать:

- объяснение снижения нагрузки на браузер;
- объяснение лёгкого агента;
- объяснение ограничений SQLite.

Чего не хватает:

- load testing;
- PostgreSQL;
- очереди сообщений;
- retry queue на агенте.

Желательно доработать:

- retention для agent metrics;
- тест нагрузки;
- логирование ошибок.

### 3.1 Реализация серверной части системы

Что реализовано:

- FastAPI server;
- SQLAlchemy;
- background local metrics worker;
- REST API;
- auth;
- nodes management;
- telemetry.

Файлы:

- `backend/main.py`;
- `backend/database.py`;
- `backend/models.py`;
- `backend/auth.py`.

Что использовать:

- фрагменты endpoint’ов;
- описание startup;
- описание фонового сбора.

Чего не хватает:

- automated API tests.

### 3.2 Реализация клиентской части и визуализации данных

Что реализовано:

- Vue dashboard;
- карточки;
- графики;
- таблицы;
- diagnostics UI;
- responsive layout;
- login.

Файлы:

- `frontend/src/App.vue`;
- `frontend/src/styles.css`.

Что использовать:

- скриншоты:
  - login;
  - systems;
  - node overview;
  - diagnostics;
  - comparison mode;
  - keys;
  - users;
  - hardware node.

Чего не хватает:

- component decomposition.

### 3.3 Реализация механизмов анализа телеметрических данных и адаптивной оптимизации визуализации

Что реализовано:

- `analysis.py`;
- `diagnostics.py`;
- `downsampleMetrics()`;
- `adaptive refresh`;
- process snapshots;
- warnings.

Файлы:

- `backend/analysis.py`;
- `backend/diagnostics.py`;
- `frontend/src/App.vue`;
- `agent/agent.py`.

Что использовать:

- формулы;
- правила;
- алгоритм downsampling;
- пример JSON diagnostics.

Чего не хватает:

- автоматические тесты правил;
- графические маркеры anomalies.

### 3.4 Реализация локального исполняемого приложения и подготовка системы к развёртыванию

Что реализовано:

- PyInstaller spec;
- build script;
- static frontend;
- browser auto-open;
- agent build scripts;
- Download Center.

Файлы:

- `build/SystemMonitor.spec`;
- `build/build_exe.ps1`;
- `backend/run.py`;
- `agent/build_windows.ps1`;
- `agent/build_linux.sh`;
- `backend/downloads/agents/.gitkeep`.

Что использовать:

- описание сборки backend/frontend в exe;
- описание сборки агента;
- структура `static/`, `dist/`, `build/`.

Чего не хватает:

- реальная проверка Linux agent build в Linux;
- полноценный service installer для Windows/Linux.

### 3.5 Тестирование разработанной системы

Что уже проверялось по проекту ранее:

- `py -m compileall backend agent`;
- `npm run build`;
- запуск backend;
- login admin/admin123;
- node list;
- Local System;
- Agent node;
- iLO/iDRAC;
- diagnostics;
- Download Center;
- frontend UX fixes.

Что можно использовать:

- функциональное тестирование API;
- тестирование frontend build;
- тестирование сценариев:
  - login;
  - создание key;
  - enrollment агента;
  - telemetry;
  - диагностика;
  - clear-history;
  - archive/restore;
  - Redfish source.

Чего не хватает:

- формализованного test plan;
- unit/integration tests.

Желательно доработать:

- подготовить таблицу тест-кейсов;
- сделать скриншоты результатов.

### 3.6 Выводы по третьей главе

Что можно написать:

- реализована система центрального мониторинга;
- есть несколько типов источников;
- данные сохраняются в БД;
- frontend отображает историю и текущие значения;
- реализованы аналитические функции;
- реализована оптимизация визуализации;
- подготовлена сборка и агент.

Ограничения:

- SQLite подходит для прототипа;
- Redfish проверен через mock;
- нет ML;
- нет промышленных миграций;
- нет полноценного service installer;
- не реализованы push/WebSocket.

---

## 13. Итоговое техническое описание проекта

Проект представляет собой центральную систему визуализации и анализа телеметрии компьютерных систем. Backend на FastAPI принимает данные от локального сборщика и внешних агентов, хранит историю в SQLite через SQLAlchemy, выполняет rule-based анализ состояния узлов, формирует health score, определяет тренды, аномалии, узкие места и рекомендации. Frontend на Vue 3 отображает список контролируемых систем, страницы отдельных узлов, графики CPU/RAM, диагностические карточки, ключи подключения, пользователей организации и Download Center для агентов.

Ключевая особенность проекта для ВКР - оптимизация визуализации временных рядов. Интерфейс не обязан отображать все точки истории, если их слишком много. Вместо этого применяется равномерный downsampling с сохранением первой и последней точки. Пользователь может переключаться между полным и оптимизированным отображением, видеть количество полученных и реально отрисованных точек, а также процент сокращения. Это позволяет снизить нагрузку на браузер и сохранить общую форму графиков.

Вторая важная особенность - аналитическое ядро на backend. Система не просто показывает текущие проценты CPU/RAM/Disk, а анализирует последние N записей, определяет сценарий нагрузки, состояние системы, предполагаемое узкое место, признаки аномалий и устойчивости проблемы. Для аппаратных источников iLO/iDRAC используется отдельная логика анализа hardware health.

---

## 14. Сильные стороны проекта для ВКР

- Есть полноценная клиент-серверная архитектура.
- Есть история метрик, а не только текущие значения.
- Есть node-aware модель для нескольких систем.
- Есть Monitoring Agent.
- Есть организации, пользователи и роли.
- Есть enrollment key и agent token.
- Есть диагностика и health score.
- Есть поиск трендов, аномалий и узких мест.
- Есть process snapshot при высокой нагрузке.
- Есть подготовка iLO/iDRAC через Redfish.
- Есть оптимизация отображения графиков через downsampling.
- Есть режим сравнения полного и оптимизированного графика.
- Есть адаптивный refresh interval.
- Есть подготовка exe-сборки.
- Есть Download Center для агентов.

---

## 15. Слабые места и ограничения

- SQLite используется как прототипное хранилище; для промышленной версии лучше PostgreSQL.
- Нет Alembic migrations.
- Большая часть frontend находится в одном `App.vue`.
- Нет автоматических unit/integration tests.
- Redfish без физического сервера проверяется через mock.
- UI скрывает mock-режим, но backend всё ещё хранит `use_mock`.
- Credentials Redfish хранятся в БД как обычные поля, без шифрования.
- Agent не имеет локальной очереди telemetry при долгой недоступности backend.
- Retention policy для agent metrics не применяется автоматически в `receive_telemetry()`.
- Download Center отдаёт готовые файлы, но не встраивает open enrollment key в бинарник.
- Windows Server/Linux Server сейчас представлены отдельными файлами, но полноценная установка как служба/systemd требует доработки.
- Нет WebSocket, поэтому обновление идёт polling’ом.
- Нет ML, анализ rule-based. Для ВКР это скорее плюс по объяснимости, но важно честно указать.

---

## 16. Срочные доработки перед защитой

1. Добавить retention cleanup для agent telemetry в `/api/telemetry`.
2. Подготовить тест-кейсы и таблицу результатов.
3. Сделать скриншоты:
   - login;
   - список систем;
   - Local System dashboard;
   - Agent dashboard;
   - diagnostics;
   - comparison mode;
   - keys;
   - users;
   - Download Center;
   - iLO/iDRAC hardware page.
4. Проверить `py -m compileall backend agent`.
5. Проверить `npm run build`.
6. Проверить запуск backend.
7. Проверить создание enrollment key и запуск agent.
8. Проверить добавление iLO/iDRAC.
9. Обновить README, если в интерфейсе изменяются формулировки.
10. Подготовить диаграммы.

---

## 17. Какие схемы можно построить

### UML / C4

1. **C4 Context Diagram**  
   Пользователь, Web UI, Central Backend, Monitoring Agent, iLO/iDRAC, SQLite.

2. **C4 Container Diagram**  
   Vue frontend, FastAPI backend, SQLite database, Agent, Redfish source.

3. **Component Diagram backend**  
   `main.py`, `auth.py`, `analysis.py`, `diagnostics.py`, `metrics_collector.py`, `database.py`, `models.py`, `redfish_client.py`.

4. **Deployment Diagram**  
   Администраторский ПК/сервер с backend, браузер, удалённые agent-узлы, серверное оборудование iLO/iDRAC.

### ER-диаграмма

Таблицы:

- users;
- organizations;
- organization_members;
- nodes;
- metrics;
- hardware_metrics;
- enrollment_keys;
- agent_tokens;
- process_snapshots;
- process_snapshot_items.

Ключевые связи:

- Organization 1:N Nodes;
- Organization 1:N EnrollmentKeys;
- User N:M Organization через OrganizationMember;
- Node 1:N Metrics;
- Node 1:N HardwareMetrics;
- Node 1:N ProcessSnapshots;
- ProcessSnapshot 1:N ProcessSnapshotItems;
- Node 1:N AgentTokens.

### Sequence diagrams

1. **Login**
   - User -> Frontend -> `/api/auth/login` -> Backend -> DB -> JWT -> Frontend.

2. **Agent enrollment**
   - Admin creates enrollment key.
   - Agent -> `/api/agents/enroll`.
   - Backend checks key hash.
   - Backend creates Node and AgentToken.
   - Agent saves `agent_state.json`.

3. **Telemetry flow**
   - Agent -> `/api/telemetry`.
   - Backend validates agent token.
   - Backend saves Metric.
   - Frontend requests history/current/diagnostics.

4. **Dashboard refresh**
   - Frontend timer.
   - Requests current/history/summary/analysis/diagnostics.
   - Backend returns data.
   - Frontend applies downsampling.
   - UI updates without reset.

5. **Redfish hardware poll**
   - Frontend -> `/api/nodes/{id}/poll-redfish`.
   - Backend -> RedfishClient или mock source.
   - Backend saves HardwareMetric.
   - Frontend shows hardware diagnostics.

6. **Process snapshot**
   - Agent detects CPU/RAM high.
   - Agent collects top-5 processes.
   - Agent -> `/api/process-snapshots`.
   - Backend saves snapshot.
   - Diagnostics adds evidence/recommendations.

### Activity diagrams

1. Алгоритм downsampling.
2. Алгоритм diagnostics.
3. Алгоритм health score.
4. Алгоритм выбора refresh interval.
5. Алгоритм подключения агента.

---

## 18. Файлы, наиболее важные для пояснительной записки

- `backend/main.py` - REST API и orchestration.
- `backend/models.py` - модель данных.
- `backend/database.py` - SQLite/SQLAlchemy.
- `backend/config.py` - конфигурация и PyInstaller paths.
- `backend/auth.py` - JWT, роли, токены, хеширование.
- `backend/metrics_collector.py` - локальный сбор psutil.
- `backend/analysis.py` - базовая аналитика.
- `backend/diagnostics.py` - диагностическая карточка.
- `backend/system_info.py` - подробные live-метрики.
- `backend/redfish_client.py` - Redfish API client.
- `backend/mock_redfish.py` - демонстрационные аппаратные источники.
- `agent/agent.py` - логика агента.
- `agent/metrics_collector.py` - сбор telemetry на агенте.
- `agent/build_windows.ps1` - сборка Windows agent.
- `agent/build_linux.sh` - сборка Linux agent.
- `frontend/src/App.vue` - интерфейс, страницы, API-запросы, downsampling, charts.
- `frontend/src/styles.css` - визуальное оформление.
- `build/SystemMonitor.spec` - PyInstaller spec.
- `build/build_exe.ps1` - сборка приложения.
- `config.json` - интервалы, лимиты, пути, пороги.

