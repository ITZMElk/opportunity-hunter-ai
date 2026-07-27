"""Configuration and student profile loading for Opportunity Hunter."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# These are official public RSS/Atom endpoints. MLH is intentionally omitted: no
# public events RSS endpoint could be verified, and this service never scrapes it.
DEFAULT_RSS_FEED_URLS = (
    "https://github.blog/feed/",
    "https://blog.google/technology/ai/rss/",
    "https://aws.amazon.com/blogs/aws/feed/",
    "https://huggingface.co/blog/feed.xml",
    "https://opensource.googleblog.com/feeds/posts/default/-/Google%20Summer%20of%20Code",
    "https://openai.com/news/rss.xml",
)


class StudentProfile(BaseModel):
    education: str = "Diploma student, Computer Engineering, 3rd year"
    skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=lambda: ["online", "india", "global"])
    experience: str = "beginner-to-intermediate"
    resume_keywords: list[str] = Field(default_factory=list)


def load_student_profile(path: Path | None = None) -> StudentProfile:
    """Load the editable profile JSON, falling back to safe built-in defaults."""
    profile_path = path or Path(os.getenv("STUDENT_PROFILE_PATH", PROJECT_ROOT / "student_profile.json"))
    try:
        return StudentProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return StudentProfile(
            skills=["Python", "Java", "Flutter", "Figma", "basic AI/ML (Gemini API)", "microcontrollers", "networking"],
            interests=["AI/ML", "app development", "cloud platforms (AWS/Azure/GCP)"],
            resume_keywords=["Python", "Flutter", "AI/ML", "cloud", "networking"],
        )
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Could not load student profile from {profile_path}") from error


STUDENT_PROFILE: dict[str, Any] = load_student_profile().model_dump()


def _rss_urls_from_env() -> tuple[str, ...]:
    raw_urls = os.getenv("RSS_FEED_URLS", "").strip()
    if not raw_urls:
        return DEFAULT_RSS_FEED_URLS
    return tuple(url.strip() for url in raw_urls.split(",") if url.strip())


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _schedule_interval_minutes() -> int:
    """Prefer the production minutes setting, retaining the MVP hours setting."""
    if os.getenv("SCHEDULE_INTERVAL_MINUTES"):
        return _positive_int("SCHEDULE_INTERVAL_MINUTES", 30)
    if os.getenv("SCHEDULE_INTERVAL_HOURS"):
        return _positive_int("SCHEDULE_INTERVAL_HOURS", 6) * 60
    return 30


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    rss_feed_urls: tuple[str, ...]
    unstop_api_url: str | None
    schedule_interval_minutes: int
    database_url: str
    log_level: str


def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'opportunities.db'}")
    # Railway/Heroku often provide postgres://, while SQLAlchemy needs a dialect.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        rss_feed_urls=_rss_urls_from_env(),
        unstop_api_url=os.getenv("UNSTOP_API_URL"),
        schedule_interval_minutes=_schedule_interval_minutes(),
        database_url=database_url,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
