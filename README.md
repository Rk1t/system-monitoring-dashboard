# Система визуализации мониторинга данных компьютерных систем

## 1. Назначение проекта

Проект разрабатывается как ВКР на тему: **«Разработка модуля визуализации мониторинга данных компьютерных систем»**.

Итоговая версия представляет собой прототип централизованной системы мониторинга. Система собирает телеметрию с разных источников, хранит историю по каждому узлу отдельно, визуализирует данные в web-интерфейсе и формирует объяснимую диагностическую карточку состояния.

Основная идея проекта:

- центральный backend на FastAPI принимает и анализирует данные;
- web-интерфейс на Vue показывает список контролируемых систем;
- локальный компьютер представлен как `Local System`;
- внешние Windows/Linux-системы могут отправлять данные через легкий `Monitoring Agent`;
- серверное оборудование HPE iLO и Dell iDRAC подготовлено через Redfish API и mock-режим;
- анализ состояния выполняется на центральном backend, а не на агенте.

Проект сохраняет простую архитектуру, чтобы код можно было объяснить на защите: без микросервисов, Docker, WebSocket, PostgreSQL, ML/LLM и тяжелых аналитических библиотек. Для web-доступа используется простой JWT-login, а агенты подключаются через отдельные enrollment keys и agent tokens.

## 2. Итоговая архитектура

Архитектура проекта:

```text
Local System / Monitoring Agent / Redfish Source
                    |
                    v
          Central Backend FastAPI
                    |
                    v
          SQLite + SQLAlchemy
                    |
                    v
             Vue 3 Web UI
```

Компоненты:

- **Central Backend FastAPI**
  Центральный сервер приложения. Принимает телеметрию, хранит данные, отдает REST API, выполняет диагностику и обслуживает собранный frontend из папки `static`.

- **Vue 3 Web UI**
  Web-интерфейс администратора. Главный экран показывает список систем, а dashboard выбранного узла отображает метрики, графики, аппаратное состояние, диагностику и возможные процессы-причины.

- **SQLite / SQLAlchemy**
  SQLite используется как прототипное локальное хранилище. SQLAlchemy описывает модели и связи между таблицами. Для промышленного режима хранения лучше заменить SQLite на PostgreSQL или другую серверную СУБД.

- **Users / Organizations / Roles**
  Продуктовый слой доступа. Пользователь входит в систему, состоит в одной или нескольких организациях, а узлы мониторинга принадлежат организации.

- **Enrollment keys / Agent tokens**
  Продуктовая схема подключения агентов. Администратор создает одноразово отображаемый ключ подключения, агент использует его для первичной привязки к организации и получает отдельный token для дальнейшей отправки телеметрии.

- **Local System node**
  Узел, представляющий компьютер, на котором запущен backend. Создается автоматически при старте.

- **Monitoring Agent**
  Отдельный легкий агент в папке `agent/`. Запускается на контролируемой системе, собирает базовые метрики через `psutil` и отправляет их на backend.

- **HPE iLO / Dell iDRAC через Redfish**
  Аппаратные источники серверной телеметрии. На текущем этапе поддержан mock-режим для демонстрации без физического сервера и подготовлен клиент Redfish для дальнейшей интеграции.

## 3. Режимы источников данных

### Local System

`Local System` используется для локальной разработки и обратной совместимости. Backend сам собирает метрики текущего компьютера через `psutil`:

- CPU;
- RAM;
- Disk;
- Network.

При запуске backend автоматически создает локальный узел, если его нет, и привязывает к нему локальные метрики.

### Monitoring Agent

Agent запускается на отдельной контролируемой Windows/Linux-системе. Он:

- читает `agent/config.json`;
- при первом запуске проходит enrollment через `/api/agents/enroll`;
- получает `node_id` и `agent_token`;
- сохраняет runtime-данные в `agent_state.json`;
- собирает CPU/RAM/Disk/Network через `psutil`;
- отправляет телеметрию через `/api/telemetry` с Bearer agent token;
- при высокой CPU/RAM нагрузке отправляет top-5 процессов через `/api/process-snapshots` с Bearer agent token.

Agent не хранит историю локально и не выполняет диагностику. Это сделано специально: агент остается легким, а аналитическое ядро находится на центральном backend.

### HPE iLO / Dell iDRAC через Redfish mock/API

iLO и iDRAC являются аппаратными контроллерами удаленного мониторинга серверов. Проект не заменяет iLO/iDRAC, а подключается к ним как к источникам телеметрии.

Поддерживается:

- добавление mock HPE iLO;
- добавление mock Dell iDRAC;
- хранение аппаратных метрик;
- отображение аппаратного состояния во frontend;
- диагностика аппаратного узла по состоянию оборудования.

Через Redfish/Mock отображаются:

- `power_state`;
- `hardware_health`;
- `temperature_c`;
- `fans_health`;
- `power_supplies_health`;
- `summary`.

Важно: управление питанием, BIOS, RAID, firmware и удаленная консоль не реализованы. На текущем этапе это только мониторинг состояния.

## 4. Структура проекта

```text
backend/
  analysis.py
  config.py
  database.py
  diagnostics.py
  main.py
  metrics_collector.py
  mock_redfish.py
  models.py
  node_manager.py
  redfish_client.py
  requirements.txt
  run.py
  schemas.py
  system_info.py

agent/
  agent.py
  metrics_collector.py
  config.json
  README.md

frontend/
  index.html
  package.json
  vite.config.js
  src/
    App.vue
    main.js
    styles.css

static/
  index.html
  assets/

database/
  .gitkeep

build/
  SystemMonitor.spec
  build_exe.ps1

dist/
config.json
README.md
PROJECT_STATE.md
```

## 5. Структура backend

- `main.py`
  FastAPI-приложение, REST endpoints, регистрация агента, прием телеметрии, Redfish endpoints, process snapshot endpoints и отдача frontend.

- `models.py`
  SQLAlchemy-модели: `Node`, `Metric`, `HardwareMetric`, `ProcessSnapshot`, `ProcessSnapshotItem`.

- `schemas.py`
  Pydantic-схемы запросов и ответов API.

