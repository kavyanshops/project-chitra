import argparse
import json
from pathlib import Path

from . import pipeline


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
    r.add_argument("--matcher", choices=["auto", "roma", "sift"], default="auto",
                   help="auto = RoMa v2 if installed (pip install .[roma]), else SIFT")
    r.add_argument("--model", choices=["affine", "homography"], default="affine")
    r.add_argument("--domain", choices=["auto", "reference", "render"], default="auto")
    r.add_argument("--out", default="runs")
    r.add_argument("--name", default="register")

    b = sub.add_parser("benchmark", help="synthetic + LROC benchmark on the Apollo 11 DTM (needs data/ref)")
    b.add_argument("--out", default="runs")
    b.add_argument("--roma", action="store_true", help="also benchmark RoMa v2 (needs pip install .[roma])")

    a = p.parse_args(argv)
    if a.cmd == "benchmark":
        from . import benchmark
        print(benchmark.run(a.out, roma=a.roma)[1])
        return

    sun = (a.sun_az, a.sun_el) if a.sun_az is not None and a.sun_el is not None else None
    try:
        res, d = pipeline.register_files(a.src, a.ref, a.dem, sun, a.src_gsd, a.ref_gsd, a.src_window, a.ref_window,
                                         a.matcher, a.model, a.domain, a.out, a.name)
    except ValueError as e:
        p.error(str(e))
    print(json.dumps(res["metrics"], indent=2))
    print(f"outputs -> {Path(d)}")
    raise SystemExit(0 if res["metrics"]["verdict"] != "REJECT" else 2)
