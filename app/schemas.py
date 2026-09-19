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
    current_stars: int
    current_forks: int
    latest_period_stars: Optional[str] = None
    latest_rank: Optional[int] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None


class PaginatedRepositories(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[RepositoryOut]


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
