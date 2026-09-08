import logging
import time
from pathlib import Path

from workers.celery_app import celery_app
from catalogue.download import download_hyg, load_filtered_catalogue
from catalogue.projection import assign_tiles, stars_for_tile, gnomonic_project, DEFAULT_NSIDE
from catalogue.quads import generate_quads_for_tile
from catalogue.index import QuadIndex

logger = logging.getLogger(__name__)

@celery_app.task(name="build_catalogue_index", bind=True)
def build_catalogue_index(self):
    start_time = time.time()
    logger.info("--- Step 1: Downloading & Loading Catalogue ---")
    
    csv_path = download_hyg()
    catalogue = load_filtered_catalogue(csv_path)
    
    logger.info("--- Step 2: Assigning Tiles ---")
    tiled_catalogue = assign_tiles(catalogue)
    unique_tiles = tiled_catalogue["tile_id"].unique()
    
    logger.info("--- Step 3: Generating Quads ---")
    all_quads = []
    
    total_tiles = len(unique_tiles)
    for i, tile_id in enumerate(unique_tiles):
        if i % 20 == 0 and i > 0:
            logger.info(f"Processed {i}/{total_tiles} tiles...")
            # Update celery task state
            self.update_state(state="PROGRESS", meta={"current": i, "total": total_tiles, "status": "Generating quads"})
            
        tile_stars, (center_ra, center_dec) = stars_for_tile(tiled_catalogue, tile_id, nside=DEFAULT_NSIDE)
        projected_stars = gnomonic_project(tile_stars, center_ra, center_dec)
        quads = generate_quads_for_tile(projected_stars)
        all_quads.extend(quads)
        
    logger.info("--- Step 4: Building the QuadIndex ---")
    self.update_state(state="PROGRESS", meta={"status": "Building KDTree Database"})
    
    index = QuadIndex.build(all_quads)
    index_dir = Path("data/index")
    index.save(index_dir)
    
    elapsed = time.time() - start_time
    logger.info(f"--- Complete! Built index in {elapsed:.2f} seconds ---")
    
    return {"status": "success", "quads_generated": len(all_quads), "elapsed_seconds": elapsed}
