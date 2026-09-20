import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app

# Sử dụng DB in-memory với StaticPool để chia sẻ bộ nhớ an toàn cho TestClient
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "GitHub Trending Tracker" in response.text
    assert "Số Lần Xuất Hiện" in response.text


def test_seed_demo_and_query_repositories():
    # 1. Seed demo
    seed_resp = client.post("/api/seed-demo")
    assert seed_resp.status_code == 200
    seed_data = seed_resp.json()
    assert "Đã tạo thành công" in seed_data["message"]
    assert len(seed_data["days"]) == 3

    # 2. Query repositories
    repo_resp = client.get("/api/repositories?sort_by=total_appearances&sort_dir=desc")
    assert repo_resp.status_code == 200
    repo_data = repo_resp.json()
    assert repo_data["total"] > 0
    items = repo_data["items"]
    assert len(items) > 0

    first_item = items[0]
    assert first_item["total_appearances"] == 3
    assert first_item["daily_appearances"] == 3

    # 3. Test filter min_appearances >= 2
    rep_filter_resp = client.get("/api/repositories?min_appearances=2")
    assert rep_filter_resp.status_code == 200
    assert rep_filter_resp.json()["total"] > 0

    # 4. Test stats summary
    stats_resp = client.get("/api/stats/summary")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_repositories"] > 0
    assert stats["total_crawl_sessions"] == 3
    assert stats["repeated_repositories_count"] > 0
    assert len(stats["top_recurring_repos"]) > 0

    # 5. Test detail & history
    repo_id = first_item["id"]
    detail_resp = client.get(f"/api/repositories/{repo_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["repository"]["full_name"] == first_item["full_name"]
    assert len(detail["snapshots"]) == 3

    history_resp = client.get(f"/api/repositories/{repo_id}/history")
    assert history_resp.status_code == 200
    assert len(history_resp.json()) == 3

    # 6. Test persistence & velocity scores presence and sorting
    assert "persistence_score" in first_item
    assert "velocity_score" in first_item
    assert first_item["persistence_score"] > 0
    assert first_item["velocity_score"] > 0

    sort_p_resp = client.get("/api/repositories?sort_by=persistence_score&sort_dir=desc")
    assert sort_p_resp.status_code == 200
    p_items = sort_p_resp.json()["items"]
    assert p_items[0]["persistence_score"] >= p_items[-1]["persistence_score"]

    # 7. Test recalculate endpoint
    recalc_resp = client.post("/api/scores/recalculate")
    assert recalc_resp.status_code == 200
    assert recalc_resp.json()["count"] > 0

    # 8. Test scheduler jobs endpoint
    jobs_resp = client.get("/api/scheduler/jobs")
    assert jobs_resp.status_code == 200
    assert isinstance(jobs_resp.json(), list)