- `database.py`
  Подключение SQLite, создание `engine`, `SessionLocal` и зависимость `get_db`.

- `config.py`
  Чтение `config.json`, настройка путей для dev-режима и будущей PyInstaller-сборки.

- `metrics_collector.py`
  Локальный сбор базовых метрик через `psutil` для `Local System`.

- `analysis.py`
  Базовая аналитика: trends, anomalies, health score, bottleneck, adaptive refresh.

- `diagnostics.py`
  Правила автоматизированной диагностики узлов: severity, trend, anomaly, persistence, scenario, system state, evidence, recommendations.

- `node_manager.py`
  Создание локального узла, обновление `last_seen`, безопасная инициализация SQLite-структуры.

- `redfish_client.py`
  Легкий клиент Redfish API. Возвращает нормализованное аппаратное состояние или понятную ошибку.

- `mock_redfish.py`
  Mock-данные HPE iLO и Dell iDRAC для демонстрации без физического сервера.

- `system_info.py`
  Подробные live-метрики локальной системы: CPU, memory, disks, network, processes.

- `run.py`
  Точка запуска backend с автоматическим открытием браузера. Полезна для будущей сборки в `.exe`.

## 6. Структура agent

```text
agent/
  agent.py
  metrics_collector.py
  config.json
  README.md
```

- `agent.py`
  Загружает конфигурацию, выполняет enrollment при первом запуске, сохраняет runtime token в `agent_state.json`, отправляет телеметрию в цикле и при высокой нагрузке отправляет process snapshot.

- `metrics_collector.py`
  Сбор CPU/RAM/Disk/Network и выбор top-N процессов через `psutil`.

- `config.json`
  Настройки агента:

  ```json
  {
    "server_url": "http://127.0.0.1:8000",
    "enrollment_key": "smk_enroll_xxxxx",
    "agent_token": "",
    "node_id": null,
    "agent_name": "Test Agent",
    "send_interval_seconds": 5,
    "process_snapshot_cooldown_seconds": 30,
    "agent_version": "0.1.0"
  }
  ```

- `README.md`
  Отдельная инструкция по запуску и проверке агента.

## 7. Структура frontend

Frontend реализован на Vue 3 + Vite.

Основные файлы:

- `frontend/src/App.vue`
  Главный компонент приложения. Содержит экран списка систем, экран выбранного узла, графики, диагностику, аппаратный блок и process snapshot блок.

- `frontend/src/styles.css`
  Стили интерфейса.

- `frontend/src/main.js`
  Точка входа Vue-приложения.

Frontend не использует сложный роутинг. Навигация реализована через состояние:

- `activePage`;
- `selectedNodeId`;
- `selectedNode`.

Главный экран открывается со списка систем. Старый dashboard используется как страница выбранного узла.

## 8. Модель данных

### `nodes`

Таблица контролируемых систем.

Основные поля:

- `id` - идентификатор узла;
- `organization_id` - организация, которой принадлежит узел;
- `name` - отображаемое имя;
- `hostname` - имя компьютера или сервера;
- `source_type` - `local`, `agent`, `ilo`, `idrac`;
- `os_name` - операционная система или платформа;
- `agent_version` - версия агента;
- `management_ip` - IP аппаратного контроллера iLO/iDRAC;
- `redfish_username` - пользователь Redfish;
- `redfish_password` - пароль Redfish;
- `use_mock` - признак mock-режима Redfish;
- `is_archived` - признак архивного узла, который скрывается из основного списка;
- `archived_at` - время архивирования;
- `description` - текстовое описание узла для администратора;
- `status` - состояние узла;
- `health_score` - общий индекс состояния;
- `first_seen` - первое появление;
- `last_seen` - последнее обновление.

Для учебного прототипа Redfish credentials хранятся в SQLite. В промышленном режиме пароль должен храниться безопаснее: через переменные окружения, секреты или специализированное хранилище.

### `users`

Таблица пользователей web-хаба.

Поля:

- `id`;
- `username`;
- `email`;
- `password_hash`;
- `role_global`;
- `is_active`;
- `created_at`;
- `last_login`.

Пароль не хранится в открытом виде. Для хэширования используется `hashlib.pbkdf2_hmac` с salt.

### `organizations`

Таблица рабочих пространств. Организация может быть личным workspace одного пользователя или корпоративной организацией с несколькими участниками.

Поля:

- `id`;
- `name`;
- `created_at`.

### `organization_members`

Связь пользователей и организаций.

Поля:

- `id`;
- `organization_id`;
- `user_id`;
- `role`;
- `created_at`.

Роли внутри организации:

- `owner` - полный доступ, управление участниками, изменение ролей, удаление участников и передача владения;
- `admin` - добавление пользователей, управление ролями `viewer/admin`, управление узлами, enrollment keys, Download Center и iLO/iDRAC;
- `viewer` - только просмотр систем, метрик и диагностики.

В текущей версии создается стартовая организация `Default Organization` и пользователь `admin`.

### `metrics`

История базовых метрик CPU/RAM/Disk/Network.

Поля:

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

Подробные данные о ядрах CPU, интерфейсах, дисках и процессах не сохраняются постоянно в `metrics`.

### `hardware_metrics`

История аппаратного состояния HPE iLO / Dell iDRAC.

Поля:

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

### Diagnostics / diagnostic output

Диагностика не хранится отдельной таблицей. Она рассчитывается backend по последним данным узла и возвращается через API.

Основные поля diagnostic output:

- `node_id`;
- `system_state`;
- `scenario`;
- `health_score`;
- `confidence`;
- `bottleneck`;
- `metrics`;
- `evidence`;
- `recommendations`;
- `summary`.

Для каждой метрики возвращаются:

- `value`;
- `severity`;
- `trend`;
- `anomaly`;
- `persistence`.

### `process_snapshots`

Снимки процессов, которые агент отправляет только при высокой CPU/RAM нагрузке.

Поля:

- `id`;
- `node_id`;
- `created_at`;
- `reason`.

### `process_snapshot_items`

Top-процессы внутри snapshot.

Поля:

- `id`;
- `snapshot_id`;
- `pid`;
- `name`;
- `cpu_percent`;
- `memory_percent`.

