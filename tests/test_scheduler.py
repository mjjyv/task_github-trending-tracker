import pytest
from app.scheduler import (
    start_scheduler,
    get_scheduled_jobs_info,
    shutdown_scheduler,
    scheduler,
)


def test_scheduler_jobs_registration():
    start_scheduler()
    assert scheduler.running is True

    jobs = get_scheduled_jobs_info()
    assert len(jobs) == 3

    job_ids = {j["id"] for j in jobs}
    assert "job_crawl_daily" in job_ids
    assert "job_crawl_weekly" in job_ids
    assert "job_crawl_monthly" in job_ids

    daily_job = next(j for j in jobs if j["id"] == "job_crawl_daily")
    assert daily_job["since"] == "daily"
    assert daily_job["frequency_label"] == "3 lần / ngày"
    assert daily_job["next_run_time"] is not None

    weekly_job = next(j for j in jobs if j["id"] == "job_crawl_weekly")
    assert weekly_job["since"] == "weekly"
    assert weekly_job["frequency_label"] == "1 lần / ngày"

    monthly_job = next(j for j in jobs if j["id"] == "job_crawl_monthly")
    assert monthly_job["since"] == "monthly"
    assert monthly_job["frequency_label"] == "2 lần / tuần"

    from app.scheduler import is_scheduler_active, toggle_scheduler
    assert is_scheduler_active() is True
    # Pause scheduler
    active = toggle_scheduler(enable=False)
    assert active is False
    assert is_scheduler_active() is False

    # Resume scheduler
    active = toggle_scheduler(enable=True)
    assert active is True
    assert is_scheduler_active() is True

    shutdown_scheduler()
    assert scheduler.running is False

