#!/usr/bin/env bash

# 始终使用项目内的 Python 3.11 虚拟环境运行
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "[ERROR] 未找到虚拟环境: $VENV_DIR"
  echo "请先创建: /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m venv $VENV_DIR"
  exit 1
fi

"$VENV_DIR/bin/python" "$SCRIPT_DIR/run.py" "$@"