### `enrollment_keys`

Ключи первичной установки агентов.

Поля:

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

Открытый ключ имеет формат:

```text
smk_enroll_xxxxxxxxxxxxxxxxx
```

В базе хранится только `key_hash` и `prefix`. Открытый ключ показывается пользователю только один раз при создании.

### `agent_tokens`

Токены конкретных агентов.

Поля:

- `id`;
- `node_id`;
- `token_hash`;
- `prefix`;
- `is_active`;
- `created_at`;
- `last_used_at`.

Открытый token имеет формат:

```text
smk_agent_xxxxxxxxxxxxxxxxx
```

В базе хранится только hash и prefix. Agent token используется для дальнейшей отправки telemetry и process snapshots от конкретного узла.

## 9. Основные API endpoints

Базовый адрес backend:

```text
http://127.0.0.1:8000
```

Swagger/OpenAPI:

```text
http://127.0.0.1:8000/docs
```

### Auth API

- `POST /api/auth/login` - вход пользователя и выдача JWT access token;
- `GET /api/auth/me` - информация о текущем пользователе и его организациях.

Стартовый пользователь после первого запуска:

```text
username: admin
password: admin123
```

Пример login-запроса:

```json
{
  "username": "admin",
  "password": "admin123"
}
```

Защищенные запросы должны отправляться с заголовком:

```text
Authorization: Bearer <access_token>
```

### Обратная совместимость

- `GET /api/metrics/current` - текущие локальные метрики `Local System`;
- `GET /api/metrics/history?limit=N` - история `Local System`;
- `GET /api/metrics/summary?limit=N` - summary `Local System`;
- `GET /api/analysis/summary?limit=N` - анализ `Local System`.

### Node-aware API

- `GET /api/nodes` - список активных контролируемых систем;
- `GET /api/nodes?include_archived=true` - список систем с архивными узлами, доступен для ролей `owner` и `admin`;
- `GET /api/nodes/{node_id}` - подробная информация об узле;
- `GET /api/nodes/{node_id}/metrics/current` - текущие/последние метрики узла;
- `GET /api/nodes/{node_id}/metrics/history?limit=N` - история узла;
- `GET /api/nodes/{node_id}/metrics/summary?limit=N` - summary узла;
- `GET /api/nodes/{node_id}/analysis/summary?limit=N` - аналитика узла;
- `GET /api/nodes/{node_id}/diagnostics?limit=N` - диагностическая карточка узла.

Эти endpoints защищены JWT и возвращают только узлы организаций, где текущий пользователь является участником.

### Node management API

- `PATCH /api/nodes/{node_id}` - изменение имени и описания узла;
- `POST /api/nodes/{node_id}/archive` - архивирование узла без физического удаления;
- `POST /api/nodes/{node_id}/restore` - восстановление архивного узла;
- `DELETE /api/nodes/{node_id}` - alias для архивирования, физическое удаление не выполняется;
- `POST /api/nodes/{node_id}/clear-history` - очистка истории метрик, аппаратных метрик и snapshots процессов выбранного узла;
- `POST /api/nodes/{node_id}/refresh` - ручное обновление: для iLO/iDRAC выполняется Redfish poll, для Local/Agent возвращаются последние данные push-модели.

Операции управления доступны только ролям `owner` и `admin`. Роль `viewer` может просматривать системы, метрики и диагностику, но не может изменять узлы и очищать историю.

### Monitoring Agent API

- `POST /api/agents/enroll` - первичная привязка агента по enrollment key;
- `POST /api/agents/register` - старый dev/local endpoint регистрации агента;
- `POST /api/telemetry` - прием базовой телеметрии с Bearer agent token;
- `POST /api/process-snapshots` - прием top-N процессов с Bearer agent token;
- `GET /api/nodes/{node_id}/process-snapshots/latest` - последний snapshot;
- `GET /api/nodes/{node_id}/process-snapshots?limit=N` - история snapshots.

Agent endpoints не используют пользовательский JWT. Агент не логинится как пользователь: первичная установка идет через enrollment key, а дальнейшая отправка telemetry идет через отдельный agent token.

### Enrollment Keys API

- `GET /api/enrollment-keys` - список ключей организаций текущего пользователя;
- `POST /api/enrollment-keys` - создание ключа подключения;
- `POST /api/enrollment-keys/{key_id}/revoke` - отзыв ключа;
- `DELETE /api/enrollment-keys/{key_id}` - удаление записи ключа из списка.

Создавать, отзывать и удалять ключи могут роли `owner` и `admin`. Роль `viewer` может только просматривать системы и диагностику.

### Download Center API

- `POST /api/downloads/agent` - сформировать пакет агента по выбранному `platform_type`;
- `POST /api/downloads/agent/windows` - совместимый endpoint для Windows Desktop package;
- `POST /api/downloads/agent/linux` - совместимый endpoint для Linux GUI package.

Тело запроса:

```json
{
  "platform_type": "windows_desktop",
  "enrollment_key_id": 1,
  "enrollment_key": "smk_enroll_xxxxx"
}
```

Скачивать agent package могут только роли `owner` и `admin`. Backend не восстанавливает открытый enrollment key из базы, потому что в SQLite хранится только hash. Пользователь вручную вставляет открытый ключ, а backend проверяет, что он соответствует выбранной записи.

### Organization members API

- `GET /api/organization/members` - список участников текущей организации;
- `POST /api/organization/members` - добавить пользователя в организацию;
- `PATCH /api/organization/members/{user_id}` - изменить роль участника;
- `DELETE /api/organization/members/{user_id}` - удалить membership без удаления аккаунта пользователя;
- `POST /api/organization/transfer-ownership` - передать роль owner другому участнику.

Пример добавления пользователя:

```json
{
  "username": "ivan",
  "password": "TempPassword123",
  "role": "viewer"
}
```

Обычное изменение роли поддерживает `viewer` и `admin`. Роль `owner` передается только через отдельный endpoint `transfer-ownership`, чтобы случайно не создать некорректное состояние организации.

### Redfish / hardware API

