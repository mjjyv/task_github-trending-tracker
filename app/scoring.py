import re
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

from app.models import Repository, RepoSnapshot


def _normalize_dt(dt: Optional[datetime]) -> datetime:
    """Đảm bảo datetime luôn ở dạng timezone-aware UTC để so sánh an toàn."""
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _extract_period_stars_count(repo: Repository, latest_snapshot: Optional[RepoSnapshot]) -> int:
    """Trích xuất số sao nhận được trong chu kỳ gần nhất."""
    if latest_snapshot and latest_snapshot.period_stars_count > 0:
        return latest_snapshot.period_stars_count

    # Fallback trích xuất từ chuỗi text ví dụ '52,955 stars this month'
    text = repo.latest_period_stars or ""
    match = re.search(r"([\d,]+)\s+stars", text)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0


def calculate_persistence_score(
    repo: Repository,
    snapshots: Optional[List[RepoSnapshot]] = None,
    current_time: Optional[datetime] = None,
) -> Tuple[float, str]:
    """
    Tính Điểm Bền Bỉ (Persistence Score) thang 0 - 100:
    Đo lường mức độ kiên trì bám trụ trên bảng trending của repo.
    """
    now = _normalize_dt(current_time or datetime.now(timezone.utc))
    
    # 1. Điểm cơ sở từ các mốc thời gian xuất hiện (tối đa 60đ)
    daily_pts = min(35.0, (repo.daily_appearances or 0) * 5.0)
    weekly_pts = min(25.0, (repo.weekly_appearances or 0) * 12.0)
    monthly_pts = min(30.0, (repo.monthly_appearances or 0) * 25.0)
    
    base_pts = daily_pts + weekly_pts + monthly_pts
    # Fallback nếu các mốc con chưa phân tách mà chỉ có total_appearances
    if base_pts == 0 and (repo.total_appearances or 0) > 0:
        base_pts = min(50.0, repo.total_appearances * 7.0)

    # 2. Tuổi thọ duy trì (Longevity: thời gian từ first_seen_at đến last_seen_at)
    longevity_pts = 0.0
    first_seen = _normalize_dt(repo.first_seen_at) if repo.first_seen_at else None
    last_seen = _normalize_dt(repo.last_seen_at or now)

    if first_seen:
        span_days = max(0.0, (last_seen - first_seen).total_seconds() / 86400.0)
        if span_days >= 30:
            longevity_pts = 25.0
        elif span_days >= 14:
            longevity_pts = 18.0
        elif span_days >= 7:
            longevity_pts = 12.0
        elif span_days >= 3:
            longevity_pts = 6.0
        else:
            longevity_pts = 2.0

    # 3. Điểm số lượng snapshot tích lũy (tối đa 15đ)
    snapshot_count = len(snapshots) if snapshots is not None else 1
    if snapshot_count >= 10:
        consistency_pts = 15.0
    elif snapshot_count >= 5:
        consistency_pts = 10.0
    elif snapshot_count >= 2:
        consistency_pts = 5.0
    else:
        consistency_pts = 2.0

    raw_score = base_pts + longevity_pts + consistency_pts

    # 4. Độ tươi mới (Recency decay)
    decay = 1.0
    if last_seen:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        days_inactive = max(0.0, (now - last_seen).total_seconds() / 86400.0)
        if days_inactive > 30:
            decay = 0.25
        elif days_inactive > 14:
            decay = 0.50
        elif days_inactive > 7:
            decay = 0.75
        elif days_inactive > 3:
            decay = 0.90
        else:
            decay = 1.0

    final_score = round(max(0.0, min(100.0, raw_score * decay)), 1)

    # Phân loại danh hiệu (Levels)
    if final_score >= 85.0:
        level = "legend"      # 🏆 Huyền thoại
    elif final_score >= 65.0:
        level = "high"        # 🔥 Bền bỉ
    elif final_score >= 35.0:
        level = "medium"      # ⚡ Ổn định
    else:
        level = "new"         # 🌱 Mới nổi

    return final_score, level


