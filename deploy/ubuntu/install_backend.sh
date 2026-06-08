#!/usr/bin/env bash
set -e

if [ "$(id -u)" -ne 0 ]; then
  echo "Запустите установку от root:"
  echo "sudo bash deploy/ubuntu/install_backend.sh"
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/system-monitor}"
APP_USER="${APP_USER:-system-monitor}"
ENV_FILE="/etc/system-monitor.env"

echo "Установка backend в ${INSTALL_DIR}"

apt-get update
apt-get install -y python3 python3-venv python3-pip tar

if ! id "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --home "${INSTALL_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi

mkdir -p "${INSTALL_DIR}"

tar \
  --exclude='.git' \
  --exclude='backend/.venv' \
  --exclude='frontend/node_modules' \
  --exclude='frontend/dist' \
  --exclude='database/*.db' \
  --exclude='database/*.db-journal' \
  --exclude='backend/server*.log' \
  --exclude='agent/agent_state.json' \
  -C "${SOURCE_DIR}" \
  -cf - . | tar -C "${INSTALL_DIR}" -xf -

cp "${INSTALL_DIR}/deploy/ubuntu/config.server.example.json" "${INSTALL_DIR}/config.json"
mkdir -p "${INSTALL_DIR}/database" "${INSTALL_DIR}/backend/downloads/agents"

python3 -m venv "${INSTALL_DIR}/backend/.venv"
"${INSTALL_DIR}/backend/.venv/bin/python" -m pip install --upgrade pip
"${INSTALL_DIR}/backend/.venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"

if [ ! -f "${ENV_FILE}" ]; then
  SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  {
    echo "SYSTEM_MONITOR_JWT_SECRET=${SECRET}"
  } > "${ENV_FILE}"
fi

cp "${INSTALL_DIR}/deploy/ubuntu/system-monitor.service" /etc/systemd/system/system-monitor.service

chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}"
chmod 600 "${ENV_FILE}"

systemctl daemon-reload
systemctl enable system-monitor
systemctl restart system-monitor

echo
echo "Готово. Проверка статуса:"
systemctl --no-pager status system-monitor || true
echo
echo "Если включен ufw, откройте порт:"
echo "sudo ufw allow 8000/tcp"
echo
echo "Адрес web-интерфейса:"
echo "http://SERVER_IP:8000"