- `POST /api/nodes/redfish` - добавление iLO/iDRAC-узла;
- `POST /api/nodes/{node_id}/poll-redfish` - опрос аппаратного источника;
- `GET /api/nodes/{node_id}/hardware/latest` - последняя аппаратная метрика;
- `GET /api/nodes/{node_id}/hardware/history?limit=N` - история аппаратных метрик.

### Подробные локальные live-метрики

Эти endpoints относятся к компьютеру, на котором запущен backend:

- `GET /api/system/info`;
- `GET /api/system/cpu`;
- `GET /api/system/memory`;
- `GET /api/system/disks`;
- `GET /api/system/network`;
- `GET /api/system/processes?limit=10&sort=cpu`.

## 10. Как запустить backend

Из корня проекта:

```powershell
cd "C:\Users\Alin\Documents\New project"
.\backend\.venv\Scripts\python.exe backend\run.py
```

Альтернативно через `uvicorn`:

```powershell
cd "C:\Users\Alin\Documents\New project\backend"
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Если PowerShell не принимает путь из-за пробела, используйте полный путь:

```powershell
& "C:\Users\Alin\Documents\New project\backend\.venv\Scripts\python.exe" "C:\Users\Alin\Documents\New project\backend\run.py"
```

После запуска доступны:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

При первом запуске backend автоматически:

1. Создает таблицы пользователей и организаций.
2. Создает `Default Organization`.
3. Создает пользователя `admin` с паролем `admin123`, если его еще нет.
4. Добавляет `admin` в `Default Organization` с ролью `owner`.
5. Привязывает существующие узлы к `Default Organization`.

## 11. Как запустить frontend

Dev-режим frontend:

```powershell
cd "C:\Users\Alin\Documents\New project\frontend"
npm.cmd run dev
```

Открыть:

```text
http://127.0.0.1:5173
```

Сборка frontend:

```powershell
cd "C:\Users\Alin\Documents\New project\frontend"
npm.cmd run build
```

После этой команды Vite кладет собранные файлы в `frontend/dist`.
Чтобы backend отдавал новую версию интерфейса из папки `static/`, нужно синхронизировать сборку:

```powershell
cd "C:\Users\Alin\Documents\New project"
$project = Resolve-Path .
$staticAssets = Join-Path $project "static\assets"
$frontendDist = Join-Path $project "frontend\dist"
New-Item -ItemType Directory -Force -Path $staticAssets | Out-Null
Get-ChildItem -Path $staticAssets -File | Remove-Item -Force
Copy-Item -Path (Join-Path $frontendDist "index.html") -Destination (Join-Path $project "static\index.html") -Force
Copy-Item -Path (Join-Path $frontendDist "assets\*") -Destination $staticAssets -Force
```

В обычной разработке Vite сначала собирает файлы в `frontend/dist`. Скрипт `build/build_exe.ps1` перед PyInstaller-сборкой копирует актуальные файлы из `frontend/dist` в `static/`. При ручной подготовке static можно выполнить такую же синхронизацию после `npm.cmd run build`.

## 12. Как запустить agent

Сначала запустить backend, затем из корня проекта:

```powershell
cd "C:\Users\Alin\Documents\New project"
.\backend\.venv\Scripts\python.exe agent\agent.py
```

После запуска агент должен:

1. Прочитать `agent/config.json`.
2. Если `agent_state.json` отсутствует, выполнить `/api/agents/enroll` по `enrollment_key`.
3. Получить `node_id` и `agent_token`.
4. Сохранить runtime-данные в `agent/agent_state.json`.
5. Начать отправку телеметрии через `/api/telemetry` с `Authorization: Bearer <agent_token>`.
6. При высокой нагрузке CPU/RAM периодически отправлять process snapshot.

Проверка:

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/nodes -Headers @{Authorization="Bearer $($login.access_token)"}
```

В списке должен появиться узел `Test Agent` с `source_type="agent"`.

## 13. Как добавить mock iLO/iDRAC

Через frontend:

1. Открыть список систем.
2. Нажать `Добавить iDRAC mock`.
3. Нажать `Добавить HPE iLO mock`.
4. Убедиться, что новые узлы появились в списке.
5. Открыть каждый узел и проверить блок `Аппаратное состояние`.

Через API:

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/nodes/redfish -Headers @{Authorization="Bearer $($login.access_token)"} -ContentType "application/json" -Body '{"name":"DELL-SERVER-01","source_type":"idrac","management_ip":"192.168.1.100","username":"root","password":"password","use_mock":true}'
```

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/nodes/redfish -Headers @{Authorization="Bearer $($login.access_token)"} -ContentType "application/json" -Body '{"name":"HPE-SERVER-01","source_type":"ilo","management_ip":"192.168.1.101","username":"Administrator","password":"password","use_mock":true}'
```

Проверка аппаратного состояния:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/nodes/{redfish_node_id}/hardware/latest" -Headers @{Authorization="Bearer $($login.access_token)"}
```

## 14. Как проверить работу системы

Проверка Python-кода:

```powershell
py -m compileall backend agent
```

Проверка frontend build:

```powershell
cd frontend
npm.cmd run build
```

Проверка старого endpoint:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/metrics/current
```

Проверка, что `/api/nodes` защищен:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/nodes
```

Ожидаемый результат без token: `401 Unauthorized`.

Login:

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}'
```

Проверка списка систем с token:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/nodes -Headers @{Authorization="Bearer $($login.access_token)"}
```

Проверка истории конкретного узла:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/nodes/1/metrics/history?limit=20" -Headers @{Authorization="Bearer $($login.access_token)"}
```

Проверка диагностики:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/nodes/1/diagnostics?limit=100" -Headers @{Authorization="Bearer $($login.access_token)"}
```

Проверка process snapshot:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/nodes/{agent_node_id}/process-snapshots/latest" -Headers @{Authorization="Bearer $($login.access_token)"}
```

