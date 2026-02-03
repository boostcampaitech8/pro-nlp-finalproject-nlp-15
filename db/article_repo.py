import pandas as pd
import os
from pathlib import Path
from typing import Optional, Dict, Any

def get_article_by_id(article_id: str, data_dir: str = "data/articles") -> Optional[Dict[str, Any]]:
    """
    Search for an article by its hex ID in the specified directory's CSV files.
    The ID is expected to be in the 'id' column of the CSV.
    
    Args:
        article_id: The 16-character hex ID.
        data_dir: Path to the directory containing article CSV files.
        
    Returns:
        A dictionary containing article information if found, else None.
    """
    path = Path(data_dir)
    if not path.exists():
        # Fallback for relative paths if needed
        root = Path(__file__).parent.parent
        path = root / "data" / "articles"

    if not path.exists():
        return None

    csv_files = list(path.glob("*.csv"))
    
    for csv_file in csv_files:
        try:
            # Direct search using pandas
            # Using chunksize to manage memory for potentially large files
            for chunk in pd.read_csv(csv_file, chunksize=10000):
                # Search for the ID in the 'id' column
                match = chunk[chunk['id'] == article_id]
                if not match.empty:
                    return match.iloc[0].to_dict()
        except Exception as e:
            # Log error or print depending on project's logging standard
            # Project uses Hydra/logging, but for now simple print or pass
            continue
            
    return None
