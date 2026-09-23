import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np

from . import geometry, io, match, metrics, prep, render
from .io import write_geotiff


RANK = {"PASS": 0, "FLAG": 1, "REJECT": 2}


def register(src, ref, dem=None, sun=None, gsd_src=1.0, gsd_ref=1.0, matcher="sift", model="affine", balance=True,
             domain="auto"):
    """Register `src` (moving) onto the grid of `ref` (fixed). Returns dict: H (source px -> ref px), matches,
    metrics, render, registered.

    With a DEM on the ref grid and the source Sun (az, el), the DEM is rendered lit like the source
    (Render-and-Match). domain: "reference" matches against `ref`, "render" against the render, "auto" tries
    both and keeps the better verdict (then more inliers)."""
    lit = render.shade(dem, gsd_ref, *sun) if dem is not None and sun is not None else None
    doms = ["reference"] if lit is None else ["reference", "render"] if domain == "auto" else [domain]
    runs = [_register_one(src, lit if d == "render" else ref, ref.shape, gsd_src, gsd_ref, matcher, model, balance)
            for d in doms]
    for d, r in zip(doms, runs):
        r["metrics"]["match_domain"] = d
    best = min(runs, key=lambda r: (RANK[r["metrics"]["verdict"]], -r["metrics"]["inliers"]))
    best["render"] = lit
    return best


def register_files(src_path, ref_path, dem_path=None, sun=None, src_gsd=None, ref_gsd=None, src_window=None,
                   ref_window=None, matcher="auto", model="affine", domain="auto", out="runs", name="register",
                   extra_config=None):
    """Read files, register, write the run folder. Used by the CLI and the web API. Returns (result, run_dir).
    sun=None reads (az, el) from the source label if one exists; a DEM needs a Sun geometry."""
    src, _, _, gs = io.read(src_path, src_window)
    ref, tr, crs, gr = io.read(ref_path, ref_window)
    dem = io.read(dem_path, ref_window)[0] if dem_path else None
    sun = sun or io.read_sun(src_path)
    if dem is not None and sun is None:
        raise ValueError("a DEM needs the source Sun geometry (azimuth + elevation, or a label that carries it)")
    matcher = match.default() if matcher == "auto" else matcher
    res = register(src, ref, dem=dem, sun=sun, gsd_src=src_gsd or gs, gsd_ref=ref_gsd or gr, matcher=matcher,
                   model=model, domain=domain)
    cfg = {"src": str(src_path), "ref": str(ref_path), "dem": dem_path and str(dem_path), "sun_used": sun,
           "src_gsd": src_gsd or gs, "ref_gsd": ref_gsd or gr, "src_window": src_window, "ref_window": ref_window,
           "matcher": matcher, "model": model, "domain": domain, **(extra_config or {})}
    return res, save_run(out, name, res, src, ref, cfg, tr, crs)


def _register_one(src, side, ref_shape, gsd_src, gsd_ref, matcher, model, balance):
    f = gsd_ref / gsd_src  # bring the reference side to the source GSD
    a = prep.normalize(src)
    b = prep.normalize(prep.resample(np.nan_to_num(side, nan=np.nanmean(side)), f))
    ps, pb, cert = (match.roma if matcher == "roma" else match.sift)(prep.clahe(a), prep.clahe(b))
    n_raw = len(ps)
    if balance and n_raw:
        k = geometry.grid_balance(ps, cert, a.shape)
        ps, pb, cert = ps[k], pb[k], cert[k]
    Hw, inl = geometry.fit(ps, pb, model)
    S = np.array([[1 / f, 0, 0.5 / f - 0.5], [0, 1 / f, 0.5 / f - 0.5], [0, 0, 1]])  # working px -> ref px
    H = None if Hw is None else S @ Hw
    pr = geometry.apply(S, pb) if len(pb) else pb
    shadow = float(prep.shadow_mask(a).mean())
    m = metrics.evaluate(H, ps, pr, inl, len(ps), a.shape, shadow, cert, gsd_src)
    m["n_raw_matches"] = n_raw
    res = metrics.residuals_src_px(H, ps, pr) if H is not None and len(ps) else np.full(len(ps), np.nan)
    reg = geometry.warp(src, H, ref_shape) if H is not None and m["verdict"] != "REJECT" else None
    return {"H": H, "src_pts": ps, "ref_pts": pr, "certainty": cert, "inlier": inl, "residual": res,
            "metrics": m, "registered": reg}


