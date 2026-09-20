import os
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func, or_

from app.database import get_db, Base, engine
from app.models import Repository, CrawlSession, RepoSnapshot
from app.crawler import GitHubTrendingCrawler
from app.scoring import recalculate_all_scores
from app.scheduler import get_scheduled_jobs_info, toggle_scheduler, is_scheduler_active
from app.analytics import (
    parse_time_window,
    calculate_window_metrics,
    compare_repo_periods,
)
from app.schemas import (
    RepositoryOut,
    PaginatedRepositories,
    CrawlSessionOut,
    CrawlTriggerRequest,
    CrawlTriggerResponse,
    StatsSummary,
    RepoSnapshotOut,
    SchedulerJobOut,
    PeriodComparisonOut,
)

router = APIRouter(prefix="/api")
crawler = GitHubTrendingCrawler()


@router.get("/repositories", response_model=PaginatedRepositories)
def get_repositories(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên repo hoặc mô tả"),
    language: Optional[str] = Query(None, description="Lọc theo ngôn ngữ lập trình"),
    since: Optional[str] = Query(None, description="Lọc theo thời gian: daily, weekly, monthly"),
    min_appearances: Optional[int] = Query(None, ge=1, description="Số lần xuất hiện tối thiểu"),
    min_persistence: Optional[float] = Query(None, ge=0, le=100, description="Điểm bền bỉ tối thiểu"),
    min_velocity: Optional[float] = Query(None, ge=0, le=100, description="Điểm tốc độ tối thiểu"),
    time_window: Optional[str] = Query("all", description="Khoảng thời gian: all, 7d, 30d, 90d, 180d, 365d, custom"),
    start_date: Optional[date] = Query(None, description="Ngày bắt đầu (khi chọn custom)"),
    end_date: Optional[date] = Query(None, description="Ngày kết thúc (khi chọn custom)"),
    hide_inactive: bool = Query(False, description="Chỉ hiển thị các repo có hoạt động trong kỳ"),
    sort_by: str = Query("total_appearances", description="Cột cần sắp xếp"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    if not isinstance(page, int):
        page = 1
    if not isinstance(page_size, int):
        page_size = 25
    if not isinstance(time_window, str):
        time_window = "all"
    if not isinstance(hide_inactive, bool):
        hide_inactive = False
    if not isinstance(sort_by, str):
        sort_by = "total_appearances"
    if not isinstance(sort_dir, str):
        sort_dir = "desc"

    start_dt, end_dt, window_label = parse_time_window(time_window, start_date, end_date)
    is_windowed = bool(start_dt or end_dt or (time_window and time_window != "all"))

    query = db.query(Repository)

    # 1. Tìm kiếm từ khóa
    if search and isinstance(search, str):
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Repository.full_name.ilike(search_pattern),
                Repository.description.ilike(search_pattern),
            )
        )

    # 2. Lọc theo ngôn ngữ
    if language and isinstance(language, str) and language != "all":
        query = query.filter(Repository.language == language)

    # 3. Lọc theo since
    if since and isinstance(since, str) and since != "all":
        if since == "daily":
            query = query.filter(Repository.daily_appearances > 0)
        elif since == "weekly":
            query = query.filter(Repository.weekly_appearances > 0)
        elif since == "monthly":
            query = query.filter(Repository.monthly_appearances > 0)

    # 4. Lọc theo số lần xuất hiện tối thiểu (khi không chọn window)
    if not is_windowed and isinstance(min_appearances, int):
        query = query.filter(Repository.total_appearances >= min_appearances)

    # 5. Lọc theo điểm số (khi không chọn window)
    if not is_windowed:
        if isinstance(min_persistence, (int, float)):
            query = query.filter(Repository.persistence_score >= min_persistence)
        if isinstance(min_velocity, (int, float)):
            query = query.filter(Repository.velocity_score >= min_velocity)

    all_matching_repos = query.all()

    # Preload snapshots in bulk
    repo_ids = [r.id for r in all_matching_repos]
    snapshots_by_repo = {rid: [] for rid in repo_ids}
    if repo_ids:
        snaps = (
            db.query(RepoSnapshot)
            .filter(RepoSnapshot.repo_id.in_(repo_ids))
            .order_by(RepoSnapshot.crawled_at.asc())
            .all()
        )
        for s in snaps:
            snapshots_by_repo[s.repo_id].append(s)

    processed_repos = []
    for r in all_matching_repos:
        repo_snaps = snapshots_by_repo.get(r.id, [])
        metrics = calculate_window_metrics(r, repo_snaps, start_dt, end_dt)

        if hide_inactive and not metrics["is_active_in_window"]:
            continue

        if is_windowed:
            if isinstance(min_appearances, int) and metrics["window_appearances"] < min_appearances:
                continue
            if isinstance(min_persistence, (int, float)) and metrics["window_persistence_score"] < min_persistence:
                continue
            if isinstance(min_velocity, (int, float)) and metrics["window_velocity_score"] < min_velocity:
                continue

        # Gán thuộc tính động
        r.window_appearances = metrics["window_appearances"] if is_windowed else r.total_appearances
        r.window_stars_gained = metrics["window_stars_gained"]
        r.window_persistence_score = metrics["window_persistence_score"] if is_windowed else r.persistence_score
        r.window_velocity_score = metrics["window_velocity_score"] if is_windowed else r.velocity_score
        r.window_trending_score = metrics["window_trending_score"] if is_windowed else round(
            0.45 * (r.velocity_score or 0.0) + 0.35 * (r.persistence_score or 0.0) + 0.20 * min(100.0, (r.total_appearances or 0) * 10.0), 1
        )
        r.window_avg_rank = metrics["window_avg_rank"] if is_windowed else r.latest_rank
        r.window_best_rank = metrics["window_best_rank"] if is_windowed else r.latest_rank
        r.is_active_in_window = metrics["is_active_in_window"] if is_windowed else True
        r.lifecycle_code = metrics["lifecycle_code"]
        r.lifecycle_label = metrics["lifecycle_label"]
        r.lifecycle_desc = metrics["lifecycle_desc"]
        processed_repos.append(r)

    # Sắp xếp linh hoạt
    def sort_key(r):
        if sort_by in ("window_trending_score", "trending_score"):
            return r.window_trending_score or 0.0
        elif sort_by in ("total_appearances", "window_appearances"):
            return r.window_appearances if is_windowed else (r.total_appearances or 0)
        elif sort_by == "window_stars_gained":
            return r.window_stars_gained or 0
        elif sort_by == "persistence_score":
            return r.window_persistence_score if is_windowed else (r.persistence_score or 0.0)
        elif sort_by == "velocity_score":
            return r.window_velocity_score if is_windowed else (r.velocity_score or 0.0)
        elif sort_by == "current_stars":
            return r.current_stars or 0
        elif sort_by == "current_forks":
            return r.current_forks or 0
        elif sort_by == "latest_rank":
            rank_val = r.window_avg_rank if is_windowed else r.latest_rank
            return -(rank_val or 999)
        elif sort_by == "last_seen_at":
            return r.last_seen_at or datetime.min
        elif sort_by == "first_seen_at":
            return r.first_seen_at or datetime.min
        return r.window_trending_score or 0.0

    reverse_sort = (sort_dir == "desc")
    processed_repos.sort(key=sort_key, reverse=reverse_sort)

    total = len(processed_repos)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    items = processed_repos[(page - 1) * page_size : page * page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "time_window": time_window or "all",
        "time_window_label": window_label,
        "start_date": start_dt.isoformat() if start_dt else None,
        "end_date": end_dt.isoformat() if end_dt else None,
        "items": items,
    }


