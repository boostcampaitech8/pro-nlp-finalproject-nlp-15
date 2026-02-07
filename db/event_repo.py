from datetime import date
from sqlalchemy.orm import Session
from db.database import Asset, Event, Article

class EventRepository:
    def __init__(self, engine):
        self.engine = engine

    def search_events(
        _self, 
        start_date: date, 
        end_date: date, 
        asset_symbol: str | None = None, 
        keyword: str | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_order: str = "desc"
    ) -> list[dict]:
        """
        Retrieves events from the database with pagination, search, and sorting.
        """
        with Session(_self.engine) as session:
            query = session.query(Event).filter(Event.date >= start_date, Event.date <= end_date)
            
            if asset_symbol:
                query = query.join(Asset).filter(Asset.code == asset_symbol.upper())
            
            if keyword:
                search_filter = f"%{keyword}%"
                query = query.filter(
                    (Event.title.ilike(search_filter)) | (Event.description.ilike(search_filter))
                )
            
            # Count for potential UI info (though we have a separate count method)
            if sort_order.lower() == "asc":
                query = query.order_by(Event.date.asc(), Event.id.asc())
            else:
                query = query.order_by(Event.date.desc(), Event.id.desc())
            
            events = query.limit(limit).offset(offset).all()
            
            # 1. Collect unique article IDs for batch fetching
            all_article_ids = set()
            for e in events:
                if e.source_article_ids:
                    all_article_ids.update(e.source_article_ids.split(","))
            
            article_map = {}
            if all_article_ids:
                article_records = session.query(Article).filter(Article.id.in_(list(all_article_ids))).all()
                for art in article_records:
                    article_map[art.id] = {
                        'id': art.id,
                        'title': art.title,
                        'description': art.description,
                        'url': art.doc_url,
                        'publish_date': art.publish_date if art.publish_date else "",
                        'source': art.meta_site_name
                    }

            # 2. Build final list
            results = []
            for e in events:
                articles = []
                if e.source_article_ids:
                    ids = e.source_article_ids.split(",")
                    for aid in ids:
                        if aid in article_map:
                            articles.append(article_map[aid])
                
                results.append({
                    'id': e.id,
                    'title': e.title,
                    'description': e.description,
                    'start_date': e.date.isoformat(),
                    'articles': articles,
                    'assets': [e.asset.code] if e.asset else []
                })
            
            return results

    def count_events(
        _self, 
        start_date: date, 
        end_date: date, 
        asset_symbol: str | None = None, 
        keyword: str | None = None
    ) -> int:
        """Returns total count of events matching filters (for pagination)."""
        with Session(_self.engine) as session:
            query = session.query(Event).filter(Event.date >= start_date, Event.date <= end_date)
            if asset_symbol:
                query = query.join(Asset).filter(Asset.code == asset_symbol.upper())
            if keyword:
                search_filter = f"%{keyword}%"
                query = query.filter(
                    (Event.title.ilike(search_filter)) | (Event.description.ilike(search_filter))
                )
            return query.count()
