"""Measured benchmark on the Apollo 11 NAC DTM and LROC orthos (docs/METRICS.md section 3)."""
import json
from pathlib import Path

import numpy as np

from . import io, metrics, pipeline, render

REF = Path("data/ref")
DTM = REF / "NAC_DTM_APOLLO11.TIF"
ORTHO_A, ORTHO_B = (REF / f"NAC_DTM_APOLLO11_{i}_2M.IMG" for i in ("M150361817", "M150368601"))
CROPS = [(600, r, 768, 768) for r in (2000, 6000, 10000)]  # (col, row, w, h) inside valid DTM data
SRC = (576, 576)
WARP = dict(angle_deg=8.0, scale=1.0, shift=np.array([5.3, -3.7]))
SUN_REF = (270.0, 30.0)
METHODS = {  # name -> register() kwargs
    "SIFT (raw images)": dict(domain="reference", balance=False),
    "CHITRA w/o grid balance": dict(domain="auto", balance=False),
    "CHITRA (full)": dict(domain="auto", balance=True),
}
ROMA_METHODS = {  # added with `chitra benchmark --roma`
    "RoMa v2 (raw images)": dict(domain="reference", balance=True, matcher="roma"),
    "CHITRA + RoMa v2": dict(domain="auto", balance=True, matcher="roma"),
}


def _row(r, Mt, src_shape):
    m = r["metrics"]
    gt = metrics.gt_rmse(r["H"], Mt, src_shape) if r["H"] is not None else None
    return {**{k: m[k] for k in ("verdict", "reasons", "inliers", "inlier_ratio", "rmse_px", "coverage_entropy",
                                 "match_domain")}, "gt_rmse_px": gt}


def _case(src, ref, Mt, px, down, dem=None, sun=None, methods=METHODS):
    out = {}
    for name, kw in methods.items():
        r = pipeline.register(src, ref, dem=dem, sun=sun, gsd_src=px * down, gsd_ref=px, **kw)
        out[name] = (_row(r, Mt, src.shape), r)
    return out


def run(out="runs", save_examples=True, roma=False):
    methods = {**METHODS, **ROMA_METHODS} if roma else METHODS
    rows, examples = [], {}
    for ci, w in enumerate(CROPS):
        dem, tr, crs, px = io.read(DTM, w)
        M = render.similarity(dem.shape, WARP["angle_deg"], WARP["scale"], WARP["shift"], SRC)
        ref_syn = render.shade(dem, px, *SUN_REF)
        A, *_ = io.read(ORTHO_A, w)
        B, *_ = io.read(ORTHO_B, w)
        sun_b = render.fit_sun(dem, px, B)
        for down in (1, 4):
            for daz in (30, 90, 150):
                sun_src = ((SUN_REF[0] + daz) % 360, 20.0)
                src, Mt = render.synthetic_source(render.shade(dem, px, *sun_src), M, SRC, down, seed=ci)
                for name, (row, r) in _case(src, ref_syn, Mt, px, down, dem, sun_src, methods).items():
                    rows.append({"set": "SYN", "crop": ci, "daz": daz, "scale": down, "method": name, **row})
                    if ci == 1 and daz == 150 and down == 1 and name == "CHITRA (full)":
                        examples["syn_daz150"] = (r, src, ref_syn, tr, crs)
            src, Mt = render.synthetic_source(np.nan_to_num(B, nan=np.nanmean(B)), M, SRC, down, seed=ci)
            for name, (row, r) in _case(src, A, Mt, px, down, dem, sun_b[:2], methods).items():
                rows.append({"set": "REAL-NAC", "crop": ci, "daz": None, "scale": down, "method": name,
                             "sun_fit_b": sun_b[:2], **row})
                if ci == 1 and down == 1 and name == "CHITRA (full)":
                    examples["real_nac"] = (r, src, A, tr, crs)
    # NEG: source from crop 0, reference from crop 2 (no overlap) -> must REJECT
    d0, _, _, px = io.read(DTM, CROPS[0])
    d2, *_ = io.read(DTM, CROPS[2])
    src, Mt = render.synthetic_source(render.shade(d0, px, 300, 20), render.similarity(d0.shape, **WARP, size_src=SRC), SRC)
    for name, kw in methods.items():
        r = pipeline.register(src, render.shade(d2, px, *SUN_REF), dem=d2, sun=(300, 20), gsd_src=px, gsd_ref=px, **kw)
        rows.append({"set": "NEG", "crop": "0 vs 2", "daz": 30, "scale": 1, "method": name, **_row(r, Mt, src.shape)})
        if name == "CHITRA (full)":
            examples["neg"] = (r, src, render.shade(d2, px, *SUN_REF), None, None)

    Path(out).mkdir(exist_ok=True)
    Path(out, "benchmark.json").write_text(json.dumps(rows, indent=1, default=str))
    md = table(rows, list(methods))
    Path(out, "benchmark.md").write_text(md)
    if save_examples:
        for k, (r, s, ref, tr, crs) in examples.items():
            pipeline.save_run(out, k, r, s, ref, {"benchmark_case": k, "warp": WARP}, tr, crs)
    return rows, md


def table(rows, methods=tuple(METHODS)):
    def agg(sel):
        ok = [r for r in sel if r["verdict"] != "REJECT"]
        gts = [r["gt_rmse_px"] for r in ok if r["gt_rmse_px"] is not None]
        sub = sum(1 for r in ok if r["gt_rmse_px"] is not None and r["gt_rmse_px"] < 1.0)
        f = lambda xs: f"{np.mean(xs):.3f}" if xs else "–"  # noqa: E731
        return (f"{sub}/{len(sel)}", f(gts), f"{np.mean([r['inliers'] for r in sel]):.0f}",
                f(ok and [r["inlier_ratio"] for r in ok]), f(ok and [r["coverage_entropy"] for r in ok]))

    head = ("| Set | Δ Sun az | Scale | Method | Sub-px success | GT RMSE (src px) | Inliers | Inlier ratio | "
            "Coverage entropy |\n|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for s in ("SYN", "REAL-NAC", "NEG"):
        keys = sorted({(r["daz"] or 0, r["scale"]) for r in rows if r["set"] == s}, key=lambda k: (k[1], k[0]))
        for daz, sc in keys:
            for meth in methods:
                sel = [r for r in rows if r["set"] == s and (r["daz"] or 0) == daz and r["scale"] == sc
                       and r["method"] == meth]
                if s == "NEG":
                    v = ", ".join(f"{r['verdict']} ({'/'.join(r['reasons'])})" for r in sel)
                    lines.append(f"| NEG | – | {sc}× | {meth} | {v} | – | {sel[0]['inliers']} | – | – |")
                else:
                    lines.append(f"| {s} | {f'{daz}°' if s == 'SYN' else '≈0° (real)'} | {sc}× | {meth} | "
                                 + " | ".join(agg(sel)) + " |")
    return head + "\n".join(lines) + "\n"
