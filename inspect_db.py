
from db.database import get_engine
from sqlalchemy import text
from hydra import initialize, compose
from dotenv import load_dotenv

load_dotenv()
initialize(version_base=None, config_path="config")
cfg = compose(config_name="chatbot")
engine = get_engine(cfg.database)

def print_table_info(table_name):
    print(f"\n--- {table_name} table ---")
    with engine.connect() as conn:
        res = conn.execute(text(f"DESCRIBE {table_name}"))
        for row in res:
            print(row)
        
        print(f"\n--- {table_name} indexes ---")
        res = conn.execute(text(f"SHOW INDEX FROM {table_name}"))
        for row in res:
            print(row._mapping['Key_name'], row._mapping['Column_name'], row._mapping['Non_unique'])

print_table_info("event")
print_table_info("futures_price")
print_table_info("article")
print_table_info("commodity")
