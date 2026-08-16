from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


SUMMARY_PROMPT = """Summarize the following crypto research article for a Korean Telegram channel.

Return strict JSON with this shape:
{{
  "sections": [
    {{"heading": "Korean section heading", "summary": "Detailed Korean summary"}}
  ]
}}

Rules:
- Follow the article's original order.
- Cover every major section or subheading, combining minor adjacent paragraphs when needed.
- If the article has no explicit subheadings, group consecutive paragraphs by topic.
- Summarize the key argument, evidence, figures, and conclusion of each section in Korean.
- Keep headings concise.
- Keep the combined headings and summaries at 1,000 Korean characters or fewer.
- Prioritize the article's main thesis, supporting evidence, important figures, and conclusion.
- Do not add facts, numbers, dates, interpretations, or conclusions absent from the article.
- Preserve project names, token names, person names, organization names, numbers, ratios, dates, and amounts exactly when possible.
- Remove ads, boilerplate, author biographies, and repetitive phrases.
- Do not phrase anything as investment advice or a buy/sell recommendation.
- Return JSON only. Do not wrap it in Markdown.

Original title (keep this title unchanged in the Telegram message):
{title}

Source:
{source_name}

Content:
{content}
"""

MAX_SUMMARY_CHARS = 1000
MAX_HEADING_CHARS = 80


@dataclass(frozen=True, slots=True)
class SummarySection:
    heading: str
    summary: str


@dataclass(frozen=True, slots=True)
class SummaryResult:
    sections: list[SummarySection]

    @property
    def summary_text(self) -> str:
        return "\n\n".join(
            f"## {section.heading}\n{section.summary}" for section in self.sections
        )


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
    sections_raw = payload.get("sections", [])
    if not isinstance(sections_raw, list):
        raise SummaryError("OpenAI response sections must be a list")

    sections: list[SummarySection] = []
    for item in sections_raw:
        if not isinstance(item, dict):
            raise SummaryError("Each summary section must be a JSON object")
        heading = str(item.get("heading", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not heading or not summary:
            raise SummaryError("Each summary section requires heading and summary")
        sections.append(
            SummarySection(
                heading=_truncate_text(heading, MAX_HEADING_CHARS),
                summary=summary,
            )
        )

    if not sections:
        raise SummaryError("OpenAI response must contain at least one section")
    return SummaryResult(sections=_limit_sections(sections))


def _limit_sections(sections: list[SummarySection]) -> list[SummarySection]:
    limited: list[SummarySection] = []
    used = 0
    for section in sections:
        separator = "\n\n" if limited else ""
        prefix = f"{separator}## {section.heading}\n"
        available = MAX_SUMMARY_CHARS - used - len(prefix)
        if available <= 0:
            break

        summary = _truncate_text(section.summary, available)
        if not summary:
            break
        limited.append(SummarySection(heading=section.heading, summary=summary))
        used += len(prefix) + len(summary)
        if len(summary) < len(section.summary):
            break
    return limited


def _truncate_text(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    if limit <= 1:
        return "…"[:limit]

    candidate = value[: limit - 1].rstrip()
    boundary = max(candidate.rfind(" "), candidate.rfind("\n"))
    if boundary >= int(limit * 0.6):
        candidate = candidate[:boundary].rstrip()
    return candidate + "…"


def _load_json(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SummaryError("OpenAI response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise SummaryError("OpenAI response must be a JSON object")
    return payload
