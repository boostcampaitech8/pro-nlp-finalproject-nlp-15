import os
from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

class Asset(Base):
    __tablename__ = "commodity"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False)
    name_ko = Column(String(50), nullable=False)
    name_en = Column(String(50))
    
    prices = relationship("Price", back_populates="asset", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="asset")


class Price(Base):
    __tablename__ = "futures_price"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column("commodity_id", Integer, ForeignKey("commodity.id"), nullable=False)
    time = Column(Date, nullable=False) # Changed from DateTime to Date based on samples
    close = Column(Float, nullable=False)
    volume = Column(Float)
    
    asset = relationship("Asset", back_populates="prices")


class Event(Base):
    __tablename__ = "event"
    
    id = Column(Integer, primary_key=True) # Samples show integer ID
    original_source_id = Column("event_id", String(50), index=True)
    date = Column("start_date", Date, nullable=False)
    end_date = Column(Date)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    source_article_ids = Column("source", Text)
    asset_id = Column("commodity_id", Integer, ForeignKey("commodity.id"))
    
    asset = relationship("Asset", back_populates="events")


class Article(Base):
    __tablename__ = "article"
    
    id = Column(String(50), primary_key=True)
    publish_date = Column(String(50)) # TEXT in MySQL, stored as string
    title = Column(Text) 
    description = Column(Text) 
    doc_url = Column(Text)
    meta_site_name = Column(Text)
    authors = Column(Text)
    key_word = Column(String(255))
    asset_id = Column("commodity_id", Integer, ForeignKey("commodity.id"))


def get_engine(cfg: Optional[dict] = None):
    """
    Creates a SQLAlchemy engine based on configuration.
    Supports both SQLite (local) and MySQL (remote).
    """
    if not cfg or cfg.get('type') == 'sqlite':
        db_path = cfg.get('db_path', 'data/stockinfo.db') if cfg else 'data/stockinfo.db'
        
        # Ensure parent directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"📁 Created directory: {db_dir}")

        timeout = cfg.get('timeout', 30) if cfg else 30
        engine = create_engine(f"sqlite:///{db_path}", connect_args={'timeout': timeout})
        
        # Enable WAL mode for SQLite
        with engine.connect() as conn:
            conn.exec_driver_sql(f"PRAGMA journal_mode={cfg.get('journal_mode', 'WAL') if cfg else 'WAL'}")
            conn.exec_driver_sql(f"PRAGMA synchronous={cfg.get('synchronous', 'NORMAL') if cfg else 'NORMAL'}")
        return engine
    
    elif cfg.get('type') == 'mysql':
        m = cfg.get('mysql', {})
        url = f"mysql+pymysql://{m['user']}:{m['password']}@{m['host']}:{m['port']}/{m['dbname']}"
        return create_engine(url)
    
    raise ValueError(f"Unsupported database type: {cfg.get('type')}")

def init_db(cfg: Optional[dict] = None):
    """Initialize database and create tables."""
    engine = get_engine(cfg)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    """Returns a new session for the given engine."""
    Session = sessionmaker(bind=engine)
    return Session()
