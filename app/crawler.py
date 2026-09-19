import logging
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any, List
import httpx
from sqlalchemy.orm import Session

from app.config import GITHUB_TRENDING_URL, DEFAULT_HEADERS
from app.parser import parse_github_trending_html
from app.models import Repository, CrawlSession, RepoSnapshot

logger = logging.getLogger(__name__)


class GitHubTrendingCrawler:
    def __init__(self, headers: Optional[Dict[str, str]] = None, timeout: float = 20.0):
        self.headers = headers or DEFAULT_HEADERS
        self.timeout = timeout

    def fetch_trending_page(self, since: str = "daily", spoken_language: Optional[str] = None) -> str:
        """
        Gửi HTTP GET đến GitHub Trending để lấy mã nguồn HTML.
        Hỗ trợ since = 'daily', 'weekly', 'monthly'.
        """
        params = {"since": since}
        if spoken_language:
            params["spoken_language_code"] = spoken_language

        with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(GITHUB_TRENDING_URL, params=params)
            response.raise_for_status()
            return response.text

    def crawl_and_save(
        self,
        db: Session,
        since: str = "daily",
        html_override: Optional[str] = None,
        is_manual: bool = False,
        crawl_date: Optional[date] = None,
        force_increment: bool = False,
    ) -> CrawlSession:
        """
        Thực hiện toàn bộ quy trình:
        1. Tạo CrawlSession record.
        2. Tải HTML (hoặc dùng html_override).
        3. Bóc tách danh sách repos.
        4. Upsert vào bảng repositories & tính toán số lần xuất hiện (occurrences).
        5. Tạo snapshot lịch sử.
        """
        if since not in ("daily", "weekly", "monthly"):
            since = "daily"

        now_utc = datetime.now(timezone.utc)
        record_date = crawl_date or date.today()

        session = CrawlSession(
            since_param=since,
            started_at=now_utc,
            status="running",
            is_manual=is_manual,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        try:
            # 1. Lấy HTML
            if html_override is not None:
                html_content = html_override
            else:
                html_content = self.fetch_trending_page(since=since)

            # 2. Parse HTML
            parsed_repos = parse_github_trending_html(html_content, since=since)
            
            # 3. Upsert vào DB
            for item in parsed_repos:
                full_name = item["full_name"]
                repo = db.query(Repository).filter(Repository.full_name == full_name).first()

                if not repo:
                    # Repo mới tinh xuất hiện lần đầu tiên
                    repo = Repository(
                        full_name=full_name,
                        owner=item["owner"],
                        name=item["name"],
                        url=item["url"],
                        description=item["description"],
                        language=item["language"],
                        language_color=item["language_color"],
                        total_appearances=1,
                        daily_appearances=1 if since == "daily" else 0,
                        weekly_appearances=1 if since == "weekly" else 0,
                        monthly_appearances=1 if since == "monthly" else 0,
                        current_stars=item["stars"],
                        current_forks=item["forks"],
                        latest_period_stars=item["period_stars_text"],
                        latest_rank=item["rank"],
                        first_seen_at=now_utc,
                        last_seen_at=now_utc,
                    )
                    db.add(repo)
                    db.flush()  # để lấy repo.id
                else:
                    # Repo đã từng xuất hiện trước đó
                    # Kiểm tra xem trong cùng ngày record_date & since này đã có snapshot chưa
                    existing_snapshot = (
                        db.query(RepoSnapshot)
                        .filter(
                            RepoSnapshot.repo_id == repo.id,
                            RepoSnapshot.record_date == record_date,
                            RepoSnapshot.since == since,
                        )
                        .first()
                    )

                    should_increment = force_increment or (existing_snapshot is None)

                    if should_increment:
                        repo.total_appearances += 1
                        if since == "daily":
                            repo.daily_appearances += 1
                        elif since == "weekly":
                            repo.weekly_appearances += 1
                        elif since == "monthly":
                            repo.monthly_appearances += 1

                    # Cập nhật các thông tin mới nhất
                    repo.current_stars = item["stars"]
                    repo.current_forks = item["forks"]
                    repo.latest_period_stars = item["period_stars_text"]
                    repo.latest_rank = item["rank"]
                    repo.last_seen_at = now_utc
                    if item["description"]:
                        repo.description = item["description"]
                    if item["language"]:
                        repo.language = item["language"]
                    if item["language_color"]:
                        repo.language_color = item["language_color"]

                # Tạo Snapshot lưu vết cho đợt cào này
                snapshot = RepoSnapshot(
                    repo_id=repo.id,
                    session_id=session.id,
                    record_date=record_date,
                    since=since,
                    rank_position=item["rank"],
                    stars=item["stars"],
                    forks=item["forks"],
                    period_stars_count=item["period_stars_count"],
                    period_stars_text=item["period_stars_text"],
                    crawled_at=now_utc,
                )
                db.add(snapshot)

            session.status = "success"
            session.items_count = len(parsed_repos)
            session.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(session)
            return session

        except Exception as e:
            logger.exception("Lỗi khi cào dữ liệu GitHub Trending: %s", e)
            db.rollback()
            session.status = "failed"
            session.error_message = str(e)
            session.completed_at = datetime.now(timezone.utc)
            db.add(session)
            db.commit()
            raise e


if __name__ == "__main__":
    import argparse
    from app.database import init_db, SessionLocal

    parser = argparse.ArgumentParser(description="GitHub Trending Crawler CLI")
    parser.add_argument(
        "--since",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Mốc thời gian trending cần cào (mặc định: daily)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bắt buộc tăng số lần xuất hiện kể cả khi cào cùng ngày",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    crawler = GitHubTrendingCrawler()
    print(f"[*] Đang bắt đầu cào GitHub Trending [since={args.since}]...")
    try:
        session = crawler.crawl_and_save(db=db, since=args.since, is_manual=True, force_increment=args.force)
        print(f"[+] Hoàn tất! Đã lưu {session.items_count} repositories (Session ID: {session.id}).")
    except Exception as err:
        print(f"[-] Thất bại: {err}")
    finally:
        db.close()
