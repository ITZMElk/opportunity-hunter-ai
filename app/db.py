from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dedupe_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(50))
    raw_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    organizer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    opportunity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deadline: Mapped[str | None] = mapped_column(String(50), nullable=True)
    eligibility: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prize_or_benefit: Mapped[str | None] = mapped_column(Text, nullable=True)
    suitability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    suitability_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills_matched: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline_urgency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resume_value: Mapped[str | None] = mapped_column(String(20), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    analyzed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    # Small additive migration for databases created by earlier MVP versions.
    expected_columns = {
        "skills_matched": "TEXT",
        "missing_skills": "TEXT",
        "deadline_urgency": "VARCHAR(20)",
        "resume_value": "VARCHAR(20)",
        "difficulty": "VARCHAR(20)",
    }
    existing_columns = {column["name"] for column in inspect(engine).get_columns("opportunities")}
    with engine.begin() as connection:
        for name, sql_type in expected_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE opportunities ADD COLUMN {name} {sql_type}"))


def get_session() -> Session:
    return SessionLocal()


def database_is_connected() -> bool:
    """Perform a minimal database round-trip for readiness checks."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
