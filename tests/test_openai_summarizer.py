import pytest

from app.summarizers.openai_summarizer import (
    MAX_BULLET_CHARS,
    SummaryError,
    parse_summary_response,
)


def test_parse_summary_response_returns_translated_title_and_limited_bullets():
    result = parse_summary_response(
        """
        {
          "korean_title": "비트코인 유동성 전망",
          "bullets": [
            "비트코인 현물 ETF 유입이 시장 유동성 회복을 뒷받침했다.",
            "ETH와 SOL 등 주요 자산의 등락률만 선별해 설명했다.",
            "거래량은 전주 대비 증가했지만 파생상품 레버리지는 제한적이었다.",
            "네 번째 불릿은 유지된다.",
            "다섯 번째 불릿은 제거된다."
          ]
        }
        """
    )

    assert result.korean_title == "비트코인 유동성 전망"
    assert len(result.bullets) == 4
    assert "다섯 번째" not in result.summary_text
    assert all(len(bullet) <= MAX_BULLET_CHARS for bullet in result.bullets)


def test_parse_summary_response_requires_at_least_three_bullets():
    with pytest.raises(SummaryError):
        parse_summary_response('{"korean_title": "제목", "bullets": ["하나", "둘"]}')

