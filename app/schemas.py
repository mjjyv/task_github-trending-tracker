from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class RepoSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repo_id: int
    session_id: int
    record_date: Optional[date] = None
    since: str
    rank_position: int
    stars: int
    forks: int
    period_stars_count: int
    period_stars_text: str
    crawled_at: Optional[datetime] = None


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    owner: str
    name: str
    url: str
    description: Optional[str] = None
    language: Optional[str] = None
    language_color: Optional[str] = None
    total_appearances: int
    daily_appearances: int
    weekly_appearances: int
    monthly_appearances: int
    persistence_score: float = 0.0
    velocity_score: float = 0.0
    persistence_level: str = "new"
    velocity_level: str = "slow"
    current_stars: int
    current_forks: int
    latest_period_stars: Optional[str] = None
    latest_rank: Optional[int] = None
    first_seen_at: Optional[datetime] = None
    # Window-specific dynamic metrics (khi lọc theo khoảng thời gian)
    window_appearances: Optional[int] = None
    window_stars_gained: Optional[int] = None
    window_persistence_score: Optional[float] = None
    window_velocity_score: Optional[float] = None
    window_trending_score: Optional[float] = None
    window_avg_rank: Optional[float] = None
    window_best_rank: Optional[int] = None
    is_active_in_window: Optional[bool] = None
    lifecycle_code: Optional[str] = None
    lifecycle_label: Optional[str] = None
    lifecycle_desc: Optional[str] = None


class PaginatedRepositories(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    time_window: Optional[str] = "all"
    time_window_label: Optional[str] = "Toàn bộ thời gian (All-time)"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    items: List[RepositoryOut]


class PeriodMetricsOut(BaseModel):
    window_appearances: int
    window_daily_appearances: int
    window_weekly_appearances: int
    window_monthly_appearances: int
    window_stars_gained: int
    window_avg_rank: Optional[float] = None
    window_best_rank: Optional[int] = None
    window_persistence_score: float
    window_velocity_score: float
    window_trending_score: float
    is_active_in_window: bool
    lifecycle_code: str
    lifecycle_label: str
    lifecycle_desc: str
    snapshots_count: int


class PeriodInfoOut(BaseModel):
    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    metrics: PeriodMetricsOut


class DeltaMetricsOut(BaseModel):
    stars_gained: int
    stars_gained_pct: Optional[float] = None
    appearances: int
    persistence_score: float
    velocity_score: float
    trending_score: Optional[float] = None
    avg_rank: Optional[float] = None


class LifecycleTrajectoryOut(BaseModel):
    badge: str
    tone: str
    stage_summary: str
    insight_text: str
    meaning_for_dev: str


class PeriodComparisonOut(BaseModel):
    repository: dict
    period_1: PeriodInfoOut
    period_2: PeriodInfoOut
    delta: DeltaMetricsOut
    lifecycle_trajectory: LifecycleTrajectoryOut


class CrawlSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    since_param: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str
    items_count: int
    error_message: Optional[str] = None
    is_manual: bool


class CrawlTriggerRequest(BaseModel):
    since: str = "daily"  # daily, weekly, monthly


class CrawlTriggerResponse(BaseModel):
    message: str
    session_id: int
    status: str
    items_count: int


class StatsSummary(BaseModel):
    total_repositories: int
    total_crawl_sessions: int
    repeated_repositories_count: int  # số repo xuất hiện > 1 lần
    top_languages: List[dict]
    top_recurring_repos: List[RepositoryOut]


class SchedulerJobOut(BaseModel):
    id: str
    name: str
    since: str
    frequency_label: str
    cron_desc: str
    next_run_time: Optional[str] = None
    is_running: bool

