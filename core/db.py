import os
import pymysql
import json
from datetime import datetime, date, timedelta
from omegaconf import DictConfig


class DBManager:
    def __init__(self, cfg: DictConfig):
        """
        cfg.db는 config/db/rdb.yaml 의 flat 구조를 그대로 사용합니다.
        예시:
          host, port, database, user, password, dbname, pool_size, max_overflow
        """
        db_cfg = cfg.db  # nested cfg.db.database 가 아니라 flat 구조
        self.conn = pymysql.connect(
            host=db_cfg.host,
            port=db_cfg.port,
            user=db_cfg.user,
            password=db_cfg.password,
            database=db_cfg.dbname,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _json_serial(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return str(obj)

    def get_batch_fact_book(self, commodity_name: str, end_date: str, n_days: int) -> dict:
        """
        종목과 기간에 해당하는 **모든 사건**을 팩트북 형태로 반환합니다.
        (뉴스 개수 기반 필터링 없이, 기간 내 전체 이벤트를 수집)

        인자:
          - commodity_name: 종목명 (예: '은', '콩')
          - end_date: 기간의 종료일 (YYYY-MM-DD)
          - n_days: end_date 기준 과거 n일 동안의 기간 길이
                    예) end_date=2026-01-31, n_days=31 -> 2026-01-01~2026-01-31
        """
        try:
            # 1. end_date와 n_days로 시작일 계산
            d2 = datetime.strptime(end_date, "%Y-%m-%d")
            d1 = d2 - timedelta(days=n_days - 1)
            start_date_str = d1.strftime("%Y-%m-%d")
            end_date_str = d2.strftime("%Y-%m-%d")

            # 기간 일수 (inclusive)
            delta = (d2 - d1).days + 1

            print(
                f"📊 [Range] 기간: {start_date_str}~{end_date_str} ({delta}일) "
                f"| 종목: {commodity_name} | (모든 사건 수집, min_news_threshold 미사용)"
            )

            with self.conn.cursor() as cursor:
                # 2. 종목 및 기간 기반 이벤트 조회 (뉴스 개수 필터 없이 전체 이벤트 수집)
                event_sql = """
                SELECT e.*, c.name_ko, c.code,
                       (LENGTH(e.source) - LENGTH(REPLACE(e.source, ',', '')) + 1) as news_count
                FROM event e
                JOIN commodity c ON e.commodity_id = c.id
                WHERE c.name_ko = %s 
                  AND e.start_date BETWEEN %s AND %s
                ORDER BY e.start_date ASC
                """
                cursor.execute(event_sql, (commodity_name, start_date_str, end_date_str))
                events = cursor.fetchall()

                events_data = []
                for ev in events:
                    # 3. 뉴스 증거 수집 (description 포함)
                    source_ids = [s.strip() for s in ev['source'].split(',')] if ev['source'] else []
                    news_evidence = []
                    if source_ids:
                        format_strings = ','.join(['%s'] * len(source_ids))
                        news_sql = f"SELECT id, title, doc_url, description FROM article WHERE id IN ({format_strings})"
                        cursor.execute(news_sql, tuple(source_ids))
                        articles = cursor.fetchall()
                        
                        news_evidence = [
                            {
                                "id": a['id'], "title": a['title'], "doc_url": a['doc_url'],
                                "description": a['description'],
                                "content_full": a['description'] if a['description'] else "내용 없음"
                            } for a in articles
                        ]

                    # 4. 시세 데이터 조회
                    market_sql = """
                    SELECT time as date, open, high, low, close, ema, volume 
                    FROM futures_price 
                    WHERE commodity_id = %s AND time BETWEEN %s AND %s 
                    ORDER BY time ASC
                    """
                    cursor.execute(market_sql, (ev['commodity_id'], ev['start_date'], ev['end_date']))
                    price_list = cursor.fetchall()

                    events_data.append({
                        "event_metadata": {"event_id": ev['event_id'], "commodity": {"name": ev['name_ko'], "code": ev['code']}},
                        "event_core": {"title": ev['title'], "summary": ev['description'], "news_count": ev['news_count']},
                        "news_evidence": news_evidence,
                        "market_evidence": {"prices": price_list}
                    })

                return json.loads(json.dumps({
                    "analysis_metadata": {
                        "commodity": commodity_name,
                        "period": {"start": start_date_str, "end": end_date_str, "delta_days": delta},
                        # 더 이상 필터링에 쓰이지 않지만, 레퍼런스 포맷 호환을 위해 0으로 둠
                        "min_news_threshold": 0,
                        "total_events_found": len(events_data),
                    },
                    "events": events_data
                }, default=self._json_serial))
        except Exception as e:
            print(f"DB Error: {e}")
            return {}

    def save_fact_book(self, fact_book: dict, output_path: str) -> None:
        """
        get_batch_fact_book 결과(dict)를 지정한 경로의 JSON 파일로 저장합니다.
        디렉터리가 없으면 자동 생성합니다.
        """
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
<<<<<<< HEAD
            json.dump(fact_book, f, ensure_ascii=False, indent=2, default=self._json_serial)
=======
            json.dump(fact_book, f, ensure_ascii=False, indent=2, default=self._json_serial)
>>>>>>> 1153383bfed1e6f5b794f9c6b3a5471bf4fa64b4
