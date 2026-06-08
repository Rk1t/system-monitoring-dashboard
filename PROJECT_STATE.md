# PROJECT STATE

## Что реализовано

Проект доведен до стабильного прототипа централизованной системы визуализации мониторинга данных компьютерных систем.

Реализованы:

- Central Backend на FastAPI;
- Web UI на Vue 3 + Vite;
- SQLite/SQLAlchemy-хранилище;
- модель контролируемых узлов `Node`;
- локальный узел `Local System`;
- отдельный `Monitoring Agent`;
- привязка метрик к `node_id`;
- mock-поддержка HPE iLO и Dell iDRAC через Redfish-архитектуру;
- rule-based диагностика состояния каждого узла;
- выборочный top-5 snapshot процессов при высокой CPU/RAM нагрузке;
- продуктовая модель `User -> Organization -> Nodes`;
- JWT-login для web-интерфейса;
- роли организации `owner`, `admin`, `viewer`;
- управление участниками организации через страницу `Users`;
- передача ownership другому участнику организации;
- enrollment keys для первичной привязки агентов к организации;
- agent tokens для дальнейшей отправки telemetry;
- Download Center для скачивания готовых одиночных файлов агента под Windows, Windows Server, Linux GUI и Linux Server;
- управление узлами из web-интерфейса: переименование, описание, refresh, archive/restore и очистка истории;
- подготовка к будущей PyInstaller-сборке.

## Режимы источников данных

- **Local System**  
  Backend собирает локальные метрики компьютера через `psutil`.

- **Monitoring Agent**  
  Отдельный агент запускается на контролируемой Windows/Linux-системе и отправляет телеметрию на центральный backend.

- **HPE iLO mock / Dell iDRAC mock**  
  Аппаратные источники представлены через mock-режим Redfish. Они показывают power state, hardware health, temperature, fans health и power supplies health.

## Основные endpoints

Обратная совместимость:

- `GET /api/metrics/current`
- `GET /api/metrics/history?limit=N`
- `GET /api/metrics/summary?limit=N`
- `GET /api/analysis/summary?limit=N`

Узлы:

- `GET /api/nodes`
- `GET /api/nodes?include_archived=true`
- `GET /api/nodes/{node_id}`
- `PATCH /api/nodes/{node_id}`
- `POST /api/nodes/{node_id}/archive`
- `POST /api/nodes/{node_id}/restore`
- `DELETE /api/nodes/{node_id}`
- `POST /api/nodes/{node_id}/clear-history`
- `POST /api/nodes/{node_id}/refresh`
- `GET /api/nodes/{node_id}/metrics/current`
- `GET /api/nodes/{node_id}/metrics/history?limit=N`
- `GET /api/nodes/{node_id}/metrics/summary?limit=N`
- `GET /api/nodes/{node_id}/analysis/summary?limit=N`
- `GET /api/nodes/{node_id}/diagnostics?limit=N`

Agent:

- `POST /api/agents/enroll`
- `POST /api/agents/register`
- `POST /api/telemetry`
- `POST /api/process-snapshots`
- `GET /api/nodes/{node_id}/process-snapshots/latest`
- `GET /api/nodes/{node_id}/process-snapshots?limit=N`

Redfish / hardware:

- `POST /api/nodes/redfish`
- `POST /api/nodes/{node_id}/poll-redfish`
- `GET /api/nodes/{node_id}/hardware/latest`
- `GET /api/nodes/{node_id}/hardware/history?limit=N`

