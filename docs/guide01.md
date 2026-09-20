Viewed database.py:1-49
Viewed config.py:1-23
Viewed api.py:460-520
Viewed api.py:115-165
Searched for "seed_demo"
Viewed api.py:315-375
Viewed crawler.py:1-60
Viewed api.py:630-672
Viewed api.py:1-30
Edited api.py
Edited api.py
Ran command: `cat << 'EOF' > reset_db.sh
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
EOF
chmod +x reset_db.sh`
Ran command: `cat << 'EOF' > app/cli_crawl.py
import argparse
import sys
from app.database import SessionLocal, init_db, Base, engine
from app.crawler import crawler
from app.scoring import recalculate_all_scores

def main():
    parser = argparse.ArgumentParser(description="GitHub Trending Crawler CLI - Chạy độc lập không cần Web Server")
    parser.add_argument(
        "--since",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Khung thời gian cào: daily, weekly hoặc monthly",
    )
    parser.add_argument(
        "--recalculate",
        action="store_true",
        help="Tính toán lại Persistence & Velocity Scores cho toàn bộ repos",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Xóa sạch toàn bộ dữ liệu và tái cấu trúc database trắng",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.reset:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            print("✔ Đã reset toàn bộ cơ sở dữ liệu thành công!")
            return

        if args.recalculate:
            updated = recalculate_all_scores(db)
            print(f"✔ Đã tính toán lại điểm cho {updated} repositories!")
            return

        print(f"[*] Bắt đầu cào dữ liệu GitHub Trending [since={args.since}]...")
        session = crawler.crawl_and_save(db=db, since=args.since, is_manual=False)
        print(f"✔ Cào hoàn tất! Thu thập {session.items_count} repositories (Phiên #{session.id}, trạng thái: {session.status})")
    finally:
        db.close()

if __name__ == "__main__":
    main()
EOF`
Ran command: `PYTHONPATH=. .venv/bin/python3 -m app.cli_crawl --help`
Viewed crawler.py:190-214
Edited cli_crawl.py
Viewed cli_crawl.py:25-40
Viewed cli_crawl.py:41-49
Edited cli_crawl.py
Ran command: `PYTHONPATH=. .venv/bin/python3 -m app.cli_crawl --help`
Ran command: `./reset_db.sh`
Viewed index.html:170-215
Edited index.html
Viewed index.html:1960-1993
Edited index.html
Ran command: `PYTHONPATH=. .venv/bin/pytest -v tests/`

Đang thực hiện chạy kiểm thử kiểm tra toàn bộ các tính năng vừa thêm...

Used tool: schedule
Viewed test_api.py:30-70
Viewed test_api.py:71-115
Edited test_api.py
Edited test_api.py
Ran command: `PYTHONPATH=. .venv/bin/pytest -v tests/`

Đang chạy kiểm tra toàn bộ test suite...

Used tool: schedule
Edited api.py
Ran command: `PYTHONPATH=. .venv/bin/pytest -v tests/`

Đang chạy kiểm tra kiểm thử tự động...

Used tool: schedule
Ran command: `git status`
Ran command: `git add app/ tests/ reset_db.sh && git commit -m "feat: add demo data clear, database reset CLI & API, and standalone crawler CLI" && git push origin main`

Dưới đây là giải đáp chi tiết và đầy đủ cho 3 câu hỏi của bạn:

---

### 1. Bấm Dữ Liệu Demo Thì Xóa Như Thế Nào?

Khi bấm nút **Demo (3 Ngày)** hoặc **Demo 12 Tháng**, dữ liệu mô phỏng sẽ được lưu vào cơ sở dữ liệu SQLite (`data/trending.db`). Bạn có **2 cách** để xóa dữ liệu demo này:

#### Cách 1: Xóa trực tiếp trên giao diện Web (Không cần gõ lệnh)
1. Trên thanh điều hướng, bấm vào nút **"Cào Dữ Liệu"** để mở menu dropdown.
2. Tại mục *Quản lý dữ liệu*, bấm chọn **"Xóa dữ liệu demo"**.
3. Bấm **OK** xác nhận. Hệ thống sẽ xóa sạch 5 repo demo (`freeCodeCamp`, `DeepSeek-V3`, `shadcn/ui`, `elixir`, `browser-use`) và các snapshot liên quan, đồng thời **giữ nguyên toàn bộ các repo cào thật khác**.

#### Cách 2: Gọi nhanh qua API hoặc Curl
```bash
curl -X POST http://127.0.0.1:8001/api/demo/clear
```

