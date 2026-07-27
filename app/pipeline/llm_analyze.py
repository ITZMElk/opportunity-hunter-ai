"""Gemini-based, schema-validated opportunity analysis."""
from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, ValidationError, field_validator

from app.config import Settings, load_student_profile
from app.http import create_http_session
from app.sources.base import RawItem

logger = logging.getLogger(__name__)


class AnalysisResult(BaseModel):
    title: str
    organizer: str = "unknown"
    type: Literal["hackathon", "ambassador_program", "internship", "scholarship", "certification", "webinar", "cloud_credits", "other"] = "other"
    deadline: str = "unknown"
    eligibility: str = "unknown"
    location: Literal["online", "india", "global", "other"] = "other"
    cost: Literal["free", "paid", "unknown"] = "unknown"
    prize_or_benefit: str = "unknown"
    score: float = Field(validation_alias=AliasChoices("score", "suitability_score"), ge=0, le=100)
    reasoning: list[str] = Field(validation_alias=AliasChoices("reasoning", "suitability_reasons"), min_length=1, max_length=5)
    skills_matched: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    deadline_urgency: Literal["low", "medium", "high", "unknown"] = "unknown"
    resume_value: Literal["low", "medium", "high", "excellent", "unknown"] = "unknown"
    difficulty: Literal["beginner", "intermediate", "advanced", "unknown"] = "unknown"
    recommendation: bool = Field(validation_alias=AliasChoices("recommendation", "recommended"))

    @field_validator("recommendation")
    @classmethod
    def recommendation_matches_score(cls, value: bool, info: object) -> bool:
        score = getattr(info, "data", {}).get("score")
        if score is not None and value != (score >= 70):
            raise ValueError("recommendation must be true exactly when score is at least 70")
        return value

    @property
    def suitability_score(self) -> float:
        return self.score

    @property
    def recommended(self) -> bool:
        return self.recommendation


def build_prompt(item: RawItem) -> str:
    return f"""You are a precise opportunity analyst for a student. Return ONLY one valid JSON object, with no markdown, commentary, or code fences.

Student profile:
{json.dumps(load_student_profile().model_dump(), indent=2)}

Scoring (0-100): +20 free, +15 online/remote, +15 beginner/intermediate friendly, +15 matches AI/ML, app development, or cloud interests, +10 India-eligible, +10 deadline more than 3 days away, +15 high resume/portfolio value. Recommendation must be true exactly when score >= 70.

Classify only facts supported by the raw item; use "unknown" when uncertain. Identify concrete matched and missing skills. Deadline urgency is low/medium/high/unknown. Resume value is low/high/excellent/unknown. Difficulty is beginner/intermediate/advanced/unknown.

Raw item:
{json.dumps(item.model_dump(), indent=2)}

Required JSON fields:
{{
  "title": "string", "organizer": "string", "type": "hackathon|ambassador_program|internship|scholarship|certification|webinar|cloud_credits|other", "deadline": "ISO date or unknown", "eligibility": "string", "location": "online|india|global|other", "cost": "free|paid|unknown", "prize_or_benefit": "string", "score": 0, "reasoning": ["string"], "skills_matched": ["string"], "missing_skills": ["string"], "deadline_urgency": "low|medium|high|unknown", "resume_value": "low|medium|high|excellent|unknown", "difficulty": "beginner|intermediate|advanced|unknown", "recommendation": true
}}
"""


def parse_analysis_response(response_text: str) -> AnalysisResult | None:
    try:
        return AnalysisResult.model_validate(json.loads(response_text))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return None


class GeminiAnalyzer:
    def __init__(self, settings: Settings, timeout_seconds: float = 30) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds
        self.http = create_http_session()

    def _generate(self, item: RawItem) -> str | None:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": build_prompt(item)}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
        }
        try:
            response = self.http.post(url, params={"key": self.settings.gemini_api_key}, json=payload, timeout=(5, self.timeout_seconds))
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError, ValueError, OSError):
            logger.exception("Gemini request failed for %r", item.title)
            return None

    def analyze(self, item: RawItem) -> AnalysisResult | None:
        if not self.settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY is not configured; skipping LLM analysis")
            return None
        for attempt in range(2):
            response_text = self._generate(item)
            if response_text:
                analysis = parse_analysis_response(response_text)
                if analysis is not None:
                    return analysis
            logger.warning("Gemini returned invalid JSON for %r (attempt %d/2)", item.title, attempt + 1)
        return None
