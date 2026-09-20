from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL

# SQLite connect_args để hỗ trợ multi-threading trong FastAPI
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # SQLite migration: Tự động bổ sung các cột mới nếu đã có database từ phiên bản trước
    if str(engine.url).startswith("sqlite"):
        with engine.connect() as conn:
            try:
                result = conn.execute(text("PRAGMA table_info(repositories)"))
                existing_cols = {row[1] for row in result.fetchall()}
                if existing_cols:
                    if "persistence_score" not in existing_cols:
                        conn.execute(text("ALTER TABLE repositories ADD COLUMN persistence_score FLOAT DEFAULT 0.0"))
                    if "velocity_score" not in existing_cols:
                        conn.execute(text("ALTER TABLE repositories ADD COLUMN velocity_score FLOAT DEFAULT 0.0"))
                    if "persistence_level" not in existing_cols:
                        conn.execute(text("ALTER TABLE repositories ADD COLUMN persistence_level VARCHAR(30) DEFAULT 'new'"))
                    if "velocity_level" not in existing_cols:
                        conn.execute(text("ALTER TABLE repositories ADD COLUMN velocity_level VARCHAR(30) DEFAULT 'slow'"))
                    conn.commit()
            except Exception:
                pass

