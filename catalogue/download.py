from __future__ import annotations
import logging
from pathlib import Path

import pandas as pd
import requests
from app.config import settings

logger = logging.getLogger(__name__)

HYG_URL = settings.HYG_URL

# Columns we actually need downstream. HYG ships ~35 columns; most are unused here.
KEEP_COLUMNS = ["id", "hip", "hr", "proper", "ra", "dec", "dist", "mag", "spect", "con", "bayer", "flam"]

DEFAULT_MAG_LIMIT = 6.5

def download_hyg(cache_path: str | Path = "data/hygdata_v41.csv", force: bool = False) -> Path:
    # Download the raw HYG v4 CSV to a local cache path, unless already cached.
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists() and not force:
        logger.info("Using cached HYG catalogue at %s", cache_path)
        return cache_path

    logger.info("Downloading HYG v4 catalogue from %s", HYG_URL)
    resp = requests.get(HYG_URL, timeout=60)
    resp.raise_for_status()
    cache_path.write_bytes(resp.content)
    logger.info("Saved %d bytes to %s", len(resp.content), cache_path)
    return cache_path


def load_filtered_catalogue(
    csv_path: str | Path,
    mag_limit: float = DEFAULT_MAG_LIMIT,
) -> pd.DataFrame:
    """
    Load the HYG CSV and filter to the naked-eye subset.

    Drops:
      - The Sun (id == 0, dist == 0) -- not a useful reference star for matching.
      - Stars fainter than mag_limit.
      - Rows with missing RA/Dec (a small number of multiple-star components).

    Returns a DataFrame indexed by a fresh 0..N-1 integer 'star_idx' -- this is
    the index the quad generator and kd-tree will reference internally. The
    original HYG id/hip/hr identifiers are retained as columns for lookup and
    for populating the matches.star_ids[] field at query time.
    """
    df = pd.read_csv(csv_path, usecols=KEEP_COLUMNS, low_memory=False)

    before = len(df)
    df = df[df["id"] != 0]  # drop the Sun
    df = df.dropna(subset=["ra", "dec", "mag"])
    df = df[df["mag"] <= mag_limit]
    df = df.reset_index(drop=True)
    df.index.name = "star_idx"
    df = df.reset_index()

    logger.info(
        "Filtered HYG catalogue: %d -> %d stars (mag <= %.1f)",
        before, len(df), mag_limit,
    )
    return df


