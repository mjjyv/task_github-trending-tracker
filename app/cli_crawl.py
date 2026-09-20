import argparse
import sys
from app.database import SessionLocal, init_db, Base, engine
from app.crawler import GitHubTrendingCrawler
from app.scoring import recalculate_all_scores

def main():
    parser = argparse.ArgumentParser(description="GitHub Trending Crawler CLI - Chạy độc lập không cần Web Server")
    parser.add_argument(
        "--since",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Khung thời gian cào: daily, weekly hoặc monthly",
    )
    parser.add_argument(
        "--recalculate",
        action="store_true",
        help="Tính toán lại Persistence & Velocity Scores cho toàn bộ repos",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Xóa sạch toàn bộ dữ liệu và tái cấu trúc database trắng",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.reset:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            print("✔ Đã reset toàn bộ cơ sở dữ liệu thành công!")
            return

        if args.recalculate:
            updated = recalculate_all_scores(db)
            print(f"✔ Đã tính toán lại điểm cho {updated} repositories!")
            return

        print(f"[*] Bắt đầu cào dữ liệu GitHub Trending [since={args.since}]...")
        crawler = GitHubTrendingCrawler()
        session = crawler.crawl_and_save(db=db, since=args.since, is_manual=False)
        print(f"✔ Cào hoàn tất! Thu thập {session.items_count} repositories (Phiên #{session.id}, trạng thái: {session.status})")
    finally:
        db.close()

if __name__ == "__main__":
    main()
