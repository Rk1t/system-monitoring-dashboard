# Развертывание проекта на Ubuntu/VPS

Этот файл описывает подготовку центрального сервера мониторинга на Ubuntu. Цель - поднять FastAPI backend как системную службу, открыть web-интерфейс с другого устройства и проверить отправку метрик агентами.

Локальный Windows/dev-режим при этом не меняется. Файл `backend/run.py` по-прежнему можно использовать для локального запуска с автоматическим открытием браузера.

## 1. Что будет установлено

На сервере создается каталог:

```text
/opt/system-monitor
```

В него копируется проект:

- `backend/` - центральный FastAPI backend;
- `static/` - собранный Vue-интерфейс;
- `database/` - каталог SQLite базы;
- `agent/` - исходный код и сборочные скрипты агента;
- `config.json` - серверная конфигурация с `server_host = 0.0.0.0`.

Backend запускается как systemd-служба:

```text
system-monitor.service
```

Служба слушает порт `8000` и не открывает браузер на сервере.

## 2. Подготовка перед загрузкой

На рабочем компьютере желательно убедиться, что frontend уже собран и лежит в `static/`.

```powershell
cd "C:\Users\Alin\Documents\New project\frontend"
npm.cmd run build
```

После сборки скопируйте `frontend/dist` в `static`, если это не было сделано автоматически:

```powershell
$project = Resolve-Path ..
$staticAssets = Join-Path $project "static\assets"
$frontendDist = Join-Path $project "frontend\dist"
New-Item -ItemType Directory -Force -Path $staticAssets | Out-Null
Get-ChildItem -Path $staticAssets -File | Remove-Item -Force
Copy-Item -Path (Join-Path $frontendDist "index.html") -Destination (Join-Path $project "static\index.html") -Force
Copy-Item -Path (Join-Path $frontendDist "assets\*") -Destination $staticAssets -Force
```

## 3. Загрузка проекта на сервер

Можно загрузить проект через `scp`, SFTP или Git.

Пример через `scp`:

```bash
scp -r "New project" user@SERVER_IP:/tmp/system-monitor
```

Если проект загружается через Git, учтите, что файлы из `backend/downloads/agents/` игнорируются `.gitignore`. Linux-агенты можно собрать уже на сервере командой из раздела 8.

## 4. Установка backend на Ubuntu

На сервере:

```bash
cd /tmp/system-monitor
sudo bash deploy/ubuntu/install_backend.sh
```

Скрипт:

- ставит `python3`, `python3-venv`, `python3-pip`;
- копирует проект в `/opt/system-monitor`;
- создает виртуальное окружение backend;
- устанавливает зависимости из `backend/requirements.txt`;
- создает `/etc/system-monitor.env` с JWT secret;
- копирует systemd unit;
- запускает службу `system-monitor`.

Проверка:

```bash
sudo systemctl status system-monitor
sudo journalctl -u system-monitor -n 50 --no-pager
```

## 5. Открытие доступа с другого устройства

Если используется `ufw`, откройте порт:

```bash
sudo ufw allow 8000/tcp
```

Также проверьте firewall у VPS-провайдера. В панели провайдера должен быть открыт входящий TCP-порт `8000`.

После этого web-интерфейс должен открываться по адресу:

```text
http://SERVER_IP:8000
```

Стартовая учетная запись после первого запуска:

```text
admin / admin123
```

Для реального размещения рекомендуется задать надежный пароль через управление пользователями или создать отдельного пользователя с ролью владельца.

## 6. Проверка API

```bash
curl http://127.0.0.1:8000/
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

После входа через web-интерфейс проверьте:

- список систем;
- страницу локального узла;
- страницу ключей подключения;
- Download Center.

## 7. Подключение агента с другого устройства

1. Откройте web-интерфейс: `http://SERVER_IP:8000`.
2. Войдите под `admin`.
3. Откройте раздел `Ключи`.
4. Создайте ключ подключения.
5. Скопируйте открытый ключ сразу после создания.
6. На другом устройстве запустите агент и укажите:
   - `server_url = http://SERVER_IP:8000`;
   - enrollment key из web-интерфейса.