def _u8(a):
    return cv2.cvtColor(prep.normalize(a), cv2.COLOR_GRAY2BGR)


def save_run(out, name, r, src, ref, config, transform=None, crs=None):
    d = Path(out) / f"{time.strftime('%Y%m%d-%H%M%S')}_{name}"
    d.mkdir(parents=True, exist_ok=True)
    cfg = {**config, "src_shape": list(src.shape), "ref_shape": list(ref.shape), "thresholds": metrics.THRESHOLDS, "H_src_to_ref": None if r["H"] is None else r["H"].tolist()}
    (d / "config.json").write_text(json.dumps(cfg, indent=2, default=str))
    (d / "metrics.json").write_text(json.dumps(r["metrics"], indent=2))
    with open(d / "matches.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["x_src", "y_src", "x_ref", "y_ref", "certainty", "inlier", "residual_px"])
        for (xs, ys), (xr, yr), c, i, e in zip(r["src_pts"], r["ref_pts"], r["certainty"], r["inlier"], r["residual"]):
            w.writerow([f"{xs:.3f}", f"{ys:.3f}", f"{xr:.3f}", f"{yr:.3f}", f"{c:.4f}", int(i), f"{e:.4f}"])
    if r["registered"] is not None:
        write_geotiff(d / "registered.tif", r["registered"], transform, crs)
    A, B = _u8(src), _u8(ref)
    # match lines: inliers green, outliers red, reference scaled to the source height
    s = A.shape[0] / B.shape[0]
    Bs = cv2.resize(B, (round(B.shape[1] * s), A.shape[0]))
    canvas = np.hstack([A, Bs])
    show = np.random.default_rng(0).permutation(len(r["src_pts"]))[:150]  # readable subset of lines
    for j in show:
        (xs, ys), (xr, yr), i = r["src_pts"][j], r["ref_pts"][j], r["inlier"][j]
        p, q = (int(xs), int(ys)), (int(xr * s + A.shape[1]), int(yr * s))
        c = (0, 200, 0) if i else (0, 0, 220)
        cv2.line(canvas, p, q, c, 1, cv2.LINE_AA)
        cv2.circle(canvas, p, 3, c, -1, cv2.LINE_AA)
        cv2.circle(canvas, q, 3, c, -1, cv2.LINE_AA)
    cv2.imwrite(str(d / "overlay_matches.png"), canvas)
    # residual arrows on the source, magnified x20
    arr = A.copy()
    if r["H"] is not None:
        back = geometry.apply(np.linalg.inv(r["H"]), r["ref_pts"])
        for (xs, ys), (xb, yb), i in zip(r["src_pts"], back, r["inlier"]):
            if i:
                cv2.arrowedLine(arr, (int(xs), int(ys)), (int(xs + 20 * (xb - xs)), int(ys + 20 * (yb - ys))),
                                (0, 220, 255), 1, cv2.LINE_AA, tipLength=0.3)
    cv2.imwrite(str(d / "overlay_residuals.png"), arr)
    if r["registered"] is not None:
        g, h = prep.normalize(ref), prep.normalize(r["registered"])
        tile = max(16, min(ref.shape) // 8)
        yy, xx = np.indices(ref.shape)
        chk = np.where(((yy // tile + xx // tile) % 2 == 0) & np.isfinite(r["registered"]), h, g)
        cv2.imwrite(str(d / "checkerboard.png"), chk)
    if r["render"] is not None:
        cv2.imwrite(str(d / "render.png"), prep.normalize(r["render"]))
    return d