Проверка аппаратного узла:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/nodes/{redfish_node_id}/hardware/latest" -Headers @{Authorization="Bearer $($login.access_token)"}
```

Ручная проверка frontend:

1. Запустить backend.
2. Запустить agent.
3. Открыть `http://127.0.0.1:5173` или `http://127.0.0.1:8000`.
4. Убедиться, что на главной странице отображаются `Local System`, `Test Agent`, mock HPE iLO и mock Dell iDRAC.
5. Открыть `Local System` и проверить карточки, графики, анализ и диагностику.
6. Вернуться к списку систем.
7. Открыть `Test Agent` и проверить метрики, графики, диагностику и блок `Возможные процессы-причины`, если snapshot уже есть.
8. Открыть HPE iLO / Dell iDRAC и проверить блок `Аппаратное состояние` и диагностику.

## 15. Диагностика состояния узлов

Диагностика выполняется на центральном backend. Agent отправляет только данные, но не анализирует их.

Backend рассчитывает:

- `severity` - уровень состояния метрики;
- `trend` - направление изменения;
- `anomaly` - резкое отклонение от среднего;
- `persistence` - кратковременный всплеск или устойчивое состояние;
- `bottleneck` - предполагаемое узкое место;
- `scenario` - сценарий нагрузки;
- `system_state` - итоговое состояние;
- `health_score` - индекс состояния от 0 до 100;
- `evidence` - причины вывода;
- `recommendations` - рекомендации.

Диагностика является rule-based. ML/LLM не используются, чтобы сохранить объяснимость, легкость и предсказуемость проекта.

## 16. Пользователи, организации и роли

Проект перешел от демонстрационного локального мониторинга к модели центрального web-хаба. Поэтому узлы нельзя привязывать только к одному пользователю: один и тот же корпоративный workspace может использоваться несколькими администраторами и наблюдателями.

Модель доступа:

```text
User -> Organization -> Nodes
```

Сценарии:

- личный пользователь работает в своей личной организации/workspace;
- компания создает организацию, где несколько пользователей имеют разные роли;
- `owner` и `admin` могут добавлять источники мониторинга;
- `viewer` может только смотреть системы, метрики и диагностику.

Узлы теперь имеют `organization_id`. Это позволяет хранить Local System, Agent-узлы и iLO/iDRAC-источники внутри конкретной организации.

### Управление участниками

Во frontend добавлена страница `Users`. Она доступна ролям `owner` и `admin`.

На странице отображаются:

- `username`;
- роль участника;
- дата создания пользователя;
- дата добавления в организацию;
- действия управления.

`owner` может:

- добавлять пользователей;
- удалять участников из организации;
- менять роли `viewer/admin`;
- передавать владение другому участнику.

`admin` может:

- добавлять пользователей;
- менять роли между `viewer` и `admin`;
- удалять `viewer/admin` из организации;
- управлять системами, ключами подключения и Download Center.

`admin` не может удалить `owner` и не может передать ownership. `viewer` не видит страницу `Users`, Download Center и кнопки управления системами.

Удаление участника означает удаление записи `organization_members`. Аккаунт пользователя из таблицы `users` физически не удаляется, поэтому тот же пользователь в будущем может быть добавлен в другую организацию.

Передача владения выполняется отдельным действием: новый участник получает `owner`, а старый owner становится `admin`.

Защищены JWT:

- `GET /api/nodes`;
- `GET /api/nodes/{node_id}`;
- `GET /api/nodes/{node_id}/metrics/current`;
- `GET /api/nodes/{node_id}/metrics/history`;
- `GET /api/nodes/{node_id}/metrics/summary`;
- `GET /api/nodes/{node_id}/analysis/summary`;
- `GET /api/nodes/{node_id}/diagnostics`;
- `POST /api/nodes/redfish`;
- `POST /api/nodes/{node_id}/poll-redfish`;
- `GET /api/nodes/{node_id}/hardware/latest`;
- `GET /api/nodes/{node_id}/hardware/history`;
- `GET /api/nodes/{node_id}/process-snapshots/latest`;
- `GET /api/nodes/{node_id}/process-snapshots`.

Frontend показывает login screen, сохраняет access token в `localStorage` и отправляет защищенные запросы с Bearer token. Если backend возвращает `401`, token очищается и пользователь возвращается на экран входа.

Agent endpoints остаются отдельно от пользовательского JWT:

- `POST /api/agents/enroll`;
- `POST /api/agents/register`;
- `POST /api/telemetry`;
- `POST /api/process-snapshots`.

Это сделано специально: агент остается легким маячком и регистрируется через enrollment key, связанный с организацией. Endpoint `/api/agents/register` оставлен для dev/local-совместимости, но продуктовый сценарий использует `/api/agents/enroll`.

## 17. Ключи подключения агентов

Для продуктового подключения внешних машин используется двухэтапная схема:

```text
enrollment key -> /api/agents/enroll -> agent token -> telemetry
```

**Enrollment key** нужен только для первичной установки устройства. Его создает `owner` или `admin` в web-интерфейсе на странице `Ключи подключения`. Ключ привязан к организации, поэтому backend понимает, в какой workspace добавить новый agent-node.

**Agent token** выдается конкретному агенту после успешного enroll. Дальше агент отправляет telemetry и process snapshots с заголовком:

```text
Authorization: Bearer <agent_token>
```

Почему ключи разделены:

- enrollment key можно ограничить по сроку действия и количеству использований;
- открытый enrollment key показывается пользователю только один раз;
- agent token привязан к конкретному node;
- при компрометации agent token можно отключить конкретный агент, не меняя все ключи подключения;
- agent остается легким маячком и не использует пользовательский JWT.

Конфигурация агента:

```json
{
  "server_url": "http://127.0.0.1:8000",
  "enrollment_key": "smk_enroll_xxxxx",
  "agent_token": "",
  "node_id": null,
  "agent_name": "Test Agent",
  "send_interval_seconds": 5,
  "process_snapshot_cooldown_seconds": 30,
  "agent_version": "0.1.0"
}
```

После первой успешной привязки агент создает локальный файл:

```text
agent/agent_state.json
```

В нем хранятся runtime-данные:

```json
{
  "node_id": 12,
  "agent_token": "smk_agent_xxxxx"
}
```

`agent_state.json` не должен попадать в git, потому что содержит открытый agent token.

В базе данных открытые enrollment keys и agent tokens не хранятся. Backend сохраняет только hash и prefix. Prefix нужен для отображения и быстрого поиска кандидатов при проверке.

