import re
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window


def read(path, window=None, band=1):
    """Return (float32 array with NaN nodata, transform, crs, pixel size in m)."""
    with rasterio.open(path) as d:
        win = Window(*window) if window else None  # (col, row, width, height)
        a = d.read(band, window=win).astype(np.float32)
        if d.nodata is not None:
            a[a == np.float32(d.nodata)] = np.nan
        a[a < -1e30] = np.nan
        tr = d.window_transform(win) if win else d.transform
        return a, tr, d.crs, abs(tr.a)


def read_sun(path):
    """(azimuth_deg clockwise from north, elevation_deg) from a PDS4 XML / PDS3 label, else None."""
    p = Path(path)
    for cand in (p, p.with_suffix(".xml"), p.with_suffix(".lbl"), p.with_suffix(".LBL")):
        if cand.exists():
            text = cand.read_bytes()[:200_000].decode("latin-1")
            break
    else:
        return None

    def grab(*keys):
        for k in keys:
            m = re.search(rf"{k}[^0-9\-+]{{0,80}}?([-+]?\d+\.?\d*)", text, re.I)
            if m:
                return float(m.group(1))

    az = grab(r"sun_azimuth", r"solar_azimuth", r"SUB_SOLAR_AZIMUTH")
    el = grab(r"sun_elevation", r"solar_elevation")
    if el is None:
        inc = grab(r"incidence_angle", r"INCIDENCE_ANGLE", r"solar_incidence")
        el = None if inc is None else 90.0 - inc
    return None if az is None or el is None else (az, el)


def write_geotiff(path, arr, transform=None, crs=None):
    arr = np.asarray(arr, np.float32)
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
                       dtype="float32", transform=transform or rasterio.Affine.identity(), crs=crs,
                       nodata=np.nan) as d:
        d.write(arr, 1)
