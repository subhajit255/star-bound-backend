"""
Section 3 (query/verification) of the plan.

Given a detected 2D point set (freckles), this module:
  1. Generates candidate quads from the query points themselves.
  2. Looks each one up in the QuadIndex (cheap 4-D nearest-neighbour query).
  3. For each candidate 4-point correspondence, estimates a similarity
     transform with RANSAC, then projects ALL query points through it and
     counts how many land near a real catalogue star -- not just the four
     quad members.
  4. Scores the match with a log-odds ratio (foreground Gaussian around the
     nearest star vs. background uniform density), matching the plan's
     stated approach.

Confidence calibration against a null distribution (section 3, "Calibrating
the confidence percentage") is a separate offline step -- see calibration.py.
This module returns raw log-odds; calibration.py converts that to a
percentile-based confidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import warnings
from skimage.measure import ransac
from skimage.transform import SimilarityTransform

# Suppress noisy ransac warnings when it doesn't find inliers
warnings.filterwarnings("ignore", message="No inliers found. Model not fitted")

from .quads import _quad_hash, assign_scale_band, SCALE_BANDS_DEG
from .index import QuadIndex

VERIFY_TOLERANCE = 0.2    # normalised-plane distance for "landed near a star"
MAX_CANDIDATE_QUADS = 200  # cap per plan section 5 ("cap at top 200 candidates")


@dataclass
class MatchResult:
    star_ids_matched: list[int]      # catalogue star_idx values the query points matched to
    n_matched: int
    n_query_points: int
    log_odds: float
    transform: SimilarityTransform
    parity: int


def _candidate_query_quads(points_xy: np.ndarray, max_quads: int = 500):
    """
    Generate candidate quads from the query point set itself. For small
    point sets (typical freckle counts, ~10-40 points) this can enumerate
    combinations directly rather than needing a neighbour restriction.
    """
    n = len(points_xy)
    all_combos = list(combinations(range(n), 4))
    if len(all_combos) > max_quads:
        rng = np.random.default_rng(0)
        idxs = rng.choice(len(all_combos), size=max_quads, replace=False)
        all_combos = [all_combos[i] for i in idxs]
    return all_combos


def match(
    points_xy: np.ndarray,
    index: QuadIndex,
    catalogue_lookup: dict[int, tuple[float, float]],  # star_idx -> (ra_deg, dec_deg) or (plane_x, plane_y) for demo
    background_density: float = 0.05,
) -> list[MatchResult]:
    """
    points_xy: (N, 2) detected freckle points, already centred/scaled to
               roughly the same units as the catalogue's projected plane.
    catalogue_lookup: maps a star_idx to its coordinates for scoring.
    """
    n = len(points_xy)
    if n < 4:
        return []

    combos = _candidate_query_quads(points_xy)
    candidates = []  # (correspondence: list of (query_pt_idx, star_idx), band)

    for combo in combos:
        pts = points_xy[list(combo)]
        result = _quad_hash(pts)
        if result is None:
            continue
        code, order, parity = result
        # order maps local positions 0..3 (A,B,C,D) back to combo indices
        query_star_order = [combo[o] for o in order]

        for band in range(len(SCALE_BANDS_DEG)):
            hits = index.query(code, band=band, k=3, max_dist=0.03)
            for dist, cat_star_idx in hits:
                correspondence = list(zip(query_star_order, cat_star_idx))
                candidates.append((correspondence, band, dist, parity))

    # Rank candidates by hash distance, cap per plan section 5
    candidates.sort(key=lambda c: c[2])
    candidates = candidates[:MAX_CANDIDATE_QUADS]

    results: list[MatchResult] = []
    seen_star_sets = set()

    # Prepare numpy arrays for fast vectorized distance computation
    cat_sids = np.array(list(catalogue_lookup.keys()))
    cat_coords = np.array(list(catalogue_lookup.values()))
    from scipy.spatial.distance import cdist

    for correspondence, band, dist, parity in candidates:
        star_key = frozenset(s for _, s in correspondence)
        if star_key in seen_star_sets:
            continue
        seen_star_sets.add(star_key)

        src = np.array([points_xy[qi] for qi, _ in correspondence])
        dst = np.array([catalogue_lookup[si] for _, si in correspondence if si in catalogue_lookup])
        if len(dst) < 4:
            continue

        try:
            model, inliers = ransac(
                (src, dst), SimilarityTransform, min_samples=3,
                residual_threshold=VERIFY_TOLERANCE, max_trials=200,
            )
        except Exception:
            continue
        if not model:
            continue

        # Project ALL query points, not just the 4 quad members
        projected = model(points_xy)
        
        # Vectorized distance computation between all projected points (N) and all catalogue stars (M)
        # cdist returns an (N, M) distance matrix
        dists = cdist(projected, cat_coords)
        
        # Find the minimum distance and corresponding star index for each projected point
        min_dist_idx = np.argmin(dists, axis=1)
        min_dists = dists[np.arange(len(projected)), min_dist_idx]
        
        # Filter points that are within VERIFY_TOLERANCE
        valid_mask = min_dists < VERIFY_TOLERANCE
        matched_star_ids = cat_sids[min_dist_idx[valid_mask]].tolist()
        
        # Remove duplicate star matches (if multiple freckles mapped to the same star)
        matched_stars = list(set(matched_star_ids))
        n_matched = len(matched_stars)
        
        if n_matched == 0:
            continue

        # Log-odds: foreground Gaussian (std = VERIFY_TOLERANCE) vs uniform background
        sigma = VERIFY_TOLERANCE
        # Calculate log_odds using the minimum distances we already found
        fg = np.exp(-0.5 * (min_dists / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
        fg = np.maximum(fg, 1e-12)
        log_odds = np.sum(np.log(fg / background_density))

        results.append(MatchResult(
            star_ids_matched=matched_stars,
            n_matched=n_matched,
            n_query_points=n,
            log_odds=float(log_odds),
            transform=model,
            parity=parity,
        ))

    # Sort primarily by how many points matched (matching percentage), then tie-break with log_odds
    results.sort(key=lambda r: (r.n_matched, r.log_odds), reverse=True)
    return results
