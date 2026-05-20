# Система визуализации мониторинга компьютерных систем

Локальное приложение для сбора и отображения системных метрик Windows ПК.

## Архитектура

- `config.json` - основные настройки локального приложения.
- `backend/` - FastAPI сервер, сбор метрик через `psutil`, работа с SQLite через SQLAlchemy.
- `frontend/` - Vue 3 + Vite интерфейс.
- `database/` - файл SQLite создается автоматически при первом запуске.
- `static/` - сюда можно копировать собранный frontend для запуска из FastAPI.
- `dist/` - будущая папка для сборки `.exe` через PyInstaller.

## Конфигурация

Файл `config.json` находится в корне проекта:

```json
{
  "server_host": "127.0.0.1",
  "server_port": 8000,
  "metrics_collect_interval_seconds": 5,
  "frontend_refresh_interval_seconds": 3,
  "normal_refresh_interval_seconds": 5,
  "alert_refresh_interval_seconds": 2,
  "history_limit_records": 200,
  "database_path": "database/metrics.db",
  "trend_threshold_percent": 5,
  "cpu_anomaly_threshold_percent": 25,
  "ram_anomaly_threshold_percent": 15,
  "network_anomaly_threshold_bytes_per_sec": 524288,
  "network_bottleneck_threshold_bytes_per_sec": 1048576
}
```

- `server_host` и `server_port` задают адрес локального сервера.
- `metrics_collect_interval_seconds` задает интервал фонового сбора метрик.
- `frontend_refresh_interval_seconds` задает интервал обновления графиков и карточек в браузере.
- `normal_refresh_interval_seconds` и `alert_refresh_interval_seconds` задают адаптивную частоту обновления интерфейса.
- `history_limit_records` ограничивает количество записей в SQLite.
- `database_path` задает путь к файлу базы данных.
- `*_anomaly_*` и `network_bottleneck_threshold_bytes_per_sec` задают простые пороги анализа.

## Быстрый запуск в режиме разработки

Backend:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

После этого интерфейс будет доступен по адресу `http://127.0.0.1:5173`.

## API

- `GET /api/metrics/current` - текущие значения CPU, RAM, диска и сети.
- `GET /api/metrics/history?limit=60` - последние точки истории метрик.
- `GET /api/metrics/summary?limit=60` - средние и максимальные значения CPU, RAM и диска по последним записям.
- `GET /api/analysis/summary?limit=60` - тренды, health score, аномалии, узкое место и рекомендуемый интервал обновления.
- `GET /api/app/config` - настройки интервалов и лимитов для интерфейса.
- `GET /api/system/info` - имя компьютера, ОС, версия ОС, архитектура и uptime.
- `GET /api/system/cpu` - ядра, потоки, частота и загрузка по ядрам.
- `GET /api/system/memory` - подробная информация об оперативной памяти.
- `GET /api/system/disks` - список дисков и заполненность.
- `GET /api/system/network` - сетевые интерфейсы, общий трафик и скорость.
- `GET /api/system/processes?limit=10&sort=cpu` - топ процессов по CPU или RAM.

После сохранения новой метрики backend удаляет старые записи, чтобы в базе оставалось не больше `history_limit_records`.
Подробные системные данные не сохраняются в SQLite, они считываются через `psutil` только при запросе.

## Интерфейс

Frontend содержит две страницы:

- `Обзор` - основные карточки, графики CPU/RAM, сводка, предупреждения и выбор лимита истории.
- `Подробные метрики` - CPU, Memory, Disks, Network, System info и Processes.

На странице `Обзор` есть:

