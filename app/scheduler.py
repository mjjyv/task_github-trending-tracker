import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.crawler import GitHubTrendingCrawler
from app.scoring import recalculate_all_scores

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
crawler = GitHubTrendingCrawler()


def _run_crawl(since: str) -> None:
    """Helper chạy cào dữ liệu cho một mốc cụ thể và tính lại điểm."""
    logger.info("Bắt đầu tác vụ cào tự động định kỳ [%s]...", since)
    db = SessionLocal()
    try:
        session = crawler.crawl_and_save(db=db, since=since, is_manual=False)
        logger.info(
            "Cào tự động [%s] hoàn tất: %d repositories (Session ID: %d)",
            since,
            session.items_count,
            session.id,
        )
        # Tính toán lại điểm số cho toàn bộ hệ thống
        updated = recalculate_all_scores(db)
        logger.info("Đã cập nhật Persistence & Velocity score cho %d repositories", updated)
    except Exception as e:
        logger.exception("Lỗi khi cào tự động [%s]: %s", since, e)
    finally:
        db.close()


def crawl_daily_job() -> None:
    """Tác vụ cào theo Ngày (Daily) - 3 lần / ngày."""
    _run_crawl("daily")


def crawl_weekly_job() -> None:
    """Tác vụ cào theo Tuần (Weekly) - 1 lần / ngày."""
    _run_crawl("weekly")


def crawl_monthly_job() -> None:
    """Tác vụ cào theo Tháng (Monthly) - 2 lần / tuần."""
    _run_crawl("monthly")


def start_scheduler() -> None:
    """
    Cấu hình và khởi động APScheduler theo đúng yêu cầu:
    1. Daily: 3 lần / ngày (07:00, 13:00, 20:00)
    2. Weekly: 1 lần / ngày (01:00)
    3. Monthly: 2 lần / tuần (Thứ Hai & Thứ Năm lúc 02:00)
    """
    if not scheduler.running:
        # Job 1: Daily (3 lần / ngày)
        scheduler.add_job(
            crawl_daily_job,
            trigger=CronTrigger(hour="7,13,20", minute=0),
            id="job_crawl_daily",
            name="Cào Daily Trending (3 lần / ngày)",
            replace_existing=True,
        )

        # Job 2: Weekly (1 lần / ngày)
        scheduler.add_job(
            crawl_weekly_job,
            trigger=CronTrigger(hour=1, minute=0),
            id="job_crawl_weekly",
            name="Cào Weekly Trending (1 lần / ngày)",
            replace_existing=True,
        )

        # Job 3: Monthly (2 lần / tuần - Thứ 2 & Thứ 5)
        scheduler.add_job(
            crawl_monthly_job,
            trigger=CronTrigger(day_of_week="mon,thu", hour=2, minute=0),
            id="job_crawl_monthly",
            name="Cào Monthly Trending (2 lần / tuần)",
            replace_existing=True,
        )

        scheduler.start()
        logger.info("APScheduler đã được khởi động với 3 lịch cào tự động thành công.")


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler đã tắt.")


def get_scheduled_jobs_info() -> List[Dict[str, Any]]:
    """Trả về thông tin chi tiết các jobs đang được lập lịch và lần chạy kế tiếp."""
    jobs_info: List[Dict[str, Any]] = []
    
    # Metadata mô tả cấu hình mong muốn
    schedules_meta = {
        "job_crawl_daily": {
            "since": "daily",
            "frequency_label": "3 lần / ngày",
            "cron_desc": "Chạy lúc 07:00, 13:00, 20:00 hàng ngày",
        },
        "job_crawl_weekly": {
            "since": "weekly",
            "frequency_label": "1 lần / ngày",
            "cron_desc": "Chạy lúc 01:00 sáng hàng ngày",
        },
        "job_crawl_monthly": {
            "since": "monthly",
            "frequency_label": "2 lần / tuần",
            "cron_desc": "Chạy lúc 02:00 sáng Thứ 2 và Thứ 5 hàng tuần",
        },
    }

    for job in scheduler.get_jobs():
        meta = schedules_meta.get(job.id, {
            "since": "unknown",
            "frequency_label": "Tùy biến",
            "cron_desc": str(job.trigger),
        })
        next_run = job.next_run_time
        jobs_info.append({
            "id": job.id,
            "name": job.name,
            "since": meta["since"],
            "frequency_label": meta["frequency_label"],
            "cron_desc": meta["cron_desc"],
            "next_run_time": next_run.isoformat() if next_run else None,
            "is_running": scheduler.running,
        })

    return jobs_info
