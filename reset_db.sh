#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=========================================================="
echo "   Reset Database GitHub Trending Tracker"
echo "=========================================================="

if [ -f "data/trending.db" ]; then
    rm -f data/trending.db
    echo "✔ Đã xóa file SQLite: data/trending.db"
fi

export PYTHONPATH="$DIR"
.venv/bin/python3 -c "from app.database import init_db; init_db(); print('✔ Đã khởi tạo lại cấu trúc database trắng!')"

echo "✔ Hoàn tất! Cơ sở dữ liệu đã được làm mới hoàn toàn."
