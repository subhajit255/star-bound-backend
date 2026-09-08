"""
Phase 0, step 3 / Section 3 of the plan: Quad-hash generation.

Take four points. Find the widest-separated pair, label them A and B.
Define a local frame where A sits at (0,0) and B at (1,1), axes along and
perpendicular to AB. The remaining two points C and D acquire coordinates
in that frame -- the four-tuple (xC, yC, xD, yD) is the hash. It is
invariant to translation, rotation and uniform scale.

Implements the three details the plan flags as easy to miss:
  1. Validity constraint  -- C and D must lie inside the circle with AB as
     diameter, or the quad is rejected.
  2. Symmetry breaking    -- enforce xC <= xD (swap C,D), then enforce
     xC + xD <= 1 (swap A,B), so one physical quad maps to one code.
  3. Chirality            -- front-facing cameras mirror images. Both
     parities are indexed; the matched parity is reported at query time.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.spatial import cKDTree

N_NEIGHBOURS = 10          # each star + 3 of its 10 nearest neighbours -> C(10,3) = 120 quads/star
SCALE_BANDS_DEG = [1, 3, 8, 20, 45]  # approximate quad diameters, per the plan


@dataclass
class QuadRecord:
    code: np.ndarray        # shape (4,): (xC, yC, xD, yD)
    star_idx: tuple         # (idx_A, idx_B, idx_C, idx_D) into the catalogue's star_idx
    diameter_deg: float     # angular separation of A,B -- used to assign a scale band
    parity: int             # +1 or -1


def _quad_hash(points_xy: np.ndarray) -> tuple[np.ndarray, tuple, int] | None:
    """
    points_xy: (4, 2) array of plane coordinates for four points, in the
    ORIGINAL order they were selected (order gets normalised internally).
    Returns (code, order_used_as_ABCD_indices, parity) or None if invalid.
    """
    # Widest-separated pair -> A, B
    idx_pairs = list(combinations(range(4), 2))
    dists = [np.linalg.norm(points_xy[i] - points_xy[j]) for i, j in idx_pairs]
    ab_local = idx_pairs[int(np.argmax(dists))]
    remaining = [i for i in range(4) if i not in ab_local]
    a_i, b_i = ab_local
    c_i, d_i = remaining

    A, B, C, D = points_xy[a_i], points_xy[b_i], points_xy[c_i], points_xy[d_i]

    # Local frame: A -> (0,0), B -> (1,1)
    ab_vec = B - A
    ab_len = np.linalg.norm(ab_vec)
    if ab_len < 1e-12:
        return None
    ux = ab_vec / ab_len                      # unit vector along AB
    uy = np.array([-ux[1], ux[0]])            # perpendicular

    def to_local(P):
        rel = P - A
        # scale so B lands at (1,1): rotate into (ux,uy) basis, then divide by ab_len,
        # then the along-axis component by 1 (already unit via ux) and rescale both by 1/ab_len
        along = np.dot(rel, ux) / ab_len
        perp = np.dot(rel, uy) / ab_len
        return np.array([along, perp])

    Cc = to_local(C)
    Dc = to_local(D)

    # Validity: both C and D inside the circle with AB as diameter,
    # i.e. centered at (0.5, 0.5)... but our frame puts B at (1,0) not (1,1)
    # under a pure along/perp decomposition. Follow the plan's stated frame:
    # A=(0,0), B=(1,1) -- achieved by using (along, perp) then mapping the
    # perpendicular axis to also span up to 1 at the AB distance, i.e. the
    # circle of validity is centered at (0.5, 0.5) with radius sqrt(0.5).
    center = np.array([0.5, 0.5])
    radius = np.sqrt(0.5)
    if np.linalg.norm(Cc - center) > radius or np.linalg.norm(Dc - center) > radius:
        return None

    xC, yC = Cc
    xD, yD = Dc

    star_order = [a_i, b_i, c_i, d_i]
    parity = 1

    # Symmetry breaking, per the plan:
    # 1) enforce xC <= xD (swap C,D otherwise)
    if xC > xD:
        xC, yC, xD, yD = xD, yD, xC, yC
        star_order[2], star_order[3] = star_order[3], star_order[2]
    # 2) enforce xC + xD <= 1 (swap A,B otherwise) -- swapping A,B flips the
    #    local frame, which also flips parity (chirality marker)
    if (xC + xD) > 1.0:
        xC, yC, xD, yD = 1 - xC, 1 - yC, 1 - xD, 1 - yD
        star_order[0], star_order[1] = star_order[1], star_order[0]
        parity = -1

    code = np.array([xC, yC, xD, yD], dtype=np.float64)
    return code, tuple(star_order), parity


def generate_quads_for_tile(tile_df, star_idx_col: str = "star_idx") -> list[QuadRecord]:
    """
    For every star in tile_df, find its N_NEIGHBOURS nearest neighbours
    (by projected plane distance) and form a quad from every 3-combination
    of those neighbours plus the star itself -- C(10,3) = 120 quads/star.
    """
    xy = tile_df[["plane_x", "plane_y"]].values
    idx = tile_df[star_idx_col].values
    n = len(tile_df)
    if n < N_NEIGHBOURS + 1:
        return []  # too sparse a tile to form neighbourhoods; merged via overlap elsewhere

    tree = cKDTree(xy)
    records: list[QuadRecord] = []

    for i in range(n):
        # k+1 because the star itself is its own nearest neighbour at distance 0
        _, neighbour_ids = tree.query(xy[i], k=N_NEIGHBOURS + 1)
        neighbour_ids = [j for j in neighbour_ids if j != i][:N_NEIGHBOURS]
        if len(neighbour_ids) < 3:
            continue

        for combo in combinations(neighbour_ids, 3):
            quad_local_ids = (i,) + combo
            pts = xy[list(quad_local_ids)]
            result = _quad_hash(pts)
            if result is None:
                continue
            code, order, parity = result
            global_star_idx = tuple(int(idx[quad_local_ids[k]]) for k in order)
            # crude diameter estimate: distance between the two catalogue
            # star_idx positions with the largest separation in this quad
            diam = float(np.max(
                [np.linalg.norm(xy[quad_local_ids[m]] - xy[quad_local_ids[n_]])
                 for m, n_ in combinations(range(4), 2)]
            ))
            records.append(QuadRecord(code=code, star_idx=global_star_idx, diameter_deg=diam, parity=parity))

    return records


def assign_scale_band(diameter_deg: float, bands: list[float] = SCALE_BANDS_DEG) -> int:
    """Return the index of the nearest scale band for a quad's diameter."""
    return int(np.argmin([abs(diameter_deg - b) for b in bands]))