---

### 2. Hướng Dẫn Lệnh Reset Dữ Liệu Repo (Làm Mới Trắng DB)

Nếu bạn muốn xóa sạch toàn bộ cơ sở dữ liệu (tất cả repo, snapshot, lịch sử cào) để bắt đầu lại từ con số 0:

#### Cách A: Dùng script reset tích hợp sẵn (Khuyên dùng - Nhanh nhất)
Mở terminal tại thư mục dự án và chạy:
```bash
./reset_db.sh
```
> Script sẽ tự động xóa file SQLite cũ và tái tạo cấu trúc bảng trắng tinh ngay tức thì.

#### Cách B: Dùng lệnh CLI Python
```bash
PYTHONPATH=. .venv/bin/python3 -m app.cli_crawl --reset
```

#### Cách C: Xóa trực tiếp file Database SQLite
```bash
rm -f data/trending.db
```
> Khi bạn chạy lại `./run.sh`, hệ thống sẽ tự động khởi tạo lại file database mới.

#### Cách D: Bấm trực tiếp trên giao diện Web
* Mở menu **"Cào Dữ Liệu"** $\rightarrow$ Chọn **"Reset toàn bộ DB"** $\rightarrow$ Xác nhận để làm trắng toàn bộ bảng.

---

### 3. Nếu Không Chạy Ứng Dụng Thì Có Cào Tự Động Được Không?

> **Trả lời ngắn gọn:** **KHÔNG THỂ**, nếu bạn tắt terminal chạy `./run.sh`.

#### Vì sao?
Bộ lập lịch tự động (`APScheduler`) được tích hợp **bên trong tiến trình Python của ứng dụng FastAPI**. Khi bạn tắt terminal hoặc tắt máy tính, tiến trình Python bị hủy $\rightarrow$ bộ hẹn giờ cũng tắt theo, nên không có gì thực thi việc cào dữ liệu.

---

### 💡 Giải Pháp Để Cào Tự Động Kể Cả Khi Tắt Ứng Dụng Web

Bạn có 2 giải pháp chuẩn cho môi trường Linux:

#### Giải Pháp 1: Dùng Crontab của Linux (Tối ưu nhất - Không cần bật web server)
Hệ điều hành Linux có sẵn bộ lập lịch hệ thống `cron`. Tôi đã tạo sẵn cho bạn công cụ CLI độc lập `app/cli_crawl.py`. Bạn chỉ cần đặt lịch vào Linux, Linux sẽ tự động chạy cào và ghi thẳng vào database mà **hoàn toàn không cần mở giao diện web**:

1. Mở trình chỉnh sửa crontab:
   ```bash
   crontab -e
   ```
2. Dán các dòng cấu hình tương ứng với lịch trình của bạn:
   ```cron
   # Daily: Cào 3 lần/ngày vào lúc 07:00, 13:00 và 20:00
   0 7,13,20 * * * cd /home/vvx/Documents/life_it_antigravity/crawl_github && .venv/bin/python3 -m app.cli_crawl --since daily >> crawl_daily.log 2>&1

   # Weekly: Cào 1 lần/ngày vào lúc 01:00 sáng
   0 1 * * * cd /home/vvx/Documents/life_it_antigravity/crawl_github && .venv/bin/python3 -m app.cli_crawl --since weekly >> crawl_weekly.log 2>&1

   # Monthly: Cào 2 lần/tuần vào Thứ 2 và Thứ 5 lúc 02:00 sáng
   0 2 * * 1,4 cd /home/vvx/Documents/life_it_antigravity/crawl_github && .venv/bin/python3 -m app.cli_crawl --since monthly >> crawl_monthly.log 2>&1
   ```
3. Lưu lại. Từ thời điểm này, máy tính Linux sẽ tự động cào đúng giờ. Khi nào bạn muốn xem bảng thống kê, chỉ cần gõ `./run.sh` mở web lên là dữ liệu mới nhất đã nằm sẵn trong database.

---

#### Giải Pháp 2: Cho Ứng Dụng Web Chạy Ngầm (Background Daemon)
Nếu bạn vẫn muốn ứng dụng web chạy liên tục 24/7 mà không bị tắt khi đóng cửa sổ terminal:

* **Chạy ngầm với nohup:**
  ```bash
  nohup ./run.sh > app.log 2>&1 &
  ```
  *(Ứng dụng vẫn sẽ chạy ngầm ngay cả khi bạn đóng terminal. Để tắt ứng dụng khi cần: `pkill -f "uvicorn app.main:app"`).*