В будущем установку агента можно оформить через CLI или installer: пользователь скачивает agent, передает enrollment key, агент выполняет enroll и дальше работает автономно.

## 18. Download Center

Download Center - это продуктовая функция для выдачи готового файла агента из web-интерфейса. Пользователь с ролью `owner` или `admin` нажимает `Скачать агент`, выбирает тип устройства и enrollment key, после чего backend отдаёт заранее собранный бинарный файл агента.

Новая логика Download Center ориентирована не на разработчика, а на администратора или обычного пользователя. Вместо выбора абстрактной платформы `Windows/Linux` интерфейс предлагает четыре сценария:

- `Windows` - обычный пользовательский Windows-ПК;
- `Windows Server` - серверный Windows-сценарий;
- `Linux GUI` - Linux с рабочим окружением и ручным foreground-запуском;
- `Linux Server` - Linux-сервер без UI.

Функция нужна для упрощения установки агента на новые машины:

- администратор создает enrollment key;
- открывает `Скачать агент`;
- выбирает один из четырех типов устройства;
- выбирает запись enrollment key;
- вручную вставляет открытый enrollment key;
- скачивает один готовый файл агента;
- запускает файл на контролируемой системе.

### Почему открытый key нужно вставлять вручную

Открытый enrollment key показывается только один раз при создании. В базе данных хранится только hash и prefix. Поэтому backend не может и не должен восстанавливать исходный key при скачивании agent package.

Download Center использует безопасную схему:

1. Frontend отправляет `enrollment_key_id` и открытый `enrollment_key`.
2. Backend находит запись ключа по `id`.
3. Backend проверяет права пользователя в организации.
4. Backend проверяет, что ключ active и не истек.
5. Backend сравнивает переданный открытый key с сохраненным hash.
6. Только после этого backend отдаёт готовый бинарный файл из `backend/downloads/agents/`.

Если открытый key потерян, нужно создать новый enrollment key. Это нормальное поведение и часть модели безопасности.

### Download Center API

Основной endpoint:

```text
POST /api/downloads/agent
```

Request:

```json
{
  "platform_type": "windows_desktop",
  "enrollment_key_id": 1,
  "enrollment_key": "smk_enroll_xxxxx"
}
```

Поддерживаемые значения `platform_type`:

- `windows_desktop`;
- `windows_server`;
- `linux_gui`;
- `linux_server`.

Старые endpoints оставлены для обратной совместимости:

```text
POST /api/downloads/agent/windows
POST /api/downloads/agent/linux
```

Они отдают файлы `agent-windows.exe` и `agent-linux-gui` соответственно.

### Сборка файлов агента

Исходный код агента находится отдельно в папке `agent/`:

```text
agent/
  agent.py
  metrics_collector.py
  requirements.txt
  build_windows.ps1
  build_linux.sh
```

Готовые файлы после сборки копируются в:

```text
backend/downloads/agents/
```

Ожидаемые имена файлов:

```text
agent-windows.exe
agent-windows-server.exe
agent-linux-gui
agent-linux-server
```

Сборка Windows-файлов выполняется на Windows:

```powershell
cd "C:\Users\Alin\Documents\New project"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\agent\build_windows.ps1
```

Сборка Linux-файлов выполняется на Linux:

```bash
cd /path/to/project
bash agent/build_linux.sh
```

PyInstaller не выполняет полноценную cross-platform сборку. Поэтому Windows `.exe` нужно собирать на Windows, а Linux executable - на Linux.

Если файл ещё не собран, backend возвращает понятную ошибку:

```text
Файл агента agent-linux-gui ещё не собран. Запустите agent/build_linux.sh.
```

### Windows Desktop

Назначение: обычный пользовательский Windows-ПК.

Что скачивается:

```text
agent-windows.exe
```

Основной запуск:

```powershell
.\agent-windows.exe
```

Если рядом нет `config.json`, агент при первом foreground-запуске спросит `server_url`, `enrollment_key` и имя агента, затем сохранит `config.json`.

### Windows Server

Назначение: серверный Windows-сценарий.

Что скачивается:

```text
agent-windows-server.exe
```

На текущем этапе это отдельное имя того же лёгкого агента. Установка именно как Windows Service остаётся направлением развития и может быть реализована через NSSM, pywin32 или отдельную service-сборку.

### Linux GUI

Назначение: обычный Linux с рабочим окружением.

Что скачивается:

```text
agent-linux-gui
```

Запуск:

```bash
chmod +x agent-linux-gui
./agent-linux-gui
```

Агент работает в foreground mode. Это удобно для обычного пользователя или демонстрации.

### Linux Server

Назначение: серверный Linux без UI.

Что скачивается:

```text
agent-linux-server
```

Запуск установки:

```bash
chmod +x agent-linux-server
./agent-linux-server
```

Systemd-установка остаётся направлением развития. Минимальная сборка уже создаёт отдельный Linux server executable.

### Конфигурация одиночного файла

Одиночный агент ищет `config.json` и `agent_state.json` рядом с исполняемым файлом. Если `config.json` отсутствует:

- в интерактивном foreground-режиме агент спросит `server_url`, `enrollment_key` и `agent_name`;
- в неинтерактивном режиме можно задать переменные окружения `SYSTEM_MONITOR_SERVER_URL`, `SYSTEM_MONITOR_ENROLLMENT_KEY`, `SYSTEM_MONITOR_AGENT_NAME`;
- после интерактивной настройки агент сохранит `config.json` рядом с собой.

После первого запуска agent выполнит enroll, получит `node_id` и `agent_token`, сохранит их в `agent_state.json` и начнет отправлять telemetry.

### Важные ограничения Download Center

- открытый enrollment key не хранится в backend;
- backend не может повторно показать старый открытый key;
- MSI/DEB/RPM не реализованы;
- Windows Service и systemd installer пока не входят в одиночный файл, это следующий шаг;
- PyInstaller не делает cross-platform build, поэтому Linux-файлы нужно собирать на Linux;
- если файл агента не собран, backend не формирует zip fallback, а возвращает ошибку;
- agent остается легким маячком и не выполняет диагностику;
- все расчеты, анализ, diagnostics и визуализация остаются на центральном backend.

