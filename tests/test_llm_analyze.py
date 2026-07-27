from app.config import Settings
from app.pipeline.llm_analyze import GeminiAnalyzer, parse_analysis_response
from app.sources.base import RawItem


VALID_RESPONSE = '''{
  "title": "Cloud Workshop",
  "organizer": "Cloud Club",
  "type": "webinar",
  "deadline": "2026-08-10",
  "eligibility": "Indian students",
  "location": "online",
  "cost": "free",
  "prize_or_benefit": "Certificate",
  "score": 80,
  "reasoning": ["Free", "Online", "Cloud interest match"],
  "skills_matched": ["Python", "Cloud"],
  "missing_skills": [],
  "deadline_urgency": "low",
  "resume_value": "high",
  "difficulty": "beginner",
  "recommendation": true
}'''


def test_parse_valid_gemini_json() -> None:
    result = parse_analysis_response(VALID_RESPONSE)
    assert result is not None
    assert result.suitability_score == 80
    assert result.recommended is True


def test_parse_malformed_or_inconsistent_response_returns_none() -> None:
    assert parse_analysis_response("not json") is None
    assert parse_analysis_response(VALID_RESPONSE.replace('"score": 80', '"score": 50')) is None


def test_analyzer_uses_mocked_gemini_response(monkeypatch: object) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {"candidates": [{"content": {"parts": [{"text": VALID_RESPONSE}]}}]}

    def fake_post(*_: object, **__: object) -> FakeResponse:
        return FakeResponse()

    class FakeSession:
        post = staticmethod(fake_post)

    monkeypatch.setattr("app.pipeline.llm_analyze.create_http_session", FakeSession)
    settings = Settings(
        gemini_api_key="test-key",
        gemini_model="test-model",
        telegram_bot_token=None,
        telegram_chat_id=None,
        rss_feed_urls=(),
        unstop_api_url=None,
        schedule_interval_minutes=30,
        database_url="sqlite:///:memory:",
        log_level="INFO",
    )
    item = RawItem(title="Cloud Workshop", organizer="Cloud Club", source="test")

    result = GeminiAnalyzer(settings).analyze(item)

    assert result is not None
    assert result.type == "webinar"


def test_analyzer_retries_once_after_invalid_json(monkeypatch: object) -> None:
    calls = 0

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {"candidates": [{"content": {"parts": [{"text": self.text}]}}]}

    class FakeSession:
        def post(self, *_: object, **__: object) -> FakeResponse:
            nonlocal calls
            calls += 1
            return FakeResponse("not JSON" if calls == 1 else VALID_RESPONSE)

    monkeypatch.setattr("app.pipeline.llm_analyze.create_http_session", FakeSession)
    settings = Settings("test-key", "test-model", None, None, (), None, 30, "sqlite:///:memory:", "INFO")

    result = GeminiAnalyzer(settings).analyze(RawItem(title="Cloud Workshop", organizer="Cloud Club", source="test"))

    assert result is not None
    assert calls == 2
