from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


SUMMARY_PROMPT = """Summarize the following crypto research article for a Korean Telegram channel.

Return strict JSON with this shape:
{{
  "korean_title": "Natural Korean translation of the article title",
  "sections": [
    {{
      "heading": "Concise Korean translation of an original section heading",
      "bullets": ["Korean key point", "Korean key point"]
    }}
  ]
}}

Rules:
- Translate the article title naturally into Korean for `korean_title`.
- Keep proper nouns, project names, token symbols, and company names recognizable, but do not leave the entire title in English.
- Follow the article's original section order.
- Use the article's real intermediate headings as section headings and translate them naturally into Korean.
- If the article has no explicit intermediate headings, create concise topic headings from the body.
- Never reuse, paraphrase, or truncate the article title as a section heading.
- Consolidate the article into 3 to 6 major sections, combining adjacent sections that support the same argument.
- Write 1 to 3 Korean bullet points per section and use one complete sentence per bullet.
- Target about 1,000 to 1,500 Korean characters for the full summary; exceed this only when essential to preserve the article's thesis or conclusion.
- Keep only the most decision-relevant figures and examples; combine long lists of trades, assets, people, or dates into one representative point.
- Preserve causal reasoning, meaningful comparisons, important caveats, and the conclusion without retelling every paragraph.
- Keep each bullet focused and self-contained. The publisher will still split unusually long summaries into consecutive Telegram posts.
- Prioritize the main thesis, supporting evidence, important figures, and conclusion.
- Summarize only the article body. Ignore ads, navigation, sidebars, related articles, image captions, author biographies, and boilerplate.
- Never describe the page or extraction process. Do not write phrases such as "the title says", "the introduction says", "the source is", "the body is missing", or "ads were removed".
- Do not add facts, numbers, dates, interpretations, or conclusions absent from the article.
- Preserve project names, token names, person names, organization names, numbers, ratios, dates, and amounts exactly when possible.
- Do not phrase anything as investment advice or a buy/sell recommendation.
- Return JSON only. Do not wrap it in Markdown.

Article title (displayed separately; do not use it as a section heading):
{title}

Source:
{source_name}

Article body:
{content}
"""

MAX_HEADING_CHARS = 80
MAX_BULLETS_PER_SECTION = 3


@dataclass(frozen=True, slots=True)
class SummarySection:
    heading: str
    bullets: list[str]


@dataclass(frozen=True, slots=True)
class SummaryResult:
    sections: list[SummarySection]
    korean_title: str | None = None

    @property
    def summary_text(self) -> str:
        return "\n\n".join(
            f"## {section.heading}\n"
            + "\n".join(f"• {bullet}" for bullet in section.bullets)
            for section in self.sections
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
    korean_title = str(payload.get("korean_title", "")).strip()
    if not korean_title:
        raise SummaryError("OpenAI response requires korean_title")
    sections_raw = payload.get("sections", [])
    if not isinstance(sections_raw, list):
        raise SummaryError("OpenAI response sections must be a list")

    sections: list[SummarySection] = []
    for item in sections_raw:
        if not isinstance(item, dict):
            raise SummaryError("Each summary section must be a JSON object")
        heading = str(item.get("heading", "")).strip()
        bullets_raw = item.get("bullets", [])
        if not heading or not isinstance(bullets_raw, list):
            raise SummaryError("Each summary section requires heading and bullets")

        bullets = [_normalize_bullet(str(bullet)) for bullet in bullets_raw]
        bullets = [bullet for bullet in bullets if bullet]
        if not bullets:
            raise SummaryError("Each summary section requires at least one bullet")
        sections.append(
            SummarySection(
                heading=_truncate_text(heading, MAX_HEADING_CHARS),
                bullets=bullets[:MAX_BULLETS_PER_SECTION],
            )
        )

    if not sections:
        raise SummaryError("OpenAI response must contain at least one section")
    return SummaryResult(sections=sections, korean_title=korean_title)


def _normalize_bullet(value: str) -> str:
    value = value.strip()
    while value.startswith(("-", "*", "•")):
        value = value[1:].strip()
    return value


def _truncate_text(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    if limit <= 1:
        return "…"[:limit]

    candidate = value[: limit - 1].rstrip()
    sentence_end = max(
        candidate.rfind(".") + 1,
        candidate.rfind("!") + 1,
        candidate.rfind("?") + 1,
        candidate.rfind("。") + 1,
    )
    if sentence_end >= int(limit * 0.5):
        return candidate[:sentence_end].rstrip() + "…"

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
