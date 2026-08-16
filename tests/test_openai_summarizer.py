import pytest

from app.summarizers.openai_summarizer import SummaryError, parse_summary_response


def test_parse_summary_response_preserves_order_and_long_section_summaries():
    long_summary = "상세한 근거와 수치를 포함한 문장입니다. " * 20
    result = parse_summary_response(
        """
        {
          "sections": [
            {
              "heading": "시장 배경",
              "summary": "거시경제 환경과 시장 변화의 배경을 설명한다."
            },
            {
              "heading": "핵심 분석",
              "summary": "%s"
            }
          ]
        }
        """
        % long_summary
    )

    assert [section.heading for section in result.sections] == [
        "시장 배경",
        "핵심 분석",
    ]
    assert result.sections[1].summary == long_summary.strip()
    assert "## 시장 배경" in result.summary_text
    assert "## 핵심 분석" in result.summary_text


def test_parse_summary_response_requires_complete_section():
    with pytest.raises(SummaryError):
        parse_summary_response(
            '{"sections": [{"heading": "시장 배경", "summary": ""}]}'
        )


def test_parse_summary_response_requires_at_least_one_section():
    with pytest.raises(SummaryError):
        parse_summary_response('{"sections": []}')