- карточки текущих значений CPU, RAM, диска и сети;
- графики CPU и RAM;
- блок "Сводка" со средними и максимальными значениями CPU/RAM;
- выбор количества точек истории: 20, 50, 100 или 200;
- переключатель "Все точки" / "Оптимизированное отображение";
- режим "Сравнение режимов" для полного и оптимизированного графика;
- подсказки при наведении на метрики;
- предупреждения при CPU > 85%, RAM > 90% или Disk > 95%;
- тренды CPU, RAM, Disk и Network;
- System Health Score от 0 до 100;
- список простых статистических аномалий;
- блок предполагаемого узкого места системы;
- текущий адаптивный интервал обновления интерфейса.

Для графиков используется функция `downsampleMetrics(data, targetCount)`: если точек слишком много, она сохраняет первую и последнюю точку, а промежуточные выбирает равномерно. Это снижает нагрузку на браузер и оставляет график понятным.

## Анализ данных

Система использует простые объяснимые правила:

- `Trend Analysis` сравнивает первую и последнюю точку выбранного окна истории.
- `Health Score` снижается при высокой CPU/RAM/Disk нагрузке, предупреждениях и аномалиях.
- `Anomaly Detection` сравнивает текущее значение со средним по последним N точкам.
- `Bottleneck Detection` выбирает наиболее вероятное узкое место: CPU, RAM, Disk или Network.
- `Adaptive Refresh Rate` обновляет интерфейс реже в стабильном состоянии и чаще при предупреждениях или аномалиях.

Машинное обучение, WebSocket и внешние аналитические библиотеки не используются.

## Подготовка к будущей exe-сборке

Проект подготовлен к безопасной сборке через PyInstaller без изменения структуры исходников.

Сборочные файлы находятся отдельно:

- `build/SystemMonitor.spec` - spec-файл PyInstaller.
- `build/build_exe.ps1` - PowerShell-скрипт сборки.
- `build/pyinstaller-work/` - временные файлы PyInstaller, игнорируются git.
- `dist/SystemMonitor/` - готовая onedir-сборка, игнорируется git.

Spec-файл явно подключает hidden imports для `uvicorn`, `fastapi`, `sqlalchemy`, `psutil` и `pydantic`, потому что часть модулей этих библиотек загружается динамически. Это предотвращает ошибки вида `ModuleNotFoundError: No module named 'uvicorn'` после запуска exe.
Для PyInstaller 6 также учтен каталог `_internal`: backend умеет искать ресурсы и рядом с exe, и внутри служебной папки PyInstaller.

### Сборка

Перед первой сборкой должны быть установлены зависимости разработки:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd ..\frontend
npm install
```

Запуск сборки из корня проекта:

```powershell
.\build\build_exe.ps1
```

Скрипт выполняет:

1. production-сборку frontend через `npm run build`;
2. копирование актуального frontend в `static`;
3. установку PyInstaller в backend `.venv`, если он еще не установлен;
4. сборку `backend/run.py` в `dist/SystemMonitor/SystemMonitor.exe`;
5. копирование `config.json`, `static/` и `database/` рядом с exe.

Файл `backend/run.py` импортирует объект `app` из `backend/main.py` напрямую. Это важно для PyInstaller: backend-модули попадают в сборку как обычные Python-импорты, а не только как строка `"main:app"`.

### Что попадает в exe-сборку

В папке `dist/SystemMonitor/` создается готовое локальное приложение:

- `SystemMonitor.exe` - запускает FastAPI и автоматически открывает браузер;
- `config.json` - настройки сервера, интервалов и пути к базе;
- `static/` - собранный Vue-интерфейс;
- `database/` - папка для локальной SQLite базы.

SQLite база создается автоматически по пути из `config.json`, по умолчанию `database/metrics.db`.
В сборку добавляется папка `database`, но текущий dev-файл `database/*.db` не обязателен и игнорируется git: exe создает чистую локальную базу при первом запуске или использует уже существующую базу рядом с exe.
После сборки приложение работает без установленного Python, Node.js и SQLite.

Dev-режим не удаляется и не ломается: backend можно запускать через `uvicorn`, frontend через `npm run dev`, а исходники остаются полностью редактируемыми.
