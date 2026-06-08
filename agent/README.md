# Monitoring Agent

## Назначение

`Monitoring Agent` - легкий компонент системы мониторинга, который запускается на контролируемом компьютере и отправляет базовую телеметрию на центральный FastAPI backend.

Агент не выполняет анализ состояния системы и не хранит историю метрик локально. Его задача - собрать текущие значения через `psutil` и передать их на сервер. Аналитика, расчет `health_score`, поиск аномалий, диагностика и определение узких мест выполняются на центральном backend.

## Структура папки

```text
agent/
  agent.py
  metrics_collector.py
  config.json
  agent_state.json
  build_windows.ps1
  build_linux.sh
  README.md
```

- `agent.py` - основной цикл агента: enrollment, сохранение runtime token и отправка телеметрии.
- `metrics_collector.py` - сбор базовых метрик и top-N процессов через `psutil`.
- `config.json` - шаблон настроек подключения.
- `agent_state.json` - локальное runtime-состояние после успешной привязки. Файл содержит agent token и не должен попадать в git.
- `build_windows.ps1` - сборка Windows `.exe` через PyInstaller.
- `build_linux.sh` - сборка Linux executable через PyInstaller.
- `README.md` - документация агента.

## Конфигурация

Пример `config.json`:

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

Поля:

- `server_url` - адрес центрального backend.
- `enrollment_key` - ключ первичной привязки, созданный администратором в web-интерфейсе.
- `agent_token` - поле для совместимости; в продуктовой схеме token сохраняется в `agent_state.json`.
- `node_id` - поле для совместимости; в продуктовой схеме сохраняется в `agent_state.json`.
- `agent_name` - отображаемое имя агента.
- `send_interval_seconds` - интервал отправки телеметрии.
- `process_snapshot_cooldown_seconds` - минимальный интервал между снимками процессов.
- `agent_version` - версия агента.

Если `server_url` указан со слэшем в конце, агент автоматически убирает его.

Если `config.json` отсутствует рядом с агентом:

- в интерактивном режиме агент спросит `server_url`, `enrollment_key` и `agent_name`;
- в неинтерактивном режиме можно задать переменные окружения:
  - `SYSTEM_MONITOR_SERVER_URL`;
  - `SYSTEM_MONITOR_ENROLLMENT_KEY`;
  - `SYSTEM_MONITOR_AGENT_NAME`.

После интерактивной настройки агент сохранит `config.json` рядом с исполняемым файлом.

## Enrollment

Перед первым запуском нужно:

1. Войти во frontend как пользователь с ролью `owner` или `admin`.
2. Открыть страницу `Ключи подключения`.
3. Создать enrollment key.
4. Скопировать открытый ключ сразу после создания.
5. Записать ключ в `agent/config.json`.

После первого успешного запуска агент выполнит:

```text
POST /api/agents/enroll
```

Backend проверит enrollment key, определит организацию, создаст или обновит agent-node и вернет:

- `node_id`;
- `agent_token`.

Агент сохранит их в `agent/agent_state.json`:

```json
{
  "node_id": 12,
  "agent_token": "smk_agent_xxxxx"
}
```

Открытый enrollment key и agent token не хранятся в базе backend в plain text. В БД сохраняются только hash и prefix.

## Какие данные собираются

Агент отправляет:

- `cpu_percent` - загрузка CPU;
- `ram_percent` - использование RAM;
- `disk_percent` - использование основного диска;
- `bytes_sent` - отправленные байты;
- `bytes_recv` - полученные байты;
- `hostname` - имя компьютера;
- `os_name` - операционная система;
- `timestamp` - время сбора метрик.

При высокой CPU/RAM нагрузке агент может отправить top-5 процессов. Это не постоянный мониторинг процессов, а выборочный snapshot для диагностики.

## Используемые endpoints

Первичная привязка:

```text
POST /api/agents/enroll
```

Отправка телеметрии:

```text
POST /api/telemetry
Authorization: Bearer <agent_token>
```

Отправка snapshot процессов:

```text
POST /api/process-snapshots
Authorization: Bearer <agent_token>
```

Старый endpoint `POST /api/agents/register` сохранен на backend для dev/local-совместимости, но продуктовый путь подключения теперь:

```text
enrollment_key -> /api/agents/enroll -> agent_token -> telemetry
```

## Как запустить

Сначала запустите центральный backend:

```powershell
cd "C:\Users\Alin\Documents\New project\backend"
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Затем в другом терминале запустите агент:

```powershell
cd "C:\Users\Alin\Documents\New project"
.\backend\.venv\Scripts\python.exe agent\agent.py
```

В консоли должны появиться сообщения:

```text
Monitoring Agent запущен
Привязка агента успешна. node_id=...
Отправка успешна. node_id=...
```

Если backend временно недоступен, агент не завершится аварийно. Он выведет сообщение об ошибке подключения и попробует повторить отправку позже.

## Сборка агента

Для Download Center нужны готовые одиночные файлы:

```text
backend/downloads/agents/
  agent-windows.exe
  agent-windows-server.exe
  agent-linux-gui
  agent-linux-server
```

### Windows

Сборка выполняется на Windows:

```powershell
cd "C:\Users\Alin\Documents\New project"
.\agent\build_windows.ps1
```

Скрипт:

- проверяет PyInstaller;
- собирает `agent.py` в один `.exe`;
- копирует результат в `backend/downloads/agents/agent-windows.exe`;
- копирует тот же бинарник как `agent-windows-server.exe`.

### Linux

Сборка выполняется на Linux:

```bash
cd /path/to/project
bash agent/build_linux.sh
```

Скрипт:

- проверяет PyInstaller;
- собирает `agent.py` в Linux executable;
- копирует результат в `backend/downloads/agents/agent-linux-gui`;
- копирует тот же бинарник как `agent-linux-server`;
- выставляет executable-bit.

Важно: PyInstaller не выполняет полноценную cross-platform сборку. Windows-файлы нужно собирать на Windows, Linux-файлы - на Linux.

## Проверка агента

1. Запустите backend.
2. Войдите во frontend как `admin`.
3. Создайте enrollment key на странице `Ключи подключения`.
4. Запишите key в `agent/config.json`.
5. Удалите `agent/agent_state.json`, если нужно проверить первичный enrollment заново.
6. Запустите агент.
7. Откройте список систем во frontend.

В результате должен появиться или обновиться узел с:

```text
source_type = agent
name = Test Agent
```

История метрик агента доступна в web-интерфейсе и через защищенный node-aware API.

## Важное ограничение

Агент остается легким маячком. Он не использует Redfish, не хранит SQLite-базу у себя, не выполняет диагностику и не использует пользовательский JWT. Все расчеты, диагностика и выводы остаются на центральном backend.