## 19. Управление системами

Web-интерфейс теперь используется не только для просмотра, но и для базового администрирования узлов организации. Это важный продуктовый слой: администратор может поддерживать список систем в актуальном состоянии, скрывать неиспользуемые узлы и очищать накопленную историю без изменения структуры базы данных.

Доступные действия для ролей `owner` и `admin`:

- открыть карточку узла;
- переименовать узел;
- добавить или изменить описание;
- выполнить ручное обновление;
- очистить историю узла;
- архивировать узел;
- восстановить архивный узел.

Роль `viewer` видит список систем, метрики, диагностику и аппаратное состояние, но кнопки управления в интерфейсе скрыты. Backend дополнительно проверяет права на каждом management endpoint, поэтому ограничение не зависит только от frontend.

### Редактирование узла

Редактирование выполняется через `PATCH /api/nodes/{node_id}`. Можно изменить:

- `name` - отображаемое имя;
- `description` - пояснение для администратора.

Идентификатор, `hostname`, `source_type`, история метрик и привязка к организации при этом не меняются.

### Архивирование вместо удаления

Физическое удаление узлов по умолчанию не используется. Вместо этого узел переводится в архив:

- `is_archived=true`;
- `archived_at=<текущее время>`;
- `status="archived"`.

Архивный узел скрывается из основного списка систем. Если включить переключатель `Показать архивные`, owner/admin увидит архивные записи и сможет восстановить их. Endpoint `DELETE /api/nodes/{node_id}` работает как alias для archive, чтобы случайно не удалить важную историю.

Если agent продолжает отправлять telemetry в архивный узел, backend не сохраняет новые метрики и возвращает понятный отказ. Это защищает базу от накопления данных по системам, которые администратор намеренно вывел из активного мониторинга.

### Очистка истории

Очистка истории выполняется через `POST /api/nodes/{node_id}/clear-history`. Узел остается в базе, но удаляются связанные данные:

- записи `metrics`;
- записи `hardware_metrics`;
- записи `process_snapshots`;
- записи `process_snapshot_items`.

Это удобно для демонстрации, повторного тестирования агента или удаления устаревших измерений без потери самого объекта мониторинга.

### Refresh

Endpoint `POST /api/nodes/{node_id}/refresh` учитывает тип источника:

- для `local` и `agent` используется push-модель, поэтому backend возвращает последние сохраненные метрики и диагностику;
- для `ilo` и `idrac` выполняется опрос Redfish-источника, в mock-режиме создается новая аппаратная запись.

Такой подход сохраняет легкость агента: agent не получает команд управления и продолжает только отправлять telemetry на центральный сервер.

## 20. Выборочный анализ процессов

Agent не отправляет полный список процессов постоянно.

Snapshot отправляется только если:

- `cpu_percent > 70`;
- или `ram_percent > 75`.

Отправляется top-5 процессов. Между отправками действует cooldown, по умолчанию 30 секунд:

```json
"process_snapshot_cooldown_seconds": 30
```

Это помогает понять возможную причину нагрузки, но не превращает систему в постоянный мониторинг процессов.

## 21. Визуализация

Во frontend реализованы:

- список контролируемых систем;
- адаптивная верхняя панель с разделами навигации, действий и пользователя;
- карточки CPU/RAM/Disk/Network;
- графики CPU и RAM;
- downsampling графиков;
- режим сравнения полного и оптимизированного отображения;
- сводка;
- предупреждения;
- health score;
- диагностика состояния;
- аппаратное состояние iLO/iDRAC;
- process snapshot table для agent/local узлов при наличии данных.
- страница `Ключи подключения` для создания и отзыва enrollment keys.

Для iLO/iDRAC CPU/RAM/Disk-графики не показываются, потому что аппаратный источник на текущем этапе передает только состояние серверного оборудования.

### Структура web-интерфейса

Web UI разделен на несколько пользовательских зон:

- `Системы` - главный экран со списком узлов организации;
- `Ключи` - управление enrollment keys для подключения агентов;
- `Users` - управление участниками организации;
- `Скачать агент` - Download Center для выдачи готового пакета агента;
- страница выбранного узла - dashboard с метриками, диагностикой, аппаратным состоянием или process snapshots.

Верхняя панель сделана как responsive flex-layout. Она разделяет:

- навигацию;
- продуктовые действия;
- информацию о пользователе, организации, роли и состоянии обновления.

Кнопки переносятся на новую строку при недостатке ширины и не должны перекрывать друг друга. Это важно для демонстрации проекта на разных экранах: ноутбук, проектор, уменьшенное окно браузера.

### Навигация без vue-router

Frontend по-прежнему не использует сложный роутинг. Внутренняя навигация реализована через состояние приложения и hash-историю браузера:

- `#systems` - список систем;
- `#keys` - ключи подключения;
- `#users` - пользователи организации;
- `#node-{id}` - страница конкретного узла.

За счет этого переход `Системы -> Узел -> Назад` работает ожидаемо: кнопка браузера `Back` возвращает пользователя к списку систем, а не к экрану login. Кнопка `Назад к системам` также переводит на главный список.

### Плавное обновление данных

Для dashboard выбранного узла разделены два состояния:

- `initial loading` - первичная загрузка, когда данных на экране еще нет;
- `background refresh` - фоновое обновление уже открытой страницы.

При фоновом обновлении frontend не очищает старые карточки, сводку, графики и диагностику до получения нового ответа. Пользователь видит прежние значения, а после успешного запроса они заменяются новыми. Это убирает визуальное мигание карточек и диагностических блоков.

Также в интерфейсе отображаются:

- время последнего обновления;
- признак фонового обновления;
- ошибка обновления, если backend временно недоступен.

### Карточки систем

Карточки систем на главной странице показывают не только техническое имя, но и краткую продуктовую сводку:

- тип источника: `Local`, `Agent`, `HPE iLO`, `Dell iDRAC`;
- status badge: `online`, `offline`, `warning`, `critical`, `archived`;
- health score;
- hostname;
- описание;
- last seen;
- краткий текст состояния;
- быстрые действия: открыть, переименовать, обновить, очистить историю, архивировать.

