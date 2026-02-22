from sqlalchemy.orm import Session
from db.database import Asset, Event, Article, Price

class DatabaseVerifier:
    """Pure logic for verifying SQLite database state."""
    
    def __init__(self, engine):
        self.engine = engine

    def get_stats(self):
        stats = {}
        with Session(self.engine) as session:
            stats['total_events'] = session.query(Event).count()
            stats['total_articles'] = session.query(Article).count()
            
            assets = session.query(Asset).all()
            asset_stats = []
            for a in assets:
                p_count = session.query(Price).filter(Price.asset_id == a.id).count()
                e_count = session.query(Event).join(Event.assets).filter(Asset.id == a.id).count()
                asset_stats.append({
                    "symbol": a.symbol,
                    "prices": p_count,
                    "events": e_count
                })
            stats['assets'] = asset_stats
            
            # Sample linkage check
            sample_ev = session.query(Event).filter(Event.source_article_ids != "", Event.source_article_ids != None).first()
            linkage_verified = False
            if sample_ev:
                first_art_uuid = sample_ev.source_article_ids.split(",")[0]
                linked_art = session.query(Article).filter(Article.id == first_art_uuid).first()
                if linked_art:
                    linkage_verified = True
            stats['linkage_verified'] = linkage_verified
            
        return stats
