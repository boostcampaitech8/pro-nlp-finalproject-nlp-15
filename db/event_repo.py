from datetime import date
from sqlalchemy.orm import Session
from db.database import Asset, Event, Article
import streamlit as st

class EventRepository:
    def __init__(self, engine):
        self.engine = engine

    @st.cache_data(ttl=3600)
    def search_events(_self, start_date: date, end_date: date, asset_symbol: str | None = None, keywords: list[str] | None = None) -> list[dict]:
        """
        Retrieves events from the database, filtered by date range and optionally by asset or keywords.
        """
        with Session(_self.engine) as session:
            query = session.query(Event).filter(Event.date >= start_date, Event.date <= end_date)
            
            if asset_symbol:
                query = query.join(Asset).filter(Asset.code == asset_symbol.upper())
            
            events = query.order_by(Event.date).all()
            
            # 1. Collect all unique article IDs
            all_article_ids = set()
            for e in events:
                if e.source_article_ids:
                    all_article_ids.update(e.source_article_ids.split(","))
            
            # 2. Fetch all articles in one batch (if any)
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

            # 3. Build results
            results = []
            for e in events:
                # Optional title/description keyword filtering
                if keywords:
                    text = (e.title + " " + (e.description or "")).lower()
                    if not any(k.lower() in text for k in keywords):
                        continue
                
                # Fetch original articles from map
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
