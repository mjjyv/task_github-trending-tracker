# Kế Hoạch: Cấu Hình Cào Tự Động & Tính Persistence Score, Velocity Score

Hệ thống nâng cấp cơ chế tự động hoá lịch cào đa tầng và tích hợp 2 chỉ số phân tích chuyên sâu cho từng repository: **Điểm Bền Bỉ (Persistence Score)** và **Điểm Tốc Độ (Velocity Score)**.

---

## 1. User Review Required (Các quyết định kỹ thuật & Công thức tính)

> [!IMPORTANT]
> **1. Lịch Trình Cào Tự Động Định Sẵn (Cron Schedule):**
> - **Theo Ngày (Daily - 3 lần/ngày):** `07:00`, `13:00`, `20:00` (mỗi 6-8 tiếng một lần để bắt nhịp giờ hoạt động các timezone châu Á, Âu, Mỹ).
> - **Theo Tuần (Weekly - 1 lần/ngày):** `01:00` sáng mỗi ngày (cập nhật bảng weekly sau khi ngày mới bắt đầu).
> - **Theo Tháng (Monthly - 2 lần/tuần):** Thứ Hai và Thứ Năm lúc `02:00` sáng (`day_of_week='mon,thu'`, `hour=2`).

> [!IMPORTANT]
> **2. Công thức tính Persistence Score (Điểm Bền Bỉ — Thang 0 - 100):**
> Điểm số đo lường mức độ kiên trì và bền bỉ của repository trên bảng xếp hạng qua thời gian.
> - **Tần suất xuất hiện theo mốc thời gian:**
>   - Mỗi ngày Daily trending: $+5$ điểm (tối đa 40đ)
>   - Mỗi lần Weekly trending: $+12$ điểm (tối đa 30đ)
>   - Mỗi lần Monthly trending: $+25$ điểm (tối đa 30đ)
> - **Longevity Bonus (Tuổi thọ trên trending):**
>   - Duy trì trên trending $\ge 7$ ngày: $+10$ điểm.
>   - Duy trì $\ge 14$ ngày: $+20$ điểm.
>   - Duy trì $\ge 30$ ngày: $+30$ điểm.
> - **Recency Decay (Hao mòn theo thời gian):**
>   - Nếu lần cuối xuất hiện (`last_seen_at`) trong vòng 48h: giữ 100% điểm.
>   - Nếu quá 3 ngày không xuất hiện: giảm 10%.
>   - Nếu quá 7 ngày không xuất hiện: giảm 25%.
>   - Nếu quá 14 ngày không xuất hiện: giảm 50%.
> - **Phân cấp danh hiệu:**
>   - `🏆 Huyền Thoại (Legend)`: $\ge 85$
>   - `🔥 Bền Bỉ (High)`: $65 - 84$
>   - `⚡ Ổn Định (Medium)`: $35 - 64$
>   - `🌱 Mới Nổi (New)`: $< 35$

> [!IMPORTANT]
> **3. Công thức tính Velocity Score (Điểm Tốc Độ / Tăng Trưởng — Thang 0 - 100):**
> Điểm số đo lường gia tốc thu hút cộng đồng và lượng star tăng vọt gần đây.
> - **Số sao tăng gần nhất (`period_stars_count`):**
>   - $> 2,000$ stars/ngày hoặc $> 10,000$ stars/tháng: $+50$ điểm.
>   - $1,000 - 2,000$ stars: $+35$ điểm.
>   - $500 - 1,000$ stars: $+20$ điểm.
>   - $100 - 500$ stars: $+10$ điểm.
> - **Tốc độ thay đổi giữa 2 snapshot gần nhất ($\Delta \text{stars} / \Delta t$):**
>   - Đo lường gia tốc thực tế giữa các lần cào trong ngày (tối đa 30 điểm).
> - **Thứ hạng đỉnh cao (Rank Factor):**
>   - Top 1 - 3: $+20$ điểm.
>   - Top 4 - 10: $+10$ điểm.
>   - Top 11 - 25: $+5$ điểm.
> - **Phân cấp tốc độ:**
>   - `🚀 Tên Lửa (Rocket)`: $\ge 80$
>   - `⚡ Bứt Phá (Surging)`: $60 - 79$
>   - `📈 Tăng Đều (Steady)`: $30 - 59$
>   - `🐌 Chậm (Slow)`: $< 30$

---

## 2. Thay Đổi Cấu Trúc Dữ Liệu (Database & Models)