Auth / product access:

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/organization/members`
- `POST /api/organization/members`
- `PATCH /api/organization/members/{user_id}`
- `DELETE /api/organization/members/{user_id}`
- `POST /api/organization/transfer-ownership`
- `GET /api/enrollment-keys`
- `POST /api/enrollment-keys`
- `POST /api/enrollment-keys/{key_id}/revoke`
- `POST /api/downloads/agent` - основной endpoint для файлов `windows_desktop`, `windows_server`, `linux_gui`, `linux_server`
- `POST /api/downloads/agent/windows` - совместимость, Windows Desktop package
- `POST /api/downloads/agent/linux` - совместимость, Linux GUI package

Подробные локальные live-метрики:

- `GET /api/system/info`
- `GET /api/system/cpu`
- `GET /api/system/memory`
- `GET /api/system/disks`
- `GET /api/system/network`
- `GET /api/system/processes?limit=10&sort=cpu`

## Что можно показать преподавателю

- Главную страницу со списком систем.
- Экран входа `admin/admin123`.
- Верхнюю панель с пользователем, организацией и ролью.
- Страницу `Users` со списком участников и ролями.
- Добавление viewer/admin пользователя.
- Смену ролей и передачу owner.
- Страницу `Ключи подключения`.
- Создание enrollment key и одноразовый показ открытого ключа.
- Кнопку `Скачать агент` и Download Center.
- Скачивание Windows/Linux agent package с `config.json`.
- Карточки `Local System`, `Test Agent`, `HPE iLO mock`, `Dell iDRAC mock`.
- Действия управления узлом: переименование, описание, ручное обновление, архивирование и восстановление.
- Переключатель `Показать архивные`.
- Очистку истории узла без удаления самого узла.
- Страницу локального узла с текущими метриками, графиками CPU/RAM и диагностикой.
- Страницу agent-узла с телеметрией, анализом и блоком возможных процессов-причин.
- Страницу iLO/iDRAC с аппаратным состоянием и диагностикой.
- Swagger UI по адресу `http://127.0.0.1:8000/docs`.
- Табличную модель данных: `nodes`, `metrics`, `hardware_metrics`, `process_snapshots`, `process_snapshot_items`.

## Ограничения

- Redfish проверен через mock-режим.
- Реальный iLO/iDRAC требует физического сервера и корректных credentials.
- Управление питанием, BIOS, RAID, firmware и удаленная консоль не реализованы.
- SQLite используется как прототипное хранилище.
- Для промышленного режима лучше PostgreSQL.
- Agent не выполняет анализ, только сбор и отправку данных.
- Agent endpoints не используют пользовательский JWT: агент работает через enrollment key и agent token.
- Самостоятельная публичная регистрация пользователей пока не реализована; пользователей добавляет owner/admin.
- Управление agent tokens через UI пока не реализовано.
- Download Center отдаёт готовые одиночные файлы из `backend/downloads/agents/`; полноценные MSI/DEB/RPM-пакеты пока не реализованы.
- Windows Service и systemd installer пока не входят в одиночный файл агента.
- Открытый enrollment key нельзя восстановить из базы, поэтому при скачивании существующего ключа его нужно вставить вручную.
- Архивирование является soft delete: физического удаления узлов из web-интерфейса нет.
- Process snapshot не является постоянным мониторингом процессов.
- Диагностика rule-based, без ML/LLM.

## Какие скриншоты сделать для ВКР

1. Главная страница со списком систем.
2. Dashboard `Local System`.
3. Dashboard `Test Agent`.
4. Страница `Users` с ролями `owner/admin/viewer`.
5. Блок `Диагностика состояния`.
6. Блок `Возможные процессы-причины`.
7. Страница HPE iLO mock с аппаратным состоянием.
8. Страница Dell iDRAC mock с аппаратным состоянием.
9. Модальное окно `Скачать агент`.
10. Содержимое архива `MonitoringAgent-Windows.zip` или `MonitoringAgent-Linux.zip`.
11. Блок управления узлом: редактирование, refresh, очистка истории, archive/restore.
12. Список систем с включенным переключателем `Показать архивные`.
13. Swagger UI со списком API endpoints.
14. Пример ответа `/api/nodes`.
15. Пример ответа `/api/nodes/{node_id}/diagnostics?limit=100`.

## Финальный статус

Функциональная разработка остановлена. Текущая задача проекта - стабилизация, проверка, документирование и подготовка материалов для пояснительной записки ВКР.
