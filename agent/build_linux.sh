#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${PROJECT_ROOT}/backend/downloads/agents"
BUILD_DIR="${PROJECT_ROOT}/build/agent-linux"
DIST_DIR="${PROJECT_ROOT}/dist/agent-build-linux"
VENV_DIR="${PROJECT_ROOT}/build/agent-linux-venv"

mkdir -p "${OUTPUT_DIR}" "${BUILD_DIR}" "${DIST_DIR}" "${VENV_DIR}"
cd "${SCRIPT_DIR}"

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r requirements.txt pyinstaller

"${VENV_DIR}/bin/python" -m PyInstaller \
  --onefile \
  --clean \
  --name agent-linux-gui \
  --distpath "${DIST_DIR}" \
  --workpath "${BUILD_DIR}" \
  --specpath "${BUILD_DIR}" \
  agent.py

cp "${DIST_DIR}/agent-linux-gui" "${OUTPUT_DIR}/agent-linux-gui"
cp "${DIST_DIR}/agent-linux-gui" "${OUTPUT_DIR}/agent-linux-server"
chmod +x "${OUTPUT_DIR}/agent-linux-gui" "${OUTPUT_DIR}/agent-linux-server"

echo "Built:"
ls -lh "${OUTPUT_DIR}/agent-linux-gui" "${OUTPUT_DIR}/agent-linux-server"
