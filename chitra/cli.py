import argparse
import json
from pathlib import Path

from . import io, pipeline


def main(argv=None):
    p = argparse.ArgumentParser(prog="chitra", description="Chandrayaan-2 lunar image registration")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="register SRC (moving) onto REF (fixed)")
    r.add_argument("src")
    r.add_argument("ref")
    r.add_argument("--dem", help="DEM on the reference grid (enables Render-and-Match)")
    r.add_argument("--sun-az", type=float, help="source Sun azimuth, deg clockwise from north")
    r.add_argument("--sun-el", type=float, help="source Sun elevation, deg")
    r.add_argument("--src-gsd", type=float, help="source m/px (default: from the raster)")
    r.add_argument("--ref-gsd", type=float, help="reference m/px (default: from the raster)")
    r.add_argument("--src-window", type=int, nargs=4, metavar=("COL", "ROW", "W", "H"))
    r.add_argument("--ref-window", type=int, nargs=4, metavar=("COL", "ROW", "W", "H"), help="also applied to --dem")
    r.add_argument("--matcher", choices=["sift", "roma"], default="sift", help="roma needs a GPU: pip install .[roma]")
    r.add_argument("--model", choices=["affine", "homography"], default="affine")
    r.add_argument("--domain", choices=["auto", "reference", "render"], default="auto")
    r.add_argument("--out", default="runs")
    r.add_argument("--name", default="register")

    b = sub.add_parser("benchmark", help="synthetic + LROC benchmark on the Apollo 11 DTM (needs data/ref)")
    b.add_argument("--out", default="runs")

    a = p.parse_args(argv)
    if a.cmd == "benchmark":
        from . import benchmark
        print(benchmark.run(a.out)[1])
        return

    src, _, _, gs = io.read(a.src, a.src_window)
    ref, tr, crs, gr = io.read(a.ref, a.ref_window)
    dem = io.read(a.dem, a.ref_window)[0] if a.dem else None
    sun = (a.sun_az, a.sun_el) if a.sun_az is not None and a.sun_el is not None else io.read_sun(a.src)
    if dem is not None and sun is None:
        p.error("--dem needs the source Sun geometry (--sun-az/--sun-el or a label that carries it)")
    res = pipeline.register(src, ref, dem=dem, sun=sun, gsd_src=a.src_gsd or gs, gsd_ref=a.ref_gsd or gr,
                            matcher=a.matcher, model=a.model, domain=a.domain)
    d = pipeline.save_run(a.out, a.name, res, src, ref, {**vars(a), "sun_used": sun}, tr, crs)
    print(json.dumps(res["metrics"], indent=2))
    print(f"outputs -> {Path(d)}")
    raise SystemExit(0 if res["metrics"]["verdict"] != "REJECT" else 2)
