import os
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func, or_

from app.database import get_db
from app.models import Repository, CrawlSession, RepoSnapshot
from app.crawler import GitHubTrendingCrawler
from app.scoring import recalculate_all_scores
from app.scheduler import get_scheduled_jobs_info
from app.schemas import (
    RepositoryOut,
    PaginatedRepositories,
    CrawlSessionOut,
    CrawlTriggerRequest,
    CrawlTriggerResponse,
    StatsSummary,
    RepoSnapshotOut,
    SchedulerJobOut,
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
    sort_by: str = Query("total_appearances", description="Cột cần sắp xếp"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    query = db.query(Repository)

    # 1. Tìm kiếm từ khóa
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Repository.full_name.ilike(search_pattern),
                Repository.description.ilike(search_pattern),
            )
        )

    # 2. Lọc theo ngôn ngữ
    if language and language != "all":
        query = query.filter(Repository.language == language)

    # 3. Lọc theo since
    if since and since != "all":
        if since == "daily":
            query = query.filter(Repository.daily_appearances > 0)
        elif since == "weekly":
            query = query.filter(Repository.weekly_appearances > 0)
        elif since == "monthly":
            query = query.filter(Repository.monthly_appearances > 0)

    # 4. Lọc theo số lần xuất hiện tối thiểu
    if min_appearances:
        query = query.filter(Repository.total_appearances >= min_appearances)

    # 5. Lọc theo điểm số
    if min_persistence is not None:
        query = query.filter(Repository.persistence_score >= min_persistence)
    if min_velocity is not None:
        query = query.filter(Repository.velocity_score >= min_velocity)

    # 6. Sắp xếp
    sort_column_map = {
        "total_appearances": Repository.total_appearances,
        "daily_appearances": Repository.daily_appearances,
        "weekly_appearances": Repository.weekly_appearances,
        "monthly_appearances": Repository.monthly_appearances,
        "persistence_score": Repository.persistence_score,
        "velocity_score": Repository.velocity_score,
        "current_stars": Repository.current_stars,
        "current_forks": Repository.current_forks,
        "latest_rank": Repository.latest_rank,
        "last_seen_at": Repository.last_seen_at,
        "first_seen_at": Repository.first_seen_at,
    }

    sort_col = sort_column_map.get(sort_by, Repository.total_appearances)
    if sort_dir == "asc":
        query = query.order_by(asc(sort_col))
    else:
        query = query.order_by(desc(sort_col))

    total = query.count()
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
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

