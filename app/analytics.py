import re
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict, Any

from app.models import Repository, RepoSnapshot


def _normalize_dt(dt: Optional[datetime]) -> datetime:
    """Đảm bảo datetime luôn ở dạng timezone-aware UTC."""
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_time_window(
    window_code: Optional[str] = "all",
    custom_start: Optional[date] = None,
    custom_end: Optional[date] = None,
    base_date: Optional[date] = None,
) -> Tuple[Optional[date], Optional[date], str]:
    """
    Phân tích mã khoảng thời gian (window_code) thành cặp (start_date, end_date) và nhãn mô tả.
    Mặc định base_date là hôm nay.
    """
    if not base_date:
        base_date = date.today()

    if not window_code or window_code == "all":
        return None, None, "Toàn bộ thời gian (All-time)"

    if window_code == "7d":
        start = base_date - timedelta(days=7)
        return start, base_date, "7 ngày gần đây"

    if window_code == "30d":
        start = base_date - timedelta(days=30)
        return start, base_date, "30 ngày gần đây"

    if window_code == "90d":
        start = base_date - timedelta(days=90)
        return start, base_date, "3 tháng gần đây (90 ngày)"

    if window_code == "180d" or window_code == "6m":
        start = base_date - timedelta(days=180)
        return start, base_date, "6 tháng gần đây (180 ngày)"

    if window_code == "365d" or window_code == "1y":
        start = base_date - timedelta(days=365)
        return start, base_date, "1 năm qua (365 ngày)"

    if window_code == "custom":
        if custom_start and custom_end:
            return custom_start, custom_end, f"Từ {custom_start} đến {custom_end}"
        if custom_start:
            return custom_start, base_date, f"Từ {custom_start} đến nay"
        if custom_end:
            return None, custom_end, f"Đến ngày {custom_end}"
        return None, None, "Tùy chọn thời gian"

    return None, None, "Toàn bộ thời gian"


