from __future__ import annotations

import logging
import pandas as pd
import hydra
from pathlib import Path
from dataclasses import asdict
from typing import List
from omegaconf import DictConfig
from hydra.core.hydra_config import HydraConfig

from extract.llm_client import WindowEventExtractor
from extract.extractor_engine import WindowEventExtractorEngine

logger = logging.getLogger(__name__)

def find_project_root() -> Path:
    here = Path.cwd().resolve()
    for c in [here, *here.parents][:10]:
        if (c / "data" / "by_keyword").exists():
            return c
    return here

def list_available_keyword_csvs(by_keyword_dir: Path) -> List[str]:
    return sorted([p.name for p in by_keyword_dir.glob("*.csv") if p.is_file() and p.name != "_manifest.csv"])

@hydra.main(version_base=None, config_path="../config", config_name="extract")
def main(cfg: DictConfig):
    root = find_project_root()
    
    input_dir = root / "data" / "by_keyword"
    hydra_dir = Path(HydraConfig.get().runtime.output_dir)
    output_dir = Path(cfg.extraction.output_dir)

    logger.info(f"Project Root: {root}")
    logger.info(f"Session Output: {hydra_dir}")
    logger.info(f"Data Input: {input_dir}")
    logger.info(f"Data Output: {output_dir}")

    extractor = WindowEventExtractor.from_hydra_config(cfg)
    engine = WindowEventExtractorEngine(extractor)

    available_files = list_available_keyword_csvs(input_dir)
    config_files = cfg.extraction.get("files")
    
    if config_files and len(config_files) > 0:
        target_files = [f for f in available_files if f in config_files]
        logger.info(f"Target: {len(target_files)} files")
    else:
        target_files = available_files
        logger.info(f"Mode: ALL {len(target_files)} files")

    if not target_files:
        logger.warning("No files to process.")
        return

    stats_all = []
    for csv_filename in target_files:
        logger.info(f"Processing: {csv_filename}")
        csv_path = input_dir / csv_filename
        
        stats = engine.run_extraction(
            csv_path=csv_path,
            output_dir=output_dir,
            args=cfg.extraction
        )
        stats_all.append(stats)

    logger.info("EXTRACTION SUMMARY")
    summary_df = pd.DataFrame([asdict(s) for s in stats_all])
    logger.info(f"\n{summary_df.to_string(index=False)}")

if __name__ == "__main__":
    main()