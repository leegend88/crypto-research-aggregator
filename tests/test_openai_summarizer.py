import pytest

from app.summarizers.openai_summarizer import SummaryError, parse_summary_response


def test_parse_summary_response_preserves_all_sections_without_truncation():
    long_bullet = "상세한 근거와 수치를 포함한 문장입니다. " * 100
    result = parse_summary_response(
        """
        {
          "korean_title": "암호화폐 시장의 구조적 변화",
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
    assert result.korean_title == "암호화폐 시장의 구조적 변화"
    assert "## 시장 배경" in result.summary_text
    assert "• 거시경제 환경을 설명한다." in result.summary_text
    assert "## 핵심 분석" in result.summary_text
    assert result.sections[1].bullets[0] == long_bullet.strip()
    assert len(result.summary_text) > 2000
    assert not result.summary_text.endswith("…")


def test_parse_summary_response_requires_complete_section():
    with pytest.raises(SummaryError):
        parse_summary_response(
            '{"korean_title": "시장 전망", "sections": '
            '[{"heading": "시장 배경", "bullets": []}]}'
        )


def test_parse_summary_response_requires_at_least_one_section():
    with pytest.raises(SummaryError):
        parse_summary_response('{"korean_title": "시장 전망", "sections": []}')


def test_parse_summary_response_requires_korean_title():
    with pytest.raises(SummaryError, match="korean_title"):
        parse_summary_response(
            '{"sections": [{"heading": "시장 배경", "bullets": ["핵심 내용"]}]}'
        )


def test_parse_summary_response_normalizes_and_limits_bullets_per_section():
    result = parse_summary_response(
        """
        {
          "korean_title": "온체인 시장 동향",
          "sections": [{
            "heading": "온체인 동향",
            "bullets": ["- 첫째", "* 둘째", "• 셋째", "넷째"]
          }]
        }
        """
    )

    assert result.sections[0].bullets == ["첫째", "둘째", "셋째"]
