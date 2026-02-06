import streamlit as st
from sqlalchemy.orm import Session
from db.database import Article

class ArticleRepository:
    def __init__(self, engine):
        self.engine = engine

    @st.cache_data(ttl=3600)
    def get_article(_self, article_id: str) -> dict | None:
        """Retrieves a single article by its ID from the database."""
        with Session(_self.engine) as session:
            art = session.query(Article).filter(Article.id == article_id).first()
            if art:
                return {
                    'id': art.id,
                    'title': art.title,
                    'content': art.description,
                    'url': art.doc_url,
                    'date': art.publish_date if art.publish_date else "",
                    'source': art.meta_site_name
                }
            return None
