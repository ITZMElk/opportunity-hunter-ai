from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.pipeline.dedupe import normalized_hash, store_new_item
from app.sources.base import RawItem


def test_hash_ignores_case_and_extra_spaces() -> None:
    assert normalized_hash("  AI Hackathon ", "Acme  Labs") == normalized_hash("ai hackathon", "acme labs")


def test_store_new_item_rejects_duplicate() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    item = RawItem(title="AI Hackathon", organizer="Acme", description="", source="test")

    assert store_new_item(session, item) is not None
    assert store_new_item(session, item) is None
