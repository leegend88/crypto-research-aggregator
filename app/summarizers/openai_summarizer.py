from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


SUMMARY_PROMPT = """Summarize the following crypto research article for a Korean Telegram channel.

Return strict JSON with this shape:
{{
  "korean_title": "Natural Korean translation of the English title",
  "bullets": ["bullet 1", "bullet 2", "bullet 3"]
}}

Rules:
- Translate the original English title into a natural Korean title.
- Write exactly 3 or 4 Korean bullet strings.
- Each bullet must be one sentence and about 80 Korean characters or fewer.
- If the article lists many token-by-token price changes, keep only the 3 most important and summarize the rest.
- Do not add facts, numbers, dates, interpretations, or conclusions absent from the article.
- Preserve project names, token names, person names, organization names, numbers, ratios, dates, and amounts exactly when possible.
- Remove ads, boilerplate, and repetitive phrases.
- Do not phrase anything as investment advice or a buy/sell recommendation.
- Return JSON only. Do not wrap it in Markdown.

Title:
{title}

Source:
{source_name}

Content:
{content}
"""

MAX_BULLETS = 4
MIN_BULLETS = 3
MAX_BULLET_CHARS = 80


@dataclass(frozen=True, slots=True)
class SummaryResult:
    korean_title: str
    bullets: list[str]

    @property
    def summary_text(self) -> str:
        return "\n".join(f"• {bullet}" for bullet in self.bullets)


class SummaryError(RuntimeError):
    pass


class OpenAISummarizer:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def summarize(self, title: str, source_name: str, content: str) -> SummaryResult:
        prompt = SUMMARY_PROMPT.format(
            title=title,
            source_name=source_name,
            content=content,
        )
        response = self.client.responses.create(model=self.model, input=prompt)
        raw = (getattr(response, "output_text", "") or "").strip()
        if not raw:
            raise SummaryError("OpenAI returned an empty summary")
        return parse_summary_response(raw)


def parse_summary_response(raw: str) -> SummaryResult:
    payload = _load_json(raw)
    korean_title = str(payload.get("korean_title", "")).strip()
    bullets_raw = payload.get("bullets", [])
    if not korean_title:
        raise SummaryError("OpenAI response is missing korean_title")
    if not isinstance(bullets_raw, list):
        raise SummaryError("OpenAI response bullets must be a list")

    bullets = [_normalize_bullet(str(item)) for item in bullets_raw]
    bullets = [bullet for bullet in bullets if bullet]
    bullets = bullets[:MAX_BULLETS]
    if len(bullets) < MIN_BULLETS:
        raise SummaryError("OpenAI response must contain at least 3 bullets")
    return SummaryResult(korean_title=korean_title, bullets=bullets)


def _load_json(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SummaryError("OpenAI response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise SummaryError("OpenAI response must be a JSON object")
    return payload


def _normalize_bullet(value: str) -> str:
    value = value.strip()
    if value.startswith(("-", "*", "•")):
        value = value[1:].strip()
    if len(value) <= MAX_BULLET_CHARS:
        return value
    return value[: MAX_BULLET_CHARS - 1].rstrip() + "…"
