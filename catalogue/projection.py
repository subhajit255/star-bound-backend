"""
Phase 0, step 2: Tile the sky and project each tile's stars to a 2D plane.

Stars sit on a sphere; freckles sit on a surface approximated as a plane.
The plan calls the gnomonic (tangent-plane) projection per tile "mandatory"
and "the most common thing teams omit" -- so it's implemented explicitly
here rather than skipped.

Uses astropy-healpix (BSD-3) instead of healpy (GPLv2) to sidestep the
licensing question raised in the plan's library matrix.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord  # pyrefly: ignore [missing-import]
from astropy.wcs import WCS  # pyrefly: ignore [missing-import]
from astropy_healpix import HEALPix  # pyrefly: ignore [missing-import]
import astropy.units as u  # pyrefly: ignore [missing-import]

# nside=4 gives 192 tiles of ~215 sq deg each, per the plan.
DEFAULT_NSIDE = 4
# 15% overlap margin so quads spanning tile boundaries aren't lost.
OVERLAP_MARGIN_DEG = 0.15 * np.sqrt(4 * np.pi * (180 / np.pi) ** 2 / (12 * DEFAULT_NSIDE ** 2))


def assign_tiles(catalogue: pd.DataFrame, nside: int = DEFAULT_NSIDE) -> pd.DataFrame:
    """Assign each star to a HEALPix tile (nested scheme) based on RA/Dec."""
    hp = HEALPix(nside=nside, order="nested")
    tile_ids = hp.lonlat_to_healpix(
        catalogue["ra"].values * 15 * u.deg,  # HYG 'ra' is in hours -> degrees
        catalogue["dec"].values * u.deg,
    )
    out = catalogue.copy()
    out["tile_id"] = tile_ids
    return out


def _tile_center_deg(tile_id: int, nside: int = DEFAULT_NSIDE) -> tuple[float, float]:
    hp = HEALPix(nside=nside, order="nested")
    lon, lat = hp.healpix_to_lonlat(tile_id)
    return lon.to(u.deg).value, lat.to(u.deg).value


def stars_for_tile(
    catalogue: pd.DataFrame,
    tile_id: int,
    nside: int = DEFAULT_NSIDE,
    overlap_deg: float = OVERLAP_MARGIN_DEG,
) -> pd.DataFrame:
    """
    Return all stars belonging to this tile PLUS a margin of stars from
    neighbouring sky within overlap_deg, so quads near tile edges aren't lost.
    """
    center_ra, center_dec = _tile_center_deg(tile_id, nside)
    center = SkyCoord(ra=center_ra * u.deg, dec=center_dec * u.deg)

    all_coords = SkyCoord(
        ra=catalogue["ra"].values * 15 * u.deg,
        dec=catalogue["dec"].values * u.deg,
    )
    sep = center.separation(all_coords).to(u.deg).value

    # Tile "radius" for nside=4 is roughly sqrt(area/pi); pad by the overlap margin.
    tile_radius_deg = np.sqrt((4 * 180 ** 2 / np.pi) / (12 * nside ** 2))
    mask = sep <= (tile_radius_deg + overlap_deg)
    return catalogue.loc[mask].reset_index(drop=True), (center_ra, center_dec)


def gnomonic_project(catalogue_slice: pd.DataFrame, center_ra_deg: float, center_dec_deg: float) -> pd.DataFrame:
    """
    Project a slice of the catalogue onto a tangent plane centered at
    (center_ra_deg, center_dec_deg) using a standard gnomonic (TAN) WCS,
    via astropy.wcs -- exactly as the plan specifies (astropy.wcs, TAN projection).

    Returns the slice with added 'plane_x', 'plane_y' columns in degrees
    on the tangent plane.
    """
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [0.0, 0.0]
    wcs.wcs.cdelt = [1.0, 1.0]  # degrees per "pixel" -- we just want the TAN math
    wcs.wcs.crval = [center_ra_deg, center_dec_deg]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    ra_deg = catalogue_slice["ra"].values * 15
    dec_deg = catalogue_slice["dec"].values
    x, y = wcs.wcs_world2pix(ra_deg, dec_deg, 0)

    out = catalogue_slice.copy()
    out["plane_x"] = x
    out["plane_y"] = y
    return out