@router.get("/repositories/{repo_id}")
def get_repository_detail(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository không tồn tại")

    snapshots = (
        db.query(RepoSnapshot)
        .filter(RepoSnapshot.repo_id == repo_id)
        .order_by(desc(RepoSnapshot.crawled_at))
        .all()
    )

    return {
        "repository": repo.to_dict(),
        "snapshots": [s.to_dict() for s in snapshots],
    }


@router.get("/repositories/{repo_id}/history", response_model=List[RepoSnapshotOut])
def get_repository_history(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository không tồn tại")

    snapshots = (
        db.query(RepoSnapshot)
        .filter(RepoSnapshot.repo_id == repo_id)
        .order_by(asc(RepoSnapshot.crawled_at))
        .all()
    )
    return snapshots


@router.post("/crawl/trigger", response_model=CrawlTriggerResponse)
def trigger_crawl(
    req: CrawlTriggerRequest,
    force_increment: bool = Query(False, description="Bắt buộc tăng số lần xuất hiện bất kể cùng ngày"),
    db: Session = Depends(get_db),
):
    try:
        session = crawler.crawl_and_save(
            db=db,
            since=req.since,
            is_manual=True,
            force_increment=force_increment,
        )
        return {
            "message": f"Cào dữ liệu thành công cho mốc '{req.since}'",
            "session_id": session.id,
            "status": session.status,
            "items_count": session.items_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi cào dữ liệu: {str(e)}")


@router.get("/crawl/sessions", response_model=List[CrawlSessionOut])
def get_crawl_sessions(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(CrawlSession)
        .order_by(desc(CrawlSession.started_at))
        .limit(limit)
        .all()
    )
    return sessions


@router.get("/languages")
def get_languages(db: Session = Depends(get_db)):
    results = (
        db.query(Repository.language, func.count(Repository.id).label("count"))
        .filter(Repository.language.isnot(None))
        .group_by(Repository.language)
        .order_by(desc("count"))
        .all()
    )
    return [{"language": r[0], "count": r[1]} for r in results]


@router.get("/stats/summary", response_model=StatsSummary)
def get_stats_summary(db: Session = Depends(get_db)):
    total_repos = db.query(func.count(Repository.id)).scalar() or 0
    total_sessions = db.query(func.count(CrawlSession.id)).scalar() or 0
    repeated_count = (
        db.query(func.count(Repository.id))
        .filter(Repository.total_appearances > 1)
        .scalar()
        or 0
    )

    # Top ngôn ngữ
    lang_results = (
        db.query(Repository.language, func.count(Repository.id).label("count"))
        .filter(Repository.language.isnot(None))
        .group_by(Repository.language)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )
    top_languages = [{"language": r[0], "count": r[1]} for r in lang_results]

    # Top repo xuất hiện nhiều nhất
    top_recurring = (
        db.query(Repository)
        .order_by(desc(Repository.total_appearances), desc(Repository.current_stars))
        .limit(5)
        .all()
    )

    return {
        "total_repositories": total_repos,
        "total_crawl_sessions": total_sessions,
        "repeated_repositories_count": repeated_count,
        "top_languages": top_languages,
        "top_recurring_repos": top_recurring,
    }


@router.post("/seed-demo")
def seed_demo_data(db: Session = Depends(get_db)):
    """
    Tải sẵn dữ liệu mẫu thực tế từ docs/html01.html mô phỏng cào qua 3 ngày liên tiếp
    để người dùng có thể ngay lập tức trải nghiệm bảng thống kê với các repo có số lần xuất hiện 1, 2, 3 lần.
    """
    html_path = os.path.join(os.path.dirname(__file__), "..", "docs", "html01.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file mẫu docs/html01.html")

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    today = date.today()
    day1 = today - timedelta(days=2)
    day2 = today - timedelta(days=1)
    day3 = today

    # Ngày 1: Cào lần đầu
    crawler.crawl_and_save(
        db=db,
        since="daily",
        html_override=html_content,
        crawl_date=day1,
        is_manual=True,
    )

    # Ngày 2: Cào lần 2 (tăng lên 2 lần)
    crawler.crawl_and_save(
        db=db,
        since="daily",
        html_override=html_content,
        crawl_date=day2,
        is_manual=True,
    )

    # Ngày 3: Cào lần 3 cho một số repo chọn lọc hoặc tất cả để minh họa
    crawler.crawl_and_save(
        db=db,
        since="daily",
        html_override=html_content,
        crawl_date=day3,
        is_manual=True,
    )

    # Tính toán lại toàn bộ Persistence & Velocity Score cho dữ liệu demo
    recalculate_all_scores(db)

    return {
        "message": "Đã tạo thành công dữ liệu demo mô phỏng 3 ngày cào dữ liệu kèm Persistence & Velocity scores!",
        "days": [day1.isoformat(), day2.isoformat(), day3.isoformat()],
    }


@router.post("/scores/recalculate")
def recalculate_scores(db: Session = Depends(get_db)):
    """Tính toán lại Persistence Score và Velocity Score cho toàn bộ repository."""
    updated = recalculate_all_scores(db)
    return {
        "message": f"Đã tính toán lại điểm số cho {updated} repositories thành công!",
        "count": updated,
    }


@router.get("/scheduler/jobs", response_model=List[SchedulerJobOut])
def get_scheduler_jobs():
    """Lấy danh sách các lịch trình cào tự động và thời gian chạy tiếp theo."""
    return get_scheduled_jobs_info()


@router.post("/scheduler/toggle")
def toggle_scheduler_endpoint(enable: Optional[bool] = None):
    """
    Bật hoặc tắt bộ lập lịch nội bộ (APScheduler).
    Rất hữu ích khi người dùng đã cài đặt cronjob của hệ điều hành Linux.
    """
    active = toggle_scheduler(enable)
    status_str = "BẬT" if active else "TẮT"
    return {
        "is_active": active,
        "message": f"Bộ lập lịch tự động nội bộ đã được {status_str} thành công!",
    }


@router.get("/scheduler/status")
def get_scheduler_status():
    """Kiểm tra trạng thái kích hoạt của bộ lập lịch tự động APScheduler."""
    return {
        "is_active": is_scheduler_active(),
    }



@router.get("/repositories/{repo_id}/compare", response_model=PeriodComparisonOut)
def compare_repository_periods(
    repo_id: int,
    preset: str = Query("6m_vs_prior_6m", description="6m_vs_prior_6m, 6m_vs_same_last_year, 30d_vs_prior_30d, custom"),
    p1_start: Optional[date] = None,
    p1_end: Optional[date] = None,
    p2_start: Optional[date] = None,
    p2_end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    So sánh trạng thái và chỉ số hoạt động của 1 repository giữa 2 khoảng thời gian (Period-over-Period).
    Ví dụ: 6 tháng gần đây vs 6 tháng trước đó, hoặc 6 tháng cùng kỳ năm ngoái.
    """
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository không tồn tại")

    today = date.today()
    if preset == "6m_vs_prior_6m":
        p1_start_dt = today - timedelta(days=180)
        p1_end_dt = today
        p1_name = "6 Tháng Gần Đây"

        p2_start_dt = today - timedelta(days=360)
        p2_end_dt = today - timedelta(days=181)
        p2_name = "6 Tháng Trước Đó"
    elif preset == "6m_vs_same_last_year":
        p1_start_dt = today - timedelta(days=180)
        p1_end_dt = today
        p1_name = "6 Tháng Gần Đây"

        p2_start_dt = (today - timedelta(days=365)) - timedelta(days=180)
        p2_end_dt = today - timedelta(days=365)
        p2_name = "6 Tháng Cùng Kỳ Năm Trước"
    elif preset == "30d_vs_prior_30d":
        p1_start_dt = today - timedelta(days=30)
        p1_end_dt = today
        p1_name = "30 Ngày Gần Đây"

        p2_start_dt = today - timedelta(days=60)
        p2_end_dt = today - timedelta(days=31)
        p2_name = "30 Ngày Trước Đó"
    else:  # custom
        p1_start_dt = p1_start or (today - timedelta(days=180))
        p1_end_dt = p1_end or today
        p1_name = f"{p1_start_dt} → {p1_end_dt}"

        p2_start_dt = p2_start or (today - timedelta(days=360))
        p2_end_dt = p2_end or (today - timedelta(days=181))
        p2_name = f"{p2_start_dt} → {p2_end_dt}"

    snapshots = (
        db.query(RepoSnapshot)
        .filter(RepoSnapshot.repo_id == repo_id)
        .order_by(RepoSnapshot.crawled_at.asc())
        .all()
    )

    result = compare_repo_periods(
        repo=repo,
        snapshots=snapshots,
        p1_start=p1_start_dt,
        p1_end=p1_end_dt,
        p2_start=p2_start_dt,
        p2_end=p2_end_dt,
        p1_name=p1_name,
        p2_name=p2_name,
    )
    return result


@router.post("/seed-timeline-demo")
def seed_timeline_demo(db: Session = Depends(get_db)):
    """
    Nạp dữ liệu mô phỏng 12 - 18 tháng lịch sử cho các trường hợp thực tế tiêu biểu:
    1. freeCodeCamp/freeCodeCamp: Di sản nổi tiếng lâu năm (395k stars), rất hot cách đây 1 năm nhưng 6 tháng gần đây không xuất hiện trên trending.
    2. deepseek-ai/DeepSeek-V3: Bùng nổ công nghệ gần đây (từ 0 lên 58k stars trong 6 tháng gần đây).
    3. shadcn-ui/ui: Trụ cột bền bỉ (tăng đều đặn cả 2 kỳ, P-score cao).
    4. elixir-lang/elixir: Hồi sinh đột phá (kỳ trước chỉ 1 lần, kỳ này 8 lần kèm bản update lớn).
    5. browser-use/browser-use: Mới nổi tiềm năng trong 60 ngày gần đây.
    """
    today = date.today()
    now_utc = datetime.now(timezone.utc)

    # Khởi tạo hoặc lấy CrawlSession đại diện cho demo
    demo_session = (
        db.query(CrawlSession)
        .filter(CrawlSession.error_message == "timeline_demo_session")
        .first()
    )
    if not demo_session:
        demo_session = CrawlSession(
            since_param="daily",
            started_at=now_utc,
            completed_at=now_utc,
            status="success",
            items_count=50,
            is_manual=True,
            error_message="timeline_demo_session",
        )
        db.add(demo_session)
        db.commit()
        db.refresh(demo_session)

    configs = [
        {
            "full_name": "freeCodeCamp/freeCodeCamp",
            "owner": "freeCodeCamp",
            "name": "freeCodeCamp",
            "url": "https://github.com/freeCodeCamp/freeCodeCamp",
            "description": "freeCodeCamp.org's open-source codebase and curriculum. Learn to code for free.",
            "language": "TypeScript",
            "language_color": "#3178c6",
            "current_stars": 395000,
            "current_forks": 36500,
            "snapshots_plan": [
                # 10 snapshots cách đây 360 -> 190 ngày (không có snapshot trong 180 ngày gần đây)
                {"days_ago": 350, "stars": 372000, "period": 1200, "rank": 1, "since": "daily"},
                {"days_ago": 330, "stars": 375000, "period": 1100, "rank": 2, "since": "weekly"},
                {"days_ago": 300, "stars": 379000, "period": 1400, "rank": 1, "since": "daily"},
                {"days_ago": 280, "stars": 381500, "period": 950, "rank": 3, "since": "daily"},
                {"days_ago": 250, "stars": 385000, "period": 1300, "rank": 2, "since": "weekly"},
                {"days_ago": 220, "stars": 388500, "period": 1050, "rank": 1, "since": "daily"},
                {"days_ago": 195, "stars": 391000, "period": 850, "rank": 4, "since": "monthly"},
            ],
        },
        {
            "full_name": "deepseek-ai/DeepSeek-V3",
            "owner": "deepseek-ai",
            "name": "DeepSeek-V3",
            "url": "https://github.com/deepseek-ai/DeepSeek-V3",
            "description": "An open-source, 671B mixture-of-experts model trained on 14.8T tokens.",
            "language": "Python",
            "language_color": "#3572A5",
            "current_stars": 58400,
            "current_forks": 7200,
            "snapshots_plan": [
                # Toàn bộ trong 150 ngày gần đây, không có snapshot kỳ trước
                {"days_ago": 140, "stars": 4200, "period": 3500, "rank": 1, "since": "daily"},
                {"days_ago": 120, "stars": 12500, "period": 4800, "rank": 1, "since": "daily"},
                {"days_ago": 95, "stars": 24000, "period": 5200, "rank": 1, "since": "weekly"},
                {"days_ago": 70, "stars": 35500, "period": 4100, "rank": 2, "since": "daily"},
                {"days_ago": 45, "stars": 44800, "period": 3900, "rank": 1, "since": "weekly"},
                {"days_ago": 20, "stars": 52300, "period": 3400, "rank": 1, "since": "daily"},
                {"days_ago": 3, "stars": 58400, "period": 2800, "rank": 1, "since": "daily"},
            ],
        },
        {
            "full_name": "shadcn-ui/ui",
            "owner": "shadcn-ui",
            "name": "ui",
            "url": "https://github.com/shadcn-ui/ui",
            "description": "Beautifully designed components that you can copy and paste into your apps. Accessible. Customizable. Open Source.",
            "language": "TypeScript",
            "language_color": "#3178c6",
            "current_stars": 74500,
            "current_forks": 6100,
            "snapshots_plan": [
                # Phân bổ đều đặn cả 2 kỳ (kỳ trước và kỳ này)
                {"days_ago": 340, "stars": 36000, "period": 1400, "rank": 3, "since": "daily"},
                {"days_ago": 290, "stars": 42500, "period": 1600, "rank": 2, "since": "weekly"},
                {"days_ago": 230, "stars": 49000, "period": 1800, "rank": 2, "since": "daily"},
                {"days_ago": 190, "stars": 53500, "period": 1500, "rank": 3, "since": "monthly"},
                # Kỳ gần đây
                {"days_ago": 150, "stars": 58200, "period": 1700, "rank": 2, "since": "daily"},
                {"days_ago": 110, "stars": 63400, "period": 1900, "rank": 2, "since": "weekly"},
                {"days_ago": 60, "stars": 69000, "period": 1650, "rank": 3, "since": "daily"},
                {"days_ago": 5, "stars": 74500, "period": 1550, "rank": 2, "since": "daily"},
            ],
        },
        {
            "full_name": "elixir-lang/elixir",
            "owner": "elixir-lang",
            "name": "elixir",
            "url": "https://github.com/elixir-lang/elixir",
            "description": "Elixir is a dynamic, functional language for building scalable and maintainable applications.",
            "language": "Elixir",
            "language_color": "#6e4a7e",
            "current_stars": 26800,
            "current_forks": 3400,
            "snapshots_plan": [
                # Kỳ trước rất trầm lắng (1 lần)
                {"days_ago": 280, "stars": 22100, "period": 250, "rank": 18, "since": "monthly"},
                # Kỳ gần đây bứt phá với bản update lớn
                {"days_ago": 110, "stars": 23200, "period": 950, "rank": 5, "since": "daily"},
                {"days_ago": 80, "stars": 24300, "period": 1200, "rank": 3, "since": "daily"},
                {"days_ago": 40, "stars": 25600, "period": 1150, "rank": 4, "since": "weekly"},
                {"days_ago": 8, "stars": 26800, "period": 980, "rank": 3, "since": "daily"},
            ],
        },
        {
            "full_name": "browser-use/browser-use",
            "owner": "browser-use",
            "name": "browser-use",
            "url": "https://github.com/browser-use/browser-use",
            "description": "Make websites accessible for AI agents. Open-source web automation library.",
            "language": "Python",
            "language_color": "#3572A5",
            "current_stars": 18200,
            "current_forks": 1950,
            "snapshots_plan": [
                # Mới toanh chỉ trong 50 ngày gần đây
                {"days_ago": 45, "stars": 1500, "period": 1500, "rank": 1, "since": "daily"},
                {"days_ago": 30, "stars": 6800, "period": 2800, "rank": 1, "since": "daily"},
                {"days_ago": 15, "stars": 13400, "period": 3200, "rank": 2, "since": "weekly"},
                {"days_ago": 2, "stars": 18200, "period": 2100, "rank": 1, "since": "daily"},
            ],
        },
    ]

    seeded_names = []
    for cfg in configs:
        repo = db.query(Repository).filter(Repository.full_name == cfg["full_name"]).first()
        if not repo:
            repo = Repository(
                full_name=cfg["full_name"],
                owner=cfg["owner"],
                name=cfg["name"],
                url=cfg["url"],
                description=cfg["description"],
                language=cfg["language"],
                language_color=cfg["language_color"],
                current_stars=cfg["current_stars"],
                current_forks=cfg["current_forks"],
                first_seen_at=now_utc - timedelta(days=cfg["snapshots_plan"][0]["days_ago"]),
                last_seen_at=now_utc - timedelta(days=cfg["snapshots_plan"][-1]["days_ago"]),
            )
            db.add(repo)
            db.flush()
        else:
            repo.current_stars = cfg["current_stars"]
            repo.current_forks = cfg["current_forks"]
            repo.description = cfg["description"]

        # Xóa các snapshot cũ của demo repo để tạo chuỗi thời gian chuẩn xác
        db.query(RepoSnapshot).filter(RepoSnapshot.repo_id == repo.id).delete()

        # Tạo snapshots theo kế hoạch
        total_snaps = len(cfg["snapshots_plan"])
        daily_cnt = 0
        weekly_cnt = 0
        monthly_cnt = 0

        for sp in cfg["snapshots_plan"]:
            snap_date = today - timedelta(days=sp["days_ago"])
            snap_dt = now_utc - timedelta(days=sp["days_ago"])
            if sp["since"] == "daily":
                daily_cnt += 1
            elif sp["since"] == "weekly":
                weekly_cnt += 1
            elif sp["since"] == "monthly":
                monthly_cnt += 1

            snapshot = RepoSnapshot(
                repo_id=repo.id,
                session_id=demo_session.id,
                record_date=snap_date,
                since=sp["since"],
                rank_position=sp["rank"],
                stars=sp["stars"],
                forks=max(10, sp["stars"] // 10),
                period_stars_count=sp["period"],
                period_stars_text=f"{sp['period']:,} stars",
                crawled_at=snap_dt,
            )
            db.add(snapshot)

        repo.total_appearances = total_snaps
        repo.daily_appearances = daily_cnt
        repo.weekly_appearances = weekly_cnt
        repo.monthly_appearances = monthly_cnt
        repo.latest_rank = cfg["snapshots_plan"][-1]["rank"]
        repo.latest_period_stars = f"{cfg['snapshots_plan'][-1]['period']:,} stars"
        seeded_names.append(repo.full_name)

    db.commit()
    recalculate_all_scores(db)

    return {
        "message": "Đã nạp thành công bộ dữ liệu mô phỏng 12 - 18 tháng cho các trường hợp vòng đời thực tế!",
        "seeded_repositories": seeded_names,
    }


@router.post("/demo/clear")
def clear_demo_data(db: Session = Depends(get_db)):
    """
    Chỉ xóa các repository mô phỏng dữ liệu demo (5 repo demo và session demo),
    giữ nguyên các repository thu thập thật khác.
    """
    demo_repos = [
        "freeCodeCamp/freeCodeCamp",
        "deepseek-ai/DeepSeek-V3",
        "shadcn-ui/ui",
        "elixir-lang/elixir",
        "browser-use/browser-use",
    ]
    repos = db.query(Repository).filter(Repository.full_name.in_(demo_repos)).all()
    deleted_count = 0
    for r in repos:
        db.query(RepoSnapshot).filter(RepoSnapshot.repo_id == r.id).delete()
        db.delete(r)
        deleted_count += 1

    # Xóa các crawl sessions demo
    db.query(CrawlSession).filter(CrawlSession.error_message == "timeline_demo_session").delete()
    db.commit()

    return {
        "message": f"Đã xóa thành công {deleted_count} repository mô phỏng demo và các snapshot liên quan!",
        "deleted_repositories": demo_repos,
    }


@router.post("/database/reset")
def reset_database(db: Session = Depends(get_db)):
    """
    Xóa sạch toàn bộ dữ liệu và tái cấu trúc database trắng từ đầu.
    """
    db.query(RepoSnapshot).delete()
    db.query(Repository).delete()
    db.query(CrawlSession).delete()
    db.commit()
    return {
        "message": "Đã xóa toàn bộ dữ liệu và reset cơ sở dữ liệu về trạng thái ban đầu thành công!"
    }

