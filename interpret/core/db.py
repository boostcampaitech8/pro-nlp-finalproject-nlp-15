"""뉴스 데이터 조회 모듈 - RDB 연동"""

from omegaconf import DictConfig


def get_news(news_id: int, cfg: DictConfig) -> str:
    """
    RDB로부터 뉴스를 가져옵니다.
    
    Args:
        news_id: 뉴스 ID (int)
        cfg: Hydra config 객체 (db 설정 포함)
    
    Returns:
        뉴스 본문 (string)
    
    TODO: 현철님 코드와 연동 필요
    - cfg.db.host, cfg.db.port, cfg.db.database 등 사용
    - 실제 RDB 연결 및 쿼리 구현
    """
    # DB 설정 참조 (연동 시 사용)
    # host = cfg.db.host
    # port = cfg.db.port
    # database = cfg.db.database
    # user = cfg.db.user
    # password = cfg.db.password
    
    # TODO: 실제 RDB 쿼리 구현
    # 예시:
    # connection = create_connection(cfg.db)
    # result = connection.execute(f"SELECT content FROM news WHERE id = {news_id}")
    # return result.fetchone()['content']
    
    raise NotImplementedError(
        f"get_news({news_id}) - RDB 연동이 필요합니다. "
        f"DB 설정: host={cfg.db.host}, database={cfg.db.database}"
    )
