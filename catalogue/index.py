"""
Phase 0, step 4 / Section 3 (query) of the plan: index the quad codes and
answer nearest-neighbour queries against them.

Codes are stored per scale band in a scipy.spatial.cKDTree, alongside a
parallel array of the four star_idx values per quad, exactly as specified.
Persisted as .npy so the match service can memory-map them at startup
instead of rebuilding on every boot.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from .quads import QuadRecord, SCALE_BANDS_DEG, assign_scale_band

logger = logging.getLogger(__name__)


class QuadIndex:
    """One cKDTree + star_idx table per scale band."""

    def __init__(self, n_bands: int = len(SCALE_BANDS_DEG)):
        self.n_bands = n_bands
        self.trees: list[cKDTree | None] = [None] * n_bands
        self.star_ids: list[np.ndarray] = [np.empty((0, 4), dtype=np.int64)] * n_bands
        self.codes: list[np.ndarray] = [np.empty((0, 4), dtype=np.float64)] * n_bands

    @classmethod
    def build(cls, quad_records: list[QuadRecord]) -> "QuadIndex":
        idx = cls()
        by_band: dict[int, list[QuadRecord]] = {b: [] for b in range(len(SCALE_BANDS_DEG))}
        for q in quad_records:
            band = assign_scale_band(q.diameter_deg)
            by_band[band].append(q)

        for band, records in by_band.items():
            if not records:
                continue
            codes = np.array([r.code for r in records], dtype=np.float64)
            star_ids = np.array([r.star_idx for r in records], dtype=np.int64)
            idx.codes[band] = codes
            idx.star_ids[band] = star_ids
            idx.trees[band] = cKDTree(codes)
            logger.info("Band %d (~%d deg): indexed %d quads", band, SCALE_BANDS_DEG[band], len(records))

        return idx

    def save(self, out_dir: str | Path) -> None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for band in range(self.n_bands):
            np.save(out_dir / f"band_{band}_codes.npy", self.codes[band])
            np.save(out_dir / f"band_{band}_starids.npy", self.star_ids[band])
        logger.info("Saved quad index to %s", out_dir)

    @classmethod
    def load(cls, in_dir: str | Path) -> "QuadIndex":
        in_dir = Path(in_dir)
        idx = cls()
        for band in range(idx.n_bands):
            codes_path = in_dir / f"band_{band}_codes.npy"
            ids_path = in_dir / f"band_{band}_starids.npy"
            if not codes_path.exists():
                continue
            codes = np.load(codes_path, mmap_mode="r")
            star_ids = np.load(ids_path, mmap_mode="r")
            idx.codes[band] = codes
            idx.star_ids[band] = star_ids
            if len(codes) > 0:
                idx.trees[band] = cKDTree(np.asarray(codes))
        return idx

    def query(self, code: np.ndarray, band: int, k: int = 5, max_dist: float = 0.05):
        """
        Nearest-neighbour lookup for one quad code in one scale band.
        Returns a list of (distance, star_idx_tuple) candidates within max_dist.
        """
        tree = self.trees[band]
        if tree is None:
            return []
        dists, ids = tree.query(code, k=min(k, tree.n))
        if k == 1:
            dists, ids = [dists], [ids]
        out = []
        for d, i in zip(np.atleast_1d(dists), np.atleast_1d(ids)):
            if d <= max_dist:
                out.append((float(d), tuple(int(x) for x in self.star_ids[band][i])))
        return out
