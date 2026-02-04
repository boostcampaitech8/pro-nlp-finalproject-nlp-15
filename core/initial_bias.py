def determine_initial_bias(schema: dict) -> str:
    """
    스키마의 텍스트 뉘앙스나 사건의 라벨을 분석하여 'bull' 또는 'bear'를 반환합니다.
    """
    # 1. 스키마에 명시적인 결과(result)나 라벨이 있는 경우 활용
    result_text = schema.get("result", "").lower()
    
    # 2. 하락/감소 관련 키워드가 많으면 bear 선공
    bear_keywords = ["감소", "하락", "위기", "shortage", "decrease", "drop"]
    if any(word in result_text for word in bear_keywords):
        return "bear"
    
    # 기본값은 상승(bull) 선공
    return "bull"