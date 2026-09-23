"""Self-check: `uv run python tests/test_pipeline.py` (or pytest). Needs no downloaded data."""
import numpy as np

from chitra import metrics, pipeline, render


def crater_dem(n=640, seed=0, px=2.0):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[:n, :n].astype(np.float32)
    z = np.zeros((n, n), np.float32)
    for _ in range(120):
        cx, cy, r = rng.uniform(0, n), rng.uniform(0, n), rng.uniform(4, 40)
        d = np.hypot(x - cx, y - cy) / r
        z += r * px * 0.2 * (np.where(d < 1, d**2 - 1, 0) + 0.3 * np.exp(-((d - 1) ** 2) / 0.05))
    return z, px


def pair(dem, px, sun_src, down=1):
    M = render.similarity(dem.shape, 8.0, 1.0, np.array([4.2, -2.9]), (480, 480))
    return render.synthetic_source(render.shade(dem, px, *sun_src), M, (480, 480), down)


def test_known_warp_is_subpixel_under_sun_change():
    dem, px = crater_dem()
    ref = render.shade(dem, px, 270, 30)
    for down in (1, 4):
        src, Mt = pair(dem, px, (60, 20), down)  # 150 deg azimuth change
        r = pipeline.register(src, ref, dem=dem, sun=(60, 20), gsd_src=px * down, gsd_ref=px)
        assert r["metrics"]["verdict"] != "REJECT", r["metrics"]
        gt = metrics.gt_rmse(r["H"], Mt, src.shape)
        assert gt < 1.0, (down, gt)


def test_non_overlapping_pair_is_rejected():
    a, px = crater_dem(seed=1)
    b, _ = crater_dem(seed=2)
    src, _ = pair(a, px, (300, 20))
    r = pipeline.register(src, render.shade(b, px, 270, 30), dem=b, sun=(300, 20), gsd_src=px, gsd_ref=px)
    assert r["metrics"]["verdict"] == "REJECT", r["metrics"]


def test_verdict_rules():
    base = dict(inliers=500, inlier_ratio=0.9, coverage_entropy=0.95, shadow_fraction=0.1, rmse_px=0.3)
    assert metrics.verdict(base) == ("PASS", [])
    assert metrics.verdict({**base, "rmse_px": 1.2}) == ("FLAG", ["rmse_above_subpixel"])
    assert metrics.verdict({**base, "inliers": 5})[0] == "REJECT"


if __name__ == "__main__":
    for t in (test_known_warp_is_subpixel_under_sun_change, test_non_overlapping_pair_is_rejected, test_verdict_rules):
        t()
        print("ok", t.__name__)
