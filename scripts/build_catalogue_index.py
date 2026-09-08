import logging
from pathlib import Path
import time
import pandas as pd

from catalogue.download import download_hyg, load_filtered_catalogue
from catalogue.projection import assign_tiles, stars_for_tile, gnomonic_project, DEFAULT_NSIDE
from catalogue.quads import generate_quads_for_tile
from catalogue.index import QuadIndex

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    start_time = time.time()
    
    # 1. Download and load the HYG catalogue
    logger.info("--- Step 1: Downloading & Loading Catalogue ---")
    csv_path = download_hyg()
    catalogue = load_filtered_catalogue(csv_path)
    
    # 2. Assign HEALPix tiles
    logger.info("--- Step 2: Assigning Tiles ---")
    tiled_catalogue = assign_tiles(catalogue)
    unique_tiles = tiled_catalogue["tile_id"].unique()
    logger.info(f"Assigned stars to {len(unique_tiles)} unique tiles.")
    
    # 3. Process each tile to generate quads
    logger.info("--- Step 3: Generating Quads (This might take a moment) ---")
    all_quads = []
    
    for i, tile_id in enumerate(unique_tiles):
        if i % 20 == 0 and i > 0:
            logger.info(f"Processed {i}/{len(unique_tiles)} tiles...")
            
        # Get stars for this tile (including overlap margin)
        tile_stars, (center_ra, center_dec) = stars_for_tile(tiled_catalogue, tile_id, nside=DEFAULT_NSIDE)
        
        # Project to 2D flat plane
        projected_stars = gnomonic_project(tile_stars, center_ra, center_dec)
        
        # Generate quads
        quads = generate_quads_for_tile(projected_stars)
        all_quads.extend(quads)
        
    logger.info(f"Generated a total of {len(all_quads)} quads.")
    
    # 4. Build and save the index
    logger.info("--- Step 4: Building the QuadIndex ---")
    index = QuadIndex.build(all_quads)
    
    index_dir = Path("data/index")
    index.save(index_dir)
    
    elapsed = time.time() - start_time
    logger.info(f"--- Complete! Built index in {elapsed:.2f} seconds ---")

if __name__ == "__main__":
    main()
