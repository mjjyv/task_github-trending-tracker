import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.crawler import GitHubTrendingCrawler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
crawler = GitHubTrendingCrawler()


def scheduled_crawl_job():
    """
    Tác vụ chạy định kỳ mỗi ngày: cào dữ liệu cho cả daily, weekly, monthly.
    """
    logger.info("Bắt đầu tác vụ cào dữ liệu tự động định kỳ...")
    db = SessionLocal()
    try:
        for since in ("daily", "weekly", "monthly"):
            try:
                session = crawler.crawl_and_save(db=db, since=since, is_manual=False)
                logger.info(
                    "Đã cào tự động thành công [%s]: %d repositories (Session ID: %d)",
                    since,
                    session.items_count,
                    session.id,
                )
            except Exception as e:
                logger.error("Lỗi khi cào tự động [%s]: %s", since, e)
    finally:
        db.close()


def start_scheduler():
    """Khởi động scheduler chạy mỗi ngày vào lúc 06:00 sáng (hoặc có thể tùy biến)."""
    if not scheduler.running:
        # Chạy lúc 06:00 sáng hàng ngày
        scheduler.add_job(
            scheduled_crawl_job,
            trigger=CronTrigger(hour=6, minute=0),
            id="daily_github_trending_crawl",
            name="Cào GitHub Trending hàng ngày",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler đã được kích hoạt thành công.")


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler đã tắt.")
