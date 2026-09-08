import logging
from pathlib import Path
import pandas as pd

from catalogue.index import QuadIndex
from catalogue.download import load_filtered_catalogue

logger = logging.getLogger(__name__)

# Global state for the matcher
_quad_index = None
_catalogue_lookup = None

def get_matcher_state():
    global _quad_index, _catalogue_lookup
    
    if _quad_index is None:
        logger.info("Loading QuadIndex into memory...")
        index_path = Path("data/index")
        if not index_path.exists():
            raise FileNotFoundError(f"Index not found at {index_path}. Run build_catalogue_index.py first.")
        _quad_index = QuadIndex.load(index_path)
        logger.info("QuadIndex loaded successfully.")
        
    if _catalogue_lookup is None:
        logger.info("Loading catalogue lookup...")
        df = load_filtered_catalogue("data/hygdata_v41.csv")
        # For small FOVs, we approximate RA/Dec as a flat plane for the final scoring step.
        # RA needs to be converted to degrees (HYG provides it in hours).
        df["ra_deg"] = df["ra"] * 15.0
        
        # Create a dictionary mapping star_idx -> (ra_deg, dec_deg)
        _catalogue_lookup = {
            row["star_idx"]: (row["ra_deg"], row["dec"]) 
            for _, row in df.iterrows()
        }
        logger.info(f"Loaded catalogue lookup for {len(_catalogue_lookup)} stars.")
        
    return _quad_index, _catalogue_lookup