def calculate_velocity_score(
    repo: Repository,
    snapshots: Optional[List[RepoSnapshot]] = None,
) -> Tuple[float, str]:
    """
    Tính Điểm Tốc Độ Tăng Trưởng (Velocity Score) thang 0 - 100:
    Đo lường gia tốc thu hút cộng đồng và lượng star tăng vọt gần đây.
    """
    latest_snapshot = snapshots[-1] if snapshots else None

    # 1. Điểm từ số lượng sao tăng theo chu kỳ (tối đa 50đ)
    period_stars = _extract_period_stars_count(repo, latest_snapshot)
    period_pts = 0.0
    if period_stars >= 3000:
        period_pts = 50.0
    elif period_stars >= 1500:
        period_pts = 40.0
    elif period_stars >= 700:
        period_pts = 30.0
    elif period_stars >= 300:
        period_pts = 20.0
    elif period_stars >= 100:
        period_pts = 12.0
    elif period_stars > 0:
        period_pts = 6.0
    else:
        period_pts = 2.0

    # 2. Tốc độ thay đổi thực tế giữa 2 snapshot gần nhất (tối đa 30đ)
    delta_pts = 10.0  # điểm cơ sở
    if snapshots and len(snapshots) >= 2:
        sorted_snaps = sorted(snapshots, key=lambda s: _normalize_dt(s.crawled_at))
        s_prev = sorted_snaps[-2]
        s_curr = sorted_snaps[-1]

        t_curr = _normalize_dt(s_curr.crawled_at)
        t_prev = _normalize_dt(s_prev.crawled_at)
        hours = max(0.1, (t_curr - t_prev).total_seconds() / 3600.0)

        star_diff = max(0, (s_curr.stars or 0) - (s_prev.stars or 0))
        rate_per_day = (star_diff / hours) * 24.0

        if rate_per_day >= 1500:
            delta_pts = 30.0
        elif rate_per_day >= 800:
            delta_pts = 24.0
        elif rate_per_day >= 300:
            delta_pts = 18.0
        elif rate_per_day >= 100:
            delta_pts = 12.0
        elif rate_per_day > 0:
            delta_pts = 6.0
        else:
            delta_pts = 4.0

    # 3. Điểm thưởng vị trí thứ hạng (Rank factor, tối đa 20đ)
    rank = repo.latest_rank or (latest_snapshot.rank_position if latest_snapshot else 25)
    rank_pts = 0.0
    if rank == 1:
        rank_pts = 20.0
    elif rank <= 3:
        rank_pts = 16.0
    elif rank <= 7:
        rank_pts = 12.0
    elif rank <= 12:
        rank_pts = 8.0
    elif rank <= 20:
        rank_pts = 5.0
    else:
        rank_pts = 2.0

    final_score = round(max(0.0, min(100.0, period_pts + delta_pts + rank_pts)), 1)

    # Phân loại tốc độ (Levels)
    if final_score >= 80.0:
        level = "rocket"      # 🚀 Tên lửa
    elif final_score >= 60.0:
        level = "surging"     # ⚡ Bứt phá
    elif final_score >= 30.0:
        level = "steady"      # 📈 Tăng đều
    else:
        level = "slow"        # 🐌 Chậm

    return final_score, level


def update_repo_scores(repo: Repository, snapshots: Optional[List[RepoSnapshot]] = None) -> None:
    """Cập nhật Persistence Score và Velocity Score cho một repository."""
    p_score, p_level = calculate_persistence_score(repo, snapshots)
    v_score, v_level = calculate_velocity_score(repo, snapshots)

    repo.persistence_score = p_score
    repo.persistence_level = p_level
    repo.velocity_score = v_score
    repo.velocity_level = v_level


def recalculate_all_scores(db: Session) -> int:
    """Tính toán lại điểm số cho toàn bộ repository trong cơ sở dữ liệu."""
    repos = db.query(Repository).all()
    count = 0
    for repo in repos:
        snapshots = (
            db.query(RepoSnapshot)
            .filter(RepoSnapshot.repo_id == repo.id)
            .order_by(RepoSnapshot.crawled_at.asc())
            .all()
        )
        update_repo_scores(repo, snapshots)
        count += 1
    db.commit()
    return count
