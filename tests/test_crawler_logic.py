import os
from datetime import date, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Repository, CrawlSession, RepoSnapshot
from app.crawler import GitHubTrendingCrawler


@pytest.fixture
def db_session():
    # Use in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_occurrence_counter_multi_day(db_session):
    crawler = GitHubTrendingCrawler()
    html_path = os.path.join(os.path.dirname(__file__), "..", "docs", "html01.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    day1 = date(2026, 9, 19)
    day2 = date(2026, 9, 20)
    day3 = date(2026, 9, 21)

    # --- Ngày 1: Cào lần đầu tiên ---
    s1 = crawler.crawl_and_save(
        db=db_session,
        since="daily",
        html_override=html_content,
        crawl_date=day1,
    )
    assert s1.status == "success"
    assert s1.items_count > 0

    repo = db_session.query(Repository).filter_by(full_name="tt-a1i/archify").first()
    assert repo is not None
    assert repo.total_appearances == 1
    assert repo.daily_appearances == 1

    # --- Ngày 1: Cào lại trong cùng ngày 1 (tránh đếm trùng) ---
    s1_dup = crawler.crawl_and_save(
        db=db_session,
        since="daily",
        html_override=html_content,
        crawl_date=day1,
    )
    assert s1_dup.status == "success"
    db_session.refresh(repo)
    assert repo.total_appearances == 1, "Cùng ngày cào lại không được làm tăng số lần xuất hiện"
    assert repo.daily_appearances == 1

    # --- Ngày 2: Sang ngày thứ hai cào lần nữa -> xuất hiện lại thì tăng lên 2 ---
    s2 = crawler.crawl_and_save(
        db=db_session,
        since="daily",
        html_override=html_content,
        crawl_date=day2,
    )
    assert s2.status == "success"
    db_session.refresh(repo)
    assert repo.total_appearances == 2, "Sang ngày thứ hai xuất hiện lại phải tăng lên 2"
    assert repo.daily_appearances == 2

    # --- Ngày 3: Sang ngày thứ ba cào lần nữa -> tăng lên 3 ---
    s3 = crawler.crawl_and_save(
        db=db_session,
        since="daily",
        html_override=html_content,
        crawl_date=day3,
    )
    assert s3.status == "success"
    db_session.refresh(repo)
    assert repo.total_appearances == 3, "Sang ngày thứ ba xuất hiện lại phải tăng lên 3"
    assert repo.daily_appearances == 3

    # Kiểm tra snapshots
    snapshots = db_session.query(RepoSnapshot).filter_by(repo_id=repo.id).all()
    # Gồm: day1 lần 1, day1 lần 2 (snapshot lưu vết), day2, day3
    assert len(snapshots) >= 3
