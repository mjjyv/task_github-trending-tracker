from datetime import date, timedelta, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Repository, RepoSnapshot, CrawlSession
from app.analytics import (
    parse_time_window,
    calculate_window_metrics,
    compare_repo_periods,
)
from app.main import app


# Isolated test database in memory
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)


def test_parse_time_window():
    base = date(2026, 9, 20)
    
    s, e, label = parse_time_window("all", base_date=base)
    assert s is None and e is None

    s, e, label = parse_time_window("7d", base_date=base)
    assert s == date(2026, 9, 13) and e == base

    s, e, label = parse_time_window("180d", base_date=base)
    assert s == date(2026, 3, 24) and e == base
    assert "6 tháng" in label

    s, e, label = parse_time_window("custom", custom_start=date(2026, 1, 1), custom_end=date(2026, 6, 1), base_date=base)
    assert s == date(2026, 1, 1) and e == date(2026, 6, 1)


def test_calculate_window_metrics_legacy_drop():
    today = date(2026, 9, 20)
    w_start = today - timedelta(days=180)

    # Repo cũ có 100k stars nhưng snapshots chỉ cách đây 300 ngày
    legacy_repo = Repository(
        id=1,
        full_name="old/famous",
        owner="old",
        name="famous",
        url="https://github.com/old/famous",
        current_stars=120000,
    )
    old_snapshots = [
        RepoSnapshot(
            id=1,
            repo_id=1,
            session_id=1,
            record_date=today - timedelta(days=320),
            stars=115000,
            rank_position=1,
            since="daily",
            period_stars_count=1500,
            crawled_at=datetime.now(timezone.utc) - timedelta(days=320),
        )
    ]

    metrics = calculate_window_metrics(legacy_repo, old_snapshots, start_date=w_start, end_date=today)
    assert metrics["window_appearances"] == 0
    assert metrics["window_stars_gained"] == 0
    assert metrics["window_trending_score"] == 0.0
    assert metrics["is_active_in_window"] is False
    assert metrics["lifecycle_code"] == "legacy_dormant"


def test_period_comparison_and_trajectory():
    today = date(2026, 9, 20)
    p1_start = today - timedelta(days=180)
    p2_start = today - timedelta(days=360)
    p2_end = today - timedelta(days=181)

    # Test Revival repo
    revival_repo = Repository(
        id=2,
        full_name="revive/project",
        owner="revive",
        name="project",
        url="https://github.com/revive/project",
        current_stars=25000,
    )
    snapshots = [
        # 1 snapshot in p2
        RepoSnapshot(
            id=2,
            repo_id=2,
            session_id=1,
            record_date=today - timedelta(days=270),
            stars=20000,
            rank_position=20,
            since="monthly",
            period_stars_count=200,
            crawled_at=datetime.now(timezone.utc) - timedelta(days=270),
        ),
        # 4 snapshots in p1
        RepoSnapshot(
            id=3,
            repo_id=2,
            session_id=1,
            record_date=today - timedelta(days=100),
            stars=21000,
            rank_position=5,
            since="daily",
            period_stars_count=1000,
            crawled_at=datetime.now(timezone.utc) - timedelta(days=100),
        ),
        RepoSnapshot(
            id=4,
            repo_id=2,
            session_id=1,
            record_date=today - timedelta(days=60),
            stars=22500,
            rank_position=3,
            since="daily",
            period_stars_count=1500,
            crawled_at=datetime.now(timezone.utc) - timedelta(days=60),
        ),
        RepoSnapshot(
            id=5,
            repo_id=2,
            session_id=1,
            record_date=today - timedelta(days=20),
            stars=24000,
            rank_position=2,
            since="weekly",
            period_stars_count=1500,
            crawled_at=datetime.now(timezone.utc) - timedelta(days=20),
        ),
        RepoSnapshot(
            id=6,
            repo_id=2,
            session_id=1,
            record_date=today - timedelta(days=2),
            stars=25000,
            rank_position=2,
            since="daily",
            period_stars_count=1000,
            crawled_at=datetime.now(timezone.utc) - timedelta(days=2),
        ),
    ]

    res = compare_repo_periods(
        repo=revival_repo,
        snapshots=snapshots,
        p1_start=p1_start,
        p1_end=today,
        p2_start=p2_start,
        p2_end=p2_end,
    )
    assert res["delta"]["stars_gained"] > 0
    assert res["delta"]["appearances"] == 3
    assert "Tái Sinh" in res["lifecycle_trajectory"]["badge"]


def test_api_time_window_and_compare():
    client = TestClient(app)

    # Seed timeline demo
    resp_seed = client.post("/api/seed-timeline-demo")
    assert resp_seed.status_code == 200
    assert len(resp_seed.json()["seeded_repositories"]) == 5

    # 1. Query with time_window=180d
    resp = client.get("/api/repositories?time_window=180d&sort_by=window_trending_score&sort_dir=desc")
    assert resp.status_code == 200
    data = resp.json()
    assert data["time_window"] == "180d"
    items = data["items"]
    assert len(items) > 0

    # Top repo in 180d should be deepseek or browser-use, NOT freeCodeCamp
    top_repo = items[0]
    assert top_repo["full_name"] != "freeCodeCamp/freeCodeCamp"
    assert top_repo["window_stars_gained"] > 10000

    # Find freeCodeCamp
    fcc = next((r for r in items if r["full_name"] == "freeCodeCamp/freeCodeCamp"), None)
    assert fcc is not None
    assert fcc["window_appearances"] == 0
    assert fcc["window_trending_score"] == 0.0

    # 2. Test Compare endpoint
    deepseek = next(r for r in items if r["full_name"] == "deepseek-ai/DeepSeek-V3")
    compare_resp = client.get(f"/api/repositories/{deepseek['id']}/compare?preset=6m_vs_prior_6m")
    assert compare_resp.status_code == 200
    comp = compare_resp.json()
    assert comp["period_1"]["metrics"]["window_stars_gained"] > 50000
    assert "Bùng Nổ" in comp["lifecycle_trajectory"]["badge"]
