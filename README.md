# GitHub Trending Tracker & Bảng Thống Kê Xu Hướng

Hệ thống tự động cào dữ liệu từ [GitHub Trending](https://github.com/trending) (hỗ trợ `daily`, `weekly`, `monthly`), lưu trữ vào cơ sở dữ liệu SQLite/PostgreSQL, tự động tính toán lũy kế **số lần xuất hiện (occurrence counter)** qua các ngày, và hiển thị bảng thống kê trực quan, lọc và sắp xếp linh hoạt.

---

## 🚀 Tính Năng Nổi Bật

1. **Bộ Cào Dữ Liệu Tự Động (GitHub Trending Crawler):**
   - Hỗ trợ đầy đủ các mốc: `daily` (hôm nay), `weekly` (tuần này), `monthly` (tháng này).
   - Bóc tách chi tiết: Tên repo, tác giả, mô tả, ngôn ngữ lập trình + mã màu, tổng stars, forks, số stars tăng thêm theo mốc, vị trí xếp hạng (rank).
   - Trang bị Headers chống chặn, cơ chế timeout và xử lý lỗi mạng tự động.

2. **Cơ Chế Đếm Số Lần Xuất Hiện Thông Minh (Occurrence Counter):**
   - **Ngày 1 cào:** Repo A xuất hiện lần đầu $\rightarrow$ Số lần xuất hiện = `1`.
   - **Cào lại trong cùng ngày 1:** Cập nhật thông số sao/fork mới nhất, **không** làm tăng số lần xuất hiện sai lệch (chống đếm trùng / idempotent).
   - **Sang ngày 2 cào tiếp:** Nếu Repo A tiếp tục xuất hiện $\rightarrow$ Số lần xuất hiện tăng lên `2`.
   - Phân loại rõ ràng: Tổng số lần xuất hiện, số lần xuất hiện theo mốc Daily, Weekly, Monthly.

3. **Giao Diện Bảng Thống Kê Trực Quan (Tabular Dashboard):**
   - Thiết kế hiện đại (Dark theme lấy cảm hứng từ GitHub & Tailwind CSS).
   - **Bảng danh sách chi tiết:** Highlight nổi bật cột **Số lần xuất hiện** (`🔥 3 lần`, `⚡ 2 lần`, `1 lần`).
   - Sắp xếp động (Click tiêu đề cột để sắp xếp theo: Số lần xuất hiện, Stars, Thời gian,...).
   - Tìm kiếm tức thì (Live search) theo tên repo, tác giả hoặc từ khóa mô tả.
   - Bộ lọc theo tab mốc thời gian (`Daily`, `Weekly`, `Monthly`, `Tất cả`), lọc theo ngôn ngữ lập trình, lọc chỉ hiện các repo lặp lại ($\ge 2$ lần).
   - Nút **"Cào Dữ Liệu Ngay"** trực tiếp từ trình duyệt.
   - Nút **"Nạp Demo (3 Ngày)"** để kiểm tra ngay dữ liệu mô phỏng 3 ngày cào liên tiếp mà không cần chờ sang ngày hôm sau.
   - Modal xem chi tiết lịch sử xuất hiện qua các ngày của từng repository.
   - Modal xem nhật ký các phiên cào dữ liệu.

4. **Tự Động Hóa Lịch Trình (Scheduler):**
   - Tích hợp `APScheduler` tự động kích hoạt cào định kỳ hàng ngày.

---

## 📁 Cấu Trúc Thư Mục

```text
crawl_github/
├── app/
│   ├── __init__.py
│   ├── config.py             # Cấu hình đường dẫn DB, URL, User-Agent
│   ├── database.py           # Kết nối SQLite/PostgreSQL, init_db
│   ├── models.py             # SQLAlchemy models (Repository, CrawlSession, RepoSnapshot)
│   ├── schemas.py            # Pydantic schemas cho API
│   ├── parser.py             # Bóc tách HTML GitHub Trending
│   ├── crawler.py            # Engine cào dữ liệu & xử lý logic tăng counter
│   ├── scheduler.py          # Background APScheduler tự động cào hàng ngày
│   ├── api.py                # Các RESTful API endpoints
│   ├── main.py               # Ứng dụng FastAPI chính
│   └── templates/
│       └── index.html        # Giao diện bảng thống kê dạng Tabular
├── tests/
│   ├── __init__.py
│   ├── test_parser.py        # Test bộ bóc tách HTML
│   ├── test_crawler_logic.py # Test logic tăng số lần xuất hiện qua nhiều ngày
│   └── test_api.py           # Test toàn bộ API endpoints
├── docs/
│   └── html01.html           # File HTML mẫu từ GitHub Trending
├── run.sh                    # Script khởi động 1-click
├── requirements.txt          # Danh sách thư viện Python
└── README.md
```

---

## 🛠️ Hướng Dẫn Cài Đặt & Chạy Ứng Dụng

### Cách 1: Chạy Bằng Script 1-Click (Khuyến nghị)
Chỉ cần mở terminal tại thư mục dự án và chạy:
```bash
./run.sh
```
Script sẽ tự động tạo môi trường ảo `.venv`, cài đặt thư viện và khởi động Web Dashboard tại:
👉 **http://127.0.0.1:8000**

---

### Cách 2: Cài Đặt Thủ Công
1. Khởi tạo môi trường ảo Python:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Cài đặt các gói thư viện:
   ```bash
   pip install -r requirements.txt
   ```
3. Khởi động Web Dashboard:
   ```bash
   python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
4. Truy cập giao diện tại: `http://127.0.0.1:8000`.

---

## 💻 Chạy Cào Dữ Liệu Từ Dòng Lệnh (CLI)

Bạn có thể cào dữ liệu trực tiếp bằng terminal mà không cần mở trình duyệt:
```bash
# Cào daily trending mặc định
python3 -m app.crawler --since daily

# Cào weekly trending
python3 -m app.crawler --since weekly

# Cào monthly trending
python3 -m app.crawler --since monthly

# Ép buộc tăng +1 lần xuất hiện (bỏ qua kiểm tra cùng ngày)
python3 -m app.crawler --since daily --force
```

---

## 🧪 Chạy Kiểm Thử (Automated Tests)

Chạy bộ test tự động để xác minh toàn bộ các chức năng:
```bash
PYTHONPATH=. .venv/bin/pytest -v -s tests/
```
Các kịch bản test bao gồm:
1. `test_parser.py`: Kiểm tra độ chính xác khi bóc tách thẻ HTML từ GitHub Trending.
2. `test_crawler_logic.py`: Kiểm tra quy tắc tăng số lần xuất hiện qua 3 ngày liên tiếp và chống đếm trùng khi cào nhiều lần trong 1 ngày.
3. `test_api.py`: Kiểm tra toàn bộ các API endpoint, lọc, tìm kiếm, phân trang và nạp dữ liệu demo.