def calculate_window_metrics(
    repo: Repository,
    snapshots: List[RepoSnapshot],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Tính toán chỉ số hoạt động của repository TRONG RIÊNG KHOẢNG THỜI GIAN [start_date, end_date].
    Giải quyết triệt để bài toán: Repo đã nổi tiếng từ lâu nhưng trong kỳ này không trending
    sẽ có điểm số = 0 hoặc rất thấp và không thể chiếm vị trí hàng đầu.
    """
    # 1. Lọc snapshot thuộc cửa sổ thời gian
    filtered_snaps: List[RepoSnapshot] = []
    for s in snapshots:
        rec_date = s.record_date
        if not rec_date and s.crawled_at:
            rec_date = s.crawled_at.date()
        
        if rec_date:
            if start_date and rec_date < start_date:
                continue
            if end_date and rec_date > end_date:
                continue
            filtered_snaps.append(s)

    # Sắp xếp theo ngày tăng dần
    filtered_snaps.sort(key=lambda s: (_normalize_dt(s.crawled_at), s.id or 0))
    snap_count = len(filtered_snaps)

    # 2. Nếu không có snapshot nào trong kỳ này
    if snap_count == 0:
        is_legacy = (repo.current_stars or 0) >= 20000
        return {
            "window_appearances": 0,
            "window_daily_appearances": 0,
            "window_weekly_appearances": 0,
            "window_monthly_appearances": 0,
            "window_stars_gained": 0,
            "window_avg_rank": None,
            "window_best_rank": None,
            "window_persistence_score": 0.0,
            "window_velocity_score": 0.0,
            "window_trending_score": 0.0,
            "is_active_in_window": False,
            "lifecycle_code": "legacy_dormant" if is_legacy else "inactive",
            "lifecycle_label": "💤 Di Sản Hạ Nhiệt" if is_legacy else "⚪ Chưa Hoạt Động",
            "lifecycle_desc": (
                f"Repo có lượng star tích lũy lớn ({repo.current_stars:,} ⭐) nhưng hoàn toàn không lọt top trending trong khoảng thời gian này."
                if is_legacy
                else "Chưa ghi nhận lần xuất hiện nào trên GitHub Trending trong khoảng thời gian này."
            ),
            "snapshots_count": 0,
        }

    # 3. Tính số lần xuất hiện theo chu kỳ trong window
    daily_count = sum(1 for s in filtered_snaps if s.since == "daily")
    weekly_count = sum(1 for s in filtered_snaps if s.since == "weekly")
    monthly_count = sum(1 for s in filtered_snaps if s.since == "monthly")
    total_window_appearances = snap_count

    # 4. Tính lượng Stars thu hoạch được trong kỳ
    first_snap = filtered_snaps[0]
    last_snap = filtered_snaps[-1]
    star_delta = max(0, (last_snap.stars or 0) - (first_snap.stars or 0))

    if star_delta == 0:
        star_delta = sum(max(0, s.period_stars_count or 0) for s in filtered_snaps)

    # 5. Phân tích thứ hạng rank
    ranks = [s.rank_position for s in filtered_snaps if s.rank_position is not None and s.rank_position > 0]
    avg_rank = round(sum(ranks) / len(ranks), 1) if ranks else None
    best_rank = min(ranks) if ranks else None

    # 6. Tính Persistence Score trong kỳ (thang 0 - 100)
    p_appearances_pts = min(40.0, daily_count * 6.0 + weekly_count * 12.0 + monthly_count * 20.0)
    p_consistency_pts = min(30.0, snap_count * 5.0)

    span_days = max(1.0, (filtered_snaps[-1].record_date - filtered_snaps[0].record_date).days) if filtered_snaps[-1].record_date and filtered_snaps[0].record_date else 1.0
    p_span_pts = min(30.0, (span_days / 30.0) * 15.0)

    raw_p_score = p_appearances_pts + p_consistency_pts + p_span_pts
    window_p_score = round(max(0.0, min(100.0, raw_p_score)), 1)

    # 7. Tính Velocity Score trong kỳ (thang 0 - 100)
    v_star_pts = 0.0
    if star_delta >= 10000:
        v_star_pts = 50.0
    elif star_delta >= 5000:
        v_star_pts = 42.0
    elif star_delta >= 2000:
        v_star_pts = 34.0
    elif star_delta >= 800:
        v_star_pts = 26.0
    elif star_delta >= 300:
        v_star_pts = 18.0
    elif star_delta > 0:
        v_star_pts = 10.0
    else:
        v_star_pts = 4.0

    v_rank_pts = 0.0
    if best_rank == 1:
        v_rank_pts = 30.0
    elif best_rank and best_rank <= 3:
        v_rank_pts = 24.0
    elif best_rank and best_rank <= 10:
        v_rank_pts = 16.0
    elif best_rank and best_rank <= 20:
        v_rank_pts = 10.0
    else:
        v_rank_pts = 4.0

    freq_rate = (snap_count / max(1.0, span_days)) * 7.0
    v_freq_pts = min(20.0, freq_rate * 5.0)

    window_v_score = round(max(0.0, min(100.0, v_star_pts + v_rank_pts + v_freq_pts)), 1)

    # 8. Điểm Trending Tổng Hợp Trong Kỳ (Window Trending Score)
    appearance_factor = min(100.0, total_window_appearances * 12.0)
    window_trending_score = round(
        0.45 * window_v_score + 0.35 * window_p_score + 0.20 * appearance_factor, 1
    )

    stage_info = _evaluate_stage(
        p_score=window_p_score,
        v_score=window_v_score,
        stars_gained=star_delta,
        appearances=total_window_appearances,
        current_stars=repo.current_stars or 0,
    )

    return {
        "window_appearances": total_window_appearances,
        "window_daily_appearances": daily_count,
        "window_weekly_appearances": weekly_count,
        "window_monthly_appearances": monthly_count,
        "window_stars_gained": star_delta,
        "window_avg_rank": avg_rank,
        "window_best_rank": best_rank,
        "window_persistence_score": window_p_score,
        "window_velocity_score": window_v_score,
        "window_trending_score": window_trending_score,
        "is_active_in_window": True,
        "lifecycle_code": stage_info["code"],
        "lifecycle_label": stage_info["label"],
        "lifecycle_desc": stage_info["desc"],
        "snapshots_count": snap_count,
    }


def _evaluate_stage(
    p_score: float,
    v_score: float,
    stars_gained: int,
    appearances: int,
    current_stars: int,
) -> Dict[str, str]:
    """Phân loại giai đoạn vòng đời dựa trên các chỉ số trong kỳ."""
    if v_score >= 70.0 and stars_gained >= 1500:
        return {
            "code": "viral_surge",
            "label": "🚀 Bùng Nổ Công Nghệ",
            "desc": f"Tốc độ tăng trưởng cực mạnh (+{stars_gained:,} ⭐), thu hút sự chú ý đặc biệt lớn từ cộng đồng.",
        }
    if p_score >= 60.0 and appearances >= 4:
        return {
            "code": "sustained_anchor",
            "label": "🛡️ Trụ Cột Bền Bỉ",
            "desc": "Bám trụ kiên cường trên top trending trong suốt kỳ, thể hiện sự ổn định và tin cậy cao.",
        }
    if current_stars >= 30000 and appearances <= 1 and v_score < 35.0:
        return {
            "code": "legacy_giant",
            "label": "💤 Di Sản / Hạ Nhiệt",
            "desc": "Dự án kinh điển đã bão hòa thị phần, tốc độ nhận star mới chậm lại và ít khi xuất hiện trên trending.",
        }
    if current_stars < 5000 and v_score >= 50.0:
        return {
            "code": "emerging_prospect",
            "label": "🌱 Mới Nổi Tiềm Năng",
            "desc": "Repository mới phát triển nhưng có gia tốc nhận sao ấn tượng, đáng để theo dõi.",
        }
    if p_score >= 35.0 or v_score >= 35.0:
        return {
            "code": "active_growth",
            "label": "📈 Tăng Trưởng Ổn Định",
            "desc": "Duy trì nhịp độ phát triển đều đặn, cộng đồng lập trình viên đón nhận tích cực.",
        }
    return {
        "code": "moderate",
        "label": "⚡ Tiềm Năng Khám Phá",
        "desc": "Có xuất hiện trên bảng xếp hạng với quy mô tăng trưởng vừa phải.",
    }


def compare_repo_periods(
    repo: Repository,
    snapshots: List[RepoSnapshot],
    p1_start: Optional[date],
    p1_end: Optional[date],
    p2_start: Optional[date],
    p2_end: Optional[date],
    p1_name: str = "Kỳ Gần Đây (6 Tháng)",
    p2_name: str = "Kỳ Trước Đó (6 Tháng)",
) -> Dict[str, Any]:
    """
    So sánh chi tiết 2 kỳ hoạt động của 1 repository (Period-over-Period).
    Ví dụ: 6 tháng gần đây vs 6 tháng trước đó, hoặc 6 tháng cùng kỳ năm trước.
    """
    m1 = calculate_window_metrics(repo, snapshots, p1_start, p1_end)
    m2 = calculate_window_metrics(repo, snapshots, p2_start, p2_end)

    delta_stars = m1["window_stars_gained"] - m2["window_stars_gained"]
    pct_stars_change = None
    if m2["window_stars_gained"] > 0:
        pct_stars_change = round(((m1["window_stars_gained"] - m2["window_stars_gained"]) / m2["window_stars_gained"]) * 100, 1)

    delta_appearances = m1["window_appearances"] - m2["window_appearances"]
    delta_p_score = round(m1["window_persistence_score"] - m2["window_persistence_score"], 1)
    delta_v_score = round(m1["window_velocity_score"] - m2["window_velocity_score"], 1)
    delta_trending_score = round(m1["window_trending_score"] - m2["window_trending_score"], 1)
    delta_avg_rank = None
    if m1.get("window_avg_rank") is not None and m2.get("window_avg_rank") is not None:
        delta_avg_rank = round(m1["window_avg_rank"] - m2["window_avg_rank"], 1)

    trajectory = _evaluate_trajectory(m1, m2, repo, delta_stars, pct_stars_change)

    return {
        "repository": repo.to_dict(),
        "period_1": {
            "name": p1_name,
            "start_date": p1_start.isoformat() if p1_start else None,
            "end_date": p1_end.isoformat() if p1_end else None,
            "metrics": m1,
        },
        "period_2": {
            "name": p2_name,
            "start_date": p2_start.isoformat() if p2_start else None,
            "end_date": p2_end.isoformat() if p2_end else None,
            "metrics": m2,
        },
        "delta": {
            "stars_gained": delta_stars,
            "stars_gained_pct": pct_stars_change,
            "appearances": delta_appearances,
            "persistence_score": delta_p_score,
            "velocity_score": delta_v_score,
            "trending_score": delta_trending_score,
            "avg_rank": delta_avg_rank,
        },
        "lifecycle_trajectory": trajectory,
    }


def _evaluate_trajectory(
    m1: Dict[str, Any],
    m2: Dict[str, Any],
    repo: Repository,
    delta_stars: int,
    pct_change: Optional[float],
) -> Dict[str, Any]:
    """
    Sinh phân tích nhận định thông minh giải thích ý nghĩa các chỉ số.
    """
    # 1. Nhận diện trường hợp Di Sản Hạ Nhiệt (Legacy Giant Saturated)
    if (repo.current_stars or 0) >= 25000 and m1["window_appearances"] <= 1 and m1["window_velocity_score"] < 35.0:
        return {
            "badge": "💤 Di Sản / Đã Bão Hòa (Legacy Giant)",
            "tone": "warning",
            "stage_summary": "Repo nổi tiếng lâu năm nhưng ít xuất hiện trên trending gần đây.",
            "insight_text": (
                f"Với tổng số sao khổng lồ ({repo.current_stars:,} ⭐), repo đã trở thành một tiêu chuẩn ngành từ lâu. "
                f"Tuy nhiên trong kỳ gần đây, repo chỉ có {m1['window_appearances']} lần trending với +{m1['window_stars_gained']:,} ⭐ mới. "
                f"Lý do: Đa số lập trình viên đều đã biết và gắn sao từ trước, tốc độ đón nhận mới tự nhiên giảm đi."
            ),
            "meaning_for_dev": "Vẫn là phần mềm chất lượng cao, nhưng không còn là 'trend' nóng hổi nhất thời điểm hiện tại.",
        }

    # 2. Nhận diện trường hợp Bùng Nổ Ra Mắt Mới (Viral Breakthrough / Apex)
    if m2["window_appearances"] == 0 and m1["window_appearances"] >= 2 and (m1["window_velocity_score"] >= 65.0 or m1["window_stars_gained"] >= 3000):
        return {
            "badge": "🚀 Đỉnh Cao Bùng Nổ (Viral Apex)",
            "tone": "accent",
            "stage_summary": "Repo xuất hiện và tạo cơn sốt với tốc độ đón nhận kỷ lục.",
            "insight_text": (
                f"Trước đây chưa từng xuất hiện trên trending, nhưng trong kỳ này repo đã bùng nổ với {m1['window_appearances']} lần lọt top "
                f"và thu hoạch +{m1['window_stars_gained']:,} stars (V-Score đạt {m1['window_velocity_score']}). "
                f"Xếp hạng trung bình đạt top {m1.get('window_avg_rank') or 'hàng đầu'}."
            ),
            "meaning_for_dev": "Công nghệ mang tính đột phá hoặc xu hướng rất hot (AI, Tooling tốc độ cao). Nên trải nghiệm ngay.",
        }

    # 3. Nhận diện trường hợp Tái Sinh (Revival)
    if m2["window_appearances"] >= 1 and m1["window_appearances"] >= 3 and delta_stars > 0 and m1["window_velocity_score"] >= 45.0:
        return {
            "badge": "🔄 Tái Sinh Đột Phá (Revival)",
            "tone": "success",
            "stage_summary": "Dự án hồi sinh mạnh mẽ sau giai đoạn trầm lắng.",
            "insight_text": (
                f"Ở {m2.get('window_appearances', 0)} lần xuất hiện trong kỳ trước, repo từng khá yên ắng (+{m2['window_stars_gained']:,} ⭐). "
                f"Tuy nhiên trong kỳ gần đây, repo đã bứt phá với {m1['window_appearances']} lần lọt top trending "
                f"và thu hút thêm +{m1['window_stars_gained']:,} ⭐ (V-Score: {m1['window_velocity_score']}). "
                f"Điều này thường phản ánh việc phát hành phiên bản lớn (Major v2/v3 rewrite) hoặc bắt nhịp công nghệ mới."
            ),
            "meaning_for_dev": "Tín hiệu tích cực: Cộng đồng đang quay trở lại ủng hộ mạnh mẽ dự án này.",
        }

    # 4. Nhận diện trường hợp Trụ Cột Bền Vững (Sustained Anchor)
    if m1["window_persistence_score"] >= 55.0 and m2["window_persistence_score"] >= 40.0:
        return {
            "badge": "🛡️ Trụ Cột Bền Vững (Ecosystem Pillar)",
            "tone": "info",
            "stage_summary": "Dự án duy trì phong độ xuất sắc liên tục qua nhiều chu kỳ.",
            "insight_text": (
                f"Repo giữ vững chỉ số bền bỉ ấn tượng: {m1['window_persistence_score']} điểm kỳ này so với {m2['window_persistence_score']} điểm kỳ trước. "
                f"Tổng số lần trending đạt {m1['window_appearances']} lần. "
                f"Không có dấu hiệu suy thoái phong độ."
            ),
            "meaning_for_dev": "Độ tin cậy ở mức cao nhất, thích hợp làm nền tảng chính cho các dự án dài hạn.",
        }

    # 5. Nhận diện trường hợp Thoái Trào (Cooling Down)
    if delta_stars < 0 and m1["window_appearances"] < m2["window_appearances"]:
        return {
            "badge": "📉 Hạ Nhiệt Tương Đối (Cooling Down)",
            "tone": "muted",
            "stage_summary": "Tốc độ quan tâm giảm bớt so với kỳ hoàng kim trước đó.",
            "insight_text": (
                f"Số sao mới và tần suất trending trong kỳ này giảm sút (giảm {abs(delta_stars):,} ⭐ và ít hơn {abs(m1['window_appearances'] - m2['window_appearances'])} lần trending). "
                f"Sự chú ý của cộng đồng đang dịch chuyển dần sang các giải pháp thay thế mới hơn."
            ),
            "meaning_for_dev": "Cần theo dõi xem dự án có ra mắt roadmap đột phá mới hay đang dần thoái trào.",
        }

    # Mặc định
    return {
        "badge": "📈 Phát Triển Ổn Định (Steady Progress)",
        "tone": "info",
        "stage_summary": "Dự án phát triển nhịp nhàng, cộng đồng duy trì sự quan tâm ổn định.",
        "insight_text": (
            f"Trong kỳ gần đây, repo ghi nhận {m1['window_appearances']} lần lọt top trending và tích lũy thêm +{m1['window_stars_gained']:,} ⭐. "
            f"Các chỉ số Persistence ({m1['window_persistence_score']}) và Velocity ({m1['window_velocity_score']}) ở mức hài hòa."
        ),
        "meaning_for_dev": "Dự án hoạt động lành mạnh và có sự phát triển liên tục.",
    }