Агент выполнит:

```text
enrollment key -> /api/agents/enroll -> agent token -> /api/telemetry
```

После успешной привязки устройство появится в списке систем.

## 8. Сборка Linux-агентов на сервере

PyInstaller не собирает Linux-бинарник на Windows. Поэтому Linux-версии агента нужно собирать на Linux:

```bash
cd /opt/system-monitor
sudo -u system-monitor bash agent/build_linux.sh
```

После сборки появятся файлы:

```text
/opt/system-monitor/backend/downloads/agents/agent-linux-gui
/opt/system-monitor/backend/downloads/agents/agent-linux-server
```

После этого Download Center сможет отдавать Linux-варианты агента.

## 9. Запуск агента без скачивания из UI

Для быстрой проверки можно запустить исходный агент напрямую на другом Linux-устройстве:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install psutil

SYSTEM_MONITOR_SERVER_URL="http://SERVER_IP:8000" \
SYSTEM_MONITOR_ENROLLMENT_KEY="smk_enroll_xxxxx" \
SYSTEM_MONITOR_AGENT_NAME="Ubuntu test agent" \
python agent.py
```

Если агент запускается из папки проекта:

```bash
cd agent
python3 agent.py
```

При отсутствии `config.json` агент спросит адрес сервера и ключ подключения в интерактивном режиме.

## 10. Windows-агент с внешнего устройства

С Windows-устройства откройте:

```text
http://SERVER_IP:8000
```

Зайдите в `Скачать агент`, выберите Windows-вариант и скачайте `.exe`.

Если рядом с `.exe` нет `config.json`, агент при первом запуске спросит:

- адрес сервера;
- enrollment key;
- имя агента.

Адрес сервера должен быть не `127.0.0.1`, а публичный адрес VPS:

```text
http://SERVER_IP:8000
```

## 11. Необязательный nginx reverse proxy

Для доступа через порт `80` можно поставить nginx:

```bash
sudo apt-get install -y nginx
sudo cp /opt/system-monitor/deploy/ubuntu/nginx.system-monitor.conf /etc/nginx/sites-available/system-monitor
sudo ln -s /etc/nginx/sites-available/system-monitor /etc/nginx/sites-enabled/system-monitor
sudo nginx -t
sudo systemctl reload nginx
```

После этого интерфейс будет доступен по:

```text
http://SERVER_IP
```

## 12. Типичные проблемы

### Сайт открывается только на сервере

Проверьте:

- служба слушает `0.0.0.0`, а не `127.0.0.1`;
- открыт порт `8000` в `ufw`;
- открыт порт в панели VPS-провайдера.

Команда проверки:

```bash
sudo ss -lntp | grep 8000
```

### Агент не появляется в списке систем

Проверьте:

- `server_url` у агента указывает на VPS, а не на `127.0.0.1`;
- enrollment key активен;
- ключ не истек;
- лимит использований ключа не исчерпан;
- сервер доступен с устройства агента.

### Download Center пишет, что файл агента не собран

Для Linux выполните:

```bash
cd /opt/system-monitor
sudo -u system-monitor bash agent/build_linux.sh
```

Для Windows `.exe` нужно собрать на Windows через:

```powershell
.\agent\build_windows.ps1
```

и загрузить готовые файлы в:

```text
/opt/system-monitor/backend/downloads/agents/
```

## 13. Что можно показать при тестировании

- web-интерфейс открывается с другого устройства;
- вход через JWT-авторизацию;
- создание ключа подключения;
- запуск агента на другом компьютере;
- появление нового agent-узла в списке систем;
- поступление CPU/RAM/Disk/Network метрик;
- графики истории;
- диагностика состояния;
- process snapshot при высокой нагрузке.
