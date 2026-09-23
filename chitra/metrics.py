import numpy as np

from .geometry import apply

THRESHOLDS = {
    "reject": {"min_inliers": 20, "min_inlier_ratio": 0.15, "min_entropy": 0.5, "max_shadow": 0.6},
    "flag": {"max_rmse_px": 1.0, "min_entropy": 0.8, "min_inlier_ratio": 0.3},
}


def coverage_entropy(p, shape, grid=8):
    if len(p) == 0:
        return 0.0
    h, w = shape
    cell = np.clip(p[:, 1] * grid // h, 0, grid - 1) * grid + np.clip(p[:, 0] * grid // w, 0, grid - 1)
    q = np.bincount(cell.astype(int), minlength=grid * grid) / len(p)
    q = q[q > 0]
    return float(-(q * np.log(q)).sum() / np.log(grid * grid))


def degenerate(H):
    if H is None or not np.all(np.isfinite(H)):
        return True
    A = H[:2, :2] / H[2, 2]
    d = np.linalg.det(A)
    return d <= 0 or np.linalg.cond(A) > 20 or not 1e-3 < abs(d) < 1e3


def residuals_src_px(H, ps, pr):
    """Residual in SOURCE pixels: ||H^-1(p_ref) - p_src||, with H mapping source -> reference."""
    return np.linalg.norm(apply(np.linalg.inv(H), pr) - ps, axis=1)


def gt_rmse(H_est, M_true_ref2src, src_shape, n=32):
    """sqrt(mean ||T_true^-1(T_est(q)) - q||^2) over an n x n grid of source points, in source px."""
    ys, xs = np.meshgrid(np.linspace(0, src_shape[0] - 1, n), np.linspace(0, src_shape[1] - 1, n), indexing="ij")
    q = np.c_[xs.ravel(), ys.ravel()]
    T = np.vstack([M_true_ref2src, [0, 0, 1]]) if M_true_ref2src.shape == (2, 3) else M_true_ref2src
    e = apply(T, apply(H_est, q)) - q
    return float(np.sqrt((e**2).sum(1).mean()))


def evaluate(H, ps, pr, inl, n_candidates, src_shape, shadow_frac, certainty, gsd_src=None):
    ok = H is not None and not degenerate(H)
    r = residuals_src_px(H, ps[inl], pr[inl]) if ok and inl.any() else np.zeros(0)
    m = {
        "n_candidates": int(n_candidates),
        "inliers": int(inl.sum()),
        "inlier_ratio": float(inl.sum() / max(n_candidates, 1)),
        "rmse_px": float(np.sqrt((r**2).mean())) if r.size else None,
        "median_px": float(np.median(r)) if r.size else None,
        "p90_px": float(np.percentile(r, 90)) if r.size else None,
        "coverage_entropy": coverage_entropy(ps[inl], src_shape),
        "shadow_fraction": float(shadow_frac),
        "mean_certainty": float(certainty[inl].mean()) if inl.any() else None,
    }
    if gsd_src and m["rmse_px"] is not None:
        m["rmse_m"] = m["rmse_px"] * gsd_src
    m["verdict"], m["reasons"] = verdict(m, ok)
    return m


def verdict(m, geometry_ok=True):
    R, F = THRESHOLDS["reject"], THRESHOLDS["flag"]
    rej = [("too_few_inliers", m["inliers"] < R["min_inliers"]),
           ("matcher_collapse", m["inlier_ratio"] < R["min_inlier_ratio"]),
           ("matches_clustered", m["coverage_entropy"] < R["min_entropy"]),
           ("shadow_dominated", m["shadow_fraction"] > R["max_shadow"]),
           ("inconsistent_geometry", not geometry_ok)]
    reasons = [k for k, bad in rej if bad]
    if reasons:
        return "REJECT", reasons
    flg = [("rmse_above_subpixel", m["rmse_px"] >= F["max_rmse_px"]),
           ("uneven_distribution", m["coverage_entropy"] < F["min_entropy"]),
           ("low_inlier_ratio", m["inlier_ratio"] < F["min_inlier_ratio"])]
    reasons = [k for k, bad in flg if bad]
    return ("FLAG", reasons) if reasons else ("PASS", [])
