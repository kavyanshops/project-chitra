"""Cut a Chandrayaan-2 L1 crop and the matching reference + DEM windows, ready for `chitra register`.

L1 calibrated images are in raw sensor geometry. The PDS4 geometry grid (lon/lat every 100 px/lines) gives the
footprint on the reference map and the flips needed to make the crop north-up. The grid-based placement is also
saved as the *label prior*, so the registration result can be compared with the label geolocation.

uv run python scripts/prep_ch2.py PRODUCT_DIR ROW0 ROW1 COL0 COL1 REF [--dem DEM] --out data/work/NAME
"""
import argparse
import csv
import glob
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window

from chitra.io import read_sun, write_geotiff

R_MOON = 1737400.0  # LROC "Equirectangular Moon": sphere, standard parallel 1°, central meridian 180°


def lonlat_to_map(lon, lat):
    return R_MOON * np.cos(np.radians(1)) * np.radians(lon - 180), R_MOON * np.radians(lat)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("product")
    p.add_argument("row0", type=int); p.add_argument("row1", type=int)
    p.add_argument("col0", type=int); p.add_argument("col1", type=int)
    p.add_argument("ref")
    p.add_argument("--dem")
    p.add_argument("--margin", type=float, default=300.0, help="metres added around the footprint")
    p.add_argument("--offset", type=float, nargs=2, default=(0.0, 0.0), metavar=("EAST_M", "NORTH_M"),
                   help="shift the reference search window from the label footprint (e.g. from a first coarse run)")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    label = glob.glob(f"{a.product}/data/calibrated/*/*.xml")[0]
    rows = list(csv.reader(open(glob.glob(f"{a.product}/geometry/calibrated/*/*.csv")[0])))[1:]
    lon, lat, pix, scan = np.array(rows, float).T
    near = (scan >= a.row0 - 500) & (scan <= a.row1 + 500) & (pix >= a.col0 - 200) & (pix <= a.col1 + 200)
    E, N = lonlat_to_map(lon[near], lat[near])
    A = np.c_[pix[near], scan[near], np.ones(near.sum())]
    ce, cn = (np.linalg.lstsq(A, v, rcond=None)[0] for v in (E, N))  # (pixel, line) -> map metres

    # north-up = pixel -> east, line -> south; flip whichever axis runs the other way
    flip_lr, flip_ud = ce[0] < 0, cn[1] > 0
    with rasterio.open(label) as d:
        src = d.read(1, window=Window(a.col0, a.row0, a.col1 - a.col0, a.row1 - a.row0)).astype(np.float32)
    src[src == 0] = np.nan  # 0 = fill in Ch-2 L1
    if flip_lr: src = src[:, ::-1]
    if flip_ud: src = src[::-1, :]
    h, w = src.shape
    gsd = float(np.sqrt(abs(ce[0] * cn[1] - ce[1] * cn[0])))

    corners = np.array([[a.col0, a.row0], [a.col1, a.row0], [a.col0, a.row1], [a.col1, a.row1]], float)
    cE, cN = corners @ ce[:2] + ce[2] + a.offset[0], corners @ cn[:2] + cn[2] + a.offset[1]
    with rasterio.open(a.ref) as d:
        inv = ~d.transform
        cols, rws = zip(*(inv * (x, y) for x, y in zip(cE, cN)))
        m = a.margin / d.res[0]
        c0, c1 = max(0, int(min(cols) - m)), min(d.width, int(max(cols) + m))
        r0, r1 = max(0, int(min(rws) - m)), min(d.height, int(max(rws) + m))
        win = Window(c0, r0, c1 - c0, r1 - r0)
        ref = d.read(1, window=win).astype(np.float32)
        if d.nodata is not None: ref[ref == d.nodata] = np.nan
        tr, crs = d.window_transform(win), d.crs
    write_geotiff(out / "ref.tif", ref, tr, crs)
    write_geotiff(out / "src.tif", src)

    if a.dem:  # DEM resampled onto the reference window grid
        dem = np.full(ref.shape, np.nan, np.float32)
        with rasterio.open(a.dem) as d:
            reproject(rasterio.band(d, 1), dem, src_nodata=d.nodata, dst_transform=tr, dst_crs=crs,
                      dst_nodata=np.nan, resampling=Resampling.bilinear)
        write_geotiff(out / "dem.tif", dem, tr, crs)

    # label prior: source crop px (after flips) -> ref window px
    def src_to_raw(x, y):
        return a.col0 + ((w - 1 - x) if flip_lr else x), a.row0 + ((h - 1 - y) if flip_ud else y)
    grid = np.array([[x, y] for x in np.linspace(0, w - 1, 5) for y in np.linspace(0, h - 1, 5)])
    raw = np.array([src_to_raw(x, y) for x, y in grid])
    ref_px = np.array([~tr * (ce @ [c, r, 1], cn @ [c, r, 1]) for c, r in raw])
    prior = np.linalg.lstsq(np.c_[grid, np.ones(len(grid))], ref_px, rcond=None)[0].T  # 2x3 affine

    sun = read_sun(label)
    meta = {"label": label, "crop_rows": [a.row0, a.row1], "crop_cols": [a.col0, a.col1],
            "window_offset_m": list(a.offset), "flip_lr": bool(flip_lr), "flip_ud": bool(flip_ud),
            "gsd_from_grid_m": gsd, "sun_az_el": sun,
            "ref": a.ref, "ref_window": [c0, r0, c1 - c0, r1 - r0], "label_prior_affine_src_to_ref": prior.tolist()}
    (out / "prep.json").write_text(json.dumps(meta, indent=2))
    dem_arg = f" --dem {out}/dem.tif" if a.dem else ""
    print(json.dumps(meta, indent=2))
    print(f"\nuv run chitra register {out}/src.tif {out}/ref.tif{dem_arg} --sun-az {sun[0]:.2f} --sun-el {sun[1]:.2f} "
          f"--src-gsd {gsd:.3f} --name {out.name}")


if __name__ == "__main__":
    main()
