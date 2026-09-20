from datetime import datetime, timezone, date
from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    DateTime,
    Date,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), unique=True, index=True, nullable=False)
    owner = Column(String(120), nullable=False)
    name = Column(String(120), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String(100), nullable=True, index=True)
    language_color = Column(String(30), nullable=True)
    
    # Bộ đếm số lần xuất hiện
    total_appearances = Column(Integer, default=1, index=True)
    daily_appearances = Column(Integer, default=0)
    weekly_appearances = Column(Integer, default=0)
    monthly_appearances = Column(Integer, default=0)
    
    # Thông tin hiện tại
    current_stars = Column(Integer, default=0)
    current_forks = Column(Integer, default=0)
    latest_period_stars = Column(String(100), nullable=True)
    latest_rank = Column(Integer, nullable=True)
    
    # Điểm đánh giá (Analytics Scores)
    persistence_score = Column(Float, default=0.0, index=True)
    velocity_score = Column(Float, default=0.0, index=True)
    persistence_level = Column(String(30), default="new")  # legend, high, medium, new
    velocity_level = Column(String(30), default="slow")    # rocket, surging, steady, slow
    
    # Mốc thời gian
    first_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    snapshots = relationship("RepoSnapshot", back_populates="repository", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "owner": self.owner,
            "name": self.name,
            "url": self.url,
            "description": self.description,
            "language": self.language,
            "language_color": self.language_color,
            "total_appearances": self.total_appearances,
            "daily_appearances": self.daily_appearances,
            "weekly_appearances": self.weekly_appearances,
            "monthly_appearances": self.monthly_appearances,
            "persistence_score": round(self.persistence_score or 0.0, 1),
            "velocity_score": round(self.velocity_score or 0.0, 1),
            "persistence_level": self.persistence_level or "new",
            "velocity_level": self.velocity_level or "slow",
            "current_stars": self.current_stars,
            "current_forks": self.current_forks,
            "latest_period_stars": self.latest_period_stars,
            "latest_rank": self.latest_rank,
            "first_seen_at": self.first_seen_at.isoformat() if self.first_seen_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
        }


class CrawlSession(Base):
    __tablename__ = "crawl_sessions"

    id = Column(Integer, primary_key=True, index=True)
    since_param = Column(String(20), nullable=False, default="daily", index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(30), default="running")  # running, success, failed
    items_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    is_manual = Column(Boolean, default=False)

    # Relationships
    snapshots = relationship("RepoSnapshot", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "since_param": self.since_param,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "items_count": self.items_count,
            "error_message": self.error_message,
            "is_manual": self.is_manual,
        }


class RepoSnapshot(Base):
    __tablename__ = "repo_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("crawl_sessions.id"), nullable=False, index=True)
    record_date = Column(Date, default=lambda: date.today(), index=True)
    since = Column(String(20), default="daily")
    rank_position = Column(Integer, nullable=False)
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    period_stars_count = Column(Integer, default=0)
    period_stars_text = Column(String(100), default="")
    crawled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    repository = relationship("Repository", back_populates="snapshots")
    session = relationship("CrawlSession", back_populates="snapshots")

    def to_dict(self):
        return {
            "id": self.id,
            "repo_id": self.repo_id,
            "session_id": self.session_id,
            "record_date": self.record_date.isoformat() if self.record_date else None,
            "since": self.since,
            "rank_position": self.rank_position,
            "stars": self.stars,
            "forks": self.forks,
            "period_stars_count": self.period_stars_count,
            "period_stars_text": self.period_stars_text,
            "crawled_at": self.crawled_at.isoformat() if self.crawled_at else None,
        }
