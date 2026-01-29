"""요약 기능 테스트 - 더미 데이터 주입 예시"""

import pytest
from unittest.mock import patch, MagicMock

from interpret import get_summarize


class TestGetSummarize:
    """get_summarize 함수 테스트"""
    
    def test_summarize_with_dummy_news(self, test_config, dummy_news_fetcher):
        """
        더미 뉴스를 주입하여 요약 테스트
        - news_fetcher 파라미터를 통해 실제 RDB 대신 더미 데이터 사용
        """
        event = "삼성전자 반도체 사업 관련 주요 뉴스"
        news_ids = [1, 2, 3]
        
        # LLM API 모킹
        with patch("interpret.core.llm.OpenAI") as mock_openai:
            # Mock response 설정
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="테스트 요약 결과"))]
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            
            # 더미 뉴스 주입하여 테스트
            result = get_summarize(
                event=event,
                news_ids=news_ids,
                cfg=test_config,
                news_fetcher=dummy_news_fetcher,  # 더미 데이터 주입
            )
            
            assert result == "테스트 요약 결과"
    
    def test_summarize_calls_news_fetcher(self, test_config):
        """news_fetcher가 각 news_id에 대해 호출되는지 확인"""
        event = "테스트 사건"
        news_ids = [1, 2, 3]
        
        # 호출 추적용 mock fetcher
        mock_fetcher = MagicMock(return_value="더미 뉴스 내용")
        
        with patch("interpret.core.llm.OpenAI") as mock_openai:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="요약"))]
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            
            get_summarize(
                event=event,
                news_ids=news_ids,
                cfg=test_config,
                news_fetcher=mock_fetcher,
            )
            
            # news_fetcher가 3번 호출되었는지 확인
            assert mock_fetcher.call_count == 3
            mock_fetcher.assert_any_call(1)
            mock_fetcher.assert_any_call(2)
            mock_fetcher.assert_any_call(3)