Для `viewer` кнопки управления скрываются, а backend дополнительно проверяет права на management endpoints.

### UI диагностики

Диагностическая карточка отображает готовый вывод backend в более наглядном виде:

- health score показан крупным числом и progress bar;
- system state и bottleneck выделяются badge-элементами;
- severity получает цветовую маркировку;
- evidence и recommendations вынесены в отдельные списки.

Это помогает использовать систему не только как график метрик, но и как объяснимую диагностическую панель.

### Secure reveal enrollment key

Backend не хранит открытый enrollment key. В базе данных остаются только hash и prefix.

После создания ключа frontend показывает открытое значение один раз и дополнительно сохраняет его локально в браузере текущего пользователя. В таблице ключей отображается:

- замаскированное значение вида `smk_enroll_********`;
- кнопка `Reveal`;
- кнопка `Copy`.

`Reveal` работает только если открытый ключ еще доступен в localStorage текущего браузера. Если пользователь очистил браузер, открыл систему с другого компьютера или ключ был создан ранее, frontend показывает сообщение:

```text
Open key unavailable. Create a new key.
```

Такой подход сохраняет модель безопасности: backend не может восстановить открытый ключ из hash, а пользователь получает удобство раскрытия только в рамках своего браузера.

## 22. Сборка в exe

Проект подготовлен к будущей сборке backend-приложения в `.exe` через PyInstaller.

Сборочные файлы:

- `build/SystemMonitor.spec`;
- `build/build_exe.ps1`.

Запуск сборки:

```powershell
cd "C:\Users\Alin\Documents\New project"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build\build_exe.ps1
```

Если обычный запуск `.ps1` запрещен политикой PowerShell, вариант с `-ExecutionPolicy Bypass` запускает скрипт только для текущей команды.
Скрипт сначала пытается выполнить `npm.cmd run build`, затем копирует `frontend/dist` в `static/` и запускает PyInstaller.
Если в конкретной Windows-среде `npm` временно не смог запустить `esbuild`, но `frontend/dist` уже существует, скрипт покажет предупреждение и продолжит сборку с имеющимся `frontend/dist`.

Результат:

```text
dist/SystemMonitor/SystemMonitor.exe
```

После запуска exe должен стартовать локальный FastAPI-сервер и открыться браузер. Исходники при этом остаются редактируемыми: backend, frontend, agent и конфигурация не удаляются и не переносятся.

## 23. Развертывание на Ubuntu/VPS

Проект подготовлен к установке центрального backend на Ubuntu-сервер без Docker. Для этого добавлены файлы в папке `deploy/ubuntu/`:

- `install_backend.sh` - установка проекта в `/opt/system-monitor`;
- `system-monitor.service` - systemd-служба для FastAPI backend;
- `config.server.example.json` - серверный вариант `config.json` с `server_host = 0.0.0.0`;
- `nginx.system-monitor.conf` - необязательный пример reverse proxy через nginx.

Основная команда на Ubuntu после загрузки проекта:

```bash
cd /tmp/system-monitor
sudo bash deploy/ubuntu/install_backend.sh
```

После установки backend работает как служба:

```bash
sudo systemctl status system-monitor
sudo journalctl -u system-monitor -n 50 --no-pager
```

Web-интерфейс открывается с другого устройства по адресу:

```text
http://SERVER_IP:8000
```

Если включен firewall, нужно открыть порт:

```bash
sudo ufw allow 8000/tcp
```

Для подключения агентов с других устройств важно указывать в агенте не `127.0.0.1`, а адрес VPS:

```text
http://SERVER_IP:8000
```

Linux-бинарники агента собираются на Linux:

```bash
cd /opt/system-monitor
sudo -u system-monitor bash agent/build_linux.sh
```

После сборки Download Center сможет отдавать:

- `agent-linux-gui`;
- `agent-linux-server`.

Подробная инструкция находится в отдельном файле:

```text
UBUNTU_DEPLOY.md
```

## 24. Ограничения текущей версии

- Redfish проверен через mock-режим.
- Реальный HPE iLO / Dell iDRAC требует физического сервера, сетевой доступности и корректных credentials.
- Управление питанием, BIOS, RAID, firmware и удаленная консоль не реализованы.
- SQLite используется как прототипное хранилище.
- Для промышленного режима лучше использовать PostgreSQL или другую серверную СУБД.
- Agent не выполняет анализ, а только собирает и отправляет данные.
- Process snapshot не является постоянным мониторингом процессов.
- Самостоятельная публичная регистрация пользователей пока не реализована; пользователей добавляет owner/admin внутри организации.
- Управление agent tokens через UI пока не реализовано.
- JWT secret задается переменной окружения `SYSTEM_MONITOR_JWT_SECRET`; если ее не задать, используется dev-значение.
- WebSocket не используется; обновление данных выполняется периодическими HTTP-запросами.
- Диагностика основана на простых правилах, без ML/LLM.

## 25. Направления развития

Возможные направления дальнейшей работы:

- регистрация и управление агентами через отдельный экран;
- установка агента как Windows Service / Linux service;
- хранение секретов Redfish вне SQLite;
- реальное подключение к HPE iLO и Dell iDRAC;
- расширение аппаратных метрик Redfish;
- переход с SQLite на PostgreSQL для промышленного сценария;
- аудит действий пользователей;
- экран управления agent tokens;
- установка агента через installer/CLI с передачей enrollment key;
- экспорт отчетов для администратора;
- расширение диагностических правил;
- подготовка установщика для Windows.

## 26. Что можно показать на защите

На текущем этапе можно демонстрировать:

- центральный список систем;
- экран входа `admin/admin123`;
- пользователя `admin` в `Default Organization` с ролью `owner`;
- страницу `Ключи подключения`;
- создание enrollment key с одноразовым показом открытого ключа;
- локальный узел `Local System`;
- внешний узел `Test Agent`;
- mock HPE iLO;
- mock Dell iDRAC;
- графики и карточки метрик;
- диагностику состояния каждого узла;
- аппаратное состояние iLO/iDRAC;
- выборочный snapshot процессов при высокой нагрузке;
- REST API в Swagger UI;
- структуру базы данных и привязку метрик к `node_id`.