### Bảng `repositories` thêm các trường:
- `persistence_score`: Float (0.0 đến 100.0, indexed)
- `velocity_score`: Float (0.0 đến 100.0, indexed)
- `persistence_level`: String (ví dụ "legend", "high", "medium", "new")
- `velocity_level`: String (ví dụ "rocket", "surging", "steady", "slow")

---

## 3. Các Bước Thực Hiện Cụ Thể

### Bước 1: Mở rộng Model & Database Migration
- Cập nhật [`app/models.py`](file:///home/vvx/Documents/life_it_antigravity/crawl_github/app/models.py) bổ sung 4 cột mới.
- Cập nhật hàm khởi tạo DB trong [`app/database.py`](file:///home/vvx/Documents/life_it_antigravity/crawl_github/app/database.py) để tự động thêm cột nếu database SQLite hiện tại chưa có (tránh phải xóa DB cũ).

### Bước 2: Xây Dựng Engine Tính Điểm (`app/scoring.py`)
- Viết module độc lập [`app/scoring.py`](file:///home/vvx/Documents/life_it_antigravity/crawl_github/app/scoring.py):
  - `calculate_persistence_score(repo, snapshots) -> (score, level)`
  - `calculate_velocity_score(repo, snapshots) -> (score, level)`
  - `update_all_repo_scores(db) -> int`
- Tích hợp tự động tính lại điểm sau mỗi đợt cào trong [`app/crawler.py`](file:///home/vvx/Documents/life_it_antigravity/crawl_github/app/crawler.py).

### Bước 3: Cấu Hình Lịch Trình Đa Tầng Trong [`app/scheduler.py`](file:///home/vvx/Documents/life_it_antigravity/crawl_github/app/scheduler.py)
- Cấu hình 3 CronTrigger riêng biệt:
  1. `daily_crawl_job`: 3 lần/ngày (`hour="7,13,20", minute=0`)
  2. `weekly_crawl_job`: 1 lần/ngày (`hour=1, minute=0`)
  3. `monthly_crawl_job`: 2 lần/tuần (`day_of_week="mon,thu", hour=2, minute=0`)
- Thêm API endpoint `GET /api/scheduler/jobs` để hiển thị thời gian chạy tiếp theo (next run time) của từng job trên UI.

### Bước 4: Mở Rộng API & Schema
- Cập nhật [`app/schemas.py`](file:///home/vvx/Documents/life_it_antigravity/crawl_github/app/schemas.py) thêm các trường score vào `RepositoryOut`.
- Cập nhật [`app/api.py`](file:///home/vvx/Documents/life_it_antigravity/crawl_github/app/api.py):
  - Hỗ trợ sắp xếp `sort_by=persistence_score` và `sort_by=velocity_score`.
  - Hỗ trợ lọc theo danh hiệu `min_persistence` và `min_velocity`.
  - Endpoint `POST /api/scores/recalculate`: Kích hoạt tính toán lại toàn bộ điểm cho tất cả repo.

### Bước 5: Cập Nhật Giao Diện UI Tabular ([`app/templates/index.html`](file:///home/vvx/Documents/life_it_antigravity/crawl_github/app/templates/index.html))
- Hiển thị cột / badge **Điểm Bền Bỉ (Persistence)** và **Điểm Tốc Độ (Velocity)** với thiết kế cao cấp (Ethereal Glass, gradient pill).
- Bổ sung tùy chọn sắp xếp và bộ lọc nhanh theo 2 chỉ số này.
- Thêm widget lịch trình tự động (hiển thị 3 mốc Daily 3x, Weekly 1x, Monthly 2x/tuần và đếm ngược lần cào kế tiếp).
- Trong modal chi tiết repo: Hiển thị Breakdown thanh điểm trực quan cho cả 2 chỉ số.

---

## 4. Kế Hoạch Xác Minh (Verification Plan)

### Automated Tests
1. `tests/test_scoring.py`:
   - Test thuật toán tính Persistence Score cho các tình huống (repo lâu năm vs repo mới nổi, repo bị decay).
   - Test thuật toán tính Velocity Score (repo tăng trưởng thần tốc vs repo tăng chậm).
2. `tests/test_scheduler.py`:
   - Kiểm tra APScheduler đăng ký chính xác 3 jobs với cron triggers tương ứng.
3. `tests/test_api.py`:
   - Kiểm tra API trả về đủ 2 trường điểm và hỗ trợ sort/filter theo score.

### Manual Verification
- Khởi động server với `./run.sh`.
- Bấm "Recalculate Scores" hoặc nạp demo để xem điểm Persistence & Velocity hiển thị trên bảng.
- Kiểm tra widget hiển thị lịch cào tự động và đếm ngược thời gian chạy tiếp theo.
