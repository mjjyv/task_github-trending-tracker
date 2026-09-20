#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "[*] Chưa tìm thấy .venv, đang khởi tạo môi trường ảo..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

echo "=========================================================="
echo "   Khởi động GitHub Trending Tracker Dashboard"
echo "   Truy cập: http://127.0.0.1:8001"
echo "=========================================================="

export PYTHONPATH="$DIR"
exec .venv/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
