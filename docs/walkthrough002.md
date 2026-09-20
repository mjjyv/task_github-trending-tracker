# Tổng Kết Triển Khai: Time-Window Trending, So Sánh Đa Kỳ (Time-Travel) & Giải Nghĩa Vòng Đời Repository

Hệ thống **GitHub Trending Tracker** đã được nâng cấp toàn diện theo yêu cầu mới của người dùng:
1. **Khắc phục triệt để vấn đề "Repo cũ ở mãi trên đầu":** Đưa vào cơ chế cửa sổ thời gian trượt (Time-Window / Sliding Window). Các dự án di sản đã bão hòa (như *freeCodeCamp, vuejs...*) với hàng trăm nghìn stars từ nhiều năm trước sẽ tự động nhường vị trí dẫn đầu cho các repo mới bùng nổ gần đây.
2. **So sánh trạng thái qua từng thời kỳ (Period-over-Period / Time-Travel):** Cho phép đối chiếu chi tiết giữa 2 khoảng thời gian (ví dụ: *6 tháng gần đây vs 6 tháng trước đó*, hoặc *6 tháng gần đây vs cùng kỳ năm ngoái*).
3. **Bộ máy giải nghĩa chỉ số & 6 giai đoạn vòng đời (Lifecycle Trajectory Engine):** Phân tích $\Delta$ biến động và tự động sinh nhận định thông minh về ý nghĩa thực tế của các chỉ số cho developer.

---

## 🚀 Các Tính Năng Mới Đã Hoàn Thành

### 1. 🪟 Cửa Sổ Thời Gian Động (Dynamic Time-Window Filtering)
- Hỗ trợ chọn nhanh các khoảng thời gian:
  - **7 Ngày** (`7d`), **30 Ngày** (`30d`), **3 Tháng** (`90d`), **6 Tháng Gần Đây** (`180d`), **1 Năm** (`365d`), hoặc **Toàn Bộ** (`all`).
- **Chỉ số động độc quyền trong kỳ:**
  - `window_appearances`: Số ngày xuất hiện trên top trending trong kỳ.
  - `window_stars_gained`: Số stars thực nhận thêm trong kỳ.
  - `window_persistence_score`: Điểm bám trụ bảng xếp hạng trong kỳ ($0 \rightarrow 100$).
  - `window_velocity_score`: Gia tốc bứt phá và thứ hạng đạt được trong kỳ ($0 \rightarrow 100$).
  - `window_trending_score`: Điểm tổng hợp trọng số ($0.45 \times V + 0.35 \times P + 0.20 \times \text{freq}$).
- **Cơ chế hạ bệ Repo bão hòa:** Nếu một repo không có bất kỳ lần trending nào trong khung thời gian đã chọn (ví dụ 6 tháng gần đây), điểm trending trong kỳ sẽ bằng $0.0$, gắn nhãn `💤 Di Sản Hạ Nhiệt`, và tự động bị đẩy xuống dưới các repo đang hot. Người dùng cũng có tùy chọn toggle *"Chỉ hiện repo có trending trong kỳ"*.

---

### 2. 📊 Bộ Máy So Sánh Đa Kỳ & Du Hành Thời Gian (`GET /api/repositories/{id}/compare`)
- Cho phép đối chiếu bất kỳ repo nào theo các preset tiêu chuẩn hoặc tùy biến:
  - `6m_vs_prior_6m`: **6 tháng gần đây vs 6 tháng trước đó**.
  - `6m_vs_same_last_year`: **6 tháng gần đây vs cùng kỳ năm ngoái**.
  - `30d_vs_prior_30d`: **30 ngày gần đây vs 30 ngày trước**.
- **Bảng đối chiếu Side-by-Side:**
  - Số ngày trending, số stars thu hoạch mới kèm % tăng trưởng.
  - Biến động Điểm Bền Bỉ ($\Delta P$), Điểm Tốc Độ ($\Delta V$), Điểm Trending ($\Delta \text{Score}$).
  - Thay đổi thứ hạng bình quân (tăng/giảm bao nhiêu bậc).

---

### 3. 🧠 Phân Loại 6 Giai Đoạn Vòng Đời & Giải Nghĩa Ý Nghĩa Cho Developer

Hệ thống tự động phân tích ma trận dữ liệu $(P_1, P_2, \Delta)$ để xếp repo vào 1 trong 6 giai đoạn vòng đời công nghệ:

| Giai Đoạn | Icon & Danh Hiệu | Đặc Điểm Nhận Diện | Ý Nghĩa Thực Tế Cho Lập Trình Viên |
| :--- | :--- | :--- | :--- |
| **1. Viral Apex** | 🚀 **Bùng Nổ** | V-Score $\ge 70$, stars tăng đột biến | Công nghệ mang tính đột phá hoặc xu hướng rất hot (AI, Tooling tốc độ cao). Nên trải nghiệm và thử nghiệm ngay. |
| **2. Ecosystem Pillar** | 🛡️ **Trụ Cột Bền Vững** | P-Score $\ge 60$ duy trì qua cả 2 kỳ | Thư viện/framework hạ tầng đã đạt độ chín muồi cao, an tâm dùng cho production quy mô lớn. |
| **3. Legacy Giant** | 💤 **Di Sản / Bão Hòa** | All-time stars rất cao ($>30k$), nhưng kỳ gần đây rất ít trending | Vẫn là phần mềm tiêu chuẩn chất lượng cao, nhưng đã bão hòa thị phần, không còn là "trend" nóng hổi thời điểm này. |
| **4. Revival** | 🔄 **Tái Sinh Đột Phá** | Kỳ trước im ắng, kỳ này tăng trưởng $>+50\%$ stars | Dự án có bước ngoặt lớn (ví dụ bản Major v2/v3 rewrite, tích hợp AI). Đáng để xem xét lại nếu trước đây từng bỏ qua. |
| **5. Cooling Down** | 📉 **Hạ Nhiệt Tương Đối** | Tần suất trending và star sụt giảm so với kỳ trước | Dự án bắt đầu chậm lại hoặc cộng đồng đang chuyển dịch sang các giải pháp thay thế hiện đại hơn. |
| **6. Emerging Prospect**| 🌱 **Mới Nổi Tiềm Năng** | Repo mới dưới 60 ngày nhưng lọt top trending cao | Dự án tiềm năng đang trên đà phát triển, nên thêm vào danh sách theo dõi (*Watchlist*). |

---

### 4. 🎨 Giao Diện UI/UX Nâng Cấp (Double-Bezel & Ethereal Glass)
- **Thanh Segmented Bar Khung Thời Gian:** Nằm ngay trên bảng điều khiển, thao tác chuyển kỳ 1 chạm với chuyển động haptic mượt mà.
- **Cột Bảng Mới "Vòng Đời / Trend Kỳ":** Hiển thị trực quan Badge vòng đời và điểm số trong kỳ của từng repo.
- **Nút So Sánh 📊:** Mở ngay modal đối chiếu side-by-side với thẻ phân tích AI trực quan.
- **Modal Cẩm Nang Ý Nghĩa Chỉ Số (Guide Modal):** Hướng dẫn lý thuyết và ý nghĩa toàn diện của từng thang đo.
- **Nút "Demo 12 Tháng" trên Navbar:** Nạp tức thì bộ dữ liệu mô phỏng 12-18 tháng cho 5 repo đại diện để người dùng trải nghiệm ngay mà không cần chờ thu thập dữ liệu thật.

---

## 🧪 Kết Quả Kiểm Thử (Verification Results)

Toàn bộ **12/12 test suites** đều vượt qua xuất sắc (**100% PASSED**):

```bash
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/vvx/Documents/life_it_antigravity/crawl_github

tests/test_analytics.py::test_parse_time_window PASSED                   [  8%]
tests/test_analytics.py::test_calculate_window_metrics_legacy_drop PASSED [ 16%]
tests/test_analytics.py::test_period_comparison_and_trajectory PASSED    [ 25%]
tests/test_analytics.py::test_api_time_window_and_compare PASSED         [ 33%]
tests/test_api.py::test_index_page PASSED                                [ 41%]
tests/test_api.py::test_seed_demo_and_query_repositories PASSED          [ 50%]
tests/test_crawler_logic.py::test_occurrence_counter_multi_day PASSED    [ 58%]
tests/test_parser.py::test_parse_html01 PASSED                           [ 66%]
tests/test_scheduler.py::test_scheduler_jobs_registration PASSED         [ 75%]
tests/test_scoring.py::test_persistence_score_calculation PASSED         [ 83%]
tests/test_scoring.py::test_velocity_score_calculation PASSED            [ 91%]
tests/test_scoring.py::test_update_repo_scores PASSED                    [100%]

======================== 12 passed, 2 warnings in 3.97s ========================
```

---

## 💻 Hướng Dẫn Trải Nghiệm Nhanh

### 1. Khởi chạy ứng dụng:
```bash
./run.sh
```
Truy cập: **http://127.0.0.1:8000** (hoặc port hiển thị trong terminal).

### 2. Thao tác thử nghiệm:
1. **Nạp dữ liệu 12 tháng:** Bấm nút **"Demo 12 Tháng"** ở thanh điều hướng trên cùng. Hệ thống sẽ tự động tạo dữ liệu mô phỏng 18 tháng và chuyển sang chế độ **"6 Tháng Gần Đây"**.
2. **Kiểm chứng hạ bệ repo cũ:**
   - Quan sát repo `freeCodeCamp/freeCodeCamp`: Dù có tổng $395,000$ stars nhưng trong 6 tháng gần đây điểm Trending Kỳ là $0.0$, danh hiệu `💤 Di Sản Hạ Nhiệt`, nhường toàn bộ vị trí đầu bảng cho các repo mới như `DeepSeek-V3` và `browser-use`.
3. **So sánh 6 tháng gần đây vs 6 tháng trước đó:**
   - Bấm nút biểu tượng đồ thị **📊** ở cột ngoài cùng của `freeCodeCamp` hoặc `DeepSeek-V3`.
   - Xem bảng đối chiếu side-by-side và đọc thẻ nhận định thông minh về vòng đời và ý nghĩa cho lập trình viên.
4. **Đọc cẩm nang:** Bấm nút **"Ý Nghĩa Chỉ Số"** trên thanh navbar để xem bảng tra cứu 6 giai đoạn vòng đời.
