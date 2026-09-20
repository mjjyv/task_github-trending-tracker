import pytest
from datetime import datetime, timezone, timedelta
from app.models import Repository, RepoSnapshot
from app.scoring import (
    calculate_persistence_score,
    calculate_velocity_score,
    update_repo_scores,
)


def test_persistence_score_calculation():
    now = datetime.now(timezone.utc)
    
    # 1. Repo mới tinh vừa xuất hiện 1 lần
    repo_new = Repository(
        full_name="test/new-repo",
        owner="test",
        name="new-repo",
        url="https://github.com/test/new-repo",
        total_appearances=1,
        daily_appearances=1,
        weekly_appearances=0,
        monthly_appearances=0,
        first_seen_at=now,
        last_seen_at=now,
    )
    score_new, level_new = calculate_persistence_score(repo_new, current_time=now)
    assert score_new < 35.0
    assert level_new == "new"

    # 2. Repo kiên trì bám trụ nhiều ngày, lên cả weekly & monthly
    repo_legend = Repository(
        full_name="test/legend-repo",
        owner="test",
        name="legend-repo",
        url="https://github.com/test/legend-repo",
        total_appearances=15,
        daily_appearances=10,
        weekly_appearances=4,
        monthly_appearances=1,
        first_seen_at=now - timedelta(days=35),
        last_seen_at=now,
    )
    # Giả lập 10 snapshots
    mock_snaps = [
        RepoSnapshot(crawled_at=now - timedelta(days=i), stars=1000 + i * 100)
        for i in range(10)
    ]
    score_legend, level_legend = calculate_persistence_score(repo_legend, mock_snaps, current_time=now)
    assert score_legend >= 85.0
    assert level_legend == "legend"

    # 3. Repo bị lãng quên (recency decay): lần cuối thấy cách đây 20 ngày
    score_decayed, _ = calculate_persistence_score(repo_legend, mock_snaps, current_time=now + timedelta(days=20))
    assert score_decayed < score_legend


def test_velocity_score_calculation():
    now = datetime.now(timezone.utc)

    # 1. Repo tên lửa: tăng 3500 stars trong ngày, rank 1
    repo_rocket = Repository(
        full_name="test/rocket-repo",
        owner="test",
        name="rocket-repo",
        url="https://github.com/test/rocket-repo",
        latest_rank=1,
        latest_period_stars="3,500 stars today",
        current_stars=20000,
    )
    snap1 = RepoSnapshot(crawled_at=now - timedelta(hours=6), stars=18000, rank_position=2)
    snap2 = RepoSnapshot(crawled_at=now, stars=20000, period_stars_count=3500, rank_position=1)
    
    score_rocket, level_rocket = calculate_velocity_score(repo_rocket, [snap1, snap2])
    assert score_rocket >= 80.0
    assert level_rocket == "rocket"

    # 2. Repo tăng chậm: ít stars, rank 22
    repo_slow = Repository(
        full_name="test/slow-repo",
        owner="test",
        name="slow-repo",
        url="https://github.com/test/slow-repo",
        latest_rank=22,
        latest_period_stars="20 stars today",
        current_stars=500,
    )
    snap_slow = RepoSnapshot(crawled_at=now, stars=500, period_stars_count=20, rank_position=22)
    score_slow, level_slow = calculate_velocity_score(repo_slow, [snap_slow])
    assert score_slow < 30.0
    assert level_slow == "slow"


def test_update_repo_scores():
    now = datetime.now(timezone.utc)
    repo = Repository(
        full_name="test/update-repo",
        owner="test",
        name="update-repo",
        url="https://github.com/test/update-repo",
        total_appearances=3,
        daily_appearances=3,
        latest_rank=5,
        latest_period_stars="800 stars today",
        first_seen_at=now - timedelta(days=2),
        last_seen_at=now,
    )
    snap = RepoSnapshot(crawled_at=now, stars=3000, period_stars_count=800, rank_position=5)
    update_repo_scores(repo, [snap])

    assert repo.persistence_score > 0.0
    assert repo.persistence_level in ("new", "medium", "high", "legend")
    assert repo.velocity_score > 0.0
    assert repo.velocity_level in ("slow", "steady", "surging", "rocket")
