import pytest

from app.summarizers.openai_summarizer import (
    MAX_SUMMARY_CHARS,
    SummaryError,
    parse_summary_response,
)


def test_parse_summary_response_preserves_order_and_limits_total_length():
    long_bullet = "상세한 근거와 수치를 포함한 문장입니다. " * 100
    result = parse_summary_response(
        """
        {
          "sections": [
            {
              "heading": "시장 배경",
              "bullets": [
                "거시경제 환경을 설명한다.",
                "시장 변화의 배경을 정리한다."
              ]
            },
            {
              "heading": "핵심 분석",
              "bullets": ["%s"]
            }
          ]
        }
        """
        % long_bullet
    )

    assert [section.heading for section in result.sections] == [
        "시장 배경",
        "핵심 분석",
    ]
    assert len(result.summary_text) <= MAX_SUMMARY_CHARS
    assert "## 시장 배경" in result.summary_text
    assert "• 거시경제 환경을 설명한다." in result.summary_text
    assert "## 핵심 분석" in result.summary_text
    assert result.summary_text.endswith("입니다.…")


def test_summary_limit_is_two_thousand_characters():
    assert MAX_SUMMARY_CHARS == 2000


def test_parse_summary_response_requires_complete_section():
    with pytest.raises(SummaryError):
        parse_summary_response(
            '{"sections": [{"heading": "시장 배경", "bullets": []}]}'
        )


def test_parse_summary_response_requires_at_least_one_section():
    with pytest.raises(SummaryError):
        parse_summary_response('{"sections": []}')


def test_parse_summary_response_normalizes_and_limits_bullets_per_section():
    result = parse_summary_response(
        """
        {
          "sections": [{
            "heading": "온체인 동향",
            "bullets": ["- 첫째", "* 둘째", "• 셋째", "넷째"]
          }]
        }
        """
    )

    assert result.sections[0].bullets == ["첫째", "둘째", "셋째", "넷째"]
